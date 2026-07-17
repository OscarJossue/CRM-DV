# Project cleanup report

## Kept intentionally
- `.env`: local/private environment used by `docker-compose.yml`.
- `.env.example`: secret-free local template.
- `.env.production.example`: secret-free production template.
- `docker-compose.yml`: local development stack.
- `docker-compose.prod.yml`: production stack.
- `backend/docker-entrypoint.sh`: container privilege/volume entrypoint.
- `backend/entrypoint.prod.sh`: production migration/static/Gunicorn entrypoint.

## Removed
- Environment backup files.
- Redundant `backend/.env` and backend environment templates.
- Obsolete root `entrypoint.sh` not referenced by Docker.
- Generated `staticfiles`, empty `media`, Celery beat schedule, caches and OS files.
- Unreferenced root screenshot `image.png`.

## Environment layout
- Local: `.env`
- Production: `.env.production` (create from `.env.production.example`; never commit it)

The two Compose files are intentionally separate. Do not merge them.
