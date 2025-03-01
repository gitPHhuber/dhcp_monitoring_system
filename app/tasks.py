import asyncio
from .extensions import celery, db
from .models import Lease, ServerConfig, LeaseStatus
from .utils import ping_host, parse_dhcp_leases, get_leases_via_ssh
from .config import Config
from . import create_app
from datetime import datetime
from .journal import record_action

@celery.task
def check_lease_status(lease_id):
    """Проверяет статус лиза (онлайн/оффлайн) и обновляет БД."""
    app = create_app()  #  <--  УБРАТЬ, когда перейдёте на ContextTask
    with app.app_context():  #  <--  УБРАТЬ, когда перейдёте на ContextTask
        lease = Lease.query.get(lease_id)
        if lease:
            is_online = asyncio.run(ping_host(lease.ip))
            lease.is_online = is_online
            lease.last_check = datetime.utcnow()
            db.session.commit()
            print(f"Checked lease: {lease.ip}, online: {is_online}")

@celery.task(bind=True)
def update_leases_from_file(self):
    """Обновляет информацию о лизах, используя правильный метод."""
    app = create_app()   #  <--  УБРАТЬ, когда перейдёте на ContextTask
    with app.app_context():  #  <--  УБРАТЬ, когда перейдёте на ContextTask
        server_config = ServerConfig.query.first()
        if not server_config:
            return

        if server_config.connection_type == 'file':
            leases_data = parse_dhcp_leases(app.config['DHCP_LEASES_FILE'], server_config.dhcp_server_ip)
        elif server_config.connection_type == 'ssh':
            leases_data = get_leases_via_ssh(
                server_config.dhcp_server_ip,
                server_config.ssh_username,
                server_config.ssh_password,
                server_config.ssh_key_path
            )
        else:
            return

        updated_count = 0
        added_count = 0
        deleted_count = 0

        for lease_data in leases_data:
            lease = Lease.query.filter_by(ip=lease_data['ip']).first()
            if lease:
                lease.mac = lease_data.get('mac', lease.mac)
                lease.hostname = lease_data.get('hostname', lease.hostname)
                lease.starts = lease_data.get('starts', lease.starts)
                lease.ends = lease_data.get('ends', lease.ends)
                lease.binding_state = lease_data.get('binding_state', lease.binding_state)
                lease.uid = lease_data.get('uid', lease.uid)
                updated_count += 1
            else:
                lease = Lease(**lease_data)
                lease.status = LeaseStatus.ACTIVE  # <-- ДОБАВЛЕНО!  Устанавливаем статус при создании.
                db.session.add(lease)
                added_count += 1

            check_lease_status.delay(lease.id)

        all_ips_in_file = {lease_data['ip'] for lease_data in leases_data}
        for lease in Lease.query.all():
            if lease.ip not in all_ips_in_file:
                 if lease.binding_state.lower() not in ['free','abandoned', 'expired']: #Удаляем, если binding_state не free, abandoned, expired
                    db.session.delete(lease)
                    deleted_count += 1
        db.session.commit()
        return f'Leases updated: {updated_count}, added: {added_count}, deleted: {deleted_count}'


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    #  ПРАВИЛЬНАЯ РЕАЛИЗАЦИЯ setup_periodic_tasks (без RedBeatSchedulerEntry)
    app = create_app()  # <--  УБРАТЬ, когда перейдёте на ContextTask
    with app.app_context():  # <--  УБРАТЬ, когда перейдёте на ContextTask
        # Удаляем все предыдущие задачи, чтобы избежать дублирования
        sender.conf.beat_schedule = {}

        # Получаем все лизы
        all_leases = Lease.query.all()

        for lease in all_leases:
            # Добавляем задачу для каждого лиза в расписание
            sender.add_periodic_task(
                app.config['PING_INTERVAL'],  # Интервал (из конфига)
                check_lease_status.s(lease.id),  # Задача и ее аргумент (ID лиза)
                name=f'check-lease-{lease.id}',  # Уникальное имя задачи
            )