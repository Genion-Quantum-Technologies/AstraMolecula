-- AstraMolecula Database Initialization Script (PostgreSQL)
-- This script creates all required tables for the AstraMolecula application.
-- All statements use IF NOT EXISTS so it's safe to run multiple times.

-- ============================================================
-- 1. users - 用户表
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
  id CHAR(36) NOT NULL,
  username VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  phone VARCHAR(20) DEFAULT NULL,
  email VARCHAR(255) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  external_user_id VARCHAR(255) DEFAULT NULL,
  source_system VARCHAR(50) DEFAULT 'internal',
  created_by_service VARCHAR(255) DEFAULT NULL,
  is_shadow_user BOOLEAN DEFAULT FALSE,
  migrated_to CHAR(36) DEFAULT NULL,
  user_role VARCHAR(20) DEFAULT 'user',
  is_admin BOOLEAN DEFAULT FALSE,
  PRIMARY KEY (id),
  UNIQUE (username)
);

CREATE INDEX IF NOT EXISTS idx_users_external_user ON users(external_user_id, source_system);
CREATE INDEX IF NOT EXISTS idx_users_is_shadow_user ON users(is_shadow_user);

-- ============================================================
-- 2. user_uploads - 用户上传文件表
-- ============================================================
CREATE TABLE IF NOT EXISTS user_uploads (
  id CHAR(32) NOT NULL,
  user_id CHAR(36) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  file_path VARCHAR(1024) NOT NULL,
  uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  file_size BIGINT DEFAULT NULL,
  content_type VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_uploads_user_id ON user_uploads(user_id);

-- ============================================================
-- 3. tasks - 任务表
-- ============================================================
CREATE TABLE IF NOT EXISTS tasks (
  id CHAR(36) NOT NULL,
  user_id CHAR(36) NOT NULL,
  task_type VARCHAR(50) NOT NULL,
  job_dir VARCHAR(1024) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP DEFAULT NULL,
  finished_at TIMESTAMP DEFAULT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);

-- ============================================================
-- 4. docking_task_params - Docking 任务参数表
-- ============================================================
CREATE TABLE IF NOT EXISTS docking_task_params (
  id CHAR(32) NOT NULL,
  task_id CHAR(32) NOT NULL,
  n_ligands INT NOT NULL,
  min_ph DECIMAL(3,1) NOT NULL,
  max_ph DECIMAL(3,1) NOT NULL,
  ph_factor DECIMAL(3,1) NOT NULL DEFAULT 1.5,
  center_x DECIMAL(10,3) NOT NULL,
  center_y DECIMAL(10,3) NOT NULL,
  center_z DECIMAL(10,3) NOT NULL,
  box_size_x DECIMAL(10,3) NOT NULL,
  box_size_y DECIMAL(10,3) NOT NULL,
  box_size_z DECIMAL(10,3) NOT NULL,
  box_volume DECIMAL(15,3) NOT NULL,
  exhaustiveness INT NOT NULL,
  n_poses INT NOT NULL,
  n_jobs INT NOT NULL,
  total_molecules DECIMAL(10,3) NOT NULL,
  core_docking_factor DECIMAL(15,6) NOT NULL,
  pose_generation_factor DECIMAL(10,6) NOT NULL,
  total_compute_units DECIMAL(20,6) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_docking_task_params_task_id ON docking_task_params(task_id);

-- ============================================================
-- 5. peptide_task_params - Peptide 任务参数表
-- ============================================================
CREATE TABLE IF NOT EXISTS peptide_task_params (
  id CHAR(32) NOT NULL,
  task_id CHAR(32) NOT NULL,
  peptide_sequence TEXT NOT NULL,
  peptide_length INT NOT NULL,
  receptor_pdb_filename VARCHAR(255) NOT NULL,
  n_iterations INT NOT NULL,
  n_rosetta_runs INT NOT NULL,
  num_seq_per_target INT NOT NULL,
  proteinmpnn_seed INT NOT NULL,
  total_calculations INT NOT NULL,
  complexity_factor DECIMAL(15,6) NOT NULL,
  total_compute_units DECIMAL(20,6) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_peptide_task_params_task_id ON peptide_task_params(task_id);

-- ============================================================
-- 6. sarm_task_params - SARM 分析任务参数表
-- ============================================================
CREATE TABLE IF NOT EXISTS sarm_task_params (
  id CHAR(32) NOT NULL,
  task_id CHAR(36) NOT NULL,
  task_subtype VARCHAR(20) NOT NULL DEFAULT 'sarm',

  -- SARM 矩阵生成参数 (task_subtype = 'sarm')
  csv_filename VARCHAR(255) DEFAULT 'compounds.csv',
  analysis_type VARCHAR(20) DEFAULT 'smiles',
  value_columns TEXT DEFAULT '[]',
  log_transform BOOLEAN DEFAULT FALSE,
  minimum_site1 DECIMAL(10,2) DEFAULT 3,
  minimum_site2 DECIMAL(10,2) DEFAULT 3,
  n_jobs INT DEFAULT 8,
  csv2excel BOOLEAN DEFAULT FALSE,

  -- SAR 树生成参数 (task_subtype = 'tree')
  fragment_core VARCHAR(1024) DEFAULT NULL,
  root_title VARCHAR(255) DEFAULT NULL,
  input_file VARCHAR(255) DEFAULT 'input.csv',
  tree_content TEXT DEFAULT '["double-cut"]',
  highlight_dict TEXT DEFAULT '[]',
  max_level INT DEFAULT 5,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sarm_task_params_task_id ON sarm_task_params(task_id);
CREATE INDEX IF NOT EXISTS idx_sarm_task_params_subtype ON sarm_task_params(task_subtype);

-- ============================================================
-- 7. service_user_mappings - 第三方服务用户映射表
-- ============================================================
CREATE TABLE IF NOT EXISTS service_user_mappings (
  id VARCHAR(36) NOT NULL DEFAULT gen_random_uuid()::text,
  service_api_key VARCHAR(255) NOT NULL,
  external_user_id VARCHAR(255) NOT NULL,
  internal_user_id VARCHAR(36) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE (service_api_key, external_user_id)
);

CREATE INDEX IF NOT EXISTS idx_service_user_mappings_service_api_key ON service_user_mappings(service_api_key);
CREATE INDEX IF NOT EXISTS idx_service_user_mappings_external_user_id ON service_user_mappings(external_user_id);
CREATE INDEX IF NOT EXISTS idx_service_user_mappings_internal_user_id ON service_user_mappings(internal_user_id);
CREATE INDEX IF NOT EXISTS idx_service_user_mappings_created_at ON service_user_mappings(created_at);

-- ============================================================
-- 8. highfold_task_params - HighFold-C2C 任务参数表
-- ============================================================
CREATE TABLE IF NOT EXISTS highfold_task_params (
  id                   CHAR(32)      NOT NULL,
  task_id              CHAR(36)      NOT NULL,

  -- C2C sequence generation params
  core_sequence        VARCHAR(50)   DEFAULT NULL,
  span_len             INT           DEFAULT 5,
  num_sample           INT           DEFAULT 20,
  temperature          DECIMAL(4,2)  DEFAULT 1.0,
  top_p                DECIMAL(4,2)  DEFAULT 0.9,
  seed                 INT           DEFAULT 42,

  -- HighFold structure prediction params
  model_type           VARCHAR(50)   DEFAULT 'alphafold2',
  msa_mode             VARCHAR(50)   DEFAULT 'single_sequence',
  disulfide_bond_pairs VARCHAR(255)  DEFAULT NULL,
  num_models           INT           DEFAULT 5,
  num_recycle          INT           DEFAULT NULL,
  use_templates        BOOLEAN       DEFAULT FALSE,
  amber                BOOLEAN       DEFAULT FALSE,
  num_relax            INT           DEFAULT 0,

  -- Stage control
  skip_generate        BOOLEAN       DEFAULT FALSE,
  skip_predict         BOOLEAN       DEFAULT FALSE,
  skip_evaluate        BOOLEAN       DEFAULT FALSE,

  created_at           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  updated_at           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_highfold_task_params_task_id ON highfold_task_params(task_id);

-- ============================================================
-- Done
-- ============================================================
