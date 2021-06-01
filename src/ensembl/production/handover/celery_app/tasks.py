# .. See the NOTICE file distributed with this work for additional information
#    regarding copyright ownership.
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#        http://www.apache.org/licenses/LICENSE-2.0
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
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
# @author: vinay kaikala
# @author: dstaines
# '''

import json
import logging
import re
import uuid

from celery import chain
from sqlalchemy.engine.url import make_url
from sqlalchemy_utils.functions import database_exists, drop_database

# handover
from ensembl.production.handover.config import HandoverConfig as cfg
from ensembl.production.handover.celery_app.celery import app
from ensembl.production.handover.celery_app.utils import process_handover_payload, log_and_publish, \
    drop_current_databases, submit_dc, submit_copy, submit_metadata_update, submit_dispatch
from ensembl.production.handover.celery_app.utils import db_copy_client, metadata_client, event_client, dc_client

# core
from ensembl.production.core.utils import send_email
from ensembl.production.core.reporting import make_report
import time

retry_wait = app.conf.get('retry_wait', 60)
release = int(cfg.RELEASE)

if release is None:
    raise RuntimeError("Can't figure out expected release, can't start, please review config files")

retry_wait = app.conf.get('retry_wait', 60)

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
    (dc_job_id, spec, src_uri) = submit_dc(spec, src_url, db_type)
    submitted_dc_msg = 'Submitted DB for data check as %s' % dc_job_id
    log_and_publish(make_report('DEBUG', submitted_dc_msg, spec, src_uri))

    # production handover workflow
    res = chain(
        datacheck_task.s(spec, dc_job_id, src_uri),
        dbcopy_task.s(),
        metadata_update_task.s(),
        dispatch_db_task.s(),
    )()
    return spec['handover_token']


@app.task(bind=True, default_retry_delay=retry_wait)
def datacheck_task(self, spec, dc_job_id, src_uri):
    """Submit the source database for data check and wait until DCs pipeline finish"""
    self.max_retries = None
    src_uri = spec['src_uri']
    progress_msg = 'Datachecks in progress, please see: %sjobs/%s' % (cfg.dc_uri, dc_job_id)
    log_and_publish(make_report('INFO', progress_msg, spec, src_uri))
    try:
        result = dc_client.retrieve_job(dc_job_id)
    except Exception as e:
        self.request.chain = None
        err_msg = 'Handover failed, cannot retrieve datacheck job'
        log_and_publish(make_report('ERROR', err_msg, spec, src_uri))
        raise ValueError('Handover failed, cannot retrieve datacheck job %s' % e) from e
    if result['status'] in ['incomplete', 'running', 'submitted']:
        log_and_publish(make_report('DEBUG', 'Datacheck Job incomplete, checking again later', spec, src_uri))
        raise self.retry()
    # check results
    elif result['status'] == 'failed':
        self.request.chain = None
        prob_msg = 'Datachecks found problems, you can download the output here: %sdownload_datacheck_outputs/%s' % (
            cfg.dc_uri, dc_job_id)
        log_and_publish(make_report('INFO', prob_msg, spec, src_uri))
        msg = """Running datachecks on %s completed but found problems. You can download the output here %s""" % (
            src_uri, cfg.dc_uri + "download_datacheck_outputs/" + str(dc_job_id))
        send_email(to_address=spec['contact'], subject='Datacheck found problems', body=msg,
                   smtp_server=cfg.smtp_server)
    elif result['status'] == 'dc-run-error':
        self.request.chain = None
        msg = """Datachecks didn't run successfully. Please see %s""" % (cfg.dc_uri + "jobs/" + str(dc_job_id))
        log_and_publish(make_report('INFO', msg, spec, src_uri))
        send_email(to_address=spec['contact'], subject='Datacheck run issue', body=msg, smtp_server=cfg.smtp_server)
    else:
        log_and_publish(make_report('INFO', 'Datachecks successful, starting copy', spec, src_uri))
        spec['progress_complete'] = 1
    return spec


@app.task(bind=True, default_retry_delay=retry_wait)
def dbcopy_task(self, spec):
    """Wait for copy to complete and then respond accordingly:
    * if Success, submit to metadata database
    * if failure, flag error using email"""
    # allow infinite retries
    self.max_retries = None
    try:
        src_uri = spec['src_uri']
        copy_job_id = submit_copy(spec)
        dbg_msg = 'Submitted DB for copying'
        log_and_publish(make_report('DEBUG', dbg_msg, spec, spec['src_uri']))
        copy_in_progress_msg = 'Copying in progress, please see: %s%s' % (cfg.copy_web_uri, copy_job_id)
        log_and_publish(make_report('INFO', copy_in_progress_msg, spec, src_uri))
        while db_copy_client.retrieve_job(copy_job_id)['overall_status'] in ['Scheduled', 'Running', 'Submitted']:
            incomplete_msg = 'Copying in progress, please see: %s%s' % (cfg.copy_web_uri, copy_job_id)
            log_and_publish(make_report('DEBUG', incomplete_msg, spec, src_uri))
            time.sleep(120)

        result = db_copy_client.retrieve_job(copy_job_id)

        if result['overall_status'] == 'Failed':
            self.request.chain = None
            copy_failed_msg = 'Copy failed, please see: %s%s' % (cfg.copy_web_uri, copy_job_id)
            log_and_publish(make_report('INFO', copy_failed_msg, spec, src_uri))
            msg = """Copying %s to %s failed. Please see %s""" % (
            src_uri, spec['tgt_uri'], cfg.copy_web_uri + str(copy_job_id))
            send_email(to_address=spec['contact'], subject='Database copy failed', body=msg,
                       smtp_server=cfg.smtp_server)
        elif 'GRCh37' in spec:
            self.request.chain = None
            log_and_publish(make_report('INFO', 'Copying complete, Handover successful', spec, src_uri))
            spec['progress_complete'] = 3
        else:
            log_and_publish(make_report('INFO', 'Copying complete, submitting metadata job', spec, src_uri))
            spec['progress_complete'] = 2
    except Exception as e:
        self.request.chain = None
        log_and_publish(make_report('ERROR', 'Handover failed, cannot retrieve copy job', spec, src_uri))
        raise ValueError('Handover failed, cannot retrieve copy job %s' % e) from e
    return spec


