# Используем официальный образ Python
FROM python:3.9-slim-buster

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP=run.py
ENV FLASK_ENV=development 

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY requirements.txt requirements.txt
# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все остальное
COPY . .

#  Устанавливаем права доступа (важно для безопасности, но для разработки можно закомментировать)
# RUN chown -R nobody:nogroup /app
# USER nobody

# Запускаем приложение с помощью Gunicorn (production) или Flask dev server (development)
# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "run:app"] # Production
CMD ["flask", "run", "--host=0.0.0.0"]