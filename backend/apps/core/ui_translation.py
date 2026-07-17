"""Central Spanish UI translation helpers for the legacy company CRM.

The project contains a large number of legacy templates whose visible labels were
written directly in English.  This module provides a safe compatibility layer:
only source-code UI literals are translated. Values rendered from normal
variables (client names, notes, addresses, company names, etc.) are not passed
through this translator unless the template explicitly marks them as UI labels.
"""

from __future__ import annotations

import re
from typing import Any

from django.utils.translation import get_language


EXACT_ES = {
    # Navigation / scope
    "Guest": "Invitado",
    "Global SaaS Admin": "Administrador global SaaS",
    "No Company Assigned": "Sin empresa asignada",
    "Dashboard": "Panel principal",
    "Customers": "Clientes",
    "Clients": "Clientes",
    "Leads": "Prospectos",
    "Opportunities": "Oportunidades",
    "Calendar Events": "Eventos del calendario",
    "Projects": "Proyectos",
    "Inspections": "Inspecciones",
    "Evidence": "Evidencias",
    "Supervision": "Supervisión",
    "Documents": "Documentos",
    "Estimates": "Proformas",
    "Contracts": "Contratos",
    "Finance": "Finanzas",
    "Invoices": "Facturas",
    "Payments": "Pagos",
    "Financial Summary": "Resumen financiero",
    "Reports": "Reportes",
    "Suppliers": "Proveedores",
    "Products": "Productos",
    "Purchases": "Compras",
    "Administration": "Administración",
    "Employees": "Empleados",
    "Users": "Usuarios",
    "Employees & Users": "Empleados y usuarios",
    "Employee & User Details": "Detalle del empleado y usuario",
    "Create Employee & User": "Crear empleado y usuario",
    "Edit Employee & User": "Editar empleado y usuario",
    "Roles": "Roles",
    "User Activities": "Actividades de usuarios",
    "Email Settings": "Configuración de correo",
    "Notifications": "Notificaciones",
    "System": "Sistema",
    "System Logs": "Registros del sistema",
    "Django Admin": "Administración de Django",
    "Integrations": "Integraciones",
    "Calendar / Meet": "Calendario / Meet",
    "Google Drive": "Google Drive",
    "Google Analytics": "Google Analytics",
    "Sync Logs": "Registros de sincronización",
    "Company Settings": "Configuración de la empresa",
    "Settings": "Configuración",
    # Common actions
    "Actions": "Acciones",
    "Action": "Acción",
    "Create": "Crear",
    "Add": "Agregar",
    "Edit": "Editar",
    "Update": "Actualizar",
    "Save": "Guardar",
    "Save Changes": "Guardar cambios",
    "Delete": "Eliminar",
    "Cancel": "Cancelar",
    "Close": "Cerrar",
    "Back": "Volver",
    "Next": "Siguiente",
    "Previous": "Anterior",
    "Search": "Buscar",
    "Filter": "Filtrar",
    "Clear": "Limpiar",
    "Apply": "Aplicar",
    "Confirm": "Confirmar",
    "Continue": "Continuar",
    "View": "Ver",
    "Detail": "Detalle",
    "Details": "Detalles",
    "Download": "Descargar",
    "Download PDF": "Descargar PDF",
    "Upload": "Subir",
    "Choose file": "Seleccionar archivo",
    "No file chosen": "Ningún archivo seleccionado",
    "Send": "Enviar",
    "Resend": "Reenviar",
    "Connect": "Conectar",
    "Disconnect": "Desconectar",
    "Activate": "Activar",
    "Deactivate": "Desactivar",
    "Archive": "Archivar",
    "Approve": "Aprobar",
    "Reject": "Rechazar",
    "Convert": "Convertir",
    "Copy Link": "Copiar enlace",
    "Open": "Abrir",
    "Logout": "Cerrar sesión",
    "Login": "Iniciar sesión",
    "Change Password": "Cambiar contraseña",
    "Reset Password": "Restablecer contraseña",
    # Common labels
    "Name": "Nombre",
    "First Name": "Nombre",
    "Middle Name": "Segundo nombre",
    "Last Name": "Apellido",
    "Email": "Correo electrónico",
    "Phone": "Teléfono",
    "Alternate Phone": "Teléfono alternativo",
    "Address": "Dirección",
    "City": "Ciudad",
    "State": "Estado",
    "Country": "País",
    "Zip Code": "Código postal",
    "Description": "Descripción",
    "Notes": "Notas",
    "Status": "Estado",
    "Type": "Tipo",
    "Category": "Categoría",
    "Position": "Cargo",
    "Position / Category": "Cargo / categoría",
    "DNI": "DNI",
    "DNI / Identification": "DNI / identificación",
    "Hire Date": "Fecha de ingreso",
    "Automatic Hire Date": "Fecha de ingreso automática",
    "Date": "Fecha",
    "Start Date": "Fecha de inicio",
    "End Date": "Fecha de finalización",
    "Due Date": "Fecha de vencimiento",
    "Issue Date": "Fecha de emisión",
    "Expiration Date": "Fecha de expiración",
    "Created At": "Creado el",
    "Updated At": "Actualizado el",
    "Last Modified": "Última modificación",
    "Created": "Creado",
    "Modified": "Modificado",
    "Assigned User": "Usuario asignado",
    "Assigned Users": "Usuarios asignados",
    "Company": "Empresa",
    "Company Name": "Nombre de la empresa",
    "Client": "Cliente",
    "Customer": "Cliente",
    "Project": "Proyecto",
    "Employee": "Empleado",
    "Supplier": "Proveedor",
    "Product": "Producto",
    "Contract": "Contrato",
    "Estimate": "Proforma",
    "Invoice": "Factura",
    "Payment": "Pago",
    "Amount": "Monto",
    "Subtotal": "Subtotal",
    "Total": "Total",
    "Tax": "Impuesto",
    "Discount": "Descuento",
    "Balance": "Saldo",
    "Balance Due": "Saldo pendiente",
    "Pending Balance": "Saldo pendiente",
    "Credit": "Crédito",
    "Client Credit": "Crédito del cliente",
    "Quantity": "Cantidad",
    "Unit Price": "Precio unitario",
    "Line Total": "Total de línea",
    "Method": "Método",
    "Reference": "Referencia",
    "Voucher": "Comprobante",
    "Password": "Contraseña",
    "Confirm Password": "Confirmar contraseña",
    "New Password": "Nueva contraseña",
    "Current Password": "Contraseña actual",
    "Role": "Rol",
    "Permissions": "Permisos",
    "Module": "Módulo",
    "Access": "Acceso",
    "Location": "Ubicación",
    "Attendees": "Asistentes",
    "Message": "Mensaje",
    "Channel": "Canal",
    "File": "Archivo",
    "Photo": "Foto",
    "Photos": "Fotos",
    "Items": "Ítems",
    # Statuses
    "Active": "Activo",
    "Inactive": "Inactivo",
    "Enabled": "Habilitado",
    "Disabled": "Deshabilitado",
    "Pending": "Pendiente",
    "Completed": "Completado",
    "Cancelled": "Cancelado",
    "Canceled": "Cancelado",
    "Approved": "Aprobado",
    "Rejected": "Rechazado",
    "Draft": "Borrador",
    "Sent": "Enviado",
    "Paid": "Pagado",
    "Unpaid": "No pagado",
    "Partial": "Parcial",
    "Void": "Anulado",
    "Voided": "Anulado",
    "Converted": "Convertido",
    "Archived": "Archivado",
    "Open": "Abierto",
    "Closed": "Cerrado",
    "In Progress": "En progreso",
    "New": "Nuevo",
    "Lost": "Perdido",
    "Contacted": "Contactado",
    "Booked": "Agendado",
    "Confirmed": "Confirmado",
    "Assigned": "Asignado",
    "Linked": "Vinculado",
    "Not connected": "No conectado",
    "Configured": "Configurado",
    "Never": "Nunca",
    "Yes": "Sí",
    "No": "No",
    "All": "Todos",
    "None": "Ninguno",
    "Other": "Otro",
    # Specific screens / phrases
    "Basic Information": "Información básica",
    "Company Information": "Información de la empresa",
    "Client Information": "Información del cliente",
    "Project Information": "Información del proyecto",
    "Employee Information": "Información del empleado",
    "Invoice Information": "Información de la factura",
    "Payment Details": "Detalles del pago",
    "Estimate Details": "Detalles de la proforma",
    "Contract Information": "Información del contrato",
    "Lead Information": "Información del prospecto",
    "Opportunity Information": "Información de la oportunidad",
    "Inspection Information": "Información de la inspección",
    "Calendar Event Information": "Información del evento de calendario",
    "Billing Address": "Dirección de facturación",
    "Billing Name": "Nombre de facturación",
    "Billing Email": "Correo de facturación",
    "Billing Phone": "Teléfono de facturación",
    "Customer Information": "Información del cliente",
    "Payment Terms And Conditions": "Términos y condiciones de pago",
    "Terms and Conditions": "Términos y condiciones",
    "Terms": "Términos",
    "Approval": "Aprobación",
    "Signature": "Firma",
    "Customer Signature": "Firma del cliente",
    "Reason": "Motivo",
    "Rejection Reason": "Motivo del rechazo",
    "Void reason": "Motivo de anulación",
    "Void Action": "Acción de anulación",
    "Void record": "Anular registro",
    "Accept Void": "Confirmar anulación",
    "Write the reason for this void action.": "Escriba el motivo de esta anulación.",
    "Please enter the reason for voiding this record.": "Ingrese el motivo para anular este registro.",
    "Please enter the reason for voiding this record. This action is sensitive and must be confirmed.": "Ingrese el motivo para anular este registro. Esta acción es sensible y debe confirmarse.",
    "Permission denied.": "Permiso denegado.",
    "Access Denied": "Acceso denegado",
    "You do not have permission to access this section.": "No tiene permiso para acceder a esta sección.",
    "If you believe this is a mistake, contact the main administrator and request access to this module.": "Si considera que esto es un error, contacte al administrador principal y solicite acceso a este módulo.",
    "Back to Dashboard": "Volver al panel principal",
    "Back to Login": "Volver al inicio de sesión",
    "General overview of the CRM system.": "Resumen general del sistema CRM.",
    "Main navigation": "Navegación principal",
    "Close menu": "Cerrar menú",
    "Open menu": "Abrir menú",
    "Open notifications": "Abrir notificaciones",
    "Current Scope": "Ámbito actual",
    "Current Page": "Página actual",
    "Manage": "Gestionar",
    "Manage Enabled": "Gestión habilitada",
    "Approve Enabled": "Aprobación habilitada",
    "View Only": "Solo lectura",
    "Approve Only": "Solo aprobar",
    "All access": "Acceso total",
    "No data for this filter.": "No hay datos para este filtro.",
    "No records found.": "No se encontraron registros.",
    "No results found.": "No se encontraron resultados.",
    "No notifications yet.": "Aún no hay notificaciones.",
    "No items added.": "No se agregaron ítems.",
    "No file available": "No hay archivo disponible",
    "Not selected": "No seleccionado",
    "Not sent": "No enviado",
    "Not signed": "No firmado",
    "Not generated": "No generado",
    "Not tested yet": "Aún no se ha probado",
    "Required": "Obligatorio",
    "Optional": "Opcional",
    "Search by name, email or phone": "Buscar por nombre, correo o teléfono",
    "Search by name": "Buscar por nombre",
    "Search anything...": "Buscar cualquier cosa...",
    "Select an option": "Seleccione una opción",
    "Select a client": "Seleccione un cliente",
    "Select a project": "Seleccione un proyecto",
    "Select a status": "Seleccione un estado",
    "Select a role": "Seleccione un rol",
    "Select a user": "Seleccione un usuario",
    "Select company": "Seleccione una empresa",
    "Company assignment is automatic. Only password changes are allowed from the edit screen.": "La empresa se asigna automáticamente. Desde la pantalla de edición solo se permiten cambios de contraseña.",
    "Company is linked automatically from your logged-in user. Do not select company manually.": "La empresa se vincula automáticamente desde el usuario autenticado. No seleccione la empresa manualmente.",
    "Only enabled modules are shown for this role.": "Solo se muestran los módulos habilitados para este rol.",
    "If View is unchecked, the module will not appear for users assigned to this role.": "Si Ver está desmarcado, el módulo no aparecerá para los usuarios asignados a este rol.",
    "Modules visible and manageable for this user through the assigned role.": "Módulos visibles y gestionables para este usuario mediante el rol asignado.",
    "Permissions are managed from Role Edit": "Los permisos se administran desde Editar rol",
    "Role & Permissions": "Rol y permisos",
    "Edit Role & Permissions": "Editar rol y permisos",
    "Module Permissions": "Permisos por módulo",
    "Company workspace support": "Soporte del espacio de trabajo de la empresa",
    "Contact Support": "Contactar soporte",
    "Need help?": "¿Necesita ayuda?",
    "Contact CRM support through WhatsApp.": "Contacte al soporte del CRM mediante WhatsApp.",
    "Completed successfully.": "Completado correctamente.",
    "Saved successfully.": "Guardado correctamente.",
    "Updated successfully.": "Actualizado correctamente.",
    "Deleted successfully.": "Eliminado correctamente.",
    "Created successfully.": "Creado correctamente.",
    "Are you sure?": "¿Está seguro?",
    "Confirm Delete": "Confirmar eliminación",
    "Confirm Status Update": "Confirmar actualización de estado",
    "403 Forbidden": "403 Prohibido",
    "404 Not Found": "404 No encontrado",
    "Page Missing": "Página no encontrada",
    "Error 404": "Error 404",
    # Company language settings
    "Language & Region": "Idioma y región",
    "Workspace Language": "Idioma del espacio de trabajo",
    "Default workspace language": "Idioma predeterminado del espacio de trabajo",
    "Choose the language used by all users in this company workspace.": "Seleccione el idioma que usarán todos los usuarios de este espacio de trabajo.",
    "Only the company Owner can change this setting.": "Solo el propietario de la empresa puede cambiar esta configuración.",
    "The change applies immediately after saving.": "El cambio se aplica inmediatamente después de guardar.",
    "English": "Inglés",
    "Español": "Español",
    "Company language updated successfully.": "El idioma de la empresa se actualizó correctamente.",
    "You are not allowed to change company settings.": "No tiene permiso para cambiar la configuración de la empresa.",
    "Language preference": "Preferencia de idioma",
    "Keep routes, IDs and stored business values unchanged.": "Las rutas, identificadores y valores comerciales almacenados se mantienen sin cambios.",
}

