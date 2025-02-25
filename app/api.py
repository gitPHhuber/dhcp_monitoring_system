from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from .models import Lease
from .extensions import db
from .utils import parse_dhcp_leases
from . import tasks

api = Blueprint('api', __name__)

@api.route('/leases', methods=['GET'])
@login_required
def get_leases():
    leases = Lease.query.all()
    return jsonify([lease.as_dict() for lease in leases])

@api.route('/leases/<int:lease_id>', methods=['GET'])
@login_required
def get_lease(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    return jsonify(lease.as_dict())

@api.route('/leases/<int:lease_id>/take', methods=['POST'])
@login_required
def take_lease(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    if lease.status != 'active':
        return jsonify({'message': 'Lease is not available.'}), 409

    lease.in_work = True
    lease.taken_by_id = current_user.id
    lease.status = 'in_work'
    db.session.commit()
    return jsonify({'message': 'Lease taken successfully.', 'lease': lease.as_dict()}), 200

#  НОВЫЕ ОБРАБОТЧИКИ для Complete, Pending, Broken

@api.route('/leases/<int:lease_id>/complete', methods=['POST'])
@login_required
def complete_lease(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    #  Проверяем, что сервер взят в работу ТЕКУЩИМ пользователем, ИЛИ это админ
    if lease.status == 'in_work' and (lease.taken_by_id == current_user.id or current_user.role == 'admin'):
        lease.status = 'completed'
        lease.in_work = False #Добавил
        db.session.commit()
        return jsonify({'message': 'Lease completed successfully.'}), 200
    else:
        return jsonify({'message': 'Unauthorized or lease not in work.'}), 403  #  Или 400 Bad Request

@api.route('/leases/<int:lease_id>/pending', methods=['POST'])
@login_required
def pending_lease(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    if current_user.role != 'admin':  #  Только админ может менять статус
        return jsonify({'message': 'Unauthorized'}), 403
    if lease.status == 'pending':
        return jsonify({'message': 'Lease is already pending.'}), 400 #
    lease.status = 'pending'
    db.session.commit()
    return jsonify({'message': 'Lease status set to pending.'}), 200

@api.route('/leases/<int:lease_id>/broken', methods=['POST'])
@login_required
def broken_lease(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    if current_user.role != 'admin':  #  Только админ может менять статус
        return jsonify({'message': 'Unauthorized'}), 403
     # Добавьте проверку, если нужно, что сервер не в статусе broken
    lease.status = 'broken'
    db.session.commit()
    return jsonify({'message': 'Lease status set to broken.'}), 200

#  НОВЫЙ ENDPOINT для сброса статуса
@api.route('/leases/<int:lease_id>/reset', methods=['POST'])
@login_required
def reset_lease(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403

    lease.status = 'active'
    lease.in_work = False  # Сбрасываем флаг "в работе"
    lease.taken_by_id = None  # Очищаем поле taken_by_id
    db.session.commit()
    return jsonify({'message': 'Lease status reset to active.'}), 200


@api.route('/leases/<int:lease_id>', methods=['PUT']) #  PUT для обновления
@login_required
def update_lease(lease_id):
    lease = Lease.query.get_or_404(lease_id)

    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'message': 'No input data provided'}), 400

    if 'binding_state' in data and data['binding_state'] not in ['active', 'free', 'expired']:
        return jsonify({'message': 'Invalid binding_state value'}), 400

    if 'status' in data and data['status'] not in ['active', 'in_work', 'completed', 'broken', 'pending']:
        return jsonify({'message': 'Invalid status value'}), 400

    for key, value in data.items():
        if hasattr(lease, key):
            setattr(lease, key, value)

    db.session.commit()
    return jsonify({'message': 'Lease updated successfully', 'lease': lease.as_dict()}), 200

@api.route('/leases/<int:lease_id>', methods=['DELETE'])
@login_required
def delete_lease(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    if current_user.role != 'admin':
         return jsonify({'message': 'Unauthorized'}), 403
    db.session.delete(lease)
    db.session.commit()
    return jsonify({'message': 'Lease deleted successfully'}), 200


@api.errorhandler(404)
def not_found(error):
    return jsonify({'message': 'Resource not found'}), 404

@api.errorhandler(400)
def bad_request(error):
    return jsonify({'message': 'Bad request'}), 400

@api.errorhandler(401)
def unauthorized(error):
    return jsonify({'message': 'Unauthorized'}), 401

@api.errorhandler(403)
def forbidden(error):
    return jsonify({'message': 'Forbidden'}), 403

@api.errorhandler(500)
def internal_server_error(error):
    return jsonify({'message': 'Internal Server Error'}), 500