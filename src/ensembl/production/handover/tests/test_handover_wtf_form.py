import unittest
from flask import Flask, render_template, jsonify, Request, request
from werkzeug.test import EnvironBuilder
from ensembl.production.handover.forms import HandoverSubmissionForm

valid_payload ={
                'src_uri':'mysql://ensro@mysql-ens-sta-1:4512/' ,
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

            if form.validate_on_submit():
                return {'valid': True}

            return {'Valid': False}

        return app

    def request(self,*args, **kwargs):
        return self.app.test_request_context(*args, **kwargs)

class TestValidateOnSubmit(TestHandoverForm):
    def test_not_submitted(self):
        with self.request(method='GET', data={}):
            f = HandoverSubmissionForm(request.form, csrf_enabled=False)
            self.assertEqual(f.is_submitted(), False)
            self.assertEqual(f.validate_on_submit(), False)

    def test_submitted_not_valid(self):
        with self.request(method='POST', data={}):
            f = HandoverSubmissionForm(request.form, csrf_enabled=False)
            self.assertEqual(f.is_submitted(), True)
            self.assertEqual(f.validate(), False)

    def test_submitted_and_valid(self):
        with self.request(method='POST', data=valid_payload):
            print(request.form)
            f = HandoverSubmissionForm(request.form, csrf_enabled=False)
            self.assertEqual(f.validate_on_submit(), True)



class TestCSRF(TestHandoverForm):
    def test_csrf_token(self):
        with self.request(method='GET'):
            f = HandoverSubmissionForm(request.form)
            self.assertEqual(hasattr(f, 'csrf_token'), True)
            self.assertEqual(f.validate(), False)

    def test_invalid_csrf(self):
        with self.request(method='POST', data=valid_payload):
            f = HandoverSubmissionForm()
            self.assertEqual(f.validate_on_submit(), False)
            self.assertEqual(f.errors['csrf_token'], [u'The CSRF token is missing.'])


    def test_valid(self):
        csrf_token = HandoverSubmissionForm().csrf_token.current_token
        builder = EnvironBuilder(method='POST', data={**valid_payload, 'csrf_token': csrf_token })
        env = builder.get_environ()
        req = Request(env)
        f = HandoverSubmissionForm(req.form)
        self.assertTrue(f.validate())

    def test_form(self):
        response = self.client.post("/formvalidate/",
                                    data=valid_payload,
                                )
        assert response.status_code == 200
         

