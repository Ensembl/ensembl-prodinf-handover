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

from wtforms import Form, FormField, StringField, SubmitField, HiddenField
from wtforms.validators import Email, InputRequired, ValidationError, Regexp
from flask_wtf import FlaskForm

class HandoverSubmissionForm(FlaskForm):
    #handover = FormField(HandoverForm, description='Handover')
    src_uri = StringField('Database server uri: ', validators=[InputRequired(), 
                             Regexp('mysql://[\w]+@[\w-]+:\d{4}', message="Server URI should follow this pattern  mysql://user(:pass)@server:port/ ")], 
                             render_kw={"placeholder": "Enter Server URI, e.g: mysql://ensro@mysql-ens-general-dev-1:4484/"})

    database = StringField('Database: ', validators=[InputRequired()],
                            render_kw={"placeholder": "eg: homo_sapiens_core_104_38"})

    contact = StringField('Email', validators=[Email(), InputRequired()], 
                            render_kw={"placeholder": "eg: username@ebi.ac.uk"})

    comment = StringField('Description', validators=[InputRequired()], 
                            render_kw={"placeholder": "eg: handover human core db release 104 "})

    source = HiddenField("source", default='Handover')

    submit = SubmitField('Submit')