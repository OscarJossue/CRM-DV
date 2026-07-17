# CRM SaaS Starter V2

CRM SaaS multiempresa con Django, Django REST Framework, PostgreSQL, JWT, React Admin, Docker, Celery, Redis, Prometheus y Grafana.

## Stack incluido

- Frontend: React + React Admin + Vite
- Backend: Django + Django REST Framework
- Base de datos: PostgreSQL
- Auth: JWT con SimpleJWT
- Métricas: Prometheus + Grafana
- Contenedores: Docker + Docker Compose
- Archivos/PDFs: volumen local `media_volume`
- Tareas pesadas: Celery + Redis

## Estructura de backend por módulo

Cada app usa esta base:

```txt
apps/<modulo>/
├── __init__.py
├── apps.py
├── admin.py
├── urls.py
├── views.py
├── serializers.py
├── forms.py
├── permissions.py
├── selectors.py
├── services.py
├── models/
│   ├── __init__.py
│   ├── entities.py
│   └── choices.py
├── templates/<modulo>/
│   ├── list.html
│   ├── form.html
│   └── detail.html
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

> Nota: se usa `__init__.py` con doble guion bajo porque es el estándar real de Python.

## Levantar el proyecto

```bash
cp .env.example .env
docker compose up --build
```

En otra terminal:

```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo
```

## URLs

```txt
Frontend React Admin: http://localhost:5173
Backend API:          http://localhost:8000/api
Django Admin:         http://localhost:8000/admin
Prometheus:           http://localhost:9090
Grafana:              http://localhost:3001
Métricas backend:     http://localhost:8000/metrics
```

## Usuarios demo

```txt
Super Admin: Oscar
email: oscar@demo.com
password: oscar12345



Super Admin:
email: admin@demo.com
password: admin12345

Owner Empresa:
email: owner@demo.com
password: owner12345

Secretaria:
email: secretary@demo.com
password: secretary12345

Inspector:
email: inspector@demo.com
password: inspector12345
```

## Flujo base del SaaS

1. `company` representa la empresa cliente.
2. `user_account` representa el usuario del CRM.
3. `role` y `role_permission` controlan permisos por módulo.
4. Cada módulo operativo filtra por empresa mediante `id_company` o por relaciones al proyecto/factura.
5. El frontend consume el API con JWT.
6. Celery queda listo para tareas pesadas como PDFs, reportes o procesos programados.
7. Prometheus y Grafana quedan listos para métricas técnicas.

## Módulos incluidos

```txt
companies
accounts
employees
clients
leads
projects
inspections
estimates
invoices
payments
contracts
evidence
supervision
calendar_events
notifications
audit
dashboard
reports
```

## Endpoints principales

```txt
/api/auth/login/
/api/auth/refresh/
/api/auth/me/
/api/companies/
/api/users/
/api/roles/
/api/role-permissions/
/api/employees/
/api/clients/
/api/leads/
/api/projects/
/api/project-assignments/
/api/inspections/
/api/estimates/
/api/estimates/{id}/pdf/
/api/invoices/
/api/invoices/{id}/pdf/
/api/payments/
/api/contracts/
/api/evidence-files/
/api/supervisions/
/api/calendar-events/
/api/notifications/
/api/system-logs/
/api/dashboard/summary/
/api/reports/financial-summary.csv
```

## Reglas importantes

- No subir `.env`.
- No subir `node_modules`.
- No subir archivos generados en `media`.
- Cada registro operativo debe pertenecer a una empresa directa o indirectamente.
- No mezclar lógica pesada en views: usar `services.py` y `selectors.py`.
- Los PDFs iniciales son básicos y deben personalizarse por empresa más adelante.
