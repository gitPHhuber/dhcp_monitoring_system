import asyncio
from .extensions import celery, db  # Добавили db
from .models import Lease, ServerConfig
from .utils import ping_host, parse_dhcp_leases, get_leases_via_ssh  # Добавили get_leases_via_ssh
from .config import Config
from . import create_app
from datetime import datetime
from redbeat import RedBeatSchedulerEntry

@celery.task
def check_lease_status(lease_id):
    # ... (без изменений) ...
    """Проверяет статус лиза (онлайн/оффлайн) и обновляет БД."""
    app = create_app()
    with app.app_context():
        lease = Lease.query.get(lease_id)
        if lease:
            is_online = asyncio.run(ping_host(lease.ip))  # Используем asyncio.run
            lease.is_online = is_online
            lease.last_check = datetime.utcnow()
            db.session.commit()
            print(f"Checked lease: {lease.ip}, online: {is_online}")

@celery.task(bind=True)
def update_leases_from_file(self):
    """Обновляет информацию о лизах, используя правильный метод."""
    app = create_app()
    with app.app_context():
        server_config = ServerConfig.query.first()
        if not server_config:
            return  # Не можем работать без настроек

        if server_config.connection_type == 'file':
            # Читаем из локального файла
            leases_data = parse_dhcp_leases(app.config['DHCP_LEASES_FILE'], server_config.dhcp_server_ip)
        elif server_config.connection_type == 'ssh':
            # Получаем данные по SSH
            leases_data = get_leases_via_ssh(
                server_config.dhcp_server_ip,
                server_config.ssh_username,
                server_config.ssh_password,  #  ВНИМАНИЕ!  Пароль!
                server_config.ssh_key_path
            )
        else:
            return  #  Или raise ValueError("Invalid connection type")

        # ... (остальной код обработки лизов - без изменений) ...
        #Счетчики для отчета
        updated_count = 0
        added_count = 0
        deleted_count = 0


        # 1. Обновляем существующие и добавляем новые
        for lease_data in leases_data:
            lease = Lease.query.filter_by(ip=lease_data['ip']).first()
            if lease:  # Лиз существует, обновляем
                lease.mac = lease_data.get('mac', lease.mac)
                lease.hostname = lease_data.get('hostname', lease.hostname)
                lease.starts = lease_data.get('starts', lease.starts)
                lease.ends = lease_data.get('ends', lease.ends)
                lease.binding_state = lease_data.get('binding_state', lease.binding_state)
                lease.uid = lease_data.get('uid', lease.uid)
                updated_count +=1

            else:  # Лиза нет, создаем новый
                lease = Lease(**lease_data)
                db.session.add(lease)
                added_count += 1

            # Сразу после обновления/добавления запускаем проверку статуса
            check_lease_status.delay(lease.id) # delay для асинхронности

        # 2. Удаляем устаревшие (которых нет в файле leases)
        all_ips_in_file = {lease_data['ip'] for lease_data in leases_data}
        for lease in Lease.query.all():
            if lease.ip not in all_ips_in_file:
              if lease.binding_state != 'free': #Удаляем только если не free
                db.session.delete(lease)
                deleted_count += 1
        db.session.commit()
        return f'Leases updated: {updated_count}, added: {added_count}, deleted: {deleted_count}'

# Добавляем задачу для периодической проверки статуса *всех* лизов
@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    app = create_app()
    with app.app_context():
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