from wtforms import Form, FormField, StringField, SubmitField, HiddenField
from wtforms.validators import Email, InputRequired, ValidationError, Regexp


class HandoverSubmissionForm(Form):
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