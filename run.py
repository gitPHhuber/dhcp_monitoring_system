from app import create_app, db
from app.models import User, Lease, ServerConfig
from flask_migrate import Migrate
from app.models import initialize_server_config

app = create_app()  # Используем 'default' по умолчанию, можно изменить
migrate = Migrate(app, db)

# Создаем shell context (для удобной работы в консоли Flask)
@app.shell_context_processor
def make_shell_context():
    return {'app': app, 'db': db, 'User': User, 'Lease': Lease, 'ServerConfig': ServerConfig}

@app.cli.command("create-user")
def create_user():
    """Creates a new user."""
    username = input("Enter username: ")
    password = getpass("Enter password: ")  # Используем getpass для безопасности
    confirm_password = getpass("Confirm password: ")
    role = input("Enter role (admin/tester): ")

    if password != confirm_password:
        print("Passwords do not match.")
        return

    if role not in ['admin', 'tester']:
        print("Invalid role.")
        return

    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print(f"User {username} created successfully.")

import click #Нужно для работы декоратора @app.cli.command
from getpass import getpass #Для безопасного ввода пароля

if __name__ == '__main__':
    initialize_server_config(app) # Инициализация настроек
    app.run()