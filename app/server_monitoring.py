from flask import Blueprint, render_template
from flask_login import login_required, current_user

server_monitoring = Blueprint('server_monitoring', __name__)

@server_monitoring.route('/monitor_servers')
@login_required
def monitor_servers():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index')) #Или редирект

    return render_template('server_monitoring/monitor_servers.html')