#!/bin/sh
set -eu

umask 077
alembic -c /app/apps/api/alembic.ini upgrade head
exec "$@"
