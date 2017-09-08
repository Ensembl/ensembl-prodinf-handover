#!/usr/bin/env python
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, text
from ensembl_prodinf import HiveInstance
from ensembl_prodinf.tasks import email_when_complete
import json
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = Flask(__name__, instance_relative_config=True)
print app.config
app.config.from_object('hc_config')
app.config.from_pyfile('hc_config.py')
app.analysis = app.config["HIVE_ANALYSIS"]

hive = None
def get_hive():
    global hive
    if hive == None:
        hive = HiveInstance(app.config["HIVE_URI"])
    return hive

cors = CORS(app)

# use re to support different charsets
json_pattern = re.compile("application/json")

@app.route('/submit', methods=['POST'])
def submit():
    if json_pattern.match(request.headers['Content-Type']):
        logging.debug("Submitting HC "+str(request.json))
        job = get_hive().create_job(app.analysis, request.json)
        results = {"job_id":job.job_id};
        email =  request.json.get('email')
        if email != None and email != '':
            logging.debug("Submitting email request for  "+email)
            email_results = email_when_complete.delay(request.url_root+"results_email/"+str(job.job_id),email)
            results['email_task'] = email_results.id
        return jsonify(results);
    else:
        return "Could not handle input of type "+request.headers['Content-Type'], 415


@app.route('/results/<int:job_id>', methods=['GET'])
def results(job_id):
    try:
        logging.info("Retrieving job with ID "+str(job_id))
        return jsonify(get_hive().get_result_for_job_id(job_id))
    except ValueError:
        return "Job "+str(job_id)+" not found", 404

@app.route('/results_email/<int:job_id>', methods=['GET'])
def results_email(job_id):
    try:
        email = request.args.get('email')
        logging.info("Retrieving job with ID "+str(job_id)+" for "+str(email))
        results = get_hive().get_result_for_job_id(job_id)
        if results['status'] == 'complete':
            results['subject'] = 'Healthchecks for %s - %s' % (results['output']['db_name'], results['output']['status'])
            results['body'] = "Results for %s:\n" % (results['output']['db_uri'])
            for (test,result) in results['output']['results'].iteritems():
                results['body'] += "* %s : %s\n" % (test, result['status'])
                if result['messages'] != None:
                    for msg in result['messages']:
                        results['body'] += "** %s\n" % (msg)
        elif results['status'] == 'failed':
            results['subject'] = 'Healthcheck job failed'
            results['body'] = 'HC job failed. Boo.'
        results['output'] = None
        return jsonify(results)
    except ValueError:
        return "Job "+str(job_id)+" not found", 404

