from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
# from .models import Playbook  <-- УДАЛЯЕМ отсюда!
from .forms import PlaybookForm  # <-- ОСТАВЛЯЕМ!  Импорт формы нужен.
from .extensions import db
import subprocess

server_management = Blueprint('server_management', __name__)

@server_management.route('/manage_servers')
@login_required
def manage_servers():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))

    from .models import Playbook  # <-- ДОБАВЛЯЕМ СЮДА!  Только здесь.
    playbooks = Playbook.query.all()
    return render_template('server_management/manage_servers.html', playbooks=playbooks)

@server_management.route('/add_playbook', methods=['GET', 'POST'])
@login_required
def add_playbook():
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    form = PlaybookForm()
    if form.validate_on_submit():
        from .models import Playbook  # <-- ДОБАВЛЯЕМ СЮДА!
        playbook = Playbook(name=form.name.data, description=form.description.data, content=form.content.data)
        db.session.add(playbook)
        db.session.commit()
        flash('Playbook added successfully.', 'success')
        return redirect(url_for('server_management.manage_servers'))
    return render_template('server_management/add_playbook.html', form=form)


@server_management.route('/run_playbook', methods=['POST'])
@login_required
def run_playbook():
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403

    playbook_id = request.form.get('playbook_id')
    if not playbook_id:
        return jsonify({'message': 'Playbook ID is required'}), 400

    from .models import Playbook  # <-- ДОБАВЛЯЕМ СЮДА!
    playbook = Playbook.query.get(playbook_id)
    if not playbook:
        return jsonify({'message': 'Playbook not found'}), 404

    #  !!!  БЕЗОПАСНОСТЬ  !!!
    #  Запуск произвольного кода, полученного от пользователя, *ОЧЕНЬ ОПАСЕН*.
    #  Нужна *ОЧЕНЬ* строгая валидация и, желательно, "песочница".
    #  В данном примере используется *КРАЙНЕ УПРОЩЁННЫЙ* запуск.
    #  В РЕАЛЬНОМ ПРОЕКТЕ ТАК ДЕЛАТЬ НЕЛЬЗЯ!!!

    try:
        #  1.  Сохраняем содержимое плейбука во временный файл.
        with open(f'/tmp/playbook_{playbook.id}.yml', 'w') as f:  #  Используем /tmp
            f.write(playbook.content)

        #  2.  Запускаем ansible-playbook (нужно установить Ansible!).
        #      В РЕАЛЬНОМ приложении нужно использовать ansible-runner
        #      или Ansible Python API, а не subprocess.
        result = subprocess.run(
            ['ansible-playbook', f'/tmp/playbook_{playbook.id}.yml'],
            capture_output=True,
            text=True,
            check=True  #  Выбрасывает исключение, если команда завершилась с ошибкой
        )

        #  3.  (Опционально) Удаляем временный файл.
        #      import os
        #      os.remove(f'/tmp/playbook_{playbook.id}.yml')

        return jsonify({'message': f'Playbook {playbook.name} executed successfully.', 'output': result.stdout}), 200

    except subprocess.CalledProcessError as e:
        return jsonify({'message': f'Playbook {playbook.name} failed.', 'error': e.stderr}), 500
    except Exception as e:
        return jsonify({'message': 'Error running playbook', 'error': str(e)}), 500