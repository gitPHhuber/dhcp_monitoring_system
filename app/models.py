from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .extensions import db, login_manager
from enum import Enum

# Таблица для связи многие-ко-многим между User и Group
user_groups = db.Table('user_groups',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id'), primary_key=True)
)

# Таблица для связи многие-ко-многим между Group и Permission
group_permissions = db.Table('group_permissions',
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)

class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    permissions = db.relationship('Permission', secondary=group_permissions, lazy='subquery',
                                backref=db.backref('groups', lazy=True))
    def __repr__(self):
        return f'<Group {self.name}>'

class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)

    def __repr__(self):
        return f'<Permission {self.name}>'
#  Добавляем Enum для статусов ПЕРЕД Lease
class LeaseStatus(str, Enum):
    ACTIVE = 'active'
    IN_WORK = 'in_work'
    COMPLETED = 'completed'
    BROKEN = 'broken'
    PENDING = 'pending'

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
    status = db.Column(
        db.Enum(LeaseStatus),
        nullable=False,
        server_default=LeaseStatus.ACTIVE
    )
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'))
    status_history = db.relationship(
        'LeaseStatusHistory',
        backref='lease_obj',
        lazy='dynamic',
        order_by='desc(LeaseStatusHistory.timestamp)',
        overlaps="status_history,lease_obj"  #  <--  ДОБАВИТЬ overlaps
    )
    
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
            'status': self.status.value if self.status else None,
            'server_id': self.server_id
        }

class ServerConfig(db.Model):
    __tablename__ = 'server_config'
    id = db.Column(db.Integer, primary_key=True)
    dhcp_server_ip = db.Column(db.String(15), nullable=False)
    connection_type = db.Column(db.String(64), nullable=False, server_default='file')  # file or ssh
    ssh_username = db.Column(db.String(64))
    ssh_password = db.Column(db.String(128))
    ssh_key_path = db.Column(db.String(255))


    def __repr__(self):
        return f'<ServerConfig {self.dhcp_server_ip}>'

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    position = db.Column(db.String(64))
    department = db.Column(db.String(64))
    contact_info = db.Column(db.String(128))

    def __repr__(self):
        return f'<Employee {self.first_name} {self.last_name}>'

class Server(db.Model):
    __tablename__ = 'servers'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), unique=True, index=True)
    ip_address = db.Column(db.String(15), unique=True, index=True)
    mac_address = db.Column(db.String(17), index=True)
    inventory_number = db.Column(db.String(64), unique=True)
    model = db.Column(db.String(64))
    os = db.Column(db.String(64))
    location = db.Column(db.String(128))
    description = db.Column(db.Text)
    leases = db.relationship('Lease', backref='server', lazy='dynamic')

    def __repr__(self):
        return f'<Server {self.hostname or self.ip_address}>'

class Metric(db.Model):
    __tablename__ = 'metrics'
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    metric_type = db.Column(db.String(64), nullable=False)  #  CPU, RAM, disk, ping, ...
    value = db.Column(db.Float, nullable=False)
    server = db.relationship('Server', backref=db.backref('metrics', lazy=True))

    def __repr__(self):
        return f'<Metric {self.server.hostname}:{self.metric_type}@{self.timestamp}>'

class LeaseStatusHistory(db.Model):
    __tablename__ = 'lease_status_history'
    id = db.Column(db.Integer, primary_key=True)
    lease_id = db.Column(db.Integer, db.ForeignKey('leases.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Может быть NULL, если статус изменился автоматически
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    old_status = db.Column(db.Enum(LeaseStatus), nullable=False)  # Используем LeaseStatus
    new_status = db.Column(db.Enum(LeaseStatus), nullable=False)
    comment = db.Column(db.Text)  # Необязательное поле для комментария

    lease = db.relationship('Lease', backref=db.backref('history_entries', lazy='dynamic', order_by='desc(LeaseStatusHistory.timestamp)'))
    user = db.relationship('User', backref=db.backref('status_changes', lazy='dynamic'))

    def __repr__(self):
        return f'<LeaseStatusHistory {self.lease_id} {self.timestamp} {self.old_status}->{self.new_status}>'


class Journal(db.Model):
    __tablename__ = 'journal'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(128))
    details = db.Column(db.Text)
    user = db.relationship('User', back_populates='journal_entries')

    def __repr__(self):
        return f'<JournalEntry {self.timestamp} - {self.user.username} - {self.action}>'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(64), nullable=False, default='tester')  # 'admin', 'tester'
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    leases = db.relationship('Lease', backref='taken_user', lazy='dynamic', foreign_keys='Lease.taken_by_id')
    groups = db.relationship('Group', secondary=user_groups, lazy='subquery',
                            backref=db.backref('users', lazy=True)) # Связь с группами
    journal_entries = db.relationship('Journal', back_populates='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_online(self):
        # Считаем пользователя онлайн, если он был активен в последние 5 минут (можно настроить)
        if self.last_seen is None:
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

    def has_permission(self, permission_name):
        """Проверяет, есть ли у пользователя разрешение (напрямую или через группу)."""
        # Проверяем, есть ли разрешение напрямую у пользователя (менее вероятно, но возможно)
        # for perm in self.permissions:  #  Если бы была прямая связь с Permission
        #     if perm.name == permission_name:
        #         return True

        # Проверяем, есть ли разрешение у какой-либо из групп пользователя
        for group in self.groups:
            for perm in group.permissions:
                if perm.name == permission_name:
                    return True
        return False

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Создаем запись с настройками по умолчанию, если ее нет.
def initialize_server_config(app):
    with app.app_context():
        if not ServerConfig.query.first():
            default_config = ServerConfig(dhcp_server_ip=app.config['DHCP_SERVER_IP'], connection_type = app.config.get('CONNECTION_TYPE', 'file'))
            db.session.add(default_config)
            db.session.commit()