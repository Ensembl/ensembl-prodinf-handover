import logging

from celery import Celery

app = Celery('ensembl_handover_celery',
             include=['ensembl.production.handover.celery_app.tasks'])

# Load the externalised config module from PYTHONPATH
try:
    from ensembl.production.handover.config import HandoverCeleryConfig 

    app.config_from_object(HandoverCeleryConfig)
except Exception as e:
    print(e)
    logging.warning('Celery email requires handover_celery_app_config module')


if __name__ == '__main__':
    app.start()
