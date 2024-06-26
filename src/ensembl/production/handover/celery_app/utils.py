# .. See the NOTICE file distributed with this work for additional information
#    regarding copyright ownership.
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#        https://www.apache.org/licenses/LICENSE-2.0
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import json
import logging
import re
import uuid
import warnings
# es clients
from sqlalchemy.engine.url import make_url
from sqlalchemy_utils.functions import database_exists, drop_database
from ensembl.production.core.es import ElasticsearchConnectionManager
from ensembl.production.core.amqp_publishing import AMQPPublisher
from ensembl.production.core.clients.datachecks import DatacheckClient
# clients
from ensembl.production.core.clients.dbcopy import DbCopyRestClient
from ensembl.production.core.clients.event import EventClient
from ensembl.production.core.clients.metadata import MetadataClient
from ensembl.production.core.models.compara import check_grch37, get_release_compara
from ensembl.production.core.models.core import get_division, get_release
from ensembl.production.core.reporting import make_report, ReportFormatter
from ensembl.production.handover.config import HandoverConfig as cfg
from sqlalchemy.exc import MovedIn20Warning

# TODO remove the day we move to SQLAlchemy > 2.0
warnings.filterwarnings("ignore", category=MovedIn20Warning)

logger = logging.getLogger(__name__)
release = int(cfg.RELEASE) if cfg.RELEASE else 0
handover_formatter = ReportFormatter('handover')
publisher = AMQPPublisher(cfg.report_server,
                          cfg.report_exchange,
                          exchange_type=cfg.report_exchange_type,
                          formatter=handover_formatter)
species_pattern = re.compile(
    r'^(?P<prefix>\w+)_(?P<type>core|rnaseq|cdna|otherfeatures|variation|funcgen)(_\d+)?_(\d+)_(?P<assembly>\d+)$')
compara_pattern = re.compile(r'^ensembl_compara(_(?P<division>[a-z]+|pan)(_homology)?)?(_(\d+))?(_\d+)$')
ancestral_pattern = re.compile(r'^ensembl_ancestral(_(?P<division>[a-z]+))?(_(\d+))?(_\d+)$')
db_types_list = [i for i in cfg.allowed_database_types.split(",")]
allowed_divisions_list = [i for i in cfg.allowed_divisions.split(",")]

# app clients
dc_client = DatacheckClient(cfg.dc_client_uri)
db_copy_client = DbCopyRestClient(cfg.copy_client_uri)
metadata_client = MetadataClient(cfg.meta_client_uri)
event_client = EventClient(cfg.event_client_uri)

# es Details
es_host = cfg.ES_HOST
es_port = str(cfg.ES_PORT)
es_index = cfg.ES_INDEX
es_user = cfg.ES_USER
es_password = cfg.ES_PASSWORD
es_ssl = cfg.ES_SSL


def qualified_name(db_uri):
    import re
    db_url = make_url(db_uri)
    if re.search('[a-z-]?(.ebi.ac.uk|.org)', db_url.host) or db_url.host in ('localhost', 'mysql'):
        return db_uri
    else:
        host = f'{db_url.host}.ebi.ac.uk'
        if db_url.password:
            return f"{db_url.drivername}://{db_url.username}:{db_url.password}@{host}:{db_url.port}/{db_url.database}"
        else:
            return f"{db_url.drivername}://{db_url.username}@{host}:{db_url.port}/{db_url.database}"


def check_handover_db_resubmit(spec: dict):
    """[Restrict Multiple handover submission with same Database name]

    Args:
        spec (dict): [Handover payload with database name]

    Raises:
        ValueError: [Handover Status in progress ]

    Returns:
        [bool]: [Status boolean]
    """
    try:
        with ElasticsearchConnectionManager(es_host, int(es_port), es_user, es_password, es_ssl) as es:
            res_error = es.client.search(index=es_index, body={
                "size": 0,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "params.database.keyword": spec['database']
                                }
                            },
                            {
                                "query_string": {
                                    "fields": [
                                        "report_type"
                                    ],
                                    "query": "(INFO|ERROR)",
                                    "analyze_wildcard": "true"
                                }
                            },
                        ]
                    }
                },
                "aggs": {
                    "handover_token": {
                        "terms": {
                            "field": "params.handover_token.keyword",
                            "size": 1000
                        },
                        "aggs": {
                            "top_result": {
                                "top_hits": {
                                    "size": 1,
                                    "sort": {
                                        "report_time": "desc"
                                    }
                                }
                            }
                        }
                    }
                },
                "sort": [
                    {
                        "report_time": {
                            "order": "desc"
                        }
                    }
                ]
            })

        failed_msg_pattern = re.compile(r'.*(failed|Failed|found problems|complete|successful).*', re.IGNORECASE)
        for each_handover_bucket in res_error['aggregations']['handover_token']['buckets']:
            for doc in each_handover_bucket['top_result']['hits']['hits']:
                msg = doc['_source']['message']
                if not failed_msg_pattern.match(msg):
                    # found  handover with status running for submitted DB
                    raise ValueError(
                        f"DB {doc['_source']['params']['database']} already submitted with handover: {doc['_source']['params']['handover_token']} and status: {msg} "
                    )
    except Exception as e:
        return {'status': False, 'error': str(e)}

    return {'status': True, 'error': ''}