@app.task(bind=True, default_retry_delay=retry_wait)
def metadata_update_task(self, spec):
    """Wait for metadata update to complete and then respond accordingly:
    * if success, submit event to event handler for further processing
    * if failure, flag error using email"""
    # allow infinite retries
    self.max_retries = None
    try:
        metadata_job_id=submit_metadata_update(spec)
        tgt_uri = spec['tgt_uri']
        loading_msg = 'Loading into metadata database, please see: %sjobs/%s' % (cfg.meta_uri, metadata_job_id)
        log_and_publish(make_report('INFO', loading_msg, spec, tgt_uri))

        while metadata_client.retrieve_job(metadata_job_id)['status'] in ['incomplete', 'running', 'submitted']:
            incomplete_msg = 'Metadata load Job incomplete, checking again later'
            log_and_publish(make_report('DEBUG', incomplete_msg, spec, tgt_uri))
            time.sleep(60)

        result = metadata_client.retrieve_job(metadata_job_id)

        if result['status'] == 'failed':
            self.request.chain = None
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
            log_and_publish(make_report('INFO', 'Metadata load complete', spec, tgt_uri))

            dispatch_to = cfg.dispatch_targets.get(spec['db_type'], None)
            if dispatch_to is not None and \
               len(result['output']['events']) > 0 and \
               result['output']['events'][0].get('genome', None) and \
               result['output']['events'][0]['genome']in cfg.compara_species[spec['db_division']]:
               
               spec['genome'] = result['output']['events'][0]['genome'] 
               spec['tgt_uri'] = cfg.dispatch_targets[spec['db_type']]
               log_and_publish(make_report('INFO', 'Dispatching Database to compara hosts'))
            else :
                log_and_publish(make_report('INFO', 'Metadata load complete, Handover successful', spec, tgt_uri))
                self.request.chain = None
      
    except Exception as e:
        self.request.chain = None
        err_msg = 'Handover failed, Cannot retrieve metadata job'
        log_and_publish(make_report('ERROR', err_msg, spec, tgt_uri))
        raise ValueError('Handover failed, Cannot retrieve metadata job %s' % e) from e

    return spec


@app.task(bind=True, default_retry_delay=retry_wait)
def dispatch_db_task(self, spec):
    """
    Process dispatched dbs after metadata updates.
    :param self:
    :param copy_job_id:
    :param spec:
    :return:
    """
    self.max_retries = None

    try:    
        src_uri = spec['src_uri']
        copy_job_id = submit_copy(spec)
        copy_in_progress_msg = 'Dispatching in progress, please see: %s%s' % (cfg.copy_web_uri, copy_job_id)
        log_and_publish(make_report('INFO', copy_in_progress_msg, spec, src_uri))
        while db_copy_client.retrieve_job(copy_job_id)['overall_status'] in [ 'Scheduled', 'Running', 'Submitted']:
            incomplete_msg = 'Database dispatch in progress, please see: %s%s' % (cfg.copy_web_uri, copy_job_id)
            log_and_publish(make_report('DEBUG', incomplete_msg, spec, src_uri))
            time.sleep(120)

        result = db_copy_client.retrieve_job(copy_job_id)
        if result['overall_status'] == 'Failed':
            self.request.chain = None
            copy_failed_msg = 'Database dispatch failed, please see: %s%s' % (cfg.copy_web_uri, copy_job_id)
            log_and_publish(make_report('INFO', copy_failed_msg, spec, src_uri))
            msg = """Dispatch %s to %s failed. Please see %s""" % (src_uri, spec['tgt_uri'], cfg.copy_web_uri + str(copy_job_id))
            send_email(to_address=spec['contact'], subject='Database dispatch failed', body=msg, smtp_server=cfg.smtp_server)            
        else:
            spec['progress_complete'] = 4 
            log_and_publish(make_report('INFO', 'Database dispatch complete, Handover successful', spec, src_uri))  

    except Exception as e:
        self.request.chain = None
        log_and_publish(make_report('ERROR', 'Database dispatch failed, cannot retrieve copy job', spec, src_uri))
        raise ValueError('Handover failed, cannot retrieve copy job %s' % e) from e

    return spec


@app.task(bind=True, default_retry_delay=retry_wait)
def event(self, spec):
    print('coming soon.....')
    return spec
