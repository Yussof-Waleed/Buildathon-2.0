FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=buildathon2.settings
ENV DJANGO_DEBUG=false

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# WhiteNoise serves from STATIC_ROOT. .env is not in the image, so use a
# throwaway secret only for this build step.
RUN DJANGO_SECRET_KEY=build-collectstatic python manage.py collectstatic --noinput

EXPOSE 8080

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn buildathon2.wsgi:application --bind 0.0.0.0:8080 --workers 2"]
