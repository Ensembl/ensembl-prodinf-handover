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

import unittest
from flask import Flask, render_template, jsonify, Request, request
from werkzeug.test import EnvironBuilder
from ensembl.production.handover.forms import HandoverSubmissionForm

valid_payload ={
                'src_uri':'mysql://ensro@mysql:4123/' ,
                'database': 'homo_sapiens_core_104_38',
                'contact': 'production@ebi.ac.uk',
                'comment': 'Testcase for handover form',
                'source': 'Handover',
                }

class TestHandoverForm(unittest.TestCase):
    def setUp(self):
        self.app = self.create_app()
        self.client = self.app.test_client()
        self.ctx = self.app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def create_app(self):
        app = Flask(__name__)
        app.secret_key = "EnsemblHandoverFormValidate"

        @app.route("/formvalidate/", methods=("POST",))
        def form_submit():
            form = HandoverSubmissionForm(csrf_enabled=False)

            if form.validate():
                return {'valid': True}

            return {'Valid': False}

        return app

    def request(self,*args, **kwargs):
        return self.app.test_request_context(*args, **kwargs)

class TestValidateOnSubmit(TestHandoverForm):
    def test_not_submitted(self):
        with self.request(method='GET', data={}):
            f = HandoverSubmissionForm(request.form, csrf_enabled=False)
            self.assertEqual(f.validate(), False)

    def test_submitted_not_valid(self):
        with self.request(method='POST', data={}):
            f = HandoverSubmissionForm(request.form, csrf_enabled=False)
            self.assertEqual(f.validate(), False)

    def test_submitted_and_valid(self):
        with self.request(method='POST', data=valid_payload):
            print(request.form)
            f = HandoverSubmissionForm(request.form, csrf_enabled=False)
            self.assertEqual(f.validate(), True)



class TestCSRF(TestHandoverForm):
    def test_csrf_token(self):
        with self.request(method='GET'):
            f = HandoverSubmissionForm(request.form)
            self.assertEqual(hasattr(f, 'csrf_token'), False)
            self.assertEqual(f.validate(), False)

    def test_invalid_csrf(self):
        with self.request(method='POST', data=valid_payload):
            f = HandoverSubmissionForm()
            self.assertEqual(f.validate(), False)


    def test_valid(self):
        builder = EnvironBuilder(method='POST', data={**valid_payload})
        env = builder.get_environ()
        req = Request(env)
        f = HandoverSubmissionForm(req.form)
        self.assertTrue(f.validate())

    def test_form(self):
        response = self.client.post("/formvalidate/",
                                    data=valid_payload,
                                )
        assert response.status_code == 200
         

