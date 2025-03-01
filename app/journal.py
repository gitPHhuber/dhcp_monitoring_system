# app/journal.py
from .extensions import db  # Импортируем только db
from datetime import datetime
from flask import Blueprint, render_template, flash, redirect, url_for  # Добавили импорты
from flask_login import login_required, current_user  # Добавили импорты
from .models import Journal


def record_action(user_id, action, details=None):
    """Записывает действие пользователя в журнал."""
    entry = Journal(user_id=user_id, action=action, details=details, timestamp=datetime.utcnow())
    db.session.add(entry)
    db.session.commit()

#Представление
journal_bp = Blueprint('journal', __name__)

@journal_bp.route('/logs')
@login_required
def view_logs():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))

    logs = db.session.query(Journal).order_by(Journal.timestamp.desc()).all()  # Используем db.session.query
    return render_template('journal/logs.html', logs=logs)