# CRM-DV — CI/CD setup

This patch prepares the repository for CI and safe production deployment.

## Included files

- `.github/workflows/ci.yml`
  - Runs on pushes and pull requests for `main` and `develop`.
  - Starts PostgreSQL 16 and Redis 7 for CI.
  - Runs Django checks, missing-migration detection, migrations and tests.
  - Runs `check --deploy` with safe CI-only production variables.
  - Validates `docker-compose.prod.yml`.
  - Builds the backend Docker image.

- `.github/workflows/deploy.yml`
  - Supports manual deployment with `workflow_dispatch`.
  - Can automatically deploy after a successful `CI` run on `main` only when the repository variable `DEPLOY_ENABLED=true` exists.
  - Uses SSH keys, not a VPS password.
  - Deploys the repository under `/opt/crm-dv`.

- `scripts/deploy-production.sh`
  - Validates Compose.
  - Builds and starts production containers.
  - Waits for the backend Docker healthcheck.
  - Fails with backend logs if health verification fails.

- `backend/.dockerignore`
  - Prevents local `.env` files, caches, generated media/static files and logs from being copied into the backend Docker image.

## Branch policy

- `main`: stable / production.
- `develop`: integration.
- Work should enter these branches through pull requests.
- Protect `main` against direct pushes and force pushes.
- Require the CI status check before merging to `main`.

## Production target

- Domain: `matth.ceomarketingusa.com`
- Deploy path: `/opt/crm-dv`
- Production Compose file: `docker-compose.prod.yml`
- Real `.env.production` stays only on the VPS and must never be committed.

## GitHub production configuration — do this only after the VPS repository is prepared

Create an Environment named `production` and add these secrets:

- `VPS_HOST`: production VPS IP or hostname.
- `VPS_USER`: SSH deployment user.
- `VPS_SSH_PRIVATE_KEY`: private key used only by GitHub Actions for deployment.
- `VPS_KNOWN_HOSTS`: trusted SSH host-key line for the VPS.

Create this repository variable only when production is ready for automatic deployment:

- `DEPLOY_ENABLED=true`

Until `DEPLOY_ENABLED` exists and equals `true`, successful pushes to `main` will run CI but will not auto-deploy. Manual deployment remains available from GitHub Actions.

## Important

Do not commit any real `.env`, `.env.production`, passwords, SSH private keys, API tokens, database passwords, Redis passwords or SMTP passwords.
