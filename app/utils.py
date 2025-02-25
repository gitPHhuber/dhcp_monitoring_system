import asyncio
from datetime import datetime
from typing import List, Dict, Tuple
from .models import Lease, db
from .extensions import celery
from .config import Config
import aioping
# from asyncio import TimeoutError  #  Уже не нужно, т.к. есть общий TimeoutError


async def ping_host(ip: str, timeout: float = Config.PING_TIMEOUT) -> bool:
    """Асинхронная проверка доступности хоста."""
    try:
        delay = await aioping.ping(ip, timeout=timeout)
        return True  # Пинг успешен
    except asyncio.TimeoutError:  #  Используем asyncio.TimeoutError
        return False  # Пинг не прошел (таймаут)
    except OSError:  #  Перехватываем OSError (например, "Network is unreachable")
        return False
    #  aioping.errors.PingError больше не нужен


def parse_dhcp_leases(leases_file: str, dhcp_server_ip:str) -> List[Dict]:
    """
    Парсинг файла dhcpd.leases (для ISC DHCP).

    Args:
        leases_file: Путь к файлу dhcpd.leases.

    Returns:
        Список словарей с информацией о лизах.
    """
    leases = []
     # leases_file может быть путем к файлу (str) или объектом StringIO
    if isinstance(leases_file, str):
        try:
            file_obj = open(leases_file, 'r')
        except FileNotFoundError:
            print(f"Error: Leases file not found: {leases_file}")
            return []
        except Exception as e:
            print(f"Error opening leases file: {e}")
            return []
    else:  # StringIO
         file_obj = leases_file

    try:
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
                    #  "starts 1 2024/03/16 08:35:13;"
                    parts = line.split()
                    date_str = f"{parts[2]} {parts[3].rstrip(';')}"
                    current_lease['starts'] = datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
                elif line.startswith('ends'):
                    parts = line.split()
                    date_str = f"{parts[2]} {parts[3].rstrip(';')}"
                    current_lease['ends'] = datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
                elif line.startswith('binding state'):
                    current_lease['binding_state'] = line.split()[2].rstrip(';')
                elif line.startswith('client-hostname'):
                    current_lease['hostname'] = line.split()[1].strip('"').rstrip(';')
                elif line.startswith('uid'):
                    current_lease['uid'] = line.split()[1].strip('"').rstrip(';')
            if current_lease:  #  Последний лиз
                leases.append(current_lease)
    except Exception as e:
        print(f"Error parsing leases file: {e}")
        return []
    finally:
        if isinstance(leases_file, str):  # Закрываем файл, только если это был путь
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
        print(f"Error: Config file not found: {conf_file}")
        return None
    except Exception as e:
         print(f"Error parsing config file: {e}")
         return None
    return None

def get_leases_via_ssh(server_ip, username, password=None, key_path=None):
    """Подключается к серверу по SSH и читает файл dhcpd.leases."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if key_path:
            key = paramiko.RSAKey.from_private_key_file(key_path)
            ssh.connect(server_ip, username=username, pkey=key)  #  Используем pkey
        elif password:
            ssh.connect(server_ip, username=username, password=password)
        else:
            raise ValueError("Either password or key_path must be provided")

        # Выполняем команду для чтения файла
        stdin, stdout, stderr = ssh.exec_command('cat /var/lib/dhcp/dhcpd.leases')  # Путь к файлу!
        leases_content = stdout.read().decode('utf-8')
        ssh.close()

        # Используем StringIO, чтобы parse_dhcp_leases мог работать со строкой, как с файлом
        return parse_dhcp_leases(io.StringIO(leases_content), server_ip)

    except paramiko.AuthenticationException:
        print(f"Authentication failed to {server_ip}")
        return []  #  Или другое действие по умолчанию
    except paramiko.SSHException as e:
        print(f"SSH error: {e}")
        return []
    except Exception as e:
        print(f"Error connecting via SSH: {e}")
        return []