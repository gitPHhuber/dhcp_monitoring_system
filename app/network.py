from flask import Blueprint, render_template, jsonify
from .models import Server
from .extensions import db

# Определяем blueprint с именем "network"
network = Blueprint('network', __name__)

@network.route('/network_map')
def network_map():
    """Отображает страницу с картой сети."""
    return render_template('network_map.html')

@network.route('/network_map/data')
def network_map_data():
    """
    Генерирует JSON с данными для карты сети.
    Узлы: каждый сервер из базы.
    Рёбра: формируются циклически, соединяя серверы последовательно.
    """
    servers = Server.query.all()
    nodes = []
    edges = []
    
    # Формируем узлы
    for server in servers:
        nodes.append({
            "data": {
                "id": f"server{server.id}",
                "label": f"{server.hostname or server.ip_address}",
                "ip": server.ip_address
            }
        })
    
    # Формируем рёбра, если серверов больше одного
    n = len(servers)
    if n > 1:
        for i in range(n):
            source_id = f"server{servers[i].id}"
            target_id = f"server{servers[(i + 1) % n].id}"  # циклическое соединение
            edges.append({
                "data": {
                    "source": source_id,
                    "target": target_id,
                    "label": "connection"
                }
            })
    
    return jsonify({"nodes": nodes, "edges": edges})
