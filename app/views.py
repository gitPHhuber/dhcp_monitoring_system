from flask import render_template, redirect, url_for, flash, request, Blueprint, jsonify
from flask_login import login_required, current_user, logout_user # Добавили logout_user
from .models import Lease, ServerConfig
from .extensions import db
from .utils import parse_dhcp_leases, ping_host, get_leases_via_ssh
from .tasks import check_lease_status
from .forms import ServerConfigForm
from . import tasks
from sqlalchemy import or_

main = Blueprint('main', __name__)

@main.route('/')
@login_required
def index():
    # ... (остальной код index() - как раньше) ...
    server_config = ServerConfig.query.first()
    if not server_config:
        flash('Please configure the DHCP server IP address.', 'warning')
        return redirect(url_for('main.settings'))

    tasks.update_leases_from_file.delay()

    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    if search_query:
        leases = Lease.query.filter(
            or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query)),
            Lease.status == 'active'  #  Фильтруем по статусу 'active'
        ).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)
    else:
        leases = Lease.query.filter_by(status='active').order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False) #Изменил

    return render_template('index.html', leases=leases, server_config=server_config, search_query=search_query)



@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    # ... (без изменений) ...
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))

    server_config = ServerConfig.query.first() or ServerConfig()
    form = ServerConfigForm(obj=server_config)

    if form.validate_on_submit():
        server_config.dhcp_server_ip = form.dhcp_server_ip.data
        server_config.connection_type = form.connection_type.data  # Сохраняем тип
        server_config.ssh_username = form.ssh_username.data      # Сохраняем SSH данные
        server_config.ssh_password = form.ssh_password.data
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
     # ... (остальной код update_table - как раньше)
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    if search_query:
        leases = Lease.query.filter(
            or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query)),
            Lease.status == 'active'  # Фильтруем по статусу 'active'
        ).order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)
    else:
        leases = Lease.query.filter_by(status='active').order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False) #Изменил

    leases_data = [lease.as_dict() for lease in leases.items]
    return jsonify(leases_data)

@main.route('/toggle_dark_mode')
def toggle_dark_mode():
    current_theme = request.args.get('theme', 'light')
    new_theme = 'dark' if current_theme == 'light' else 'light'
    return jsonify({'theme': new_theme})

# --------  Новые вкладки  --------

@main.route('/in_work')
@login_required
def in_work():
    search_query = request.args.get('q', '')  # Добавлено для поиска
    if current_user.role == 'admin':
        if search_query:
            leases = Lease.query.filter(
                Lease.status == 'in_work',
                or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
            ).order_by(Lease.ip).all()
        else:
            leases = Lease.query.filter_by(status='in_work').order_by(Lease.ip).all()
    else:
        if search_query:
            leases = Lease.query.filter(
                Lease.taken_by_id == current_user.id,
                Lease.status == 'in_work',
                or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
            ).order_by(Lease.ip).all()
        else:
            leases = Lease.query.filter_by(taken_by_id=current_user.id, status='in_work').order_by(Lease.ip).all()

    return render_template('in_work.html', leases=leases, search_query=search_query)

@main.route('/completed')
@login_required
def completed():
    search_query = request.args.get('q', '')  # Добавлено для поиска
    if search_query:
        leases = Lease.query.filter(
            Lease.status == 'completed',
            or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
        ).order_by(Lease.ip).all()
    else:
        leases = Lease.query.filter_by(status='completed').order_by(Lease.ip).all()
    return render_template('completed.html', leases=leases, search_query=search_query)

@main.route('/broken')
@login_required
def broken():
    search_query = request.args.get('q', '')  # Добавлено для поиска
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))

    if search_query:
        leases = Lease.query.filter(
            Lease.status == 'broken',
            or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
        ).order_by(Lease.ip).all()
    else:
        leases = Lease.query.filter_by(status='broken').order_by(Lease.ip).all()

    return render_template('broken.html', leases=leases, search_query=search_query)

@main.route('/pending')
@login_required
def pending():
    search_query = request.args.get('q', '')  # Добавлено для поиска
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))

    if search_query:
         leases = Lease.query.filter(
            Lease.status == 'pending',
            or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
        ).order_by(Lease.ip).all()
    else:
        leases = Lease.query.filter_by(status='pending').order_by(Lease.ip).all()

    return render_template('pending.html', leases=leases, search_query=search_query)