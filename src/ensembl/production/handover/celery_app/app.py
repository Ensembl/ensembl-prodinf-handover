#!/usr/bin/env python
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

import logging

from celery import Celery
from ensembl.production.handover.config import HandoverCeleryConfig
import ensembl.production.handover.celery_app.tasks

try:
    app = Celery('ensembl_handover_celery',
                 include=['ensembl.production.handover.celery_app.tasks'])
    app.config_from_object(HandoverCeleryConfig)
except Exception as e:
    print(e)
    logging.warning('Celery email requires handover_celery_app_config module')


if __name__ == '__main__':
    app.start()
