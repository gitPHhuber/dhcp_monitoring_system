from flask import render_template, redirect, url_for, flash, request, Blueprint, jsonify
from flask_login import login_required, current_user
from .models import Lease, ServerConfig, LeaseStatus
from .extensions import db
from .utils import parse_dhcp_leases, ping_host, get_leases_via_ssh
from .tasks import check_lease_status, update_leases_from_file  # Импортируем конкретную функцию
from .forms import ServerConfigForm
from sqlalchemy import or_
# from .models import Lease, LeaseStatus  # Уже импортировано выше


def get_filtered_leases(status=None, search_query='', user_id=None, page=1, per_page=10):
    """
    Возвращает отфильтрованный и пагинированный список лизов.
    """
    query = Lease.query

    if status:
        if isinstance(status, list):
            query = query.filter(Lease.status.in_(status))
        else:
            query = query.filter(Lease.status == status)

    if user_id:
        query = query.filter(Lease.taken_by_id == user_id)

    if search_query:
        query = query.filter(
            or_(Lease.ip.contains(search_query), Lease.hostname.contains(search_query))
        )

    return query.order_by(Lease.ip).paginate(page=page, per_page=per_page, error_out=False)


main = Blueprint('main', __name__)


@main.route('/')
@login_required
def index():
    server_config = ServerConfig.query.first()
    if not server_config:
        flash('Please configure the DHCP server IP address.', 'warning')
        return redirect(url_for('main.settings'))
    update_leases_from_file.delay()
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    leases = get_filtered_leases(search_query=search_query, page=page)  # Убрали фильтр по статусу
    return render_template('index.html', leases=leases, server_config=server_config, search_query=search_query) # Убрали dark_mode


@main.route('/in_work')
@login_required
def in_work():
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    if current_user.role == 'admin':
        leases = get_filtered_leases(status=LeaseStatus.IN_WORK, search_query=search_query, page=page)
    else:
        leases = get_filtered_leases(status=LeaseStatus.IN_WORK, search_query=search_query, user_id=current_user.id,
                                     page=page)
    return render_template('in_work.html', leases=leases, search_query=search_query)


@main.route('/completed')
@login_required
def completed():
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    leases = get_filtered_leases(status=LeaseStatus.COMPLETED, search_query=search_query, page=page)
    return render_template('completed.html', leases=leases, search_query=search_query)


@main.route('/broken')
@login_required
def broken():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    leases = get_filtered_leases(status=LeaseStatus.BROKEN, search_query=search_query, page=page)
    broken_count = Lease.query.filter(Lease.status == LeaseStatus.BROKEN).count()
    return render_template('broken.html', leases=leases, search_query=search_query, broken_count=broken_count)


@main.route('/pending')
@login_required
def pending():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    leases = get_filtered_leases(status=LeaseStatus.PENDING, search_query=search_query, page=page)
    return render_template('pending.html', leases=leases, search_query=search_query)


@main.route('/update_table')
@login_required
def update_table():
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    status = request.args.get('status', 'active') #  'active' – значение по умолчанию

    if status == 'in_work':
        if current_user.role == 'admin':
            leases = get_filtered_leases(status=LeaseStatus.IN_WORK, search_query=search_query, page=page,
                                         per_page=per_page)
        else:
            leases = get_filtered_leases(status=LeaseStatus.IN_WORK, search_query=search_query,
                                         user_id=current_user.id, page=page, per_page=per_page)
    elif status == 'completed':
        leases = get_filtered_leases(status=LeaseStatus.COMPLETED, search_query=search_query, page=page,
                                     per_page=per_page)
    elif status == 'broken':
        if current_user.role != 'admin':
            return jsonify({'message': 'Forbidden'}), 403
        leases = get_filtered_leases(status=LeaseStatus.BROKEN, search_query=search_query, page=page,
                                     per_page=per_page)
    elif status == 'pending':
        if current_user.role != 'admin':
            return jsonify({'message': 'Forbidden'}), 403
        leases = get_filtered_leases(status=LeaseStatus.PENDING, search_query=search_query, page=page,
                                     per_page=per_page)
    else:  # По умолчанию – все
        leases = get_filtered_leases(search_query=search_query, page=page, per_page=per_page) # Убрали фильтр

    return render_template('leases_table.html', leases=leases, search_query=search_query)


@main.route('/toggle_dark_mode')
def toggle_dark_mode():
    current_theme = request.args.get('theme', 'light')
    new_theme = 'dark' if current_theme == 'light' else 'light'
    return jsonify({'theme': new_theme})


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
        server_config.ssh_password = form.ssh_password.data  # !!! НЕ ХРАНИТЬ В ОТКРЫТОМ ВИДЕ !!!
        server_config.ssh_key_path = form.ssh_key_path.data

        if not server_config.id:
            db.session.add(server_config)
        db.session.commit()
        flash('Settings saved successfully.', 'success')
        return redirect(url_for('main.index'))

    return render_template('settings.html', form=form) # Убрали dark_mode