def get_celery_task_id(handover_token: str):
    """[Get celery task id for given handover id]

    Args:
        hadover_id (str): [Handover Id]

    Raises:
        ValueError: [Handover Status in progress ]

    Returns:
        [task_id]: [str]
    """
    try:
        task_id = ''
        with ElasticsearchConnectionManager(es_host, int(es_port), es_user, es_password, es_ssl) as es:
            res = es.client.search(index=es_index, body={
                "size": 0,
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"params.handover_token.keyword": str(handover_token)}},
                            {
                                "query_string": {
                                    "fields": ["report_type"], "query": "(INFO|ERROR)",
                                    "analyze_wildcard": "true"
                                }
                            },
                        ]
                    }
                },
                "aggs": {
                    "top_result": {
                        "top_hits": {
                            "size": 1,
                            "sort": {
                                "report_time": "desc"
                            }
                        }
                    }
                },
                "sort": [
                    {
                        "report_time": {
                            "order": "desc"
                        }
                    }
                ]
            })

        for doc in res['aggregations']['top_result']['hits']['hits']:
            task_id = doc['_source']['params']['task_id']

    except Exception as e:
        return {'status': False, 'error': str(e)}

    return {'status': True, 'error': '', 'task_id': task_id, 'spec': doc['_source']['params']}


def log_and_publish(report):
    """Handy function to mimick the logger/publisher behaviour.
    """
    level = report['report_type']
    routing_key = 'report.%s' % level.lower()
    logger.log(getattr(logging, level), report['msg'])
    publisher.publish(report, routing_key)


def parse_db_infos(database):
    """Parse database name and extract db_prefix and db_type. Also extract release and assembly for species databases"""
    if species_pattern.match(database):
        m = species_pattern.match(database)
        db_prefix = m.group('prefix')
        db_type = m.group('type')
        assembly = m.group('assembly')
        return db_prefix, db_type, assembly
    elif compara_pattern.match(database):
        m = compara_pattern.match(database)
        division = m.group('division')
        db_prefix = division if division else 'vertebrates'
        return db_prefix, 'compara', None
    elif ancestral_pattern.match(database):
        m = ancestral_pattern.match(database)
        division = m.group('division')
        db_prefix = division if division else 'vertebrates'
        return db_prefix, 'ancestral', None
    else:
        raise ValueError("Database type for %s is not expected. Please contact the Production team" % database)


def check_staging_server(spec, db_type, db_prefix, assembly):
    """Find which staging server should be used. secondary_staging for GRCh37 and Bacteria, staging for the rest"""
    qualified_uri = qualified_name(spec['src_uri'])
    if 'bacteria' in db_prefix:
        staging_uri = cfg.secondary_staging_uri
        live_uri = cfg.secondary_live_uri
    elif db_prefix == 'homo_sapiens' and assembly == '37':
        staging_uri = cfg.secondary_staging_uri
        live_uri = cfg.secondary_live_uri
        spec['GRCh37'] = 1
        spec['progress_total'] = 2
    elif db_type == 'compara' and check_grch37(qualified_uri, 'homo_sapiens'):
        staging_uri = cfg.secondary_staging_uri
        live_uri = cfg.secondary_live_uri
        spec['GRCh37'] = 1
        spec['progress_total'] = 2
    else:
        staging_uri = cfg.staging_uri
        live_uri = cfg.live_uri
    return spec, staging_uri, live_uri


def get_tgt_uri(src_url, staging_uri):
    """Create target URI from staging details and name of source database"""
    return '%s%s' % (staging_uri, src_url.database)