# Domain phrases are replaced before the fallback word translator.  Longer
# phrases must appear first.
PHRASE_ES = {
    "customer public contract link": "enlace público del contrato del cliente",
    "customer review link": "enlace de revisión del cliente",
    "google calendar events": "eventos de Google Calendar",
    "google guaranteed": "Google Guaranteed",
    "local services": "Servicios Locales",
    "financial summary": "resumen financiero",
    "system logs": "registros del sistema",
    "user activities": "actividades de usuarios",
    "email settings": "configuración de correo",
    "calendar events": "eventos del calendario",
    "assigned user": "usuario asignado",
    "billing information": "información de facturación",
    "billing snapshot": "resumen de facturación",
    "payment status": "estado del pago",
    "invoice status": "estado de la factura",
    "estimate status": "estado de la proforma",
    "contract status": "estado del contrato",
    "inspection status": "estado de la inspección",
    "project status": "estado del proyecto",
    "lead status": "estado del prospecto",
    "opportunity status": "estado de la oportunidad",
    "date range": "rango de fechas",
    "start time": "hora de inicio",
    "end time": "hora de finalización",
    "last login": "último acceso",
    "last sync": "última sincronización",
    "last error": "último error",
    "last sent": "último envío",
    "public link": "enlace público",
    "open balance": "saldo abierto",
    "pending receivable": "cuenta por cobrar pendiente",
    "available client credit": "crédito disponible del cliente",
    "credit balance": "saldo de crédito",
    "paid amount": "monto pagado",
    "discount amount": "monto de descuento",
    "tax rate": "tasa de impuesto",
    "unit price": "precio unitario",
    "line total": "total de línea",
    "company name": "nombre de la empresa",
    "company address": "dirección de la empresa",
    "company phone": "teléfono de la empresa",
    "company email": "correo de la empresa",
    "client name": "nombre del cliente",
    "client phone": "teléfono del cliente",
    "client code": "código del cliente",
    "project name": "nombre del proyecto",
    "contract number": "número de contrato",
    "invoice number": "número de factura",
    "estimate number": "número de proforma",
    "payment number": "número de pago",
    "inspection date": "fecha de inspección",
    "payment date": "fecha de pago",
    "contract date": "fecha del contrato",
    "issue date": "fecha de emisión",
    "due date": "fecha de vencimiento",
    "created at": "creado el",
    "updated at": "actualizado el",
    "last modified": "última modificación",
    "first name": "nombre",
    "last name": "apellido",
    "middle name": "segundo nombre",
    "zip code": "código postal",
    "tax id": "identificación tributaria",
    "phone number": "número de teléfono",
    "login email": "correo de acceso",
    "temporary password": "contraseña temporal",
    "confirm password": "confirmar contraseña",
    "new password": "nueva contraseña",
    "current password": "contraseña actual",
}

WORD_ES = {
    "a": "un", "an": "un", "the": "el", "and": "y", "or": "o", "of": "de",
    "for": "para", "from": "desde", "to": "a", "with": "con", "without": "sin",
    "in": "en", "on": "en", "by": "por", "before": "antes", "after": "después",
    "only": "solo", "all": "todos", "any": "cualquier", "this": "este", "that": "ese",
    "these": "estos", "those": "esos", "your": "su", "you": "usted", "we": "nosotros",
    "is": "es", "are": "son", "was": "fue", "were": "fueron", "be": "ser", "been": "sido",
    "can": "puede", "cannot": "no puede", "will": "se", "must": "debe", "should": "debería",
    "do": "hacer", "does": "hace", "did": "hizo", "have": "tener", "has": "tiene",
    "add": "agregar", "create": "crear", "edit": "editar", "update": "actualizar",
    "delete": "eliminar", "save": "guardar", "send": "enviar", "select": "seleccionar",
    "choose": "elegir", "open": "abrir", "close": "cerrar", "view": "ver",
    "manage": "gestionar", "approve": "aprobar", "reject": "rechazar", "cancel": "cancelar",
    "confirm": "confirmar", "apply": "aplicar", "convert": "convertir", "link": "vincular",
    "download": "descargar", "upload": "subir", "search": "buscar", "filter": "filtrar",
    "client": "cliente", "clients": "clientes", "customer": "cliente", "customers": "clientes",
    "lead": "prospecto", "leads": "prospectos", "opportunity": "oportunidad", "opportunities": "oportunidades",
    "project": "proyecto", "projects": "proyectos", "inspection": "inspección", "inspections": "inspecciones",
    "estimate": "proforma", "estimates": "proformas", "invoice": "factura", "invoices": "facturas",
    "payment": "pago", "payments": "pagos", "contract": "contrato", "contracts": "contratos",
    "supplier": "proveedor", "suppliers": "proveedores", "product": "producto", "products": "productos",
    "purchase": "compra", "purchases": "compras", "employee": "empleado", "employees": "empleados",
    "user": "usuario", "users": "usuarios", "role": "rol", "roles": "roles",
    "permission": "permiso", "permissions": "permisos", "module": "módulo", "modules": "módulos",
    "company": "empresa", "companies": "empresas", "calendar": "calendario", "event": "evento", "events": "eventos",
    "notification": "notificación", "notifications": "notificaciones", "report": "reporte", "reports": "reportes",
    "evidence": "evidencia", "supervision": "supervisión", "activity": "actividad", "activities": "actividades",
    "information": "información", "details": "detalles", "detail": "detalle", "summary": "resumen",
    "list": "lista", "data": "datos", "record": "registro", "records": "registros",
    "status": "estado", "type": "tipo", "category": "categoría", "source": "origen", "sources": "orígenes",
    "name": "nombre", "email": "correo", "phone": "teléfono", "address": "dirección",
    "city": "ciudad", "state": "estado", "country": "país", "description": "descripción",
    "note": "nota", "notes": "notas", "date": "fecha", "time": "hora", "amount": "monto",
    "total": "total", "balance": "saldo", "credit": "crédito", "tax": "impuesto", "discount": "descuento",
    "item": "ítem", "items": "ítems", "quantity": "cantidad", "price": "precio",
    "active": "activo", "inactive": "inactivo", "pending": "pendiente", "completed": "completado",
    "approved": "aprobado", "rejected": "rechazado", "sent": "enviado", "paid": "pagado",
    "draft": "borrador", "void": "anulado", "enabled": "habilitado", "disabled": "deshabilitado",
    "new": "nuevo", "current": "actual", "available": "disponible", "required": "obligatorio",
    "optional": "opcional", "automatic": "automático", "automatically": "automáticamente",
    "successfully": "correctamente", "found": "encontrado", "assigned": "asignado",
    "no": "no", "yes": "sí", "not": "no", "more": "más", "less": "menos",
    "reason": "motivo", "message": "mensaje", "file": "archivo", "photo": "foto", "photos": "fotos",
    "settings": "configuración", "language": "idioma", "workspace": "espacio de trabajo",
    "welcome": "bienvenido", "please": "por favor", "enter": "ingrese", "write": "escriba",
    "review": "revisar", "below": "a continuación", "above": "arriba", "inside": "dentro",
    "when": "cuando", "where": "donde", "what": "qué", "why": "por qué", "how": "cómo",
    "need": "necesita", "needs": "necesita", "used": "usado", "use": "usar", "using": "usando",
    "show": "mostrar", "shown": "mostrado", "visible": "visible", "available": "disponible",
    "connected": "conectado", "connection": "conexión", "account": "cuenta", "accounts": "cuentas",
    "secure": "seguro", "security": "seguridad", "encrypted": "cifrado", "automatically": "automáticamente",
    "internal": "interno", "external": "externo", "public": "público", "private": "privado",
    "main": "principal", "general": "general", "complete": "completo", "complete": "completar",
    "latest": "más reciente", "recent": "reciente", "scheduled": "programado", "schedule": "programar",
    "task": "tarea", "tasks": "tareas", "assignment": "asignación", "assignments": "asignaciones",
    "responsible": "responsable", "team": "equipo", "workflow": "flujo de trabajo",
    "process": "proceso", "processes": "procesos", "value": "valor", "values": "valores",
    "field": "campo", "fields": "campos", "form": "formulario", "forms": "formularios",
    "support": "soporte", "help": "ayuda", "issue": "problema", "error": "error", "errors": "errores",
    "warning": "advertencia", "success": "éxito", "failed": "fallido", "missing": "faltante",
    "valid": "válido", "invalid": "inválido", "locked": "bloqueado", "generated": "generado",
    "signed": "firmado", "signature": "firma", "terms": "términos", "condition": "condición",
    "conditions": "condiciones", "notice": "aviso", "instructions": "instrucciones",
    "reason": "motivo", "reasons": "motivos", "change": "cambio", "changes": "cambios",
    "same": "mismo", "different": "diferente", "first": "primero", "last": "último",
    "each": "cada", "every": "cada", "one": "uno", "two": "dos", "more": "más",
    "less": "menos", "empty": "vacío", "leave": "deje", "keep": "mantenga",
    "include": "incluir", "includes": "incluye", "included": "incluido",
    "based": "basado", "according": "según", "related": "relacionado", "associated": "asociado",
    "selected": "seleccionado", "linked": "vinculado", "registered": "registrado",
    "remaining": "restante", "pending": "pendiente", "received": "recibido", "sent": "enviado",
    "display": "mostrar", "distribution": "distribución", "overview": "resumen", "dashboard": "panel",
    "chart": "gráfico", "charts": "gráficos", "metric": "métrica", "metrics": "métricas",
    "revenue": "ingresos", "income": "ingresos", "cost": "costo", "clicks": "clics",
    "impressions": "impresiones", "conversions": "conversiones", "source": "origen",
    "folder": "carpeta", "drive": "Drive", "meeting": "reunión", "meetings": "reuniones",
}



