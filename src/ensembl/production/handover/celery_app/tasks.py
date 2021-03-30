# '''
# Tasks and entrypoint need to accept and sequentially process a database.
# The data flow is:
# 1. handover_database (standard function)
# - checks existence of database
# - submits HCs if appropriate and submits celery task process_checked_db
# - if not, submits copy and submits celery task process_copied_db
# 2. process_checked_db (celery task)
# - wait/retry until healthcheck job has completed
# - if success, submit copy job and submits celery task process_copied_db
# 3. process_copied_db (celery task)
# - wait/retry until copy job has completed
# - if success, submit metadata update job and submit celery task process_db_metadata
# 4. process_db_metadata (celery task)
# - wait/retry until metadara load job has completed
# - if success, process event using a event handler endpoint celery task
# @author: dstaines
# '''

import json
import logging
import re
import uuid

from sqlalchemy.engine.url import make_url
from sqlalchemy_utils.functions import database_exists, drop_database

#handover
from ensembl.production.handover.config import HandoverConfig as cfg
from ensembl.production.handover.celery_app.celery import app
from ensembl.production.handover.celery_app.utils import process_handover_payload, log_and_publish, submit_dc
from ensembl.production.handover.celery_app.utils import db_copy_client , metadata_client , event_client, dc_client

#core
from ensembl.production.core.utils import send_email
from ensembl.production.core.reporting import make_report
import time

retry_wait = app.conf.get('retry_wait', 60)
release = int(cfg.RELEASE)

if release is None:
    raise RuntimeError("Can't figure out expected release, can't start, please review config files")

retry_wait = app.conf.get('retry_wait', 60)

print(cfg)
blat_species = cfg.BLAT_SPECIES


logger = logging.getLogger(__name__)

def handover_database(spec):
    """ Method to accept a new database for incorporation into the system
    Argument is a dict with the following keys:
    * src_uri - URI to database to handover (required)
    * tgt_uri - URI to copy database to (optional - generated from staging and src_uri if not set)
    * contact - email address of submitter (required)
    * comment - additional information about submission (required)
    The following keys are added during the handover process:
    * handover_token - unique identifier for this particular handover invocation
    * dc_job_id - job ID for datacheck process
    * db_job_id - job ID for database copy process
    * metadata_job_id - job ID for the metadata loading process
    * progress_total - Total number of task to do
    * progress_complete - Total number of task completed
    """
    # TODO verify dict
    (spec, src_url, db_type) = process_handover_payload(spec)
    (dc_job_id, spec, src_uri)=submit_dc(spec, src_url, db_type)
    task_id = process_datachecked_db.delay(dc_job_id, spec)

    submitted_dc_msg = 'Submitted DB for checking as %s' % task_id
    log_and_publish(make_report('DEBUG', submitted_dc_msg, spec, src_uri))

    return spec['handover_token']


@app.task(bind=True, default_retry_delay=retry_wait)
def process_datachecked_db(self, dc_job_id, spec):
    """ Task to wait until DCs finish and then respond e.g.
    * submit copy if DC succeed
    * send error email if not
    """
    # allow infinite retries
    self.max_retries = None
    src_uri = spec['src_uri']
    progress_msg = 'Datachecks in progress, please see: %sjobs/%s' % (cfg.dc_uri, dc_job_id)
    log_and_publish(make_report('INFO', progress_msg, spec, src_uri))
    try:
        result = dc_client.retrieve_job(dc_job_id)
    except Exception as e:
        err_msg = 'Handover failed, cannot retrieve datacheck job'
        log_and_publish(make_report('ERROR', err_msg, spec, src_uri))
        raise ValueError('Handover failed, cannot retrieve datacheck job %s' % e) from e
    if result['status'] in ['incomplete', 'running', 'submitted']:
        log_and_publish(make_report('DEBUG', 'Datacheck Job incomplete, checking again later', spec, src_uri))
        raise self.retry()
    # check results
    elif result['status'] == 'failed':
        prob_msg = 'Datachecks found problems, you can download the output here: %sdownload_datacheck_outputs/%s' % (
            cfg.dc_uri, dc_job_id)
        log_and_publish(make_report('INFO', prob_msg, spec, src_uri))
        msg = """Running datachecks on %s completed but found problems. You can download the output here %s""" % (
            src_uri, cfg.dc_uri + "download_datacheck_outputs/" + str(dc_job_id))
        send_email(to_address=spec['contact'], subject='Datacheck found problems', body=msg,
                   smtp_server=cfg.smtp_server)
    elif result['status'] == 'dc-run-error':

        msg = """Datachecks didn't run successfully. Please see %s""" % (cfg.dc_uri + "jobs/" + str(dc_job_id))
        log_and_publish(make_report('INFO', msg, spec, src_uri))
        send_email(to_address=spec['contact'], subject='Datacheck run issue', body=msg, smtp_server=cfg.smtp_server)
    else:
        log_and_publish(make_report('INFO', 'Datachecks successful, starting copy', spec, src_uri))
        spec['progress_complete'] = 1
        submit_copy(spec)


