from flask import render_template, redirect, url_for, flash, request, Blueprint, jsonify
from flask_login import login_required, current_user
from .models import Lease, ServerConfig, LeaseStatus
from .extensions import db
from .utils import parse_dhcp_leases, ping_host, get_leases_via_ssh
from .tasks import check_lease_status, update_leases_from_file  # Импортируем конкретную функцию
from .forms import ServerConfigForm
from sqlalchemy import or_

main = Blueprint('main', __name__)

@main.route('/')
@login_required
def index():
    server_config = ServerConfig.query.first()
    if not server_config:
        flash('Please configure the DHCP server IP address.', 'warning')
        return redirect(url_for('main.settings'))
    # Запуск асинхронного обновления DHCP-лизов
    update_leases_from_file.delay()  # Теперь вызов корректен
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Показываем лизы со статусом ACTIVE и IN_WORK на главной странице  <-- ВАЖНО!
    if search_query:
        leases = Lease.query.filter(
            or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query)),
            Lease.status.in_([LeaseStatus.ACTIVE, LeaseStatus.IN_WORK])  #  <--  СТАТУС В ACTIVE и IN_WORK
        ).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)
    else:
        leases = Lease.query.filter(
            Lease.status.in_([LeaseStatus.ACTIVE, LeaseStatus.IN_WORK]) #  <--  СТАТУС В ACTIVE и IN_WORK
        ).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('index.html', leases=leases, server_config=server_config, search_query=search_query)

@main.route('/in_work')
@login_required
def in_work():
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    if current_user.role == 'admin':
        if search_query:
            leases = Lease.query.filter(
                Lease.status == LeaseStatus.IN_WORK,
                or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
            ).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)
        else:
            leases = Lease.query.filter(Lease.status == LeaseStatus.IN_WORK).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)
    else:
        if search_query:
            leases = Lease.query.filter(
                Lease.taken_by_id == current_user.id,
                Lease.status == LeaseStatus.IN_WORK,
                or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
            ).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)
        else:
            leases = Lease.query.filter(Lease.taken_by_id == current_user.id, Lease.status == LeaseStatus.IN_WORK).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('in_work.html', leases=leases, search_query=search_query)

@main.route('/completed')
@login_required
def completed():
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    if search_query:
        leases = Lease.query.filter(
            Lease.status == LeaseStatus.COMPLETED,
            or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
        ).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)
    else:
        leases = Lease.query.filter(Lease.status == LeaseStatus.COMPLETED).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('completed.html', leases=leases, search_query=search_query)

@main.route('/broken')
@login_required
def broken():
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))
    if search_query:
        leases = Lease.query.filter(
            Lease.status == LeaseStatus.BROKEN,
            or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
        ).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)
    else:
        leases = Lease.query.filter(Lease.status == LeaseStatus.BROKEN).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('broken.html', leases=leases, search_query=search_query)

@main.route('/pending')
@login_required
def pending():
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))

    if search_query:
         leases = Lease.query.filter(
            Lease.status == LeaseStatus.PENDING,
            or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
        ).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)
    else:
        leases = Lease.query.filter(Lease.status == LeaseStatus.PENDING).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('pending.html', leases=leases, search_query=search_query)


@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))

    server_config = ServerConfig.query.first() or ServerConfig()
    form = ServerConfigForm(obj=server_config)

    if form.validate_on_submit():
        server_config.dhcp_server_ip = form.dhcp_server_ip.data
        server_config.connection_type = form.connection_type.data
        server_config.ssh_username = form.ssh_username.data
        server_config.ssh_password = form.password.data
        server_config.ssh_key_path = form.ssh_key_path.data

        if not server_config.id:
            db.session.add(server_config)
        db.session.commit()
        flash('Settings saved successfully.', 'success')
        return redirect(url_for('main.index'))

    return render_template('settings.html', form=form)

@main.route('/update_table')
@login_required
def update_table():
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    status = request.args.get('status', 'active')  #  <--  Значение по умолчанию 'active'

    if status == 'in_work':
        if current_user.role == 'admin':
            query = Lease.query.filter(Lease.status == LeaseStatus.IN_WORK)
        else:
            query = Lease.query.filter(Lease.taken_by_id == current_user.id, Lease.status == LeaseStatus.IN_WORK)
    elif status == 'completed':
        query = Lease.query.filter(Lease.status == LeaseStatus.COMPLETED)
    elif status == 'broken':
        if current_user.role != 'admin':
            return jsonify({'message': 'Forbidden'}), 403
        query = Lease.query.filter(Lease.status == LeaseStatus.BROKEN)
    elif status == 'pending':
        if current_user.role != 'admin':
            return jsonify({'message': 'Forbidden'}), 403
        query = Lease.query.filter(Lease.status == LeaseStatus.PENDING)
    else:  # По умолчанию - active и in_work <-- ИСПРАВЛЕНО!
        query = Lease.query.filter(Lease.status.in_([LeaseStatus.ACTIVE, LeaseStatus.IN_WORK])) # <-- ACTIVE и IN_WORK


    if search_query:  # Добавлено условие поиска
        leases = query.filter(
            or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
        ).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)
    else:
        leases = query.order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('leases_table.html', leases=leases, search_query=search_query) # <-- ВОТ ЭТО ИЗМЕНЕНИЕ!

@main.route('/toggle_dark_mode')
def toggle_dark_mode():
    current_theme = request.args.get('theme', 'light')
    new_theme = 'dark' if current_theme == 'light' else 'light'
    return jsonify({'theme': new_theme})