def drop_current_databases(current_db_list, spec, target_db_delete=None):
    """[Drop databases on a previous assembly or previous genebuild (e.g: Wormbase) from the staging MySQL server]

    Args:
        current_db_list ([List]): [List of databases names to be dropped]
        spec ([Dict]): [Handover payload with details ]
        target_db_delete ([Boolean], optional): [Flag to delete given list of databases]. Defaults to None.

    Returns:
        [Boolean]: [status of dropdatabase method]
    """

    try:

        if target_db_delete:
            drop_database(spec['tgt_uri'])
            return True

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
                    msg = 'Dropping database %s' % database
                    log_and_publish(make_report('INFO', msg, spec, tgt_uri))
                    drop_database(db_uri)
    except Exception as e:
        return False


def process_handover_payload(spec):
    """ """
    src_uri = spec['src_uri']
    # create unique identifier
    spec['handover_token'] = str(uuid.uuid1())
    spec['progress_total'] = 3
    qualified_uri = qualified_name(src_uri)
    if not database_exists(qualified_uri):
        msg = "Handover failed, %s does not exist" % src_uri
        log_and_publish(make_report('ERROR', msg, spec, src_uri))
        raise ValueError("%s does not exist" % src_uri)
    src_url = make_url(src_uri)

    # Scan database name and retrieve species or compara name, database type, release number and assembly version
    db_prefix, db_type, assembly = parse_db_infos(src_url.database)
    # Check if the given database can be handed over
    logger.debug("Retrieved %s %s %s ", db_prefix, db_type, assembly)
    if db_type not in db_types_list:
        msg = "Handover failed, %s has been handed over after deadline. Please contact the Production team" % src_uri
        log_and_publish(make_report('ERROR', msg, spec, src_uri))
        raise ValueError(msg)
    # Check if the database release match the handover service
    if db_type == 'compara':
        if check_grch37(qualified_uri, 'homo_sapiens') and cfg.HANDOVER_TYPE != 'grch37':
            raise ValueError("Please use the dedicated handover for Grch37 databases. Contact Production team")
        db_release = get_release_compara(qualified_uri)
    else:
        db_release = get_release(qualified_uri)
        logger.info("Db_release %s %s", db_type, db_release)
        if db_prefix == 'homo_sapiens' and assembly == '37' and cfg.HANDOVER_TYPE != 'grch37':
            raise ValueError("Please use the dedicated handover for Grch37 databases. Contact Production team")
        elif (db_type in cfg.dispatch_targets.keys() and any(
                db_prefix in val for val in cfg.compara_species)) or cfg.dispatch_all:
            logger.info("Adding dispatch step to total")
            spec['progress_total'] = 4
    if release != db_release:
        msg = "Handover failed, %s database release version %s does not match handover service " \
              "release version %s, update schema version in meta table to current handover version %s" % (
                  src_uri, db_release, release, release)
        log_and_publish(make_report('ERROR', msg, spec, src_uri))
        raise ValueError(msg)
    # Check to which staging server the database need to be copied to
    spec, staging_uri, live_uri = check_staging_server(spec, db_type, db_prefix, assembly)
    if 'tgt_uri' not in spec:
        spec['tgt_uri'] = get_tgt_uri(src_url, staging_uri)
    # Check that the database division match the target staging server
    if db_type in ['compara', 'ancestral']:
        db_division = db_prefix
    else:
        db_division = get_division(qualified_uri, qualified_name(spec['tgt_uri']), db_type)

    if db_division not in allowed_divisions_list:
        raise ValueError(
            'Database division %s does not match server division list %s' % (db_division, allowed_divisions_list))
    spec['staging_uri'] = staging_uri
    spec['progress_complete'] = 0
    spec['db_division'] = db_division
    spec['db_type'] = db_type
    msg = "Handling %s" % spec
    logger.info("Handover Specs %s", spec)
    log_and_publish(make_report('INFO', msg, spec, src_uri))
    return spec, src_url, db_type


# submit handover jobs to respective
def submit_dc(spec, src_url, db_type):
    """Submit the source database for checking. Returns a celery job identifier"""
    try:
        src_uri = spec['src_uri']
        tgt_uri = spec['tgt_uri']
        qualified_uri = qualified_name(src_uri)
        staging_uri = spec['staging_uri']
        handover_token = spec['handover_token']
        server_url = 'mysql://%s@%s:%s/' % (src_url.username, src_url.host, src_url.port)
        submitting_dc_msg = 'Submitting DC for %s on server: %s' % (src_url.database, server_url)
        submitting_dc_report = make_report('DEBUG', submitting_dc_msg, spec, src_uri)
        if db_type == 'compara':
            log_and_publish(submitting_dc_report)
            dc_job_id = dc_client.submit_job(server_url, src_url.database, None, None,
                                             db_type, None, db_type, 'critical', None, handover_token, staging_uri)
        elif db_type == 'ancestral':
            log_and_publish(submitting_dc_report)
            dc_job_id = dc_client.submit_job(server_url, src_url.database, None, None,
                                             'core', None, 'ancestral', 'critical', None, handover_token, staging_uri)
        elif db_type in ['rnaseq', 'cdna', 'otherfeatures']:
            division_msg = 'division: %s' % get_division(qualified_uri, qualified_name(tgt_uri), db_type)
            log_and_publish(make_report('DEBUG', division_msg, spec, src_uri))
            log_and_publish(submitting_dc_report)
            dc_group = 'corelike,rapid_release' if cfg.HANDOVER_TYPE == 'rapid' else 'corelike'
            dc_job_id = dc_client.submit_job(server_url, src_url.database, None, None,
                                             db_type, None, dc_group, 'critical', None, handover_token, staging_uri)
        else:
            db_msg = 'src_uri: %s dbtype %s server_url %s' % (src_uri, db_type, server_url)
            log_and_publish(make_report('DEBUG', db_msg, spec, src_uri))
            division_msg = 'division: %s' % get_division(qualified_uri, qualified_name(tgt_uri), db_type)
            log_and_publish(make_report('DEBUG', division_msg, spec, src_uri))
            log_and_publish(submitting_dc_report)
            dc_group = db_type + ',rapid_release' if cfg.HANDOVER_TYPE == 'rapid' else db_type
            dc_job_id = dc_client.submit_job(server_url, src_url.database, None, None,
                                             db_type, None, dc_group, 'critical', None, handover_token, staging_uri)
    except Exception as e:
        err_msg = 'Handover failed, Cannot submit dc job'
        log_and_publish(make_report('ERROR', err_msg, spec, src_uri))
        raise ValueError('Handover failed, Cannot submit dc job %s' % e) from e
    spec['dc_job_id'] = dc_job_id

    return dc_job_id, spec, src_uri


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

        # submit a copy job
        copy_job_id = db_copy_client.submit_job(src_host, src_incl_db, None, None, None,
                                                tgt_host, tgt_db_name, False, False, False,
                                                cfg.production_email,
                                                cfg.copy_job_user)

    except Exception as e:
        log_and_publish(make_report('ERROR', 'Handover failed, cannot submit copy job', spec, src_uri))
        raise ValueError('Handover failed, cannot submit copy job %s' % e) from e
    spec['copy_job_id'] = copy_job_id

    return copy_job_id


def submit_metadata_update(spec):
    """Submit the source database for copying to the target. Returns a celery job identifier."""
    src_uri = spec['src_uri']
    try:
        logger.error("Submit metadata %s", spec['tgt_uri'])
        # self, database_uri, e_release, eg_release, release_date, current_release, email, comment, source
        metadata_job_id = metadata_client.submit_job(spec['tgt_uri'], None, None, None,
                                                     None, spec['contact'], spec['comment'], 'Handover')
    except Exception as e:
        logger.error("Unable to submit metadata %s", e)
        log_and_publish(make_report('ERROR', 'Handover failed, cannot submit metadata job', spec, src_uri))
        raise ValueError('Handover failed, cannot submit metadata job %s' % e) from e
    spec['metadata_job_id'] = metadata_job_id
    # task_id = process_db_metadata.delay(metadata_job_id, spec)
    # dbg_msg = 'Submitted DB for metadata loading %s' % task_id
    # log_and_publish(make_report('DEBUG', dbg_msg, spec, src_uri))
    return metadata_job_id


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
    # task_id = process_dispatch_db.delay(copy_job_id, spec)
    # dbg_msg = 'Submitted DB for dispatch as %s' % task_id
    # log_and_publish(make_report('DEBUG', dbg_msg, spec, src_uri))
    return copy_job_id


def submit_event(spec, result):
    """Submit an event"""
    tgt_uri = spec['tgt_uri']
    logger.debug(result['output']['events'])
    for event in result['output']['events']:
        logger.debug(event)
        event_client.submit_job({'type': event['type'], 'genome': event['genome']})
        log_and_publish(make_report('DEBUG', 'Submitted event to event handler endpoint', spec, tgt_uri))