def submit_copy(spec):
    """Submit the source database for copying to the target. Returns a celery job identifier"""
    src_uri = spec['src_uri']
    try:
        src_url = make_url(src_uri)
        tgt_url = make_url(spec['tgt_uri'])
        src_host = f"{src_url.host}:{src_url.port}"
        tgt_host = f"{tgt_url.host}:{tgt_url.port}"
        src_incl_db = src_url.database
        tgt_db_name = tgt_url.database

        #submit a copy job                                   
        copy_job_id=db_copy_client.submit_job(src_host, src_incl_db, None, None, None,
                                             tgt_host, tgt_db_name, False, False, False, cfg.production_email, cfg.copy_job_user)

    except Exception as e:
        log_and_publish(make_report('ERROR', 'Handover failed, cannot submit copy job', spec, src_uri))
        raise ValueError('Handover failed, cannot submit copy job %s' % e) from e
    spec['copy_job_id'] = copy_job_id
    task_id = process_copied_db.delay(copy_job_id, spec)
    dbg_msg = 'Submitted DB for copying as %s' % task_id
    log_and_publish(make_report('DEBUG', dbg_msg, spec, spec['src_uri']))
    return task_id


@app.task(bind=True, default_retry_delay=retry_wait)
def process_copied_db(self, copy_job_id, spec):
    """Wait for copy to complete and then respond accordingly:
    * if success, submit to metadata database
    * if failure, flag error using email"""
    # allow infinite retries
    self.max_retries = None
    src_uri = spec['src_uri']
    copy_in_progress_msg = 'Copying in progress, please see: %s%s' % (cfg.copy_web_uri, copy_job_id)
    log_and_publish(make_report('INFO', copy_in_progress_msg, spec, src_uri))
    try:
        result = db_copy_client.retrieve_job(copy_job_id)
    except Exception as e:
        log_and_publish(make_report('ERROR', 'Handover failed, cannot retrieve copy job', spec, src_uri))
        raise ValueError('Handover failed, cannot retrieve copy job %s' % e) from e
    if result['overall_status'] in [ 'Scheduled', 'Running', 'Submitted']:
        log_and_publish(make_report('DEBUG', 'Database copy job incomplete, checking again later', spec, src_uri))
        raise self.retry()
    if result['overall_status'] == 'Failed':
        copy_failed_msg = 'Copy failed, please see: %s%s' % (cfg.copy_web_uri, copy_job_id)
        log_and_publish(make_report('INFO', copy_failed_msg, spec, src_uri))
        msg = """Copying %s to %s failed. Please see %s""" % (src_uri, spec['tgt_uri'], cfg.copy_web_uri + str(copy_job_id))
        send_email(to_address=spec['contact'], subject='Database copy failed', body=msg, smtp_server=cfg.smtp_server)
        return
    elif 'GRCh37' in spec:
        log_and_publish(make_report('INFO', 'Copying complete, Handover successful', spec, src_uri))
        spec['progress_complete'] = 3
    else:
        log_and_publish(make_report('INFO', 'Copying complete, submitting metadata job', spec, src_uri))
        spec['progress_complete'] = 2
        submit_metadata_update(spec)