# Human-readable English labels for known raw database values.
MACHINE_EN = {
    "active": "Active", "inactive": "Inactive", "enabled": "Enabled", "disabled": "Disabled",
    "pending": "Pending", "pending_send": "Pending Send", "pending_approval": "Pending Approval",
    "pending_payment": "Pending Payment", "pending_review": "Pending Review",
    "in_progress": "In Progress", "completed": "Completed", "cancelled": "Cancelled",
    "canceled": "Canceled", "approved": "Approved", "rejected": "Rejected", "draft": "Draft",
    "generated": "Generated", "sent": "Sent", "viewed": "Viewed", "signed": "Signed",
    "expired": "Expired", "converted": "Converted", "void": "Void", "voided": "Voided",
    "paid": "Paid", "unpaid": "Unpaid", "partially_paid": "Partially Paid", "partial": "Partial",
    "overdue": "Overdue", "open": "Open", "closed": "Closed", "archived": "Archived",
    "scheduled": "Scheduled", "done": "Done", "success": "Success", "failed": "Failed",
    "error": "Error", "skipped": "Skipped", "connected": "Connected",
    "disconnected": "Disconnected", "revoked": "Revoked", "synced": "Synced",
    "logged": "Logged", "logged_in_crm": "Logged in CRM",
    "new": "New", "contacted": "Contacted", "follow_up": "Follow Up", "qualified": "Qualified",
    "won": "Won", "lost": "Lost", "start_inspection": "Start Inspection",
    "sent_proposal": "Sent Proposal", "approval_cost": "Approval Cost", "complete": "Complete",
    "not_started": "Not Started", "on_hold": "On Hold", "assigned": "Assigned",
    "unassigned": "Unassigned", "before": "Before", "during": "During", "after": "After",
    "no_invoice": "No Invoice", "invoice_attached": "Invoice Attached",
    "website": "Website", "phone": "Phone", "phone_call": "Phone Call", "email": "Email",
    "referral": "Referral", "social": "Social Media", "social_media": "Social Media",
    "local_services_ads": "Local Services Ads", "lead_forms": "Lead Forms",
    "local_services": "Google Guaranteed / Local Services", "crm_note": "CRM Note",
    "google_message": "Google Message", "whatsapp": "WhatsApp", "text": "Text Message",
    "visit": "Visit", "note": "Note", "cash": "Cash", "check": "Check",
    "bank_transfer": "Bank Transfer", "credit_card": "Credit Card", "debit_card": "Debit Card",
    "zelle": "Zelle", "other": "Other", "low": "Low", "normal": "Normal", "high": "High",
    "manual": "Manual", "renewal": "Renewal", "payment_follow_up": "Payment Follow Up",
    "company_review": "Company Review", "suspension": "Suspension", "document": "Document",
    "image": "Image", "video": "Video", "general": "General",
}

# Raw database values that may be rendered directly by legacy templates.
# Only known UI identifiers are translated; route names, slugs and arbitrary
# user-entered values remain untouched.
MACHINE_ES = {
    # Generic lifecycle
    "active": "Activo",
    "inactive": "Inactivo",
    "enabled": "Habilitado",
    "disabled": "Deshabilitado",
    "pending": "Pendiente",
    "pending_send": "Pendiente de envío",
    "pending_approval": "Pendiente de aprobación",
    "pending_payment": "Pendiente de pago",
    "pending_review": "Pendiente de revisión",
    "in_progress": "En progreso",
    "completed": "Completado",
    "cancelled": "Cancelado",
    "canceled": "Cancelado",
    "approved": "Aprobado",
    "rejected": "Rechazado",
    "draft": "Borrador",
    "generated": "Generado",
    "sent": "Enviado",
    "viewed": "Visto",
    "signed": "Firmado",
    "expired": "Vencido",
    "converted": "Convertido",
    "void": "Anulado",
    "voided": "Anulado",
    "paid": "Pagado",
    "unpaid": "No pagado",
    "partially_paid": "Pagado parcialmente",
    "partial": "Parcial",
    "overdue": "Vencido",
    "open": "Abierto",
    "closed": "Cerrado",
    "archived": "Archivado",
    "scheduled": "Programado",
    "done": "Completado",
    "success": "Correcto",
    "failed": "Fallido",
    "error": "Error",
    "skipped": "Omitido",
    "connected": "Conectado",
    "disconnected": "Desconectado",
    "revoked": "Revocado",
    "synced": "Sincronizado",
    "logged": "Registrado",
    "logged_in_crm": "Registrado en el CRM",
    # Commercial pipeline
    "new": "Nuevo",
    "contacted": "Contactado",
    "follow_up": "Seguimiento",
    "qualified": "Calificado",
    "won": "Ganado",
    "lost": "Perdido",
    "start_inspection": "Iniciar inspección",
    "sent_proposal": "Propuesta enviada",
    "approval_cost": "Aprobación de costo",
    "complete": "Completado",
    # Project / assignment
    "not_started": "No iniciado",
    "on_hold": "En espera",
    "assigned": "Asignado",
    "unassigned": "Sin asignar",
    "before": "Antes",
    "during": "Durante",
    "after": "Después",
    "no_invoice": "Sin factura",
    "invoice_attached": "Factura adjunta",
    # Sources / channels
    "website": "Sitio web",
    "phone": "Teléfono",
    "phone_call": "Llamada telefónica",
    "email": "Correo electrónico",
    "referral": "Referido",
    "social": "Redes sociales",
    "social_media": "Redes sociales",
    "local_services_ads": "Anuncios de Servicios Locales",
    "lead_forms": "Formularios de clientes potenciales",
    "local_services": "Google Guaranteed / Servicios Locales",
    "crm_note": "Nota del CRM",
    "google_message": "Mensaje de Google",
    "whatsapp": "WhatsApp",
    "text": "Mensaje de texto",
    "visit": "Visita",
    "note": "Nota",
    # Payment methods
    "cash": "Efectivo",
    "check": "Cheque",
    "bank_transfer": "Transferencia bancaria",
    "credit_card": "Tarjeta de crédito",
    "debit_card": "Tarjeta de débito",
    "zelle": "Zelle",
    "other": "Otro",
    # Priorities / document types
    "low": "Baja",
    "normal": "Normal",
    "high": "Alta",
    "manual": "Manual",
    "renewal": "Renovación",
    "payment_follow_up": "Seguimiento de pago",
    "company_review": "Revisión de empresa",
    "suspension": "Suspensión",
    "document": "Documento",
    "image": "Imagen",
    "video": "Video",
    "general": "General",
}

_TEMPLATE_TOKEN_RE = re.compile(r"({{.*?}}|{%.*?%}|{#.*?#})", re.S)
_ATTR_RE = re.compile(
    r'(?P<name>placeholder|title|aria-label|alt|data-tooltip|data-label|data-empty-message|data-confirm-message|data-confirm-title|data-delete-message|data-message|data-title|data-cancel-label|data-submit-label|data-approve-label|data-reject-label|data-default-message|data-greeting|data-topic-label|data-name-label|data-email-label|data-company-label|data-message-label|data-platform-message|data-company-message|data-company-message-prefix|data-platform-greeting|data-company-greeting|data-company-greeting-prefix)'
    r'(?P<eq>\s*=\s*)(?P<quote>["\'])(?P<value>.*?)(?P=quote)',
    re.I | re.S,
)
_TEXT_BETWEEN_TAGS_RE = re.compile(r">(?P<text>[^<>]+)<", re.S)
_SCRIPT_RE = re.compile(r"(<script\b[^>]*>)(?P<body>.*?)(</script>)", re.I | re.S)
_QUOTED_RE = re.compile(r'(?P<q>["\'])(?P<value>[^"\'\n]{2,180})(?P=q)')
_PROTECTED_BLOCK_RE = re.compile(
    r"<(script|style|pre|code|textarea)\b[^>]*>.*?</\1>",
    re.I | re.S,
)
_CODE_LIKE_RE = re.compile(
    r"[=;{}]|\b(?:const|let|var|function|return|document|window|querySelector|addEventListener)\b",
    re.I,
)


def _restore_case(source: str, translated: str) -> str:
    if source.isupper() and len(source) > 1:
        return translated.upper()
    if source[:1].isupper():
        return translated[:1].upper() + translated[1:]
    return translated


def _fallback_translate(text: str) -> str:
    result = text

    for english, spanish in sorted(PHRASE_ES.items(), key=lambda item: len(item[0]), reverse=True):
        result = re.sub(
            rf"\b{re.escape(english)}\b",
            lambda match: _restore_case(match.group(0), spanish),
            result,
            flags=re.I,
        )

    def replace_word(match):
        word = match.group(0)
        translated = WORD_ES.get(word.lower())
        return _restore_case(word, translated) if translated else word

    result = re.sub(r"[A-Za-z]+(?:'[A-Za-z]+)?", replace_word, result)
    return result


def translate_ui_text(value: Any) -> Any:
    """Translate a source-code UI label while preserving surrounding whitespace.

    Known raw choice values are also humanized in English, so legacy templates
    never expose identifiers such as ``pending_send`` in either language.
    """
    if not isinstance(value, str):
        return value
    if not value:
        return value

    leading = value[: len(value) - len(value.lstrip())]
    trailing = value[len(value.rstrip()) :]
    core = value.strip()
    if not core:
        return value

    # HTML collapses internal whitespace in visible text. Normalize it before
    # dictionary lookup so multi-line template copy matches curated sentences.
    lookup_core = re.sub(r"\s+", " ", core)

    language = (get_language() or "en").lower()
    is_spanish = language in {"es", "es-es", "es-ec", "es-us", "es-419"}
    machine_key = lookup_core.lower().strip()

    if machine_key in MACHINE_EN:
        display = MACHINE_ES[machine_key] if is_spanish else MACHINE_EN[machine_key]
        return f"{leading}{display}{trailing}"

    if not is_spanish:
        return value

    if not re.search(r"[A-Za-z]", value):
        return value

    # Translation is applied at several safe UI layers (form metadata, choice
    # labels and literal template text). Keep the operation idempotent so a
    # value already translated to Spanish is never translated a second time.
    spanish_values = globals().get("SPANISH_UI_VALUES", set())
    if lookup_core in spanish_values:
        return value

    # Do not touch URLs, emails, CSS selectors, route names, DOM identifiers or
    # other code-like values. Hyphenated/underscored single tokens are usually
    # CSS classes, IDs or machine values (for example ``is-active``).
    if (
        "http://" in lookup_core
        or "https://" in lookup_core
        or re.search(r"\b[\w.+-]+@[\w.-]+\.\w+\b", lookup_core)
        or (
            re.fullmatch(r"[/#._:\w-]+", lookup_core)
            and any(marker in lookup_core for marker in ("/", "_", "-", "#", ".", ":"))
        )
    ):
        return value

    translated = EXACT_ES.get(lookup_core)
    if translated is None:
        # Common structural patterns keep grammar natural for many legacy labels.
        patterns = [
            (r"^Create (.+)$", lambda m: f"Crear {translate_ui_text(m.group(1)).lower()}"),
            (r"^Edit (.+)$", lambda m: f"Editar {translate_ui_text(m.group(1)).lower()}"),
            (r"^Delete (.+)$", lambda m: f"Eliminar {translate_ui_text(m.group(1)).lower()}"),
            (r"^Add (.+)$", lambda m: f"Agregar {translate_ui_text(m.group(1)).lower()}"),
            (r"^New (.+)$", lambda m: f"Nuevo {translate_ui_text(m.group(1)).lower()}"),
            (r"^Back to (.+)$", lambda m: f"Volver a {translate_ui_text(m.group(1)).lower()}"),
            (r"^All (.+)$", lambda m: f"Todos los {translate_ui_text(m.group(1)).lower()}"),
            (r"^No (.+) found\.?$", lambda m: f"No se encontraron {translate_ui_text(m.group(1)).lower()}."),
            (r"^(.+) Information$", lambda m: f"Información de {translate_ui_text(m.group(1)).lower()}"),
            (r"^(.+) Details$", lambda m: f"Detalles de {translate_ui_text(m.group(1)).lower()}"),
            (r"^(.+) List$", lambda m: f"Lista de {translate_ui_text(m.group(1)).lower()}"),
            (r"^(.+) Status$", lambda m: f"Estado de {translate_ui_text(m.group(1)).lower()}"),
            (r"^(.+) Summary$", lambda m: f"Resumen de {translate_ui_text(m.group(1)).lower()}"),
            (r"^(.+) Settings$", lambda m: f"Configuración de {translate_ui_text(m.group(1)).lower()}"),
            (r"^(.+) Date$", lambda m: f"Fecha de {translate_ui_text(m.group(1)).lower()}"),
            (r"^(.+) Number$", lambda m: f"Número de {translate_ui_text(m.group(1)).lower()}"),
            (r"^(.+) Amount$", lambda m: f"Monto de {translate_ui_text(m.group(1)).lower()}"),
            (r"^(.+) Required$", lambda m: f"{translate_ui_text(m.group(1))} obligatorio"),
            (r"^Are you sure you want to (.+)\?$", lambda m: f"¿Está seguro de que desea {_fallback_translate(m.group(1))}?"),
        ]
        for pattern, builder in patterns:
            match = re.match(pattern, lookup_core, flags=re.I)
            if match:
                translated = builder(match)
                break

    if translated is None:
        translated = _fallback_translate(lookup_core)

    return f"{leading}{translated}{trailing}"


def _translate_attributes(fragment: str) -> str:
    def repl(match):
        value = match.group("value")
        if _TEMPLATE_TOKEN_RE.search(value):
            return match.group(0)
        translated = translate_ui_text(value)
        return f'{match.group("name")}{match.group("eq")}{match.group("quote")}{translated}{match.group("quote")}'

    return _ATTR_RE.sub(repl, fragment)


def _translate_script_literals(fragment: str) -> str:
    def script_repl(script_match):
        body = script_match.group("body")

        def quoted_repl(match):
            value = match.group("value")
            clean = value.strip()
            safe_sentence = (
                clean in EXACT_ES
                or (
                    " " in clean
                    and re.search(r"[A-Za-z]", clean)
                    and not re.search(r"[/#{}\[\]_=<>]", clean)
                )
            )
            if not safe_sentence:
                return match.group(0)
            translated = translate_ui_text(value)
            return f'{match.group("q")}{translated}{match.group("q")}'

        body = _QUOTED_RE.sub(quoted_repl, body)
        return f'{script_match.group(1)}{body}{script_match.group(3)}'

    return _SCRIPT_RE.sub(script_repl, fragment)


def translate_template_fragment(fragment: str) -> str:
    """Translate literal HTML from a Django TextNode without touching data or code.

    Script, style, code, preformatted and textarea bodies are protected. This is
    critical because legacy templates contain large inline CSS/JavaScript blocks.
    """
    if not isinstance(fragment, str) or not fragment:
        return fragment
    if get_language() not in {"es", "es-es", "es-ec", "es-us", "es-419"}:
        return fragment

    protected = []

    def protect(match):
        protected.append(match.group(0))
        return f"\ue000{len(protected) - 1}\ue001"

    translated = _PROTECTED_BLOCK_RE.sub(protect, fragment)

    # A protected block split by a Django variable may leave an unmatched open
    # or closing tag in this TextNode. Skip that fragment rather than risking a
    # CSS/JavaScript mutation.
    if re.search(r"</?(?:script|style|pre|code|textarea)\b", translated, flags=re.I):
        return fragment

    translated = _translate_attributes(translated)

    def text_repl(match):
        text = match.group("text")
        if _TEMPLATE_TOKEN_RE.search(text):
            return match.group(0)
        return f">{translate_ui_text(text)}<"

    translated = _TEXT_BETWEEN_TAGS_RE.sub(text_repl, translated)

    # Plain literal nodes around template variables can occur inside scripts.
    # Code-like fragments must never be translated.
    if "<" not in translated and ">" not in translated and not _TEMPLATE_TOKEN_RE.search(translated):
        if not _CODE_LIKE_RE.search(translated):
            translated = translate_ui_text(translated)

    for index, original in enumerate(protected):
        translated = translated.replace(f"\ue000{index}\ue001", original)

    return translated



def get_company_language(source: Any) -> str:
    """Return the configured workspace language for a company or company record."""
    company = getattr(source, "id_company", None) or source
    language = getattr(company, "default_language", "en") or "en"
    return language if language in {"en", "es"} else "en"


def company_language(source: Any):
    """Request-independent translation context for PDFs, emails and background tasks."""
    from django.utils import translation

    return translation.override(get_company_language(source))


def use_company_language(function):
    """Decorator for document/email jobs that may run outside a web request."""
    from functools import wraps

    @wraps(function)
    def wrapped(source, *args, **kwargs):
        with company_language(source):
            return function(source, *args, **kwargs)

    return wrapped

# Document/email copy translated explicitly. These are source-code literals;
# customer-entered values are never passed through this table automatically.
EXACT_ES.update(
    {
        "Page": "Página",
        "No.": "N.º",
        "Issue": "Emisión",
        "Issue Date": "Fecha de emisión",
        "Valid Until": "Válido hasta",
        "Estimate Date": "Fecha de la proforma",
        "Invoice Date": "Fecha de la factura",
        "Bill To": "Facturar a",
        "Paid Amount": "Monto pagado",
        "Grand Total": "Total general",
        "Summary": "Resumen",
        "Scope & Pricing": "Alcance y precios",
        "Scope / Description": "Alcance / Descripción",
        "Notes / Terms": "Notas / Términos",
        "Estimate pricing summary": "Resumen de precios de la proforma",
        "Items & Services": "Ítems y servicios",
        "All amounts are shown in USD": "Todos los montos se muestran en USD",
        "Thank you for your business": "Gracias por confiar en nosotros",
        "Thank you": "Gracias",
        "Thank you.": "Gracias.",
        "Review / Approve Estimate": "Revisar / Aprobar proforma",
        "Review, approve or reject this estimate here:": "Revise, apruebe o rechace esta proforma aquí:",
        "If the button does not work, copy and paste this link into your browser:": "Si el botón no funciona, copie y pegue este enlace en su navegador:",
        "Please review your estimate information. You can approve or reject it from the secure review link below.": "Revise la información de su proforma. Puede aprobarla o rechazarla desde el enlace seguro que aparece a continuación.",
        "A PDF copy is attached for your records.": "Se adjunta una copia en PDF para sus registros.",
        "This estimate is based on the scope and pricing shown above. Please review all details before approval.": "Esta proforma se basa en el alcance y los precios indicados anteriormente. Revise todos los detalles antes de aprobarla.",
        "Please review the invoice information.": "Revise la información de la factura.",
        "Please review your invoice information.": "Revise la información de su factura.",
        "Payment is due according to the invoice terms. Please contact us if you have any questions about this invoice.": "El pago vence conforme a los términos de la factura. Contáctenos si tiene alguna pregunta sobre esta factura.",
        "Description of Project and Materials": "Descripción del proyecto y materiales",
        "Customer Name": "Nombre del cliente",
        "Project Address": "Dirección del proyecto",
        "Work to be done": "Trabajo que se realizará",
        "Additional work to be done": "Trabajo adicional que se realizará",
        "Work NOT to be done": "Trabajo que NO se realizará",
        "Special Instructions": "Instrucciones especiales",
        "Notice to Consumer": "Aviso al consumidor",
        "Cancellation Notice": "Aviso de cancelación",
        "Signatures": "Firmas",
        "Customer Signature Name": "Nombre de la firma del cliente",
        "Signed Date": "Fecha de firma",
        "Signature image could not be loaded.": "No se pudo cargar la imagen de la firma.",
        "No signature available.": "No hay una firma disponible.",
        "Evidence Photos / Annexes": "Fotos de evidencia / Anexos",
        "Evidence photos attached to this contract.": "Fotos de evidencia adjuntas a este contrato.",
        "Image could not be loaded.": "No se pudo cargar la imagen.",
        "Payment Terms and Conditions": "Términos y condiciones de pago",
        "Cancellation": "Cancelación",
        "Guarantee": "Garantía",
        "Miscellaneous Terms": "Términos diversos",
        "ReportLab is required to generate contract PDFs": "ReportLab es necesario para generar los PDF de contratos",
        "Our Team": "Nuestro equipo",
        "CRM Team": "Equipo CRM",
        "your project": "su proyecto",
        "Hello": "Hola",
        "for": "para",
        "Please review the contract": "Revise el contrato",
        "Please review the contract for": "Revise el contrato correspondiente a",
        "You can review, approve, or reject the contract using this secure link:": "Puede revisar, aprobar o rechazar el contrato mediante este enlace seguro:",
        "This link does not require a CRM login.": "Este enlace no requiere iniciar sesión en el CRM.",
        "A PDF copy of the contract is attached for your records.": "Se adjunta una copia en PDF del contrato para sus registros.",
        "The PDF copy is available through the secure contract link above.": "La copia en PDF está disponible mediante el enlace seguro del contrato indicado anteriormente.",
        "It was not attached because the file is large": "No se adjuntó porque el archivo es demasiado grande",
        "The PDF was not attached because the file is large": "El PDF no se adjuntó porque el archivo es demasiado grande",
        "Please use the secure contract link to review the full contract.": "Utilice el enlace seguro del contrato para revisar el documento completo.",
        "Contract Ready For Review": "Contrato listo para revisión",
        "Contract Number": "Número de contrato",
        "Total Amount Due": "Monto total adeudado",
        "Use the secure button below to review, approve, or reject the contract. No CRM login is required.": "Utilice el botón seguro a continuación para revisar, aprobar o rechazar el contrato. No es necesario iniciar sesión en el CRM.",
        "View Contract": "Ver contrato",
        "Contract Signed Successfully": "Contrato firmado correctamente",
        "Your contract": "Su contrato",
        "has been signed successfully.": "se firmó correctamente.",
        "has been approved and signed successfully.": "se aprobó y firmó correctamente.",
        "View contract": "Ver contrato",
        "View Signed Contract": "Ver contrato firmado",
    }
)


