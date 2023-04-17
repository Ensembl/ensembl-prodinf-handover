# See the NOTICE file distributed with this work for additional information
#   regarding copyright ownership.
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#       http://www.apache.org/licenses/LICENSE-2.0
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
import ssl

import urllib3
from elasticsearch import Elasticsearch, ElasticsearchException
from elasticsearch.connection import create_ssl_context


# TODO move this in ensembl-prodinf-core
class ElasticsearchConnectionManager:
    def __init__(self, host: str, port: str, user: str, password: str, with_ssl: bool):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.ssl = with_ssl
        self.client = None

    def __enter__(self):
        urllib3.disable_warnings(category=urllib3.connectionpool.InsecureRequestWarning)
        ssl_context = create_ssl_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        self.client = Elasticsearch(hosts=[{'host': self.host, 'port': self.port}],
                                    scheme="https" if self.ssl else "http",
                                    ssl_context=ssl_context,
                                    http_auth=(self.user, self.password))
        if not self.client.ping():
            raise (
                f"Cannot connect to Elasticsearch server. User: {self.user}, Host: {self.host}:{self.port}"
            )
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.client.transport.close()
