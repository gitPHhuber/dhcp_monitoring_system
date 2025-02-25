import os
from dotenv import load_dotenv

load_dotenv()  # Загрузка переменных окружения из .env

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'  # Обязательно сменить в .env!
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    DHCP_SERVER_IP = os.environ.get('DHCP_SERVER_IP') or '127.0.0.1' # IP адрес DHCP-сервера по умолчанию
    DHCP_LEASES_FILE = os.environ.get('DHCP_LEASES_FILE') or '/var/lib/dhcp/dhcpd.leases' #  Путь к dhcpd.leases (для ISC DHCP)
    DHCP_CONF_FILE = os.environ.get('DHCP_CONF_FILE') or '/etc/dhcp/dhcpd.conf' # Путь к dhcpd.conf
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['your-email@example.com'] # Email для уведомлений об ошибках
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
    PING_TIMEOUT = 2  # Таймаут пинга в секундах
    PING_INTERVAL = 60 # Интервал проверки доступности в секундах

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # In-memory база данных для тестов
    WTF_CSRF_ENABLED = False  # Отключение CSRF-защиты в тестах
    CELERY_TASK_ALWAYS_EAGER = True # Celery задачи выполняются синхронно


class ProductionConfig(Config):
     DEBUG = False
     #  Добавить настройки для production (например, PostgreSQL)

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