# Additional complete-workspace vocabulary. These translations cover legacy
# templates, form metadata, table headings, statuses, dialogs and helper copy.
EXACT_ES.update({
    "Languages": "Idiomas",
    "Workspace language": "Idioma del espacio de trabajo",
    "Choose the language used across this company workspace.": "Elija el idioma utilizado en todo el espacio de trabajo de esta empresa.",
    "Select English or Spanish. The complete company CRM interface changes immediately after saving.": "Seleccione inglés o español. Toda la interfaz del CRM de la empresa cambia inmediatamente después de guardar.",
    "Company Owner": "Propietario de la empresa",
    "Use the CRM in English": "Usar el CRM en inglés",
    "Use the CRM in Spanish": "Usar el CRM en español",
    "Spanish": "Español",
    "Save language": "Guardar idioma",
    "Workspace language updated successfully.": "El idioma del espacio de trabajo se actualizó correctamente.",
    "Please select a valid language.": "Seleccione un idioma válido.",
    "Only the company Owner can manage workspace languages.": "Solo el propietario de la empresa puede administrar los idiomas del espacio de trabajo.",
    "User-entered information is never translated. Client names, company names, project names, addresses, notes, products, services, codes and document numbers remain exactly as entered.": "La información ingresada por los usuarios nunca se traduce. Los nombres de clientes, empresas y proyectos, las direcciones, notas, productos, servicios, códigos y números de documentos permanecen exactamente como fueron ingresados.",
    "Company Workspace": "Espacio de trabajo de la empresa",
    "Daily operations, users, sales and workflow control.": "Operaciones diarias, usuarios, ventas y control del flujo de trabajo.",
    "Operations and business management.": "Operaciones y gestión empresarial.",
    "Search menu": "Buscar en el menú",
    "No role assigned": "Sin rol asignado",
    "System Notice": "Aviso del sistema",
    "Confirm action": "Confirmar acción",
    "Company Dashboard": "Panel de la empresa",
    "Manage customers, contact information and CRM records.": "Administre clientes, información de contacto y registros del CRM.",
    "Smart company calendar for assigned events, notifications, inspections, projects, estimates, invoices and payments.": "Calendario inteligente de la empresa para eventos asignados, notificaciones, inspecciones, proyectos, proformas, facturas y pagos.",
    "Create Google Calendar events and generate Meet links for clients and teams.": "Cree eventos de Google Calendar y genere enlaces de Meet para clientes y equipos.",
    "No records available.": "No hay registros disponibles.",
    "No data available.": "No hay datos disponibles.",
    "No matching records found.": "No se encontraron registros coincidentes.",
    "Showing": "Mostrando",
    "entries": "registros",
    "First": "Primero",
    "Last": "Último",
    "Processing...": "Procesando...",
    "Loading...": "Cargando...",
    "Please wait...": "Espere por favor...",
    "Select all": "Seleccionar todo",
    "Clear all": "Limpiar todo",
    "Total records": "Total de registros",
    "Assigned To": "Asignado a",
    "Created By": "Creado por",
    "Updated By": "Actualizado por",
    "Date From": "Fecha desde",
    "Date To": "Fecha hasta",
    "All Statuses": "Todos los estados",
    "All Types": "Todos los tipos",
    "All Sources": "Todos los orígenes",
    "Apply Filters": "Aplicar filtros",
    "Clear Filters": "Limpiar filtros",
    "Export CSV": "Exportar CSV",
    "Export PDF": "Exportar PDF",
    "Print": "Imprimir",
    "Internal Notes": "Notas internas",
    "Additional Information": "Información adicional",
    "Audit Information": "Información de auditoría",
    "Recent Activity": "Actividad reciente",
    "Current Status": "Estado actual",
    "Action status": "Estado de la acción",
    "Last Test": "Última prueba",
    "Not tested yet": "Aún no se ha probado",
    "Save Email Settings": "Guardar configuración de correo",
    "SMTP Test": "Prueba SMTP",
    "Send Test Email": "Enviar correo de prueba",
    "Default From Email": "Correo remitente predeterminado",
    "Display Name": "Nombre para mostrar",
    "Activate SMTP for this company": "Activar SMTP para esta empresa",
    "Connection model": "Modelo de conexión",
    "Analytics reports": "Reportes de Analytics",
    "Analytics settings": "Configuración de Analytics",
    "Google connection": "Conexión con Google",
    "Connect / Reconnect Google": "Conectar / Reconectar Google",
    "Disconnect Google": "Desconectar Google",
    "Configure Google App": "Configurar aplicación de Google",
    "Google account connected successfully.": "La cuenta de Google se conectó correctamente.",
    "Google account disconnected successfully.": "La cuenta de Google se desconectó correctamente.",
    "Sync completed successfully.": "La sincronización se completó correctamente.",
    "No synchronization logs found.": "No se encontraron registros de sincronización.",
    "Previous Status": "Estado anterior",
    "New Status": "Nuevo estado",
    "Pending Send": "Pendiente de envío",
    "Partially Paid": "Pagado parcialmente",
    "Overdue": "Vencido",
    "Expired": "Expirado",
    "Suspended": "Suspendido",
    "Trial": "Prueba",
    "Success": "Correcto",
    "Failed": "Fallido",
    "Error": "Error",
    "Warning": "Advertencia",
    "Information": "Información",
})

WORD_ES.update({
    "actions":"acciones", "back":"volver", "subscription":"suscripción", "subscriptions":"suscripciones",
    "document":"documento", "documents":"documentos", "access":"acceso", "billing":"facturación",
    "password":"contraseña", "created":"creado", "plan":"plan", "plans":"planes", "renewal":"renovación",
    "renewals":"renovaciones", "yet":"aún", "system":"sistema", "login":"inicio", "owner":"propietario",
    "at":"a", "logs":"registros", "control":"control", "if":"si", "register":"registrar",
    "due":"vencimiento", "contact":"contacto", "audit":"auditoría", "clear":"limpiar", "export":"exportar",
    "unit":"unidad", "administration":"administración", "subtotal":"subtotal", "want":"desea", "sync":"sincronizar",
    "analytics":"analítica", "as":"como", "financial":"financiero", "global":"global", "code":"código",
    "approval":"aprobación", "work":"trabajo", "scope":"alcance", "services":"servicios", "track":"seguimiento",
    "line":"línea", "profile":"perfil", "final":"final", "generate":"generar", "configured":"configurado",
    "already":"ya", "start":"inicio", "filters":"filtros", "uploaded":"subido", "proformas":"proformas",
    "method":"método", "follow":"seguimiento", "inspector":"inspector", "reference":"referencia",
    "deactivate":"desactivar", "activate":"activar", "totals":"totales", "mark":"marcar", "configure":"configurar",
    "suspended":"suspendido", "statuses":"estados", "log":"registro", "voided":"anulado", "reset":"restablecer",
    "page":"página", "remove":"eliminar", "dates":"fechas", "test":"prueba", "assign":"asignar",
    "operational":"operativo", "gallery":"galería", "number":"número", "proforma":"proforma", "rejection":"rechazo",
    "admin":"administración", "resources":"recursos", "supervisor":"supervisor", "sure":"seguro", "expired":"expirado",
    "recipient":"destinatario", "expiration":"vencimiento", "compact":"compacto", "into":"en", "snapshot":"resumen",
    "request":"solicitud", "history":"historial", "configuration":"configuración", "end":"fin", "reactivate":"reactivar",
    "important":"importante", "screen":"pantalla", "inbox":"bandeja", "issued":"emitido", "done":"completado",
    "converted":"convertido", "rate":"tasa", "materials":"materiales", "validity":"validez", "staff":"personal",
    "business":"negocio", "technical":"técnico", "other":"otro", "database":"base de datos", "controls":"controles",
    "updates":"actualizaciones", "now":"ahora", "canceled":"cancelado", "cycle":"ciclo", "limit":"límite",
    "updated":"actualizado", "needed":"necesario", "applied":"aplicado", "saved":"guardado", "voucher":"comprobante",
    "unpaid":"no pagado", "background":"fondo", "tool":"herramienta", "local":"local", "operations":"operaciones",
    "monitor":"monitor", "logged":"registrado", "progress":"progreso", "simple":"simple", "files":"archivos",
    "attach":"adjuntar", "attached":"adjunto", "connect":"conectar", "observations":"observaciones", "range":"rango",
    "currently":"actualmente", "added":"agregado", "during":"durante", "preview":"vista previa", "direct":"directo",
    "see":"ver", "their":"sus", "creates":"crea", "subject":"asunto", "emails":"correos", "mode":"modo",
    "appear":"aparecer", "delivery":"entrega", "print":"imprimir", "loaded":"cargado", "flow":"flujo",
    "existing":"existente", "conversion":"conversión", "alert":"alerta", "modified":"modificado", "style":"estilo",
    "snapshots":"resúmenes", "scopes":"alcances", "second":"segundo", "resend":"reenviar", "rule":"regla",
    "never":"nunca", "tools":"herramientas", "daily":"diario", "sales":"ventas", "names":"nombres",
    "filtered":"filtrado", "response":"respuesta", "qty":"cantidad", "then":"luego", "detailed":"detallado",
    "balances":"saldos", "such":"tales", "here":"aquí", "rules":"reglas", "manual":"manual", "marked":"marcado",
    "stay":"permanecer", "additional":"adicional", "quick":"rápido", "high":"alto", "statement":"estado de cuenta",
    "cancelled":"cancelado", "read":"leído", "edited":"editado", "rows":"filas", "sessions":"sesiones",
    "property":"propiedad", "links":"enlaces", "per":"por", "integration":"integración", "days":"días",
    "enable":"habilitar", "cancellation":"cancelación", "management":"gestión", "through":"mediante", "basic":"básico",
    "across":"en todo", "english":"inglés", "spanish":"español", "saving":"guardar", "requires":"requiere",
    "check":"verificar", "receipt":"recibo", "locality":"localidad", "real":"real", "summaries":"resúmenes",
    "stage":"etapa", "inspectors":"inspectores", "sensitive":"sensible", "administrative":"administrativo",
    "directly":"directamente", "fresh":"nuevo", "onboarding":"incorporación", "recorded":"registrado",
    "until":"hasta", "owners":"propietarios", "usage":"uso", "unavailable":"no disponible", "priority":"prioridad",
    "smart":"inteligente", "previous":"anterior", "next":"siguiente", "object":"objeto", "movements":"movimientos",
    "than":"que", "full":"completo", "exists":"existe", "location":"ubicación", "expand":"expandir",
    "header":"encabezado", "labor":"mano de obra", "quantities":"cantidades", "synchronize":"sincronizar",
    "protected":"protegido", "granted":"concedido", "credentials":"credenciales", "isolated":"aislado",
    "tokens":"tokens", "uploads":"cargas", "call":"llamada", "middle":"segundo", "findings":"hallazgos",
    "estimated":"estimado", "sending":"enviando", "image":"imagen", "submit":"enviar", "position":"posición",
    "hourly":"por hora", "legal":"legal", "special":"especial", "which":"que", "section":"sección",
    "administrator":"administrador", "continue":"continuar", "working":"funcionando", "logout":"cerrar sesión",
    "unread":"no leído", "prepare":"preparar", "topic":"tema", "entered":"ingresado", "addresses":"direcciones",
    "codes":"códigos", "numbers":"números", "remain":"permanecen", "exactly":"exactamente",
    "responsibilities":"responsabilidades", "endpoints":"puntos de conexión", "center":"centro", "receipts":"recibos",
    "registering":"registrando", "info":"información", "click":"clic", "money":"dinero", "match":"coincidir",
    "allowed":"permitido", "manually":"manualmente", "approvals":"aprobaciones", "audits":"auditorías",
    "verify":"verificar", "usually":"normalmente", "tested":"probado", "billed":"facturado", "reporting":"reportes",
    "generates":"genera", "exports":"exportaciones", "changing":"cambiando", "verified":"verificado",
    "unknown":"desconocido", "organize":"organizar", "categories":"categorías", "generating":"generando",
    "belong":"pertenecer", "trial":"prueba", "define":"definir", "managed":"administrado", "limits":"límites",
    "once":"una vez", "made":"realizado", "becomes":"se convierte", "channel":"canal", "notices":"avisos",
    "types":"tipos", "compose":"redactar", "reminders":"recordatorios", "messages":"mensajes", "but":"pero",
    "arrive":"llegar", "belongs":"pertenece", "websites":"sitios web", "solutions":"soluciones", "load":"cargar",
    "filled":"completado", "being":"siendo", "website":"sitio web", "because":"porque", "pipeline":"embudo",
    "upcoming":"próximo", "movement":"movimiento", "specific":"específico", "today":"hoy", "agenda":"agenda",
    "month":"mes", "logic":"lógica", "actor":"actor", "pay":"pagar", "allocated":"asignado",
    "allocations":"asignaciones", "updating":"actualizando", "approximate":"aproximado", "incoming":"entrante",
    "potential":"potencial", "contacted":"contactado", "lost":"perdido", "light":"claro", "longer":"más largo",
    "aligned":"alineado", "matching":"coincidente", "taxes":"impuestos", "prices":"precios", "leaving":"dejando",
    "campaign":"campaña", "numeric":"numérico", "attendees":"asistentes", "receive":"recibir", "secret":"secreto",
    "integrations":"integraciones", "application":"aplicación", "destination":"destino", "pdfs":"PDF",
    "service":"servicio", "conversation":"conversación", "text":"texto", "key":"clave", "requested":"solicitado",
    "spreadsheet":"hoja de cálculo", "tab":"pestaña", "damage":"daño", "path":"ruta", "changed":"cambiado",
    "touched":"modificado", "rejecting":"rechazando", "copy":"copiar", "identification":"identificación",
    "hire":"contratar", "finance":"finanzas", "jobs":"trabajos", "consumer":"consumidor", "stored":"almacenado",
    "guarantee":"garantía", "miscellaneous":"diversos", "signatures":"firmas", "initial":"inicial",
    "sign":"firmar", "signing":"firma", "disable":"deshabilitar", "temporarily":"temporalmente",
    "correctly":"correctamente", "recommended":"recomendado", "horizontal":"horizontal", "slug":"slug",
    "enables":"habilita", "manageable":"gestionable"
})

WORD_ES.update({
    "action":"acción", "it":"esto", "title":"título", "them":"ellos", "forbidden":"prohibido",
    "denied":"denegado", "restricted":"restringido", "believe":"considera", "mistake":"error",
    "looking":"buscando", "moved":"movido", "removed":"eliminado", "existed":"existía",
    "return":"volver", "safely":"de forma segura", "guest":"invitado", "authenticated":"autenticado",
    "voiding":"anulación", "accept":"aceptar", "languages":"idiomas", "interface":"interfaz",
    "immediately":"inmediatamente", "translated":"traducido", "attention":"atención", "health":"salud",
    "disconnected":"desconectado", "engine":"motor", "tables":"tablas", "installed":"instalado",
    "apps":"aplicaciones", "connecting":"conectando", "offer":"oferta", "quotes":"cotizaciones",
    "warranties":"garantías", "supporting":"soporte", "under":"bajo", "amounts":"montos",
    "purchased":"comprado", "attachments":"adjuntos", "like":"como", "adding":"agregando",
    "options":"opciones", "deleting":"eliminando", "otherwise":"de lo contrario", "deactivated":"desactivado",
    "preserve":"preservar", "mandatory":"obligatorio", "directory":"directorio", "registry":"registro",
    "statements":"estados de cuenta", "host":"servidor", "username":"usuario", "default":"predeterminado",
    "server":"servidor", "mailboxes":"buzones", "mail":"correo", "expanded":"expandido", "later":"después",
    "structure":"estructura", "verification":"verificación", "expected":"esperado", "unassigned":"sin asignar",
    "area":"área", "grant":"conceder", "reserved":"reservado", "marking":"marcando",
    "approving":"aprobando", "confirming":"confirmando", "flows":"flujos", "suspend":"suspender",
    "blocks":"bloques", "handled":"gestionado", "reactivation":"reactivación", "restores":"restaura",
    "reopens":"reabre", "separately":"por separado", "calculate":"calcular", "calculates":"calcula",
    "maximum":"máximo", "context":"contexto", "automation":"automatización", "reactivates":"reactiva",
    "connects":"conecta", "renew":"renovar", "again":"nuevamente", "make":"hacer", "methods":"métodos",
    "expirations":"vencimientos", "workflows":"flujos de trabajo", "skipped":"omitido", "reminder":"recordatorio",
    "contacts":"contactos", "printed":"impreso", "delivered":"entregado", "inboxes":"bandejas",
    "touching":"modificar", "footer":"pie de página", "sends":"envía", "issues":"problemas",
    "shipping":"envío", "guide":"guía", "thank":"gracias", "choosing":"seleccionando", "restore":"restaurar",
    "focus":"enfoque", "volume":"volumen", "soon":"pronto", "worker":"trabajador", "reviews":"reseñas",
    "pulls":"obtiene", "helps":"ayuda", "label":"etiqueta", "agent":"agente", "metadata":"metadatos",
    "affected":"afectado", "timestamps":"marcas de tiempo", "trail":"trazabilidad", "summarizes":"resume",
    "partial":"parcial", "debit":"débito", "registration":"registro", "chosen":"seleccionado",
    "option":"opción", "checked":"marcado", "greater":"mayor", "least":"mínimo", "vouchers":"comprobantes",
    "fast":"rápido", "receivable":"por cobrar", "confirmed":"confirmado", "recalculate":"recalcular",
    "annulled":"anulado", "archive":"archivar", "layout":"diseño", "capture":"capturar", "intake":"registro",
    "converting":"convirtiendo", "live":"activo", "qualified":"calificado", "referral":"referido",
    "social":"social", "media":"medios", "icons":"iconos", "eligible":"elegible", "applications":"aplicaciones",
    "cash":"efectivo", "allocation":"asignación", "legacy":"heredado", "selecting":"seleccionando",
    "adjust":"ajustar", "developer":"desarrollador", "visualize":"visualizar", "results":"resultados",
    "independent":"independiente", "scales":"escalas", "synced":"sincronizado", "comma":"coma",
    "separated":"separado", "invitation":"invitación", "invitations":"invitaciones", "creating":"creando",
    "connections":"conexiones", "maintained":"mantenido", "model":"modelo", "setup":"configuración",
    "teams":"equipos", "synchronization":"sincronización", "images":"imágenes", "qualify":"calificar",
    "answers":"respuestas"
})


# Curated natural translations for frequently rendered company-workspace copy.
# These entries intentionally override the word-by-word compatibility fallback.
EXACT_ES.update({
    # Statuses and display values
    "Pending Send": "Pendiente de envío",
    "Pending send": "Pendiente de envío",
    "Pending Approval": "Pendiente de aprobación",
    "Pending Payment": "Pendiente de pago",
    "Pending Review": "Pendiente de revisión",
    "Viewed": "Visto",
    "Follow Up": "Seguimiento",
    "Partially Paid": "Pagado parcialmente",
    "No Invoice": "Sin factura",
    "Invoice Attached": "Factura adjunta",
    "Before": "Antes",
    "During": "Durante",
    "After": "Después",
    "Scheduled": "Programado",
    "Revoked": "Revocado",
    "Synced": "Sincronizado",
    "Skipped": "Omitido",
    "Logged in CRM": "Registrado en el CRM",
    "CRM Note": "Nota del CRM",
    "Phone Call": "Llamada telefónica",
    "Text Message": "Mensaje de texto",
    "Google Message": "Mensaje de Google",
    "Local Services Ads": "Anuncios de Servicios Locales",
    "Website": "Sitio web",
    "Referral": "Referido",
    "Social Media": "Redes sociales",
    "Bank Transfer": "Transferencia bancaria",
    "Credit Card": "Tarjeta de crédito",
    "Debit Card": "Tarjeta de débito",
    # Icon actions / tooltips
    "View": "Ver",
    "View Details": "Ver detalles",
    "Open Details": "Abrir detalles",
    "Edit": "Editar",
    "Delete": "Eliminar",
    "Send": "Enviar",
    "Resend": "Reenviar",
    "Download PDF": "Descargar PDF",
    "Open PDF": "Abrir PDF",
    "Preview PDF": "Vista previa del PDF",
    "Generate PDF": "Generar PDF",
    "Print PDF": "Imprimir PDF",
    "Copy Link": "Copiar enlace",
    "Open Link": "Abrir enlace",
    "Send Email": "Enviar correo",
    "Void": "Anular",
    "Approve": "Aprobar",
    "Reject": "Rechazar",
    "Create Project": "Crear proyecto",
    "Update Project": "Actualizar proyecto",
    "Convert To Project": "Convertir en proyecto",
    "Convert to Project": "Convertir en proyecto",
    "Convert to Invoice": "Convertir en factura",
    "Mark as Read": "Marcar como leída",
    "Mark as Unread": "Marcar como no leída",
    # Tables and totals
    "Total Activities": "Total de actividades",
    "Total Balance": "Saldo total",
    "Total Billed": "Total facturado",
    "Total Clients": "Total de clientes",
    "Total Companies": "Total de empresas",
    "Total Estimates": "Total de proformas",
    "Total Evidence": "Total de evidencias",
    "Total Inspections": "Total de inspecciones",
    "Total Invoiced": "Total facturado",
    "Total Invoices": "Total de facturas",
    "Total Items": "Total de ítems",
    "Total Paid": "Total pagado",
    "Total Purchases": "Total de compras",
    "Total Roles": "Total de roles",
    "Total Suppliers": "Total de proveedores",
    "Total Users": "Total de usuarios",
    "Total Employees": "Total de empleados",
    "With Position": "Con cargo",
    "New Employee": "Nuevo empleado",
    "Edit Employee": "Editar empleado",
    "Unified Profile": "Perfil unificado",
    "Personal Information": "Información personal",
    "Role & Access": "Rol y acceso",
    "CRM Access Capacity": "Capacidad de accesos al CRM",
    "Slots Left": "Cupos disponibles",
    "User Limit": "Límite de usuarios",
    "Active Users": "Usuarios activos",
    "Capacity": "Capacidad",
    "Limit reached": "Límite alcanzado",
    "Save Employee": "Guardar empleado",
    "Employee and user created successfully.": "El empleado y su usuario se crearon correctamente.",
    "Employee and user updated successfully.": "El empleado y su usuario se actualizaron correctamente.",
    "Please review the employee and user form.": "Revise el formulario del empleado y usuario.",
    "Please review the user form.": "Revise el formulario del empleado y usuario.",
    "No employees found.": "No se encontraron empleados.",
    "Employee summary": "Resumen de empleados",
    "User limit summary": "Resumen del límite de usuarios",
    "No phone": "Sin teléfono",
    "No role": "Sin rol",
    "Not assigned": "Sin asignar",
    "Optional / not provided": "Opcional / no registrado",
    "Automatic": "Automática",
    "Never": "Nunca",
    "New Password": "Nueva contraseña",
    "Confirm New Password": "Confirmar nueva contraseña",
    "Estimate Total": "Total de la proforma",
    "Invoice Total": "Total de la factura",
    "Paid Total": "Total pagado",
    "Line Total": "Total de línea",
    "Last Tested At": "Última prueba realizada el",
    "Last Error": "Último error",
    "Drive Folder": "Carpeta de Drive",
    "Drive Link": "Enlace de Drive",
    # Natural helper copy
    "Apply changes to the linked project?": "¿Desea aplicar los cambios al proyecto vinculado?",
    "Assign a client inspection to an inspector and schedule the inspection date.": "Asigne la inspección de un cliente a un inspector y programe la fecha de la visita.",
    "Assign role, access status and password. Company is assigned automatically from the logged-in account. Only enter a new password when you need to reset access for this user.": "Asigne el rol, el estado de acceso y la contraseña. La empresa se asigna automáticamente desde la cuenta autenticada. Ingrese una contraseña nueva únicamente cuando necesite restablecer el acceso de este usuario.",
    "Audit records should normally be created automatically from services when users perform important actions.": "Los registros de auditoría se crean automáticamente cuando los usuarios realizan acciones importantes.",
    "Change the company Owner password. Leave both password fields empty if you do not want to change it.": "Cambie la contraseña del propietario de la empresa. Deje ambos campos vacíos si no desea modificarla.",
    "Choose the client, project, method and amount. Then select the unpaid invoices to apply the payment.": "Seleccione el cliente, el proyecto, el método y el monto. Luego elija las facturas pendientes a las que se aplicará el pago.",
    "Click Add Product to add one item at a time. Product options change according to the selected supplier.": "Seleccione Agregar producto para incluir un ítem a la vez. Las opciones disponibles cambian según el proveedor seleccionado.",
    "Configure the email account that this company will use to send documents from the CRM.": "Configure la cuenta de correo que esta empresa utilizará para enviar documentos desde el CRM.",
    "Control active users, assigned roles and login access with the same action style used across the CRM.": "Controle los usuarios activos, los roles asignados y el acceso al sistema con el mismo diseño de acciones utilizado en todo el CRM.",
    "Manage employee information and CRM access from one unified workspace.": "Gestione la información de empleados y el acceso al CRM desde un solo espacio unificado.",
    "Each employee has one CRM user account. Personal data, role, position, status and access are managed together.": "Cada empleado tiene una sola cuenta de usuario del CRM. Los datos personales, el rol, el cargo, el estado y el acceso se gestionan juntos.",
    "Create the employee profile and CRM access in one step.": "Cree el perfil del empleado y su acceso al CRM en un solo paso.",
    "Update personal information, employment data, role, status or password from one form.": "Actualice la información personal, los datos laborales, el rol, el estado o la contraseña desde un solo formulario.",
    "Basic employee and contact information. The company is assigned automatically from the logged-in account.": "Información básica del empleado y de contacto. La empresa se asigna automáticamente desde la cuenta autenticada.",
    "The selected role controls module permissions. Inactive employees cannot log in.": "El rol seleccionado controla los permisos de los módulos. Los empleados inactivos no pueden iniciar sesión.",
    "The hire date will be saved automatically when this employee is created.": "La fecha de ingreso se guardará automáticamente al crear este empleado.",
    "Review personal information, employment data, role and CRM access in one profile.": "Revise la información personal, los datos laborales, el rol y el acceso al CRM en un solo perfil.",
    "The employee record and login account are synchronized automatically.": "El registro del empleado y la cuenta de acceso se sincronizan automáticamente.",
    "Leave both password fields empty to keep the current password.": "Deje ambos campos de contraseña vacíos para conservar la contraseña actual.",
    "Do you want to apply the estimate values to the selected project, save only the estimate, or cancel?": "¿Desea aplicar los valores de la proforma al proyecto seleccionado, guardar únicamente la proforma o cancelar?",
    "Do you want to save this inspection assignment?": "¿Desea guardar esta asignación de inspección?",
    "Do you want to update this inspection status?": "¿Desea actualizar el estado de esta inspección?",
    "Each role controls which modules are visible, manageable and available for sensitive approvals.": "Cada rol determina qué módulos son visibles, cuáles puede gestionar y en cuáles puede realizar aprobaciones sensibles.",
    "Enter your account email and we will send you a secure link to create a new password.": "Ingrese el correo de su cuenta y le enviaremos un enlace seguro para crear una contraseña nueva.",
    "Enter your new password twice to secure your CRM account.": "Ingrese dos veces su nueva contraseña para proteger su cuenta del CRM.",
    "Every integration action is tracked here for troubleshooting and audit.": "Cada acción de integración queda registrada aquí para facilitar el diagnóstico y la auditoría.",
    "Every product must be linked to a registered supplier from your company.": "Cada producto debe estar vinculado a un proveedor registrado de su empresa.",
    "Leave empty only when you are not changing the password.": "Déjelo vacío únicamente si no va a cambiar la contraseña.",
    "No dashboard metrics are available for this role. Enable module view permissions from Roles to show them here.": "No hay métricas del panel disponibles para este rol. Habilite los permisos de visualización desde Roles para mostrarlas aquí.",
    "No Analytics snapshot exists yet. Configure the numeric GA4 Property ID and synchronize a date range.": "Aún no existe un reporte de Analytics. Configure el ID numérico de la propiedad GA4 y sincronice un rango de fechas.",
    "No Analytics snapshots yet.": "Aún no hay reportes de Analytics.",
    "No Drive uploads yet.": "Aún no hay archivos subidos a Drive.",
    "No Google connection yet. Configure the Google App, then connect the company account.": "Aún no existe una conexión con Google. Configure la aplicación de Google y luego conecte la cuenta de la empresa.",
    "No integration logs yet.": "Aún no hay registros de integración.",
    "No meetings yet.": "Aún no hay reuniones.",
    "No photos uploaded yet.": "Aún no se han subido fotos.",
    "No project photos uploaded yet.": "Aún no se han subido fotos del proyecto.",
    "No inspection photos uploaded yet.": "Aún no se han subido fotos de la inspección.",
    "No responses logged yet.": "Aún no hay respuestas registradas.",
    "No synchronization logs yet.": "Aún no hay registros de sincronización.",
    "No unpaid invoices were found. You must have at least one invoice with pending balance before registering a payment.": "No se encontraron facturas pendientes. Debe existir al menos una factura con saldo por pagar antes de registrar un pago.",
    "Only the mapped estimate fields will be applied to the project. Other project data will not be touched.": "Solo se aplicarán al proyecto los campos vinculados de la proforma. Los demás datos del proyecto no se modificarán.",
    "Optional billing information for the proforma PDF. Expand only when you need to customize it.": "Información de facturación opcional para el PDF de la proforma. Expanda esta sección únicamente cuando necesite personalizarla.",
    "Optional. Expand only if you need to adjust billing information before generating.": "Opcional. Expanda esta sección únicamente si necesita ajustar la información de facturación antes de generar el documento.",
    "Payments and credit applications linked to this invoice.": "Pagos y aplicaciones de crédito vinculados a esta factura.",
    "Please draw your signature inside the box below. By signing, you confirm that you approve this contract.": "Dibuje su firma dentro del recuadro. Al firmar, confirma que aprueba este contrato.",
    "Please review the estimate information below. You may approve or reject this estimate while the review link is active.": "Revise la información de la proforma. Puede aprobarla o rechazarla mientras el enlace de revisión permanezca activo.",
    "Read and review your CRM notifications.": "Consulte y revise las notificaciones del CRM.",
    "Repeat the same password to confirm the change.": "Repita la misma contraseña para confirmar el cambio.",
    "Search, register and manage your company suppliers.": "Busque, registre y administre los proveedores de su empresa.",
    "Select English or Spanish. The complete company CRM interface changes immediately after saving.": "Seleccione inglés o español. Toda la interfaz del CRM de la empresa cambiará inmediatamente después de guardar.",
    "The complete company CRM interface changes immediately after saving.": "Toda la interfaz del CRM de la empresa cambia inmediatamente después de guardar.",
    "User-entered information is never translated. Client names, company names, project names, addresses, notes, products, services, codes and document numbers remain exactly as entered.": "La información ingresada por los usuarios nunca se traduce. Los nombres de clientes, empresas y proyectos, las direcciones, notas, productos, servicios, códigos y números de documentos permanecen exactamente como fueron escritos.",
})

# Final action, confirmation and document vocabulary used by icon-only controls.
EXACT_ES.update({
    "Activate": "Activar",
    "Deactivate": "Desactivar",
    "Add Product": "Agregar producto",
    "Analytics settings": "Configuración de Analytics",
    "Change Password": "Cambiar contraseña",
    "Configure Google App": "Configurar aplicación de Google",
    "Connect / Reconnect Google": "Conectar / reconectar Google",
    "Disconnect": "Desconectar",
    "Disconnect Google": "Desconectar Google",
    "Delete Draft": "Eliminar borrador",
    "Final Audit": "Auditoría final",
    "Generate": "Generar",
    "Integrations dashboard": "Panel de integraciones",
    "Mark Paid": "Marcar como pagado",
    "Open Project": "Abrir proyecto",
    "Re-send": "Reenviar",
    "Register Payment": "Registrar pago",
    "Register Purchase": "Registrar compra",
    "Remove": "Quitar",
    "Tool settings": "Configuración de la herramienta",
    "Verify": "Verificar",
    "View Invoice": "Ver factura",
    "View Payment": "Ver pago",
    "View Statement": "Ver estado de cuenta",
    "View all logs": "Ver todos los registros",
    "View connection": "Ver conexión",
    "Notice To Consumer": "Aviso al consumidor",
    "Notice to Consumer": "Aviso al consumidor",
    "Work NOT To Be Done": "Trabajo que NO se realizará",
    "Work Not To Be Done": "Trabajo que no se realizará",
    "Scope of Work": "Alcance del trabajo",
    "Reject with reason": "Rechazar con motivo",
    "No, approve only": "No, aprobar únicamente",
    "Yes, apply and open project": "Sí, aplicar y abrir el proyecto",
    "Open without updating": "Abrir sin actualizar",
    "Save estimate only": "Guardar solo la proforma",
    "Save Project Updates": "Guardar cambios del proyecto",
    "Open Public Preview": "Abrir vista pública",
    "Open Public View": "Abrir vista pública",
    "Request new link": "Solicitar un enlace nuevo",
    "Send Reset Link": "Enviar enlace de restablecimiento",
    "Check your email": "Revise su correo",
    "Back to login": "Volver al inicio de sesión",
    "Go to login": "Ir al inicio de sesión",
    "Go to Login": "Ir al inicio de sesión",
    "Go to Dashboard": "Ir al panel principal",
    "Close support form": "Cerrar formulario de soporte",
    "CRM access support": "Soporte de acceso al CRM",
    "Company access issue": "Problema de acceso a la empresa",
    "Password reset issue": "Problema para restablecer la contraseña",
    "Secure CRM Access": "Acceso seguro al CRM",
    "Remember me": "Recordarme",
    "Second Last Name": "Segundo apellido",
    "All Calendar Items": "Todos los eventos del calendario",
    "All CRM status": "Todos los estados del CRM",
    "Available Client Credit": "Crédito disponible del cliente",
    "Billing Email Optional": "Correo de facturación opcional",
    "Billing Name Optional": "Nombre de facturación opcional",
    "Billing Phone Optional": "Teléfono de facturación opcional",
    "Client Billing Snapshot": "Resumen de facturación del cliente",
    "Customer Review Link": "Enlace de revisión del cliente",
    "Dark logo background": "Fondo oscuro para el logotipo",
    "Light logo background": "Fondo claro para el logotipo",
    "Existing Project Optional": "Proyecto existente opcional",
    "External Lead ID": "ID externo del prospecto",
    "Item Photo Optional": "Foto del ítem opcional",
    "Project Address Optional": "Dirección del proyecto opcional",
    "Project Name Required": "Nombre del proyecto obligatorio",
    "Selected Project Address": "Dirección del proyecto seleccionado",
    "Expected End Date": "Fecha prevista de finalización",
    "Inspection gallery preview": "Vista previa de la galería de inspección",
    "Project gallery preview": "Vista previa de la galería del proyecto",
    "Project photo preview": "Vista previa de la foto del proyecto",
    "Selected photo preview": "Vista previa de la foto seleccionada",
    "Preview before upload": "Vista previa antes de subir",
    "Project Photo Categories": "Categorías de fotos del proyecto",
    "Supplier Control Center": "Centro de control de proveedores",
    "Supplier Purchase Report": "Reporte de compras a proveedores",
    "Export Financial CSV": "Exportar resumen financiero en CSV",
    "Export Payments CSV": "Exportar pagos en CSV",
    "Export Projects CSV": "Exportar proyectos en CSV",
    "Google App Configuration": "Configuración de la aplicación de Google",
    "Google integration actions": "Acciones de integración con Google",
    "Google Leads Inbox": "Bandeja de prospectos de Google",
    "Google Tool Settings": "Configuración de herramientas de Google",
    "Recent Sync Logs": "Registros recientes de sincronización",
    "Save Encrypted Configuration": "Guardar configuración cifrada",
    "Company-isolated encryption": "Cifrado aislado por empresa",
    "Encrypted per company": "Cifrado por empresa",
    "One Google connection per company": "Una conexión de Google por empresa",
    "OAuth client secret and tokens encrypted at rest": "Secreto OAuth y tokens cifrados en reposo",
    "Conversions and revenue": "Conversiones e ingresos",
    "Estimate status distribution": "Distribución de estados de proformas",
    "Invoice status distribution": "Distribución de estados de facturas",
    "Latest invoices generated.": "Facturas generadas recientemente.",
    "Latest sales opportunities.": "Oportunidades de venta recientes.",
    "Review customers and contact information.": "Revise los clientes y su información de contacto.",
    "Track sales opportunities and follow-ups.": "Controle las oportunidades de venta y sus seguimientos.",
    "Track projects, clients, inspectors and current status.": "Controle proyectos, clientes, inspectores y su estado actual.",
    "Track technical inspections connected to active projects.": "Controle las inspecciones técnicas vinculadas a proyectos activos.",
    "Review supervision records, approval status and final audits.": "Revise registros de supervisión, estados de aprobación y auditorías finales.",
    "Review employees, users, positions, schedules and rates.": "Revise empleados, usuarios, cargos, horarios y tarifas.",
    "Review potential projects, client data and conversion status.": "Revise proyectos potenciales, información del cliente y estado de conversión.",
    "Register supervision observations and approval controls.": "Registre observaciones de supervisión y controles de aprobación.",
    "Main lead data in a compact layout.": "Información principal del prospecto en un diseño compacto.",
    "Recent GA4 report history for this company.": "Historial reciente de reportes de GA4 de esta empresa.",
    "Only enabled integration IDs are editable here.": "Aquí solo se pueden editar los identificadores de integraciones habilitadas.",
    "Calendar, Drive and the numeric GA4 Property ID only.": "Solo Calendar, Drive y el ID numérico de la propiedad GA4.",
    "Latest Calendar, Drive, Analytics and OAuth activity.": "Actividad reciente de Calendar, Drive, Analytics y OAuth.",
    "Delete this product? If it is already used in purchases, it will be deactivated instead.": "¿Desea eliminar este producto? Si ya se utiliza en compras, se desactivará para conservar el historial.",
    "Cancel this purchase?": "¿Desea cancelar esta compra?",
    "Delete this document?": "¿Desea eliminar este documento?",
    "Delete this supplier? If it has purchases, it will be deactivated instead.": "¿Desea eliminar este proveedor? Si tiene compras registradas, se desactivará para conservar el historial.",
    "Delete this photo?": "¿Desea eliminar esta foto?",
    "Void this estimate? After voiding it, no more workflow actions will be available.": "¿Desea anular esta proforma? Después de anularla, no estarán disponibles más acciones del flujo.",
    "Are you sure you want to reject this estimate?": "¿Está seguro de que desea rechazar esta proforma?",
    "Delete this draft estimate?": "¿Desea eliminar esta proforma en borrador?",
    "Void this estimate? After voiding it, no more actions will be available.": "¿Desea anular esta proforma? Después de anularla, no habrá más acciones disponibles.",
})


# Unified History module.
EXACT_ES.update({
    "History": "Historial",
    "History details": "Detalle del historial",
    "Review important CRM activity by user, module, record and date.": "Revise la actividad importante del CRM por usuario, módulo, registro y fecha.",
    "Detailed immutable record of a CRM action.": "Registro detallado e inmutable de una acción del CRM.",
    "Total records": "Registros totales",
    "Today": "Hoy",
    "Critical events": "Eventos críticos",
    "Users recorded": "Usuarios registrados",
    "Automatic retention enabled": "Retención automática activada",
    "Files and complete document contents are never copied into the history.": "Los archivos y el contenido completo de los documentos nunca se copian al historial.",
    "All users": "Todos los usuarios",
    "All modules": "Todos los módulos",
    "All actions": "Todas las acciones",
    "All severities": "Todas las severidades",
    "Apply filters": "Aplicar filtros",
    "Export CSV": "Exportar CSV",
    "View details": "Ver detalle",
    "Back to history": "Volver al historial",
    "Performed by": "Realizado por",
    "No history records found": "No se encontraron registros en el historial",
    "Change the filters or perform a CRM action to create the first record.": "Cambie los filtros o realice una acción en el CRM para crear el primer registro.",
    "Created": "Creado",
    "Updated": "Actualizado",
    "Deleted": "Eliminado",
    "Status changed": "Estado actualizado",
    "Voided": "Anulado",
    "Cancelled": "Cancelado",
    "Approved": "Aprobado",
    "Rejected": "Rechazado",
    "Sent": "Enviado",
    "File uploaded": "Archivo subido",
    "Payment registered": "Pago registrado",
    "Permissions updated": "Permisos actualizados",
    "Signed in": "Inició sesión",
    "Signed out": "Cerró sesión",
    "Exported": "Exportado",
    "System event": "Evento del sistema",
    "Information": "Información",
    "Warning": "Advertencia",
    "Critical": "Crítico",
    "Security": "Seguridad",
    "Successful": "Exitoso",
    "Failed": "Fallido",
    "Record type": "Tipo de registro",
    "Record ID": "ID del registro",
    "IP address": "Dirección IP",
    "Request ID": "ID de solicitud",
    "Retention expiration": "Vencimiento de retención",
    "Technical event": "Evento técnico",
    "Browser / device": "Navegador / dispositivo",
    "Changed fields": "Campos modificados",
    "Deleted record snapshot": "Resumen del registro eliminado",
    "No field comparison": "Sin comparación de campos",
    "This event records an access or system action that does not modify a CRM field.": "Este evento registra una acción de acceso o del sistema que no modifica un campo del CRM.",
    "Legacy retention policy": "Política de retención anterior",
    "Not available": "No disponible",
    "User account": "Cuenta de usuario",
})

# Curated CEO MARKETING platform-administration translations.
from .platform_ui_translation import PLATFORM_EXACT_ES

EXACT_ES.update(PLATFORM_EXACT_ES)

# Normalized translated values used to make runtime translation idempotent.
# This prevents already-Spanish placeholders and labels from being processed
# by the fallback word translator a second time.
SPANISH_UI_VALUES = {
    re.sub(r"\s+", " ", str(item).strip())
    for item in (
        list(EXACT_ES.values())
        + list(MACHINE_ES.values())
        + list(PHRASE_ES.values())
        + list(WORD_ES.values())
    )
    if str(item).strip()
}
