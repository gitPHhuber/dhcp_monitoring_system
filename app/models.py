from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .extensions import db, login_manager


class User(UserMixin, db.Model):
    # ... (без изменений) ...
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(64), nullable=False, default='tester')  # 'admin', 'tester'
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    leases = db.relationship('Lease', backref='taken_user', lazy='dynamic', foreign_keys='Lease.taken_by_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_online(self):
        # Считаем пользователя онлайн, если он был активен в последние 5 минут (можно настроить)
        if self.last_seen is None:  # Добавили проверку на None
            return False
        return self.last_seen > datetime.utcnow() - timedelta(minutes=5)

    def as_dict(self):
        """Сериализация объекта User в словарь."""
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_online': self.is_online()
        }
    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Lease(db.Model):
    __tablename__ = 'leases'
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(15), unique=True, index=True, nullable=False)
    mac = db.Column(db.String(17), index=True, nullable=False)
    hostname = db.Column(db.String(255), index=True)
    starts = db.Column(db.DateTime)
    ends = db.Column(db.DateTime)
    binding_state = db.Column(db.String(64), index=True, nullable=False)
    uid = db.Column(db.String(255))
    is_online = db.Column(db.Boolean, default=False)
    last_check = db.Column(db.DateTime)
    in_work = db.Column(db.Boolean, default=False)
    taken_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    status = db.Column(db.String(64), default='active')  # Добавили: active, in_work, completed, broken, pending

    def __repr__(self):
        return f'<Lease {self.ip}>'

    def as_dict(self):
        """Сериализация объекта Lease в словарь (для API)."""
        return {
            'id': self.id,
            'ip': self.ip,
            'mac': self.mac,
            'hostname': self.hostname,
            'starts': self.starts.isoformat() if self.starts else None,
            'ends': self.ends.isoformat() if self.ends else None,
            'binding_state': self.binding_state,
            'uid': self.uid,
            'is_online': self.is_online,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'in_work': self.in_work,
            'taken_by': self.taken_user.username if self.taken_user else None,
            'status': self.status  # Добавили
        }

class ServerConfig(db.Model):
    # ... (без изменений) ...
    __tablename__ = 'server_config'
    id = db.Column(db.Integer, primary_key=True)
    dhcp_server_ip = db.Column(db.String(15), nullable=False)
    connection_type = db.Column(db.String(64), nullable=False, server_default='file')  # Добавили, 'file' или 'ssh'
    ssh_username = db.Column(db.String(64))  # Добавили
    ssh_password = db.Column(db.String(128)) # Добавили
    ssh_key_path = db.Column(db.String(255))  # Добавили

    def __repr__(self):
      return f'<ServerConfig {self.dhcp_server_ip}>'

# Создаем запись с настройками по умолчанию, если ее нет.
def initialize_server_config(app):
    with app.app_context():
        if not ServerConfig.query.first():
            default_config = ServerConfig(dhcp_server_ip=app.config['DHCP_SERVER_IP'], connection_type = app.config['CONNECTION_TYPE'])
            db.session.add(default_config)
            db.session.commit()