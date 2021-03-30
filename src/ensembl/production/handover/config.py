'''
@author: dstaines; Vinay
'''
import os
from ensembl.production.core.config import load_config_yaml

class HandoverConfig():

    config_file_path = os.environ.get('HANDOVER_CORE_CONFIG_PATH', os.path.join(os.path.dirname(__file__),
                                                                            'handover_config.dev.yaml'))
    file_config = load_config_yaml(config_file_path)

    #core config
    dc_uri = os.environ.get("DC_URI",
                        file_config.get('dc_uri', "http://ens-prod-1:5006/datacheck"))
    copy_uri = os.environ.get("COPY_URI",
                          #file_config.get('copy_uri', "http://127.0.0.1:5002/")) production-services.ensembl.org
                          file_config.get('copy_uri', "http://production-services.ensembl.org/api/dbcopy/requestjob"))
    copy_uri_dropdown = os.environ.get("COPY_URI_DROPDOWN",
                          file_config.get('copy_uri_dropdown', "http://production-services.ensembl.org:80/")) 
                                                
    copy_web_uri = os.environ.get("COPY_WEB_URI",
                              file_config.get('copy_web_uri',
                                              "http://production-services.ensembl.org/admin/ensembl_dbcopy/requestjob/"))
    meta_uri = os.environ.get("META_URI",
                          file_config.get('meta_uri',
                                          "http://127.0.0.1:5003/"))
    meta_web_uri = os.environ.get("META_WEB_URI",
                              file_config.get('meta_web_uri',
                                              "http://127.0.0.1:9000/#!/metadata_result/"))
    event_uri = os.environ.get("EVENT_URI",
                           file_config.get('event_uri',
                                           'http://127.0.0.1:5004/'))
    staging_uri = os.environ.get("STAGING_URI",
                             file_config.get('staging_uri',
                                             "mysql://ensro@mysql-ens-general-dev-1:4484/"))
    secondary_staging_uri = os.environ.get("SECONDARY_STAGING_URI",
                                       file_config.get('secondary_staging_uri',
                                                       "mysql://ensro@mysql-ens-general-dev-1:4484/"))
    live_uri = os.environ.get("LIVE_URI",
                          file_config.get('live_uri',
                                          "mysql://user@127.0.0.1:3306/"))
    secondary_live_uri = os.environ.get("SECONDARY_LIVE_URI",
                                    file_config.get('secondary_live_uri',
                                                    "mysql://ensembl@127.0.0.1:3306/"))
    smtp_server = os.environ.get("SMTP_SERVER",
                             file_config.get('smtp_server', 'smtp.ebi.ac.uk'))
    report_server = os.environ.get("REPORT_SERVER",
                               file_config.get('report_server',
                                               "amqp://qrp:qrp@localhost:5672/%2F"))
    report_exchange = os.environ.get("REPORT_EXCHANGE",
                                 file_config.get('report_exchange', 'report_exchange'))
    report_exchange_type = os.environ.get("REPORT_EXCHANGE_TYPE",
                                      file_config.get('report_exchange_type', 'topic'))
    data_files_path = os.environ.get("DATA_FILE_PATH",
                                 file_config.get('data_files_path', '/data_files/'))
    allowed_database_types = os.environ.get("ALLOWED_DATABASE_TYPES",
                                        file_config.get('allowed_database_types',
                                                        'core,rnaseq,cdna,otherfeatures,variation,'
                                                        'funcgen,compara,ancestral'))
    production_email = os.environ.get("PRODUCTION_EMAIL",
                                  file_config.get('production_email',
                                                  'email@ebi.ac.uk'))
    allowed_divisions = os.environ.get("ALLOWED_DIVISIONS",
                                   file_config.get('allowed_divisions',
                                                   'vertebrates'))


    dispatch_targets = file_config.get('dispatch_targets', [])
    compara_species = file_config.get('compara_species', [])
    copy_job_user = file_config.get('copy_job_user', 'ensprod')
    
    #handover layout
    HANDOVER_TYPE = os.environ.get('HANDOVER_TYPE', file_config.get('handover_type', 'vertebrates'))   # change this value based on haver you want to deploy ex: plants/metazoa/bacteria 
    HANDOVER_LAYOUT = {
        'vertebrates': ['info', 'Handover Vertebrates', '#17a2b8!important'],
        'plants': ['success', 'Handover Plants', '#28a745!important'],
        'metazoa': ['primary', 'Handover Metazoa', '#007bff!important'],
        'microbes': ['secondary', 'Handover Microbes', '#6c757d!important'],
        'bacteria': ['secondary', 'Handover Bacteria', '#6c757d!important']
    }

    #es config 
    HOST = os.environ.get('SERVICE_HOST', file_config.get('host', '0.0.0.0'))
    PORT = os.environ.get('SERVICE_PORT', file_config.get('port'))
    ES_HOST = os.environ.get('ES_HOST', file_config.get('es_host', 'es.production.ensembl.org'))
    ES_PORT = os.environ.get('ES_PORT', file_config.get('es_port', '80'))
    ES_INDEX = os.environ.get('ES_INDEX', file_config.get('es_index', 'reports_vert'))
    RELEASE = os.environ.get('ENS_RELEASE', file_config.get('ens_release', '104'))
    BLAT_SPECIES = ['homo_sapiens',
                'mus_musculus',
                'danio_rerio',
                'rattus_norvegicus',
                'gallus_gallus',
                'canis_lupus_familiaris',
                'bos_taurus',
                'oryctolagus_cuniculus',
                'oryzias_latipes',
                'sus_scrofa',
                'meleagris_gallopavo',
                'anas_platyrhynchos_platyrhynchos',
                'ovis_aries',
                'oreochromis_niloticus',
                'gadus_morhua']


class HandoverCeleryConfig():

    config_file_path = os.environ.get('HANDOVER_CELERY_CONFIG_PATH')
    
    file_config = load_config_yaml(config_file_path)

    broker_url = os.environ.get("CELERY_BROKER_URL",
                            file_config.get('celery_broker_url', 'pyamqp://qrp:qrp@localhost:5672/'))
    result_backend = os.environ.get("CELERY_RESULT_BACKEND",
                                file_config.get('celery_result_backend', 'rpc://qrp:qrp@localhost:5672/'))
    smtp_server = os.environ.get("SMTP_SERVER",
                             file_config.get('smtp_server', 'localhost'))
    from_email_address = os.environ.get("FROM_EMAIL_ADDRESS",
                                    file_config.get('from_email_address', 'ensembl-production@ebi.ac.uk'))
    retry_wait = int(os.environ.get("RETRY_WAIT",
                                file_config.get('retry_wait', 60)))

    task_routes = {
        os.environ.get("ROUTING_KEY",
                       file_config.get('routing_key', 'ensembl_prodinf.handover_tasks.*')): {
                           'queue': os.environ.get("QUEUE",
                                               file_config.get('queue', 'handover'))}
    }

