#!/bin/sh
set -eu

echo "Checking production configuration"
python manage.py check --deploy

if [ "${AUTO_MIGRATE:-false}" = "true" ]; then
  echo "Applying database migrations"
  python manage.py migrate --noinput
fi

echo "Collecting static files"
python manage.py collectstatic --noinput

echo "Starting Gunicorn"
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile -
