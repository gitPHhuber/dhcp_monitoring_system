from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from .models import User
from .extensions import db

users = Blueprint('users', __name__)

@users.route('/users')
@login_required
def user_list():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))

    users = User.query.all()
    return render_template('users/user_list.html', users=users)