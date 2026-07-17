-- CRM SaaS Starter V2
-- Este SQL refleja el modelado funcional del CRM para empresas, usuarios, roles,
-- clientes, leads, proyectos, inspecciones, proformas, facturas, pagos,
-- contratos, evidencias, supervisión, calendario, notificaciones y logs.

CREATE TABLE company (
    id_company BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    logo TEXT,
    description TEXT,
    plan VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active',
    user_limit INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE role (
    id_role BIGSERIAL PRIMARY KEY,
    id_company BIGINT NOT NULL REFERENCES company(id_company) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active'
);

CREATE TABLE role_permission (
    id_permission BIGSERIAL PRIMARY KEY,
    id_role BIGINT NOT NULL REFERENCES role(id_role) ON DELETE CASCADE,
    module VARCHAR(100) NOT NULL,
    can_view BOOLEAN DEFAULT FALSE,
    can_create BOOLEAN DEFAULT FALSE,
    can_edit BOOLEAN DEFAULT FALSE,
    can_delete BOOLEAN DEFAULT FALSE,
    can_approve BOOLEAN DEFAULT FALSE
);

-- Las demás tablas están implementadas en Django en apps/<modulo>/models/entities.py
