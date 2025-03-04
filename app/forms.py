from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from .models import User

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('admin', 'Administrator'), ('tester', 'Tester')], validators=[DataRequired()])
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

class ServerConfigForm(FlaskForm):
    dhcp_server_ip = StringField('DHCP Server IP', validators=[DataRequired()])
    connection_type = SelectField('Connection Type', choices=[('file', 'Local File'), ('ssh', 'SSH')], validators=[DataRequired()])
    ssh_username = StringField('SSH Username')
    ssh_password = PasswordField('SSH Password')
    ssh_key_path = StringField('SSH Key Path')
    submit = SubmitField('Save')

class PlaybookForm(FlaskForm):  # <-- ВОТ ЭТОТ КЛАСС!
    name = StringField('Name', validators=[DataRequired()])
    description = StringField('Description')
    content = TextAreaField('Content', validators=[DataRequired()])
    submit = SubmitField('Save')