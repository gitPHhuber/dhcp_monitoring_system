from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField  # Добавили SelectField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from .models import User

class LoginForm(FlaskForm):
      # ... (без изменений) ...
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
      # ... (без изменений) ...
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('admin', 'Administrator'), ('tester', 'Tester')], validators=[DataRequired()])
    first_name = StringField('First Name', validators=[DataRequired()])  # Добавили
    last_name = StringField('Last Name', validators=[DataRequired()])   # Добавили
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

class ServerConfigForm(FlaskForm):
    dhcp_server_ip = StringField('DHCP Server IP', validators=[DataRequired()])
    connection_type = SelectField('Connection Type', choices=[('file', 'Local File'), ('ssh', 'SSH')], validators=[DataRequired()])  # Добавили выбор
    ssh_username = StringField('SSH Username')  # Добавили
    ssh_password = PasswordField('SSH Password')  # Добавили
    ssh_key_path = StringField('SSH Key Path')    # Добавили
    submit = SubmitField('Save')