#!/bin/sh
set -eu

MEDIA_DIR="${MEDIA_ROOT:-/app/media}"
STATIC_DIR="${STATIC_ROOT:-/app/staticfiles}"

mkdir -p "$MEDIA_DIR" "$STATIC_DIR"

# Named Docker volumes can preserve root ownership from an older container.
# Repair it at every startup, then run Django/Celery as the non-root crm user.
if [ "$(id -u)" = "0" ]; then
  chown -R crm:crm "$MEDIA_DIR" "$STATIC_DIR"
  exec gosu crm "$@"
fi

exec "$@"
