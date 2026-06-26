-- ACU Database Initialization Script
-- Crea las tablas base para el sistema

USE acu_db;

-- Tabla de Memoria Evolutiva
CREATE TABLE IF NOT EXISTS memoria_evolutiva (
    id INT AUTO_INCREMENT PRIMARY KEY,
    categoria VARCHAR(100) NOT NULL,
    leccion_aprendida TEXT NOT NULL,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    relevancia INT DEFAULT 1,
    veces_utilizada INT DEFAULT 0,
    INDEX idx_categoria (categoria),
    INDEX idx_fecha (fecha_registro)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de Auditoría de Herramientas
CREATE TABLE IF NOT EXISTS tool_execution_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre_herramienta VARCHAR(100) NOT NULL,
    action_type VARCHAR(50),
    target_resource VARCHAR(512),
    payload_size_bytes INT DEFAULT 0,
    parametros JSON,
    resultado JSON,
    tiempo_ms INT,
    exito BOOLEAN,
    fecha_ejecucion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_herramienta (nombre_herramienta),
    INDEX idx_action (action_type),
    INDEX idx_fecha (fecha_ejecucion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de Auditoria de Acceso API
CREATE TABLE IF NOT EXISTS api_access_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    method VARCHAR(10) NOT NULL,
    path VARCHAR(512) NOT NULL,
    status_code INT NOT NULL,
    key_fingerprint VARCHAR(64),
    roles JSON,
    client_ip VARCHAR(64),
    user_agent VARCHAR(512),
    authorized BOOLEAN,
    duration_ms INT,
    fecha_acceso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_api_access_path (path(255)),
    INDEX idx_api_access_status (status_code),
    INDEX idx_api_access_fecha (fecha_acceso)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de Claves API Gestionadas
CREATE TABLE IF NOT EXISTS api_keys (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    key_hash CHAR(64) NOT NULL,
    key_fingerprint VARCHAR(64) NOT NULL,
    roles JSON NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_by VARCHAR(120),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP NULL,
    expires_at TIMESTAMP NULL,
    last_used_at TIMESTAMP NULL,
    UNIQUE KEY uq_api_key_hash (key_hash),
    INDEX idx_api_key_fingerprint (key_fingerprint),
    INDEX idx_api_key_status (status),
    INDEX idx_api_key_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de Sesiones de Agente
CREATE TABLE IF NOT EXISTS agent_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    domain VARCHAR(50),
    inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fin TIMESTAMP NULL,
    total_iteraciones INT,
    estado VARCHAR(20),
    INDEX idx_session (session_id),
    INDEX idx_fecha_inicio (inicio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de Contexto de Conversación
CREATE TABLE IF NOT EXISTS conversation_context (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100),
    usuario_query TEXT,
    respuesta_agente TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pasos_utilizados INT,
    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id),
    INDEX idx_session (session_id),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- BrainCore: Registro de Decisiones Arquitectonicas
CREATE TABLE IF NOT EXISTS brain_decisions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    contexto TEXT NOT NULL,
    decision_text TEXT NOT NULL,
    alternativas JSON,
    impacto TEXT,
    domain VARCHAR(100) DEFAULT 'generic',
    estado VARCHAR(30) DEFAULT 'accepted',
    tags JSON,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_brain_domain (domain),
    INDEX idx_brain_estado (estado),
    INDEX idx_brain_fecha (fecha_registro)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- BrainCore: Fuentes Indexadas
CREATE TABLE IF NOT EXISTS brain_sources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_path VARCHAR(1024) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    content_hash CHAR(64) NOT NULL,
    metadata JSON,
    estado VARCHAR(30) DEFAULT 'indexed',
    fecha_indexacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_brain_source_path (source_path(255)),
    INDEX idx_brain_source_type (source_type),
    INDEX idx_brain_source_hash (content_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- BrainCore: Chunks de Fuentes
CREATE TABLE IF NOT EXISTS brain_chunks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL,
    chunk_index INT NOT NULL,
    chunk_hash CHAR(64) NOT NULL,
    titulo VARCHAR(255),
    contenido MEDIUMTEXT NOT NULL,
    metadata JSON,
    fecha_indexacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES brain_sources(id) ON DELETE CASCADE,
    UNIQUE KEY uq_brain_source_chunk (source_id, chunk_index),
    INDEX idx_brain_chunk_hash (chunk_hash),
    FULLTEXT INDEX ft_brain_chunk_content (titulo, contenido)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Usuario de solo lectura para el agente
CREATE USER IF NOT EXISTS 'acu_reader'@'%' IDENTIFIED BY 'acu_secure_read_only';
GRANT SELECT ON acu_db.* TO 'acu_reader'@'%';
FLUSH PRIVILEGES;

-- Insertamos lecciones de ejemplo
INSERT INTO memoria_evolutiva (categoria, leccion_aprendida) VALUES
('sql_optimization', 'Usar índices en columnas de búsqueda frecuente para mejorar performance'),
('error_handling', 'Error 1054 indica que falta una columna en la cláusula SELECT'),
('database_design', 'Usar FOREIGN KEYS para mantener integridad referencial entre tablas');
