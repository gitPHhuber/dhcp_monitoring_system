from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from celery import Celery
import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
import os
from .journal import journal_bp  #  Импортируем blueprint
from .journal import journal_bp as journal_blueprint


from .extensions import db, login_manager, csrf, mail, celery
from .config import config

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  #  Указываем, какой view отвечает за логин
    login_manager.login_message_category = 'info'
    csrf.init_app(app)
    mail.init_app(app)
    init_celery(app)


    # Регистрация blueprints (разделение приложения на модули)
    from .views import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')

    # Отключаем CSRF для API-блюпринта, используя метод exempt экземпляра csrf
    csrf.exempt(api_blueprint)

    from .auth import auth as auth_blueprint  # Blueprint для аутентификации
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .server_management import server_management as server_management_blueprint #Добавлено
    app.register_blueprint(server_management_blueprint) #Добавлено

    from .server_monitoring import server_monitoring as server_monitoring_blueprint #Добавлено
    app.register_blueprint(server_monitoring_blueprint) #Добавлено

    from .users import users as users_blueprint  # Добавили
    app.register_blueprint(users_blueprint)      # Добавили

    from .journal import journal_bp as journal_blueprint  #  Добавили
    app.register_blueprint(journal_blueprint)            #  Добавили

    #Настройка журналирования
    if not app.debug and not app.testing:
        if app.config['MAIL_SERVER']:
            auth = None
            if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
                auth = (app.config['MAIL_USERNAME'],
                        app.config['MAIL_PASSWORD'])
            secure = None
            if app.config['MAIL_USE_TLS']:
                secure = ()
            mail_handler = SMTPHandler(
                mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
                fromaddr='no-reply@' + app.config['MAIL_SERVER'],
                toaddrs=app.config['ADMINS'], subject='DHCP Monitoring Failure',
                credentials=auth, secure=secure)
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)
        if app.config['LOG_TO_STDOUT']:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)
        else:
            if not os.path.exists('logs'):
                os.mkdir('logs')
            file_handler = RotatingFileHandler('logs/dhcp_monitoring.log',
                                                maxBytes=10240, backupCount=10)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s '
                '[in %(pathname)s:%(lineno)d]'))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('DHCP Monitoring startup')

    return app

def init_celery(app=None):
    app = app or create_app()
    celery.conf.broker_url = app.config['CELERY_BROKER_URL']
    celery.conf.result_backend = app.config['CELERY_RESULT_BACKEND']
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context"""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery