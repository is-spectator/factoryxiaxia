#!/bin/sh
set -eu

echo "[backend] running migrations..."
python manage.py migrate

echo "[backend] bootstrapping runtime data..."
python manage.py bootstrap

export SKIP_RUNTIME_BOOTSTRAP=1

echo "[backend] starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
