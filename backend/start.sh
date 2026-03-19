#!/bin/sh
set -eu

echo "[backend] running migrations..."
python manage.py migrate

echo "[backend] starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