def submit_metadata_update(spec):
    """Submit the source database for copying to the target. Returns a celery job identifier."""
    src_uri = spec['src_uri']
    try:
        metadata_job_id = metadata_client.submit_job(spec['tgt_uri'], None, None, None,
                                                     None, spec['contact'], spec['comment'], 'Handover', None)
    except Exception as e:
        log_and_publish(make_report('ERROR', 'Handover failed, cannot submit metadata job', spec, src_uri))
        raise ValueError('Handover failed, cannot submit metadata job %s' % e) from e
    spec['metadata_job_id'] = metadata_job_id
    task_id = process_db_metadata.delay(metadata_job_id, spec)
    dbg_msg = 'Submitted DB for metadata loading %s' % task_id
    log_and_publish(make_report('DEBUG', dbg_msg, spec, src_uri))
    return task_id


@app.task(bind=True, default_retry_delay=retry_wait)
def process_db_metadata(self, metadata_job_id, spec):
    """Wait for metadata update to complete and then respond accordingly:
    * if success, submit event to event handler for further processing
    * if failure, flag error using email"""
    # allow infinite retries
    self.max_retries = None
    tgt_uri = spec['tgt_uri']
    loading_msg = 'Loading into metadata database, please see: %sjobs/%s' % (cfg.meta_uri, metadata_job_id)
    log_and_publish(make_report('INFO', loading_msg, spec, tgt_uri))
    try:
        result = metadata_client.retrieve_job(metadata_job_id)
    except Exception as e:
        err_msg = 'Handover failed, Cannot retrieve metadata job'
        log_and_publish(make_report('ERROR', err_msg, spec, tgt_uri))
        raise ValueError('Handover failed, Cannot retrieve metadata job %s' % e) from e
    if result['status'] in ['incomplete', 'running', 'submitted']:
        incomplete_msg = 'Metadata load Job incomplete, checking again later'
        log_and_publish(make_report('DEBUG', incomplete_msg, spec, tgt_uri))
        raise self.retry()
    if result['status'] == 'failed':
        drop_msg = 'Dropping %s' % tgt_uri
        log_and_publish(make_report('INFO', drop_msg, spec, tgt_uri))
        drop_database(spec['tgt_uri'])
        failed_msg = 'Metadata load failed, please see %sjobs/%s?format=failures' % (cfg.meta_uri, metadata_job_id)
        log_and_publish(make_report('INFO', failed_msg, spec, tgt_uri))
        msg = """
Metadata load of %s failed.
Please see %s
""" % (tgt_uri, cfg.meta_uri + 'jobs/' + str(metadata_job_id) + '?format=failures')
        send_email(to_address=spec['contact'],
                   subject='Metadata load failed, please see: ' + cfg.meta_uri + 'jobs/' + str(
                       metadata_job_id) + '?format=failures', body=msg, smtp_server=cfg.smtp_server)
    else:
        # Cleaning up old assembly or old genebuild databases for Wormbase when database suffix has changed
        if 'events' in result['output'] and result['output']['events']:
            for event in result['output']['events']:
                details = json.loads(event['details'])
                if 'current_database_list' in details:
                    drop_current_databases(details['current_database_list'], spec)
                if event['genome'] in blat_species and event['type'] == 'new_assembly':
                    msg = 'The following species %s has a new assembly, please update the port number for this ' \
                          'species here and communicate to Web: https://github.com/Ensembl/ensembl-production/blob/' \
                          'master/modules/Bio/EnsEMBL/Production/Pipeline/PipeConfig/DumpCore_conf.pm#L107' % \
                          event['genome']
                    send_email(to_address=cfg.production_email,
                               subject='BLAT species list needs updating in FTP Dumps config',
                               body=msg)
        spec['progress_complete'] = 3
        log_and_publish(make_report('INFO', 'Metadata load complete, Handover successful', spec, tgt_uri))
        dispatch_to = cfg.dispatch_targets.get(spec['db_type'], None)
        if dispatch_to is not None:
            # if core db
            log_and_publish(make_report('INFO', 'Dispatching Database to compara hosts'))
            # retrieve species list from genome division
            if spec['genome'] in cfg.compara_species[spec['db_division']]:
                # if species in species_list trigger a supplementary copy to vertannot-staging
                spec['tgt_uri'] = cfg.dispatch_targets[spec['db_type']]
                submit_dispatch(spec)

        # log_and_publish(make_report('INFO', 'Metadata load complete, submitting event', spec, tgt_uri))
        # submit_event(spec,result)


def submit_dispatch(spec):
    """ dispatch database to dedicated host """
    src_uri = spec['src_uri']
    try:
        copy_job_id = db_copy_client.submit_job(src_uri, spec['tgt_uri'], None, None,
                                                False, True, True, None, None)
    except Exception as e:
        log_and_publish(make_report('ERROR', 'Handover failed, cannot dispatch database', spec, src_uri))
        raise ValueError('Handover failed, cannot submit dispatch job %s' % e) from e
    spec['copy_job_id'] = copy_job_id
    task_id = process_dispatch_db.delay(copy_job_id, spec)
    dbg_msg = 'Submitted DB for dispatch as %s' % task_id
    log_and_publish(make_report('DEBUG', dbg_msg, spec, src_uri))
    return task_id


def submit_event(spec, result):
    """Submit an event"""
    tgt_uri = spec['tgt_uri']
    logger.debug(result['output']['events'])
    for event in result['output']['events']:
        logger.debug(event)
        event_client.submit_job({'type': event['type'], 'genome': event['genome']})
        log_and_publish(make_report('DEBUG', 'Submitted event to event handler endpoint', spec, tgt_uri))


def drop_current_databases(current_db_list, spec):
    """Drop databases on a previous assembly or previous genebuild (e.g: Wormbase) from the staging MySQL server"""
    tgt_uri = spec['tgt_uri']
    staging_uri = spec['staging_uri']
    tgt_url = make_url(tgt_uri)
    # Check if the new database has the same name as the one on staging. In this case DO NOT drop it
    # This can happen if the assembly get renamed or genebuild version has changed for Wormbase
    if tgt_url.database in current_db_list:
        msg = 'The assembly or genebuild has been updated but the new database %s is the same as old one' % tgt_url.database
        log_and_publish(make_report('DEBUG', msg, spec, tgt_uri))
    else:
        for database in current_db_list:
            db_uri = staging_uri + database
            if database_exists(db_uri):
                msg = 'Dropping %s' % db_uri
                log_and_publish(make_report('INFO', msg, spec, tgt_uri))
                drop_database(db_uri)


@app.task(bind=True, default_retry_delay=retry_wait)
def process_dispatch_db(self, copy_job_id, spec):
    """
    Process dispatched dbs after metadata updates.
    :param self:
    :param copy_job_id:
    :param spec:
    :return:
    """
    self.max_retries = None
    src_uri = spec['src_uri']
    copy_in_progress_msg = 'Dispatching in progress, please see: %s%s' % (cfg.copy_web_uri, copy_job_id)
    log_and_publish(make_report('INFO', copy_in_progress_msg, spec, src_uri))
    try:
        result = db_copy_client.retrieve_job(copy_job_id)
    except Exception as e:
        log_and_publish(make_report('ERROR', 'Database dispatch failed, cannot retrieve copy job', spec, src_uri))
        raise ValueError('Handover failed, cannot retrieve copy job %s' % e) from e
    if result['status'] in ['incomplete', 'running', 'submitted']:
        log_and_publish(make_report('DEBUG', 'Database dispatch job incomplete, checking again later', spec, src_uri))
        raise self.retry()
    else:
        log_and_publish(make_report('INFO', 'Database dispatch complete, handover complete', spec, src_uri))
        spec['progress_complete'] = 4