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

import datetime
import logging
import os
import re

import requests
from elasticsearch import TransportError, NotFoundError
from flasgger import Swagger
from flask import Flask, request, jsonify, render_template, redirect, flash, url_for
from flask_bootstrap import Bootstrap4
from flask_cors import CORS
from requests.exceptions import HTTPError
from sqlalchemy.exc import OperationalError
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

import ensembl.production.handover.exceptions
from ensembl.production.core import app_logging
from ensembl.production.core.es import ElasticsearchConnectionManager
from ensembl.production.core.exceptions import HTTPRequestError
from ensembl.production.handover.celery_app.tasks import handover_database, stop_handover_job, restart_handover_job
from ensembl.production.handover.config import HandoverConfig as cfg
from ensembl.production.handover.exceptions import MissingDispatchException
from ensembl.production.handover.forms import HandoverSubmissionForm

# set static and template paths
app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_path = os.path.join(app_path, 'static')
template_path = os.path.join(app_path, 'templates')
app = Flask(__name__,
            instance_relative_config=True,
            static_folder=static_path,
            template_folder=template_path,
            static_url_path='/static/handovers/')
app.config.from_object('ensembl.production.handover.config.HandoverConfig')
formatter = logging.Formatter("[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")
handler = app_logging.default_handler()
handler.setFormatter(formatter)
handler.setLevel(cfg.log_level)
app.logger.addHandler(handler)
app.url_map.strict_slashes = False

app.config['SWAGGER'] = {
    'title': 'Ensembl %s Handover Service' % app.config['HANDOVER_TYPE'],
    'uiversion': 3,
    'hide_top_bar': True,
    'ui_params': {
        'defaultModelsExpandDepth': -1
    },
    'favicon': f'{cfg.script_name}/img/production.png'
}
if app.env == 'development':
    # ENV dev (assumed run from builtin server, so update script_name at wsgi level)
    app.wsgi_app = DispatcherMiddleware(
        Response('Not Found', status=404),
        {cfg.script_name: app.wsgi_app}
    )

swagger = Swagger(app)
cors = CORS(app)
bootstrap = Bootstrap4(app)

# use re to support different charsets
json_pattern = re.compile("application/json")
form_pattern = re.compile("multipart/form-data")
es_host = app.config['ES_HOST']
es_port = int(app.config['ES_PORT'])
es_index = app.config['ES_INDEX']
es_user = app.config['ES_USER']
es_password = app.config['ES_PASSWORD']
es_ssl = app.config['ES_SSL']


@app.context_processor
def inject_configs():
    app.logger.info(f"Script name {cfg.script_name}")
    return dict(script_name=cfg.script_name,
                copy_uri=cfg.copy_uri,
                css_url=f"css/{cfg.HANDOVER_TYPE}.css")


@app.route('/', methods=['GET'])
def info():
    if not cfg.compara_species:
        # Empty list of compara
        raise MissingDispatchException

    app.config['SWAGGER'] = {
        'title': '%s handover REST endpoints' % os.getenv('APP_ENV', '').capitalize(),
        'uiversion': 2
    }
    return jsonify(app.config['SWAGGER'])


@app.route('/ping', methods=['GET'])
def ping():
    if not cfg.compara_species:
        # Empty list of compara
        raise MissingDispatchException

    return jsonify({"status": "ok"})


@app.route('/jobs/dropdown/src_host', methods=['GET'])
@app.route('/jobs/dropdown/databases/<string:src_host>/<string:src_port>', methods=['GET'])
def dropdown(src_host=None, src_port=None):
    try:
        src_name = request.args.get('name', None)
        search = request.args.get('search', None)
        if src_name:
            res = requests.get(f"{cfg.copy_uri_dropdown}api/dbcopy/srchost", params={'name': src_name})
            res.raise_for_status()
            return jsonify(res.json())
        elif src_host and src_port and search:
            res = requests.get(f"{cfg.copy_uri_dropdown}api/dbcopy/databases/{src_host}/{src_port}",
                               params={'search': search})
            res.raise_for_status()
            return jsonify(res.json())
        else:
            raise Exception('required params not provided')
    except HTTPError as http_err:
        raise HTTPRequestError(f'{http_err}', 404)
    except Exception as e:
        logging.fatal(str(e))
        return jsonify({"count": 0, "next": None, "previous": None, "results": [], "error": str(e)})


# UI Submit-form for handover
@app.route('/jobs/submit', methods=['GET', 'POST'])
def handover_form():
    if not cfg.compara_species:
        # Empty list of compara
        raise MissingDispatchException

    form = HandoverSubmissionForm(request.form)
    try:

        if request.method == 'POST':

            if form.validate() and not request.form.get('handover_submit'):
                spec = request.form.to_dict()
                spec['src_uri'] = spec['src_uri'] + spec['database']
                app.logger.debug('Submitting handover request %s', spec)
                ticket = handover_database(spec)
                app.logger.info('Ticket: %s', ticket)
                return redirect(url_for('handover_result', handover_token=str(ticket)))
            else:
                for error_key, error in form.errors.items():
                    flash(f"{error_key}: {error}")
    except Exception as e:
        app.logger.exception(f"Handover error {e}")
        flash(f"Something went wrong: {e}")
    return render_template(
        'submit.html',
        form=form,
        ALLOWED_DATABASE_TYPES=cfg.allowed_database_types if cfg.allowed_database_types else "None - Handover closed",
        disable_submission=cfg.allowed_database_types == ''
    )


@app.route('/config', methods=['GET'])
def config():
    """ Disply all configs vars"""
    config = {key: value if 'pass' not in key.lower() else 'XXXXXX' for key, value in cfg.__dict__.items() if key[:1] != '_'}
    return render_template(
        'config.html',
        config=config
    )


@app.route('/jobs', methods=['POST'])
def handovers():
    """
    Endpoint to submit an handover job
    This is using docstring for specifications
    ---
    tags:
      - handovers
    parameters:
      - in: body
        name: body
        description: DC object
        required: false
        schema:
          $ref: '#/definitions/jobs'
    operationId: handovers
    consumes:
      - application/json
    produces:
      - application/json
    security:
      handovers_auth:
        - 'write:jobs'
        - 'read:jobs'
    schemes: ['http', 'https']
    deprecated: false
    externalDocs:
      description: Project repository
      url: http://github.com/rochacbruno/flasgger
    definitions:
      handovers:
        title: handover job
        description: A job to handover a database, the database will be healthchecked, copied and added to metadata database
        type: object
        required:
          -src_uri
          -contact
          -type
          -comment
        properties:
          src_uri:
            type: string
            example: 'mysql://user@server:port/saccharomyces_cerevisiae_core_91_4'
          comment:
            type: string
            example: 'handover new Panda OF'
          contact:
            type: string
            example: 'joe.blogg@ebi.ac.uk'
    responses:
      200:
        description: submit of an handover job
        schema:
          $ref: '#/definitions/jobs'
        examples:
          {src_uri: "mysql://user@server:port/saccharomyces_cerevisiae_core_91_4", contact: "joe.blogg@ebi.ac.uk", comment: "handover new Panda OF"}
    """
    try:
        if not cfg.compara_species:
            # Empty list of compara
            raise MissingDispatchException
            # get form data
        if form_pattern.match(request.headers['Content-Type']):
            spec = request.form.to_dict(flat=True)
        elif json_pattern.match(request.headers['Content-Type']):
            spec = request.json
        else:
            raise HTTPRequestError('Could not handle input of type %s' % request.headers['Content-Type'])

        if 'src_uri' not in spec or 'contact' not in spec or 'comment' not in spec:
            raise HTTPRequestError("Handover specification incomplete - please specify src_uri, contact and comment")

        app.logger.debug('Submitting handover request %s', spec)
        ticket = handover_database(spec)
        app.logger.info('Ticket: %s', ticket)

    except Exception as e:
        raise HTTPRequestError(str(e), 400)
    return jsonify(ticket)


