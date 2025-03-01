from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from .models import Lease, LeaseStatus  # Добавили LeaseStatus
from .extensions import db
from .utils import parse_dhcp_leases
from . import tasks
from .journal import record_action # Добавил

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
    if lease.in_work and lease.taken_by_id != current_user.id:
        return jsonify({'message': 'Lease is already taken by another user.'}), 409

    old_status = lease.status  # Сохраняем старый статус
    lease.in_work = True
    lease.taken_by_id = current_user.id
    lease.status = LeaseStatus.IN_WORK
    db.session.add(LeaseStatusHistory(lease=lease, user=current_user, old_status=old_status, new_status=lease.status)) #Добавили
    db.session.commit()
    record_action(current_user.id, 'take_lease', f'Lease ID: {lease_id}') # Добавил
    return jsonify({'message': 'Lease taken successfully.', 'lease': lease.as_dict()}), 200

@api.route('/leases/<int:lease_id>/release', methods=['POST'])
@login_required
def release_lease(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    if not lease.in_work:
        return jsonify({'message': 'Lease is not taken.'}), 400
    if lease.taken_by_id != current_user.id and current_user.role != 'admin':
        return jsonify({'message': 'You do not have permission to release this lease.'}), 403
    old_status = lease.status  # Добавили
    lease.in_work = False
    lease.taken_by_id = None
    lease.status = LeaseStatus.ACTIVE
    db.session.add(LeaseStatusHistory(lease=lease, user=current_user, old_status=old_status, new_status=lease.status)) # Добавили
    db.session.commit()
    record_action(current_user.id, 'release_lease', f'Lease ID: {lease_id}') # Добавил
    return jsonify({'message': 'Lease released successfully.', 'lease': lease.as_dict()}), 200


@api.route('/leases/<int:lease_id>/complete', methods=['POST'])
@login_required
def complete_lease(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    old_status = lease.status # Добавили
    lease.status = LeaseStatus.COMPLETED
    lease.in_work = False
    db.session.add(LeaseStatusHistory(lease=lease, user=current_user, old_status=old_status, new_status=lease.status)) # Добавили
    db.session.commit()
    record_action(current_user.id, 'complete_lease', f'Lease ID: {lease_id}')  # Добавил
    return jsonify({'message': 'Lease completed successfully.', 'lease': lease.as_dict()}), 200


@api.route('/leases/<int:lease_id>/pending', methods=['POST'])
@login_required
def pending_lease(lease_id):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    lease = Lease.query.get_or_404(lease_id)
    old_status = lease.status  # Добавили
    lease.status = LeaseStatus.PENDING
    db.session.add(LeaseStatusHistory(lease=lease, user=current_user, old_status=old_status, new_status=lease.status)) # Добавили
    db.session.commit()
    record_action(current_user.id, 'pending_lease', f'Lease ID: {lease_id}') # Добавил
    return jsonify({'message': 'Lease set to pending successfully.', 'lease': lease.as_dict()}), 200


@api.route('/leases/<int:lease_id>/broken', methods=['POST'])
@login_required
def broken_lease(lease_id):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    lease = Lease.query.get_or_404(lease_id)
    old_status = lease.status  # Добавили
    lease.status = LeaseStatus.BROKEN
    db.session.add(LeaseStatusHistory(lease=lease, user=current_user, old_status=old_status, new_status=lease.status)) # Добавили
    db.session.commit()
    record_action(current_user.id, 'broken_lease', f'Lease ID: {lease_id}') # Добавил
    return jsonify({'message': 'Lease set to broken successfully.', 'lease': lease.as_dict()}), 200

@api.route('/leases/<int:lease_id>/reset', methods=['POST'])
@login_required
def reset_lease(lease_id):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    lease = Lease.query.get_or_404(lease_id)
    old_status = lease.status  #  Добавили
    lease.status = LeaseStatus.ACTIVE
    lease.in_work = False
    lease.taken_by_id = None
    db.session.add(LeaseStatusHistory(lease=lease, user=current_user, old_status=old_status, new_status=lease.status)) # Добавили
    db.session.commit()
    record_action(current_user.id, 'reset_lease', f'Lease ID: {lease_id}')# Добавил
    return jsonify({'message': 'Lease status reset successfully.', 'lease': lease.as_dict()}), 200

@api.route('/leases/<int:lease_id>', methods=['PUT'])
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
    for key, value in data.items():
        if hasattr(lease, key):
            setattr(lease, key, value)
    db.session.commit()
    record_action(current_user.id, 'update_lease', f'Lease ID: {lease_id}')  # Добавил
    return jsonify({'message': 'Lease updated successfully', 'lease': lease.as_dict()}), 200


@api.route('/leases/<int:lease_id>', methods=['DELETE'])
@login_required
def delete_lease(lease_id):
  #Реализовать если требуется удаление записей (и поддерживается DHCP сервером)
    pass

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