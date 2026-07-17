# CRM SaaS Starter

CRM SaaS Starter es una plataforma web multiempresa desarrollada con Django. El sistema permite administrar un panel SaaS global para CEO MARKETING y, al mismo tiempo, entregar a cada empresa cliente su propio mini CRM mediante una URL basada en el slug de la empresa.

El proyecto está diseñado para separar claramente dos niveles de operación:

1. Platform SaaS Admin: administración interna de CEO MARKETING.
2. Company Workspace: mini CRM privado para cada empresa cliente.

Ejemplo de rutas:

```txt
/crm/dashboard/
/crm/companies/
/crm/platform-users/
/roofex2/dashboard/
/roofex2/clients/
/roofex-llc/projects/
```

---

## 1. Objetivo general del sistema

El objetivo principal del sistema es permitir que CEO MARKETING pueda crear, vender, administrar y controlar accesos a mini CRM independientes para diferentes empresas.

Cada empresa registrada tiene:

- Un slug único.
- Una ruta propia.
- Usuarios propios.
- Clientes propios.
- Leads propios.
- Proyectos propios.
- Estimados propios.
- Facturas propias.
- Pagos propios.
- Reportes propios.
- Permisos propios.

A nivel plataforma, CEO MARKETING puede controlar:

- Empresas.
- Planes SaaS.
- Suscripciones.
- Renovaciones.
- Pagos SaaS.
- Documentos SaaS.
- Usuarios internos de plataforma.
- Permisos internos.
- Auditoría.
- Notificaciones.
- Correos platform.
- Calendario platform.
- Métricas técnicas.
- Monitoreo del sistema.

---

## 2. Concepto de distribución del sistema

El sistema no usa un campo simple llamado `website` para controlar el acceso del cliente. La distribución se hace por medio del slug de la empresa.

Cuando se crea una empresa, el sistema genera o utiliza un `slug`.

Ejemplo:

```txt
Company Name: Roofex2
Slug: roofex2
Workspace URL: /roofex2/dashboard/
```

Otro ejemplo:

```txt
Company Name: Roofex LLC
Slug: roofex-llc
Workspace URL: /roofex-llc/dashboard/
```

Esto permite entregar a cada cliente una URL limpia y automática:

```txt
/{company_slug}/dashboard/
/{company_slug}/clients/
/{company_slug}/projects/
/{company_slug}/invoices/
```

Por eso, en producción, el cliente no necesita una ruta manual tipo `/website/`. El sistema distribuye los espacios por medio de:

```txt
company.slug
id_company
```

---

## 3. Capas principales del proyecto

El CRM se divide en dos capas.

---

## 3.1 Platform SaaS Admin

Esta capa pertenece a CEO MARKETING.

Ruta base:

```txt
/crm/
```

Rutas principales:

```txt
/crm/dashboard/
/crm/companies/
/crm/plans/
/crm/subscriptions/
/crm/documents/
/crm/payments/
/crm/calendar/
/crm/platform-email/
/crm/notifications/
/crm/audit/
/crm/platform-users/
/dashboard-metrics/
/system-monitor/
```

Esta capa permite administrar toda la plataforma SaaS.

---

## 3.2 Company Workspace

Esta capa pertenece a cada empresa cliente.

Ruta base:

```txt
/{company_slug}/
```

Ejemplo:

```txt
/roofex2/dashboard/
/roofex2/clients/
/roofex2/projects/
/roofex2/estimates/
/roofex2/invoices/
/roofex2/payments/
```

Cada empresa tiene su propio mini CRM aislado por `id_company`.

---

## 4. Tecnologías utilizadas

Backend:

```txt
Python 3.11
Django 5
Django REST Framework
PostgreSQL
Redis
Celery
Simple JWT
Django Prometheus
WhiteNoise
CORS Headers
```

Infraestructura:

```txt
Docker
Docker Compose
PostgreSQL container
Redis container
Backend container
```

Autenticación:

```txt
Custom User Model
Login por email
Roles
Permisos por módulo
Permisos platform directos
Separación entre usuarios platform y usuarios company
```

---

## 5. Estructura general del backend

```txt
backend/
├── apps/
│   ├── accounts/
│   ├── audit/
│   ├── calendar_events/
│   ├── clients/
│   ├── companies/
│   ├── company_modules/
│   ├── contracts/
│   ├── core/
│   ├── dashboard/
│   ├── dashboard_metrics/
│   ├── employees/
│   ├── estimates/
│   ├── evidence/
│   ├── inspections/
│   ├── invoices/
│   ├── leads/
│   ├── notifications/
│   ├── payments/
│   ├── platform_audit/
│   ├── platform_calendar/
│   ├── platform_core/
│   ├── platform_documents/
│   ├── platform_email/
│   ├── platform_notifications/
│   ├── platform_payments/
│   ├── platform_plans/
│   ├── platform_subscriptions/
│   ├── platform_users/
│   ├── projects/
│   ├── reports/
│   ├── supervision/
│   └── system_monitor/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── company_urls.py
│   ├── asgi.py
│   └── wsgi.py
├── templates/
│   └── layouts/
│       └── base.html
├── manage.py
└── requirements.txt
```

---

## 6. Distribución de rutas

El archivo principal de rutas es:

```txt
backend/config/urls.py
```

El sistema tiene rutas globales y rutas por empresa.

Ejemplo de rutas globales:

```txt
/crm/dashboard/
/crm/companies/
/crm/plans/
/crm/subscriptions/
/crm/documents/
/crm/payments/
/crm/calendar/
/crm/platform-email/
/crm/notifications/
/crm/audit/
/crm/platform-users/
```

Ejemplo de rutas por empresa:

```txt
/<slug:company_slug>/dashboard/
/<slug:company_slug>/clients/
/<slug:company_slug>/leads/
/<slug:company_slug>/projects/
/<slug:company_slug>/inspections/
/<slug:company_slug>/estimates/
/<slug:company_slug>/invoices/
/<slug:company_slug>/payments/
/<slug:company_slug>/contracts/
/<slug:company_slug>/reports/
```

Las rutas por empresa se concentran en:

```txt
backend/config/company_urls.py
```

---

## 7. Middleware de distribución por empresa

Archivo:

```txt
backend/apps/platform_core/middleware.py
```

El middleware se encarga de:

- Detectar si la ruta usa `company_slug`.
- Validar que la empresa exista.
- Validar que el usuario pertenece a esa empresa.
- Redirigir al usuario a su empresa correcta si intenta entrar a otra.
- Validar si la empresa tiene acceso activo.
- Bloquear el workspace si la suscripción está vencida o suspendida.
- Redirigir rutas legacy como `/clients/` hacia `/{company_slug}/clients/`.
- Permitir rutas globales como `/crm/`, `/login/`, `/system-monitor/`, `/dashboard-metrics/`.

Ejemplo:

```txt
/clients/
```

Puede redirigirse automáticamente a:

```txt
/roofex2/clients/
```

---

## 8. Tipos de usuario

El sistema maneja cuatro tipos principales de usuarios.

---

## 8.1 Superuser

Es el usuario raíz de Django y de la plataforma.

Tiene:

```txt
is_superuser=True
is_staff=True
```

Puede acceder a todo:

```txt
/crm/dashboard/
/crm/companies/
/crm/platform-users/
/crm/payments/
/crm/audit/
/system-monitor/
```

Uso recomendado:

- Crear la plataforma.
- Crear empresas.
- Crear usuarios internos.
- Asignar permisos.
- Revisar pagos y auditoría.
- Administrar módulos sensibles.

---

## 8.2 Platform Staff

Es un usuario interno de CEO MARKETING, pero no es superuser.

Tiene:

```txt
is_superuser=False
is_staff=True
id_company=CEO MARKETING
```

Este usuario puede tener permisos específicos.

Ejemplo:

```txt
Puede ver Companies.
Puede ver Platform Documents.
Puede ver Platform Calendar.
No puede ver Platform Payments.
No puede ver Platform Audit.
```

Estos permisos se administran desde:

```txt
/crm/platform-users/
```

---

## 8.3 Company Owner

Es el usuario principal de una empresa cliente.

Ejemplo:

```txt
owner@roofex.com
```

Accede a:

```txt
/roofex2/dashboard/
```

No debe acceder a:

```txt
/crm/dashboard/
```

Su información está limitada por:

```txt
id_company
company.slug
```

---

## 8.4 Company Staff

Son usuarios internos de cada empresa cliente.

Pueden acceder al mini CRM de la empresa según los permisos de su rol.

Ejemplo:

```txt
/roofex2/clients/
/roofex2/projects/
/roofex2/invoices/
```

---

## 9. Platform Users y permisos directos

Uno de los cambios importantes realizados fue separar los usuarios internos de plataforma en un módulo propio:

```txt
backend/apps/platform_users/
```

Ruta:

```txt
/crm/platform-users/
```

Este módulo permite crear usuarios internos para CEO MARKETING sin convertirlos en superuser.

Antes, el sistema dependía demasiado de `is_superuser`. Eso provocaba que un desarrollador interno tuviera acceso total si se marcaba como superuser.

Ahora la lógica correcta es:

```txt
Superuser:
Acceso total.

Platform Staff:
Acceso según permisos asignados.

Company User:
Acceso solo a su empresa.
```

---

## 10. Permisos de Platform Users

Los permisos platform se asignan directamente al crear o editar un usuario interno.

Acciones disponibles:

```txt
View
Create
Edit
Delete
Approve
```

Módulos platform disponibles:

```txt
CRM Admin Dashboard
Companies
Platform Plans
Subscriptions
Platform Documents
Platform Payments
Platform Calendar
Platform Email
Platform Notifications
Platform Audit
Resources Dashboard
System Monitor
```

Ejemplo de caso real:

Un desarrollador interno puede tener:

```txt
CRM Admin Dashboard: View
Companies: View, Create, Edit
Platform Plans: View, Create, Edit
Subscriptions: View, Create, Edit
Platform Documents: View, Create, Edit
Platform Payments: Sin permisos
Platform Calendar: View
Platform Email: View
Platform Notifications: View
Platform Audit: View
System Monitor: View
```

Así el usuario puede trabajar en la plataforma sin tener acceso al módulo de pagos.

---

## 11. Significado de Approve

El permiso `Approve` está preparado para flujos donde una acción necesita aprobación.

Actualmente puede servir para casos futuros como:

```txt
Aprobar pagos.
Aprobar documentos.
Aprobar cambios sensibles.
Aprobar activación o suspensión.
Aprobar renovaciones.
Aprobar acciones administrativas.
```

Aunque no todos los módulos lo usan todavía, se dejó preparado para crecimiento del sistema.

---

## 12. Pantalla 403 Forbidden

Se agregó el manejo de acceso denegado para usuarios que intentan entrar a módulos sin permisos.

Casos donde debe aparecer 403:

```txt
Un platform staff intenta entrar a Platform Payments sin permiso.
Un platform staff intenta entrar a Platform Audit sin permiso.
Un company user intenta entrar a un módulo no permitido.
Un usuario intenta entrar a rutas administrativas sin acceso.
```

La idea es evitar errores feos del sistema y mostrar una pantalla clara de acceso denegado.

---

## 13. Redirección después del login

Archivo:

```txt
backend/apps/core/redirects.py
```

Función principal:

```python
get_user_dashboard_url(user)
```

La redirección se maneja así:

```txt
Superuser:
    /crm/dashboard/

Platform Staff:
    /crm/dashboard/

Company User:
    /{company_slug}/dashboard/

Usuario sin empresa:
    /account-suspended/
```

Esto soluciona errores como:

```txt
NoReverseMatch for dashboard_home
```

Porque ahora el sistema sabe si debe enviar al usuario al dashboard global o al dashboard de empresa.

---

## 14. Módulo Platform Core

Ruta:

```txt
/crm/dashboard/
```

Archivo principal:

```txt
backend/apps/platform_core/views.py
```

Función:

- Dashboard administrativo global.
- Métricas de empresas.
- Métricas de suscripciones.
- Métricas de documentos.
- Métricas de pagos.
- Accesos rápidos.
- Próximas renovaciones.
- Separación clara entre plataforma y operaciones de empresa.

---

## 15. Módulo Companies

Ruta:

```txt
/crm/companies/
```

Función:

- Crear empresas.
- Editar empresas.
- Activar empresas.
- Desactivar empresas.
- Ver owner.
- Ver suscripciones.
- Ver documentos platform.
- Ver pagos platform.
- Hacer onboarding de empresa con owner y suscripción.

Este módulo es central porque de aquí nace el workspace del cliente.

Ejemplo:

```txt
Company Name: Roofex2
Slug: roofex2
Workspace: /roofex2/dashboard/
```

---

## 16. Módulo Platform Plans

Ruta:

```txt
/crm/plans/
```

Función:

- Crear planes SaaS.
- Definir precio.
- Definir ciclo de facturación.
- Definir límite máximo de usuarios.
- Activar o desactivar planes.

Campos principales:

```txt
Plan Name
Plan Code
Description
Price
Billing Cycle
Maximum Users
Status
```

Los planes no controlan módulos operativos. Los módulos se controlan por configuración de empresa y permisos.

---

## 17. Módulo Platform Subscriptions

Ruta:

```txt
/crm/subscriptions/
```

Función:

- Conectar una empresa con un plan.
- Definir fecha de inicio.
- Definir fecha de renovación.
- Definir fecha de finalización.
- Controlar estado de acceso.

Estados:

```txt
Trial
Active
Expired
Suspended
Canceled
```

Este módulo es clave porque el middleware usa la suscripción para permitir o bloquear el acceso de la empresa al mini CRM.

---

## 18. Lógica de acceso por suscripción

Archivo:

```txt
backend/apps/platform_subscriptions/services.py
```

Funciones principales:

```txt
subscription_is_date_current
sync_subscription_status
company_has_current_subscription
sync_company_access
sync_all_platform_subscriptions
```

Regla general:

```txt
Si la empresa tiene una suscripción trial o active con fecha válida:
    Puede acceder al mini CRM.

Si la suscripción está expired, suspended o canceled:
    La empresa queda inactive.
    El usuario es redirigido a account suspended.
```

Ruta de suspensión:

```txt
/account-suspended/
```

---

## 19. Módulo Platform Documents

Ruta:

```txt
/crm/documents/
```

Función:

- Crear proformas.
- Crear invoices.
- Agregar line items.
- Calcular subtotal.
- Calcular tax.
- Calcular descuento.
- Calcular total.
- Imprimir o guardar PDF desde navegador.
- Enviar por email.
- Generar invoice desde proforma pagada.

Tipos:

```txt
Proforma
Invoice
```

Estados:

```txt
Draft
Sent
Paid
Void
Overdue
```

Flujo recomendado:

```txt
1. Crear proforma.
2. Agregar items.
3. Enviar al cliente.
4. Registrar pago.
5. Marcar pago como paid.
6. Proforma pasa a paid.
7. Generar invoice desde proforma pagada.
```

---

## 20. Módulo Platform Payments

Ruta:

```txt
/crm/payments/
```

Función:

- Registrar pagos SaaS que las empresas realizan a CEO MARKETING.
- Conectar pago con empresa.
- Conectar pago con suscripción.
- Conectar pago con documento SaaS.
- Marcar pago como paid.
- Anular pago.
- Exportar CSV.

Estados:

```txt
Pending
Paid
Failed
Refunded
Void
```

Métodos:

```txt
Manual
Bank Transfer
Zelle
Card
Cash
Other
```

Importante:

```txt
/crm/payments/ = pagos SaaS hacia CEO MARKETING.
/{company_slug}/payments/ = pagos operativos internos de la empresa cliente.
```

No se deben mezclar.

---

## 21. Módulo Platform Calendar

Ruta:

```txt
/crm/calendar/
```

Función:

- Ver calendario interno de CEO MARKETING.
- Ver renovaciones.
- Crear eventos manuales.
- Filtrar por mes.
- Filtrar por tipo.
- Filtrar por búsqueda.

Puede mostrar eventos automáticos relacionados con renovaciones.

---

## 22. Módulo Platform Email

Ruta:

```txt
/crm/platform-email/
```

Función:

- Enviar correos desde configuración SMTP de plataforma.
- Guardar logs.
- Probar salida de correos.
- Enviar documentos SaaS por email.

Configuración relacionada:

```txt
PLATFORM_EMAIL_BACKEND
PLATFORM_EMAIL_HOST
PLATFORM_EMAIL_PORT
PLATFORM_EMAIL_HOST_USER
PLATFORM_EMAIL_HOST_PASSWORD
PLATFORM_DEFAULT_FROM_EMAIL
```

---

## 23. Módulo Platform Notifications

Ruta:

```txt
/crm/notifications/
```

Función:

- Ver logs de notificaciones.
- Enviar recordatorios de renovación.
- Controlar notificaciones enviadas, fallidas y pendientes.

Comando:

```bash
docker compose exec backend python manage.py send_platform_notifications --days-before 5
```

---

## 24. Módulo Platform Audit

Ruta:

```txt
/crm/audit/
```

Función:

- Registrar acciones importantes.
- Ver quién hizo un cambio.
- Ver qué módulo fue afectado.
- Ver fecha, IP, usuario y descripción.
- Guardar metadata de acciones sensibles.

Ejemplos de acciones:

```txt
Company created
Company updated
Company activated
Company deactivated
Payment created
Payment marked as paid
Document created
Platform user updated
```

---

## 25. Módulo System Monitor

Ruta:

```txt
/system-monitor/
```

Función:

- Ver estado técnico del sistema.
- Revisar recursos.
- Revisar datos de monitoreo.
- Permitir vista global para superuser.
- Permitir vista según permisos para platform staff.

---

## 26. Módulo Dashboard Metrics

Ruta:

```txt
/dashboard-metrics/
```

Función:

- Revisar métricas generales.
- Consultar recursos.
- Usar como panel técnico complementario.

---

## 27. Módulos del mini CRM por empresa

Cada empresa tiene estos módulos disponibles en su workspace:

```txt
/{company_slug}/dashboard/
/{company_slug}/clients/
/{company_slug}/leads/
/{company_slug}/projects/
/{company_slug}/employees/
/{company_slug}/inspections/
/{company_slug}/evidence/
/{company_slug}/supervision/
/{company_slug}/calendar/
/{company_slug}/estimates/
/{company_slug}/invoices/
/{company_slug}/payments/
/{company_slug}/contracts/
/{company_slug}/reports/
```

Cada registro debe pertenecer a la empresa mediante:

```txt
id_company
```

---

## 28. Separación de datos por empresa

La separación se hace con `id_company`.

Ejemplo:

```txt
Client.id_company
Lead.id_company
Project.id_company
Estimate.id_company
Invoice.id_company
Payment.id_company
Employee.id_company
```

El sistema debe filtrar automáticamente según el usuario autenticado.

Si un usuario pertenece a `Roofex2`, solo debe ver registros de `Roofex2`.

---

## 29. Sidebar actualizado

Se actualizó el sidebar principal en:

```txt
backend/templates/layouts/base.html
```

Ahora muestra opciones diferentes según el tipo de usuario.

Para superuser:

```txt
CRM Admin Dashboard
Platform Users
Companies
Platform Plans
Subscriptions
Platform Documents
Platform Payments
Platform Calendar
Platform Email
Platform Notifications
Platform Audit
Resources Dashboard
System Monitor
```

Para platform staff:

Debe mostrar únicamente los módulos permitidos.

Para company user:

```txt
Dashboard
Clients
Leads
Projects
Inspections
Estimates
Invoices
Payments
Calendar
Users
Employees
Reports
```

---

## 30. Cambios recientes realizados en el trabajo

Durante esta etapa se trabajaron los siguientes puntos principales:

---

### 30.1 Corrección del concepto de URL por empresa

Se definió que la URL del cliente debe ser generada por slug:

```txt
/{company_slug}/dashboard/
```

No por un campo manual de website.

Ejemplo:

```txt
Roofex2 -> /roofex2/dashboard/
Roofex LLC -> /roofex-llc/dashboard/
```

---

### 30.2 Corrección de redirección al login

Se corrigió el problema donde el sistema intentaba hacer reverse a `dashboard_home` sin `company_slug`.

Ahora se usa:

```txt
get_user_dashboard_url(user)
```

Esto permite redirigir correctamente:

```txt
Superuser -> /crm/dashboard/
Platform Staff -> /crm/dashboard/
Company User -> /{company_slug}/dashboard/
```

---

### 30.3 Corrección del dashboard por empresa

Se ajustó la lógica del dashboard para trabajar con rutas por slug:

```txt
/{company_slug}/dashboard/
```

Y evitar errores de rutas sin argumentos.

---

### 30.4 Corrección de errores por campos inexistentes

Se detectaron errores como:

```txt
Cannot resolve keyword 'created_at'
```

Esto pasa cuando un modelo no tiene ese campo.

Se corrigió la lógica para usar campos reales del modelo como:

```txt
issue_date
id_estimate
id_invoice
id_project
```

según cada caso.

---

### 30.5 Implementación de Platform Payments

Se trabajó el módulo de pagos SaaS:

```txt
backend/apps/platform_payments/
```

Incluye:

```txt
Model
Choices
Forms
Views
Services
URLs
Templates
CSV Export
Mark Paid
Void Payment
Sync Document Status
```

---

### 30.6 Implementación de Platform Subscriptions

Se trabajó el módulo de suscripciones:

```txt
backend/apps/platform_subscriptions/
```

Incluye:

```txt
Model
Choices
Forms
Views
Services
URLs
Templates
Access Sync
Company Status Sync
Renewal Validation
```

---

### 30.7 Implementación de Platform Documents

Se trabajó el módulo de documentos SaaS:

```txt
backend/apps/platform_documents/
```

Incluye:

```txt
Proformas
Invoices
Line Items
Totals
Tax
Discount
Print View
Email Send View
Generate Invoice from Paid Proforma
CSV Export
```

---

### 30.8 Implementación de Platform Plans

Se trabajó el módulo de planes SaaS:

```txt
backend/apps/platform_plans/
```

Incluye:

```txt
Plan Name
Plan Code
Price
Billing Cycle
Max Users
Status
List
Detail
Create
Update
```

---

### 30.9 Implementación y ajuste de Platform Core

Se trabajó el dashboard global:

```txt
backend/apps/platform_core/
```

Incluye:

```txt
CRM Admin Dashboard
Smart Home Redirect
Account Suspended View
Subscription Middleware
Global Metrics
```

---

### 30.10 Implementación de Platform Users

Se agregó un módulo separado:

```txt
backend/apps/platform_users/
```

Este fue un cambio importante porque permite crear usuarios internos de CEO MARKETING sin hacerlos superuser.

Incluye:

```txt
Platform User List
Platform User Create
Platform User Edit
Platform User Detail
Direct Permissions
Permission Matrix
Internal Platform Company
```

---

### 30.11 Cambio de roles a permisos directos

Se concluyó que para platform staff era mejor asignar permisos directamente al usuario al momento de crearlo o editarlo.

Esto evita confusión entre:

```txt
Rol
Permiso
Superuser
Platform staff
Company staff
```

La idea final:

```txt
Superuser crea Platform User.
Superuser marca permisos.
Platform User ve solo lo permitido.
```

---

### 30.12 Implementación de 403 Forbidden

Se agregó pantalla y lógica para bloquear acceso cuando no existe permiso.

Ejemplo:

```txt
Usuario sin permiso para Platform Payments
-> 403 Forbidden
```

---

### 30.13 Corrección de acceso para módulos platform

Se revisaron módulos que todavía dependían solo de:

```txt
user_is_global_admin(user)
```

y se empezó a adaptar la lógica para aceptar:

```txt
superuser
platform staff con permiso
```

Módulos revisados:

```txt
Platform Email
Platform Notifications
Platform Audit
Companies
System Monitor
```

---

## 31. Variables de entorno

Ejemplo de `.env`:

```env
SECRET_KEY=dev-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,backend

POSTGRES_DB=crm_saas
POSTGRES_USER=crm_user
POSTGRES_PASSWORD=crm_password
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_CONN_MAX_AGE=60

TIME_ZONE=UTC

JWT_ACCESS_HOURS=8
JWT_REFRESH_DAYS=7

CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

PLATFORM_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
PLATFORM_EMAIL_HOST=
PLATFORM_EMAIL_PORT=587
PLATFORM_EMAIL_HOST_USER=
PLATFORM_EMAIL_HOST_PASSWORD=
PLATFORM_EMAIL_USE_TLS=True
PLATFORM_EMAIL_USE_SSL=False
PLATFORM_DEFAULT_FROM_EMAIL=CEO Marketing CRM <noreply@ceomarketingusa.com>

EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=False
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=webmaster@localhost
```

---

## 32. Instalación con Docker

Levantar el proyecto:

```bash
docker compose up -d --build
```

Ver logs:

```bash
docker compose logs -f backend
```

Entrar al contenedor backend:

```bash
docker compose exec backend sh
```

---

## 33. Migraciones

Crear migraciones:

```bash
docker compose exec backend python manage.py makemigrations
```

Crear migraciones de una app específica:

```bash
docker compose exec backend python manage.py makemigrations platform_users
```

Aplicar migraciones:

```bash
docker compose exec backend python manage.py migrate
```

Ver migraciones:

```bash
docker compose exec backend python manage.py showmigrations
```

---

## 34. Crear superuser

```bash
docker compose exec backend python manage.py createsuperuser
```

Luego entrar en:

```txt
/login/
```

El superuser debe ir a:

```txt
/crm/dashboard/
```

---

## 35. Comandos útiles

Revisar configuración:

```bash
docker compose exec backend python manage.py check
```

Crear migraciones:

```bash
docker compose exec backend python manage.py makemigrations
```

Aplicar migraciones:

```bash
docker compose exec backend python manage.py migrate
```

Crear superuser:

```bash
docker compose exec backend python manage.py createsuperuser
```

Entrar al shell:

```bash
docker compose exec backend python manage.py shell
```

Enviar notificaciones de suscripción:

```bash
docker compose exec backend python manage.py send_platform_notifications --days-before 5
```

Recolectar estáticos:

```bash
docker compose exec backend python manage.py collectstatic --noinput
```

---

## 36. Flujo de prueba recomendado

---

### 36.1 Probar como superuser

```txt
1. Iniciar sesión como superuser.
2. Entrar a /crm/dashboard/.
3. Ver Companies.
4. Ver Platform Users.
5. Ver Platform Plans.
6. Ver Subscriptions.
7. Ver Platform Documents.
8. Ver Platform Payments.
9. Ver Platform Calendar.
10. Ver Platform Audit.
11. Ver System Monitor.
```

---

### 36.2 Probar Platform User con permisos totales

```txt
1. Entrar como superuser.
2. Ir a /crm/platform-users/create/.
3. Crear usuario devtest.
4. Marcar permisos de View, Create, Edit, Delete y Approve.
5. Guardar.
6. Cerrar sesión.
7. Entrar como devtest.
8. Confirmar que entra a /crm/dashboard/.
9. Confirmar que ve todos los módulos permitidos.
```

---

### 36.3 Probar Platform User limitado

```txt
1. Crear otro platform user.
2. Dar acceso a Dashboard, Companies y Documents.
3. No dar acceso a Platform Payments.
4. Entrar con ese usuario.
5. Confirmar que no ve Platform Payments.
6. Intentar entrar manualmente a /crm/payments/.
7. Confirmar 403 Forbidden.
```

---

### 36.4 Probar Company Owner

```txt
1. Crear empresa desde onboarding.
2. Crear owner.
3. Cerrar sesión.
4. Entrar como owner.
5. Confirmar redirección a /{company_slug}/dashboard/.
6. Crear cliente.
7. Crear proyecto.
8. Confirmar que no puede entrar a /crm/dashboard/.
```

---

### 36.5 Probar suspensión de empresa

```txt
1. Crear empresa con suscripción.
2. Cambiar renewal_date a fecha vencida.
3. Iniciar sesión como owner.
4. Confirmar redirección a /account-suspended/.
```

---

## 37. Errores comunes y soluciones

---

### 37.1 Python no encontrado en Windows

Error:

```txt
Python was not found
```

Solución:

Usar Docker:

```bash
docker compose exec backend python manage.py migrate
```

No usar directamente:

```bash
python manage.py migrate
```

si el proyecto está corriendo dentro del contenedor.

---

### 37.2 NoReverseMatch con dashboard_home

Error:

```txt
Reverse for 'dashboard_home' with no arguments not found
```

Causa:

El dashboard por empresa necesita `company_slug`.

Solución:

Usar:

```python
get_user_dashboard_url(user)
```

---

### 37.3 FieldError con created_at

Error:

```txt
Cannot resolve keyword 'created_at' into field
```

Causa:

El modelo consultado no tiene campo `created_at`.

Solución:

Usar un campo real del modelo.

Ejemplo:

```txt
issue_date
payment_date
id_estimate
id_invoice
```

---

### 37.4 Migraciones pendientes

Mensaje:

```txt
Your models in app(s) have changes that are not yet reflected in a migration.
```

Solución:

```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
```

---

## 38. Seguridad del sistema

El sistema aplica:

```txt
LoginRequiredMixin
UserPassesTestMixin
Permisos por módulo
Separación por id_company
Validación por company_slug
Middleware de suscripción
Pantalla 403
Cuenta suspendida
Protección CSRF
Contraseñas hasheadas por Django
```

La seguridad se divide en:

```txt
Platform Access
Company Access
Module Permission
Subscription Access
Object Company Ownership
```

---

## 39. Diferencia entre pagos SaaS y pagos operativos

Es importante no mezclar estos dos contextos.

Pagos SaaS:

```txt
/crm/payments/
```

Son pagos de empresas hacia CEO MARKETING.

Pagos operativos:

```txt
/{company_slug}/payments/
```

Son pagos de clientes finales hacia la empresa cliente.

Ejemplo:

```txt
Roofex paga a CEO MARKETING por usar el CRM -> /crm/payments/
Cliente de Roofex paga una factura de roofing -> /roofex2/payments/
```

---

## 40. Diferencia entre documentos SaaS y facturas operativas

Documentos SaaS:

```txt
/crm/documents/
```

Son proformas e invoices de CEO MARKETING hacia las empresas.

Facturas operativas:

```txt
/{company_slug}/invoices/
```

Son facturas que la empresa cliente crea para sus propios clientes.

---

## 41. Estado actual del proyecto

El sistema ya cuenta con la base principal para funcionar como CRM SaaS multiempresa.

Módulos trabajados o integrados:

```txt
Platform Core
Platform Users
Platform Permissions
Platform Plans
Platform Subscriptions
Platform Documents
Platform Payments
Platform Calendar
Platform Email
Platform Notifications
Platform Audit
Companies
Company Onboarding
Company Workspace Routing
Dashboard
Clients
Leads
Projects
Employees
Inspections
Evidence
Supervision
Estimates
Invoices
Payments
Contracts
Reports
System Monitor
Dashboard Metrics
403 Forbidden
Account Suspended
```

---

## 42. Pendientes recomendados

Aunque la base principal ya está bastante completa, se recomienda revisar estos puntos antes de producción:

```txt
1. Terminar pruebas manuales de todos los módulos.
2. Revisar permisos de cada vista platform.
3. Revisar permisos de cada vista company.
4. Validar que el sidebar oculte módulos no permitidos.
5. Validar 403 en rutas directas.
6. Agregar tests unitarios.
7. Agregar tests de integración.
8. Crear seed inicial de planes.
9. Crear seed inicial de permisos platform.
10. Automatizar notificaciones con Celery beat.
11. Agregar backups automáticos de PostgreSQL.
12. Revisar configuración real SMTP.
13. Configurar variables de entorno para producción.
14. Revisar seguridad de DEBUG=False.
15. Configurar ALLOWED_HOSTS de producción.
16. Revisar archivos media y static.
17. Preparar documentación técnica por módulo.
18. Preparar manual de usuario para CEO MARKETING.
19. Preparar manual de usuario para empresas cliente.
```

---

## 43. Producción

Antes de producción, se recomienda:

```txt
DEBUG=False
SECRET_KEY segura
ALLOWED_HOSTS configurado
Base de datos PostgreSQL segura
Backups automáticos
SMTP real configurado
Static files configurados
Media files configurados
SSL activo
Logs activos
Permisos revisados
Superuser protegido
Usuarios platform sin permisos innecesarios
```

---

## 44. Resumen final

Este proyecto funciona como una base SaaS para entregar mini CRM a empresas clientes.

La lógica central es:

```txt
CEO MARKETING administra la plataforma desde /crm/.
Cada empresa accede a su mini CRM desde /{company_slug}/.
Los datos se separan por id_company.
Los accesos se controlan por suscripción.
Los usuarios internos se controlan con Platform Users.
Los permisos se asignan por módulo y acción.
Los errores de acceso se controlan con 403 Forbidden.
```

El sistema ya tiene una arquitectura clara para seguir creciendo con nuevos módulos, automatizaciones, reportes, dashboards, exportaciones y controles administrativos.