@app.route('/jobs/status', methods=['PUT'])
def handover_status_update():
    """update handover status to success"""
    try:
        if json_pattern.match(request.headers['Content-Type']):
            handover_token = request.json.get('handover_token')
        else:
            raise HTTPRequestError('Could not handle input of type %s' % request.headers['Content-Type'])
        with ElasticsearchConnectionManager(es_host, es_port, es_user, es_password, es_ssl) as es:
            res_error = es.client.search(index=es_index, body={
                "query": {
                    "bool": {
                        "must": [{"term": {"params.handover_token.keyword": str(handover_token)}},
                                 {"term": {"report_type.keyword": "INFO"}},
                                 {"query_string": {"fields": ["message"], "query": "*Metadata load failed*"}}],
                        "must_not": [], "should": []
                    }
                }, "from": 0, "size": 1,
                "sort": [{"report_time": {"order": "desc"}}], "aggs": {}
            })

            if len(res_error['hits']['hits']) == 0:
                raise HTTPRequestError('No Hits Found for Handover Token : %s' % handover_token)

            # set handover message to success
            result = res_error['hits']['hits'][0]['_source']
            h_id = res_error['hits']['hits'][0]['_id']
            result['report_time'] = str(datetime.datetime.now().isoformat())[:-3]
            result['message'] = 'Metadata load complete, Handover successful'
            result['report_type'] = 'INFO'
            res = es.client.update(index=es_index, id=h_id, doc_type='report', body={"doc": result})
    except Exception as e:
        raise HTTPRequestError('%s' % str(e))

    return res


@app.route('/job', methods=['GET'])
@app.route('/jobs/<string:handover_token>', methods=['GET'])
def handover_result(handover_token=''):
    """
    Endpoint to get an handover job detail
    This is using docstring for specifications
    ---
    tags:
      - handovers
    parameters:
      - name: handover_token
        in: path
        type: string
        required: true
        default: 15ce20fd-68cd-11e8-8117-005056ab00f0
        description: handover token for the database handed over
    operationId: handovers
    consumes:
      - application/json
    produces:
      - application/json
    security:
      handovers_auth:
        - 'write:handovers'
        - 'read:handovers'
    schemes: ['http', 'https']
    deprecated: false
    externalDocs:
      description: Project repository
      url: http://github.com/rochacbruno/flasgger
    definitions:
      handovers:
        title: Get a handover job details
        description: This will retrieve a handover job details
        type: object
        required:
          -handover_token
        properties:
          handover_token:
            type: string
            example: '15ce20fd-68cd-11e8-8117-005056ab00f0'
    responses:
      200:
        description: Retrieve an handover job ticket
        schema:
          $ref: '#/definitions/jobs'
        examples:
          [{"comment": "handover new Tiger database", "contact": "maurel@ebi.ac.uk", "handover_token": "605f1191-7a13-11e8-aa7e-005056ab00f0", "id": "X1qcQWQBiZ0vMed2vaAt", "message": "Metadata load complete, Handover successful", "progress_total": 3, "report_time": "2018-06-27T15:19:08.459", "src_uri": "mysql://ensro@mysql-ens-general-prod-1:4525/panthera_tigris_altaica_core_93_1", "tgt_uri": "mysql://ensro@mysql-ens-general-dev-1:4484/panthera_tigris_altaica_core_93_1"} ]
    """

    fmt = request.args.get('format', None)
    # TODO Move this into core (potential usage on every flask app)
    # renter bootstrap table
    if fmt != 'json' and not request.is_json:
        return render_template('result.html',
                               handover_token=handover_token)

    with ElasticsearchConnectionManager(es_host, es_port, es_user, es_password, es_ssl) as es:
        handover_detail = []
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
        result = {"id": doc['_id']}
        params = doc['_source']['params']
        if 'job_progress' in params:
            result['job_progress'] = params['job_progress']
        result['message'] = doc['_source']['message']
        result['comment'] = params.get('comment', '')
        result['handover_token'] = params.get('handover_token', '')
        result['contact'] = params.get('contact', '')
        result['src_uri'] = params.get('src_uri', '')
        result['tgt_uri'] = params.get('tgt_uri', '')
        result['progress_complete'] = params.get('progress_complete', '')
        result['progress_total'] = params.get('progress_total', '')
        result['report_time'] = doc['_source']['report_time']
        handover_detail.append(result)

    if len(handover_detail) == 0:
        raise HTTPRequestError('Handover token %s not found' % handover_token, 404)
    else:
        return jsonify(handover_detail)


@app.route('/jobs', methods=['GET'])
def handover_results():
    """
    Endpoint to get a list of all the handover by release
    This is using docstring for specifications
    ---
    tags:
      - handovers
    operationId: handovers
    parameters:
      - name: release
        in: query
        type: string
        description: get handover list for the given release
      - name: format
        in: query
        type: string
        example: json
        description: get hadover format

    consumes:
      - application/json
    produces:
      - application/json
    security:
      handovers_auth:
        - 'write:handovers'
        - 'read:handovers'
    schemes: ['http', 'https']
    deprecated: false
    externalDocs:
      description: Project repository
      url: http://github.com/rochacbruno/flasgger
    definitions:
      handovers:
        title: Retrieve a list of handover databases
        description: This will retrieve all the handover job details
        type: object
    responses:
      200:
        description: Retrieve all the handover job details
        schema:
          $ref: '#/definitions/jobs'
        examples:
          [{"comment": "handover new Tiger database", "contact": "maurel@ebi.ac.uk", "handover_token": "605f1191-7a13-11e8-aa7e-005056ab00f0", "id": "QFqRQWQBiZ0vMed2vKDI", "message": "Handling {u'comment': u'handover new Tiger database', 'handover_token': '605f1191-7a13-11e8-aa7e-005056ab00f0', u'contact': u'maurel@ebi.ac.uk', u'src_uri': u'mysql://ensro@mysql-ens-general-prod-1:4525/panthera_tigris_altaica_core_93_1', 'tgt_uri': 'mysql://ensro@mysql-ens-general-dev-1:4484/panthera_tigris_altaica_core_93_1'}", "report_time": "2018-06-27T15:07:07.462", "src_uri": "mysql://ensro@mysql-ens-general-prod-1:4525/panthera_tigris_altaica_core_93_1", "tgt_uri": "mysql://ensro@mysql-ens-general-dev-1:4484/panthera_tigris_altaica_core_93_1"}, {"comment": "handover new Leopard database", "contact": "maurel@ebi.ac.uk", "handover_token": "5dcb1aca-7a13-11e8-b24e-005056ab00f0", "id": "P1qRQWQBiZ0vMed2rqBh", "message": "Handling {u'comment': u'handover new Leopard database', 'handover_token': '5dcb1aca-7a13-11e8-b24e-005056ab00f0', u'contact': u'maurel@ebi.ac.uk', u'src_uri': u'mysql://ensro@mysql-ens-general-prod-1:4525/panthera_pardus_core_93_1', 'tgt_uri': 'mysql://ensro@mysql-ens-general-dev-1:4484/panthera_pardus_core_93_1'}", "report_time": "2018-06-27T15:07:03.145", "src_uri": "mysql://ensro@mysql-ens-general-prod-1:4525/panthera_pardus_core_93_1", "tgt_uri": "mysql://ensro@mysql-ens-general-dev-1:4484/panthera_pardus_core_93_1"} ]
    """
    app.logger.info("Retrieving all handover report")

    release = request.args.get('release', str(app.config['RELEASE']))
    fmt = request.args.get('format', None)

    # renter bootstrap table
    if fmt != 'json' and not request.is_json:
        return render_template('list.html')

    with ElasticsearchConnectionManager(es_host, es_port, es_user, es_password, es_ssl) as es:
        res = es.client.search(index=es_index, body={
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {
                            "query_string": {
                                "fields": [
                                    "report_type"
                                ],
                                "query": "(INFO|ERROR)",
                                "analyze_wildcard": "true"
                            }
                        },
                        {
                            "query_string": {
                                "fields": [
                                    "params.database"
                                ],
                                "query": "/.*_{}(_[0-9]+)?/".format(release)
                            }
                        }
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
                        },
                        "submission_time": {"min": {"field": "report_time"}},
                        "last_message": {"max": {"field": "report_time"}}
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

    list_handovers = []
    app.logger.info(f"Results {res}")
    for each_handover_bucket in res['aggregations']['handover_token']['buckets']:
        for doc in each_handover_bucket['top_result']['hits']['hits']:
            result = {"id": doc['_id']}
            if 'job_progress' in doc['_source']['params']:
                result['job_progress'] = doc['_source']['params']['job_progress']

            result['handover_token'] = doc['_source']['params']['handover_token']
            result['message'] = doc['_source']['message']
            result['comment'] = doc['_source']['params']['comment']
            result['current_message'] = doc['_source']['message']
            result['contact'] = doc['_source']['params']['contact']
            result['src_uri'] = doc['_source']['params']['src_uri']
            result['report_time'] = doc['_source']['report_time']
            result['handover_submission_time'] = each_handover_bucket['submission_time']['value_as_string']
            list_handovers.append(result)

    return jsonify(list_handovers)


def valid_handover(doc, release):
    src_uri = doc['_source']['params']['src_uri']
    match = re.match(r'^.*?_(?P<first>\d+)(_(?P<second>\d+))?(_(\d+))?$', src_uri)
    if match:
        first = match.group('first')
        second = match.group('second')
        return (first == release) or ((second == release) and (int(second) - int(first) == 53))
    return False


@app.route('/jobs/<string:handover_token>', methods=['DELETE'])
def delete_handover(handover_token):
    """
    Endpoint to delete all the reports linked to a handover_token
    This is using docstring for specifications
    ---
    tags:
      - handovers
    parameters:
      - name: handover_token
        in: path
        type: string
        required: true
        default: 15ce20fd-68cd-11e8-8117-005056ab00f0
        description: handover token for the database handed over
    operationId: handovers
    consumes:
      - application/json
    produces:
      - application/json
    security:
      delete_auth:
        - 'write:delete'
        - 'read:delete'
    schemes: ['http', 'https']
    deprecated: false
    externalDocs:
      description: Project repository
      url: http://github.com/rochacbruno/flasgger
    definitions:
      handover_token:
        type: object
        properties:
          handover_token:
            type: integer
            items:
              $ref: '#/definitions/handover_token'
      id:
        type: integer
        properties:
          id:
            type: integer
            items:
              $ref: '#/definitions/id'
    responses:
      200:
        description: handover_token of the reports that need deleting
        schema:
          $ref: '#/definitions/handover_token'
        examples:
          id: 15ce20fd-68cd-11e8-8117-005056ab00f0
    """
    try:
        app.logger.info('Retrieving handover data with token %s', handover_token)
        with ElasticsearchConnectionManager(es_host, es_port, es_user, es_password, es_ssl) as es:
            result = es.client.delete_by_query(index=es_index, doc_type='report', body={
                "query": {"bool": {"must": [{"term": {"params.handover_token.keyword": str(handover_token)}}]}}
            })
            app.logger.info(str(result))
        stop_handover_job(handover_token)
        app.logger.info('Delete query success for %s', handover_token)
        return jsonify(str(handover_token))
    except NotFoundError as e:
        raise HTTPRequestError('Error while looking for handover token: {} - {}:{}'.format(
            handover_token, e.error, e.info['error']['reason']), 404)


@app.route('/jobs/stop/<string:handover_token>', methods=['GET'])
def stop_handover(handover_token=None):
    """
    Endpoint to delete all the reports linked to a handover_token
    This is using docstring for specifications
    ---
    tags:
      - handovers
    parameters:
      - name: handover_token
        in: path
        type: string
        required: true
        default: 15ce20fd-68cd-11e8-8117-005056ab00f0
        description: handover token for the database handed over
    operationId: handovers
    consumes:
      - application/json
    produces:
      - application/json
    security:
      delete_auth:
        - 'write:delete'
        - 'read:delete'
    schemes: ['http', 'https']
    deprecated: false
    externalDocs:
      description: Project repository
      url: http://github.com/rochacbruno/flasgger
    definitions:
      handover_token:
        type: object
        properties:
          handover_token:
            type: integer
            items:
              $ref: '#/definitions/handover_token'
      id:
        type: integer
        properties:
          id:
            type: integer
            items:
              $ref: '#/definitions/id'
    responses:
      200:
        description: handover_token of the reports that need deleting
        schema:
          $ref: '#/definitions/handover_token'
        examples:
          id: 15ce20fd-68cd-11e8-8117-005056ab00f0
    """
    try:

        handover_token = request.args.get('handover_token', handover_token)
        if handover_token is None:
            raise ValueError('required handover_token')

        status = stop_handover_job(handover_token)
        return status

    except NotFoundError as e:
        raise HTTPRequestError('Error while looking for handover token: {} - {}:{}'.format(
            handover_token, e.error, e.info['error']['reason']), 404)


@app.route('/jobs/restart', methods=['GET'])
def restart_handover():
    """
    Endpoint to restart specific handover task
    This is using docstring for specifications
    ---
    tags:
      - handovers
    parameters:
      - name: handover_token
        in: path
        type: string
        required: true
        default: 15ce20fd-68cd-11e8-8117-005056ab00f0
        description: handover token for the database handed over
      - name: task_name
        in: path
        type: string
        required: true
        default: datacheck
        description: handover task name to restart the job
    operationId: handovers
    consumes:
      - application/json
    produces:
      - application/json
    security:
      delete_auth:
        - 'write:delete'
        - 'read:delete'
    schemes: ['http', 'https']
    deprecated: false
    externalDocs:
      description: Project repository
      url: http://github.com/rochacbruno/flasgger
    definitions:
      handover_token:
        type: object
        properties:
          handover_token:
            type: integer
            items:
              $ref: '#/definitions/handover_token'
      id:
        type: integer
        properties:
          id:
            type: integer
            items:
              $ref: '#/definitions/id'
    responses:
      200:
        description: handover_token with restart status
        schema:
          $ref: '#/definitions/handover_token'
        examples:
          id: 15ce20fd-68cd-11e8-8117-005056ab00f0
    """
    try:

        handover_token = request.args.get('handover_token', None)
        task_name = request.args.get('task_name', None)

        if handover_token is None or task_name is None:
            raise ValueError('request arguments handover_token and task_name are required')

        if task_name not in app.config.get('ALLOWED_TASK_RESTART', []):
            raise ValueError('request arguments task_name is not in ALLOWED_TASK_RESTART')

        res = restart_handover_job(handover_token, task_name)

        if not res['status']:
            raise ValueError(res['error'])

        return jsonify(res)

    except Exception as e:
        return jsonify(error=str(e)), 400


@app.errorhandler(TransportError)
def handle_elastisearch_error(e):
    app.logger.error(str(e))
    message = 'Elasticsearch Error [%s] %s: %s' % (e.status_code, e.error, e)
    return jsonify(error=message), e.status_code


@app.errorhandler(HTTPRequestError)
def handle_bad_request_error(e):
    app.logger.error(str(e))
    return jsonify(error=str(e)), e.status_code


@app.errorhandler(OperationalError)
def handle_sqlalchemy_error(e):
    app.logger.error(str(e))
    return jsonify(error=str(e)), 500


@app.errorhandler(404)
def handle_notfound_error(e):
    app.logger.error(str(e))
    return jsonify(error=str(e)), 404


@app.errorhandler(requests.exceptions.HTTPError)
def handle_server_error(e):
    return jsonify(error=str(e)), 500


@app.errorhandler(ensembl.production.handover.exceptions.MissingDispatchException)
def handle_server_error(e):
    message = f"Missing Handover db dispatch configuration for {app.config['RELEASE']} {e}"
    return jsonify(error=message), 500
