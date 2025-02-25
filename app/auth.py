from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from .forms import LoginForm, RegistrationForm
from .models import User
from .extensions import db
from urllib.parse import urlparse
from datetime import datetime  # Импортируем datetime


auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('main.index')

            user.last_seen = datetime.utcnow() # В auth.login добавил
            db.session.commit()# В auth.login добавил

            return redirect(next_page)

        flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if current_user.role != 'admin':
        flash('Only administrators can register new users.', 'danger')
        return redirect(url_for('main.index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, role=form.role.data, first_name = form.first_name.data, last_name = form.last_name.data) #Изменено
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('New user registered successfully.', 'success')
        return redirect(url_for('auth.login'))  # Или куда-то еще
    return render_template('register.html', form=form)


@auth.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    # ... (Реализация запроса на сброс пароля) ...
    pass


@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # ... (Реализация сброса пароля по токену) ...
    pass