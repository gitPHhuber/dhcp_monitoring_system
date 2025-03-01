import re
import asyncio
from datetime import datetime
from typing import List, Dict, Tuple
from .models import Lease, db, LeaseStatus  # LeaseStatus нужен!
from .extensions import celery
from .config import Config
import aioping
from asyncio import TimeoutError  # Явный импорт TimeoutError
import paramiko
import io
import logging

#  Настройка логгера для utils.py
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  #  Или DEBUG для отладки

async def ping_host(ip: str, timeout: float = Config.PING_TIMEOUT) -> bool:
    """Асинхронная проверка доступности хоста."""
    try:
        delay = await aioping.ping(ip, timeout=timeout)
        return True  # Пинг успешен
    except (TimeoutError, OSError):  #  <--  Исправлено: убрали aioping.errors.PingError
        return False  # Пинг не прошел


def parse_dhcp_leases(leases_file: str, dhcp_server_ip:str) -> List[Dict]:
    """
    Парсинг файла dhcpd.leases (для ISC DHCP).  Обрабатывает и путь к файлу (str), и StringIO.
    """
    leases = []
    file_obj = None  #  Добавлено для корректного finally
    try:
        if isinstance(leases_file, str):
            try:
                file_obj = open(leases_file, 'r')
            except FileNotFoundError:
                logger.error(f"Leases file not found: {leases_file}")  #  Логирование!
                return []
            except OSError as e:  #  Более конкретная ошибка
                logger.error(f"Error opening leases file {leases_file}: {e}")
                return []
        else:
            file_obj = leases_file

        with file_obj as f:
            current_lease = {}
            for line in f:
                line = line.strip()
                if line.startswith('lease'):
                    if current_lease:
                        leases.append(current_lease)
                    current_lease = {'ip': line.split()[1]}
                elif line.startswith('hardware ethernet'):
                    current_lease['mac'] = line.split()[2].rstrip(';')
                elif line.startswith('starts'):
                    parts = line.split()
                    date_str = f"{parts[2]} {parts[3].rstrip(';')}"
                    current_lease['starts'] = datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
                elif line.startswith('ends'):
                    parts = line.split()
                    date_str = f"{parts[2]} {parts[3].rstrip(';')}"
                    current_lease['ends'] = datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
                elif line.startswith('binding state'):
                    #  <--  ПРЕОБРАЗУЕМ В ВЕРХНИЙ РЕГИСТР -->
                    current_lease['binding_state'] = line.split()[2].rstrip(';').upper()
                elif line.startswith('client-hostname'):
                    current_lease['hostname'] = line.split()[1].strip('"').rstrip(';')
                elif line.startswith('uid'):
                    current_lease['uid'] = line.split()[1].strip('"').rstrip(';')
            if current_lease:
                leases.append(current_lease)

    except Exception as e:
        logger.exception(f"Error parsing leases file: {e}")  #  Более подробный лог
        return []
    finally:
        if isinstance(leases_file, str) and file_obj is not None: #  Добавили проверку file_obj
            file_obj.close()

    return leases


def parse_dhcp_conf_for_ip(conf_file: str) -> str | None:
    """Парсит файл dhcpd.conf и возвращает IP-адрес сервера (если найден)."""
    try:
        with open(conf_file, 'r') as f:
            for line in f:
                if line.strip().startswith('server-identifier'):
                    return line.split()[1].rstrip(';')
    except FileNotFoundError:
        logger.error(f"Config file not found: {conf_file}")  #  Логирование
        return None
    except Exception as e:
        logger.exception(f"Error parsing config file: {e}")  #  Более подробный лог
        return None
    return None


def get_leases_via_ssh(server_ip, username, password=None, key_path=None):
    """Подключается к серверу по SSH и читает файл dhcpd.leases."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if key_path:
            key = paramiko.RSAKey.from_private_key_file(key_path)
            ssh.connect(server_ip, username=username, pkey=key)
        elif password:
            ssh.connect(server_ip, username=username, password=password)
        else:
            raise ValueError("Either password or key_path must be provided")

        stdin, stdout, stderr = ssh.exec_command('cat /var/lib/dhcp/dhcpd.leases')  #  <--  ПУТЬ!
        leases_content = stdout.read().decode('utf-8')
        ssh.close()
        return parse_dhcp_leases(io.StringIO(leases_content), server_ip)

    except paramiko.AuthenticationException as e:
        logger.error(f"Authentication failed to {server_ip}: {e}")  #  Логирование!
        flash(f"Authentication failed to {server_ip}", "error")  #  Сообщение пользователю
        return []
    except paramiko.SSHException as e:
        logger.error(f"SSH error connecting to {server_ip}: {e}") #  Логирование!
        flash(f"SSH error: {e}", "error") # Сообщение
        return []
    except Exception as e:
        logger.exception(f"Error connecting to {server_ip} via SSH: {e}")  #  Более подробный лог
        return []