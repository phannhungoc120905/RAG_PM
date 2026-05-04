-- MySQL 8+ schema for RAG_PM
-- Mapping notes:
-- 1) UUID -> CHAR(36)
-- 2) JSONB -> JSON

CREATE DATABASE IF NOT EXISTS local_rag_pm
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE local_rag_pm;

-- 1. Phan he Quan tri & Phan quyen
CREATE TABLE IF NOT EXISTS roles (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  role_name VARCHAR(50) NOT NULL,
  description TEXT,
  UNIQUE KEY uq_roles_role_name (role_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS permissions (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  permission_key VARCHAR(50) NOT NULL,
  module_name VARCHAR(50) NOT NULL,
  UNIQUE KEY uq_permissions_permission_key (permission_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS departments (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  dept_name VARCHAR(255) NOT NULL,
  parent_id CHAR(36) NULL,
  description TEXT,
  CONSTRAINT fk_departments_parent
    FOREIGN KEY (parent_id) REFERENCES departments(id)
    ON UPDATE CASCADE
    ON DELETE SET NULL,
  KEY idx_departments_parent_id (parent_id),
  KEY idx_departments_dept_name (dept_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  username VARCHAR(50) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  full_name VARCHAR(100) NOT NULL,
  email VARCHAR(100) NOT NULL,
  phone_number VARCHAR(15),
  department_id CHAR(36),
  role_id CHAR(36),
  status ENUM('active', 'inactive', 'locked') NOT NULL DEFAULT 'active',
  last_login_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_users_username (username),
  UNIQUE KEY uq_users_email (email),
  KEY idx_users_department_id (department_id),
  KEY idx_users_role_id (role_id),
  CONSTRAINT fk_users_department
    FOREIGN KEY (department_id) REFERENCES departments(id)
    ON UPDATE CASCADE
    ON DELETE SET NULL,
  CONSTRAINT fk_users_role
    FOREIGN KEY (role_id) REFERENCES roles(id)
    ON UPDATE CASCADE
    ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS role_permissions (
  role_id CHAR(36) NOT NULL,
  permission_id CHAR(36) NOT NULL,
  PRIMARY KEY (role_id, permission_id),
  KEY idx_role_permissions_permission_id (permission_id),
  CONSTRAINT fk_role_permissions_role
    FOREIGN KEY (role_id) REFERENCES roles(id)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  CONSTRAINT fk_role_permissions_permission
    FOREIGN KEY (permission_id) REFERENCES permissions(id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB;

-- 2. Phan he Quan ly Van ban & Tien xu ly
CREATE TABLE IF NOT EXISTS document_types (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  type_name VARCHAR(100) NOT NULL,
  priority_level INT NOT NULL DEFAULT 0,
  UNIQUE KEY uq_document_types_type_name (type_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS documents (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  title VARCHAR(500) NOT NULL,
  doc_number VARCHAR(100),
  document_type_id CHAR(36),
  issuing_body VARCHAR(255),
  issued_date DATE,
  security_level ENUM('normal', 'confidential', 'top_secret') NOT NULL DEFAULT 'normal',
  storage_path VARCHAR(500) NOT NULL,
  file_size BIGINT,
  file_extension VARCHAR(10),
  upload_by CHAR(36),
  status ENUM('pending', 'processing', 'ocr_completed', 'indexed', 'error') NOT NULL DEFAULT 'pending',
  metadata JSON,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_documents_title (title),
  KEY idx_documents_doc_number (doc_number),
  KEY idx_documents_document_type_id (document_type_id),
  KEY idx_documents_upload_by (upload_by),
  KEY idx_documents_issued_date (issued_date),
  CONSTRAINT fk_documents_document_type
    FOREIGN KEY (document_type_id) REFERENCES document_types(id)
    ON UPDATE CASCADE
    ON DELETE SET NULL,
  CONSTRAINT fk_documents_upload_by
    FOREIGN KEY (upload_by) REFERENCES users(id)
    ON UPDATE CASCADE
    ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS document_versions (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  document_id CHAR(36) NOT NULL,
  version_number INT NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  change_log TEXT,
  created_by CHAR(36),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_document_versions_doc_version (document_id, version_number),
  KEY idx_document_versions_created_by (created_by),
  CONSTRAINT fk_document_versions_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  CONSTRAINT fk_document_versions_created_by
    FOREIGN KEY (created_by) REFERENCES users(id)
    ON UPDATE CASCADE
    ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ocr_results (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  document_id CHAR(36) NOT NULL,
  full_text_content LONGTEXT,
  confidence_score FLOAT,
  ocr_engine VARCHAR(50),
  has_handwriting BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_ocr_results_document_id (document_id),
  CONSTRAINT fk_ocr_results_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3. Phan he AI & RAG
CREATE TABLE IF NOT EXISTS prompt_templates (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  template_name VARCHAR(100) NOT NULL,
  system_instruction TEXT,
  user_prompt_format TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE KEY uq_prompt_templates_template_name (template_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS document_chunks (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  document_id CHAR(36) NOT NULL,
  chunk_index INT NOT NULL,
  content LONGTEXT NOT NULL,
  vector_id CHAR(36),
  page_number INT,
  line_start INT,
  line_end INT,
  semantic_context TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_document_chunks_doc_chunk (document_id, chunk_index),
  KEY idx_document_chunks_vector_id (vector_id),
  KEY idx_document_chunks_page_number (page_number),
  CONSTRAINT fk_document_chunks_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS summaries (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  document_id CHAR(36) NOT NULL,
  model_name VARCHAR(100) NOT NULL,
  prompt_template_id CHAR(36),
  summary_content LONGTEXT NOT NULL,
  word_count INT,
  execution_time_ms INT,
  groundedness_score FLOAT,
  status ENUM('draft', 'final', 'rejected') NOT NULL DEFAULT 'draft',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_summaries_document_id (document_id),
  KEY idx_summaries_prompt_template_id (prompt_template_id),
  CONSTRAINT fk_summaries_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  CONSTRAINT fk_summaries_prompt_template
    FOREIGN KEY (prompt_template_id) REFERENCES prompt_templates(id)
    ON UPDATE CASCADE
    ON DELETE SET NULL
) ENGINE=InnoDB;

-- 4. Phan he Tuong tac & Tien ich
CREATE TABLE IF NOT EXISTS chat_sessions (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  user_id CHAR(36) NOT NULL,
  document_id CHAR(36),
  session_name VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_chat_sessions_user_id (user_id),
  KEY idx_chat_sessions_document_id (document_id),
  CONSTRAINT fk_chat_sessions_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  CONSTRAINT fk_chat_sessions_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON UPDATE CASCADE
    ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS chat_messages (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  session_id CHAR(36) NOT NULL,
  role ENUM('user', 'assistant') NOT NULL,
  content LONGTEXT NOT NULL,
  sources JSON,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_chat_messages_session_id (session_id),
  KEY idx_chat_messages_created_at (created_at),
  CONSTRAINT fk_chat_messages_session
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mindmaps (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  document_id CHAR(36) NOT NULL,
  graph_data JSON NOT NULL,
  style_config JSON,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_mindmaps_document_id (document_id),
  CONSTRAINT fk_mindmaps_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5. Phan he Giam sat & Nhat ky
CREATE TABLE IF NOT EXISTS audit_logs (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  user_id CHAR(36),
  action VARCHAR(100) NOT NULL,
  resource_type VARCHAR(50),
  resource_id CHAR(36),
  ip_address VARCHAR(45),
  user_agent TEXT,
  old_value JSON,
  new_value JSON,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_audit_logs_user_id (user_id),
  KEY idx_audit_logs_action (action),
  KEY idx_audit_logs_resource (resource_type, resource_id),
  KEY idx_audit_logs_created_at (created_at),
  CONSTRAINT fk_audit_logs_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON UPDATE CASCADE
    ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS system_metrics (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  cpu_usage FLOAT,
  ram_usage FLOAT,
  gpu_usage FLOAT,
  vram_usage FLOAT,
  active_queries INT,
  recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_system_metrics_recorded_at (recorded_at)
) ENGINE=InnoDB;

-- Optional seed roles
INSERT INTO roles (id, role_name, description)
VALUES
  (UUID(), 'Admin', 'Quan tri he thong'),
  (UUID(), 'Chuyen vien', 'Xu ly nghiep vu va van ban'),
  (UUID(), 'Lanh dao', 'Phe duyet va xem bao cao')
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- Optional seed permissions
INSERT INTO permissions (id, permission_key, module_name)
VALUES
  (UUID(), 'doc_upload', 'document'),
  (UUID(), 'ai_summary', 'ai'),
  (UUID(), 'sys_config', 'system')
ON DUPLICATE KEY UPDATE module_name = VALUES(module_name);
