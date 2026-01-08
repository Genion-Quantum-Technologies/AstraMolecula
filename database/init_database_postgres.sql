-- ============================================================
-- AstraMolecula PostgreSQL 数据库初始化脚本
-- 数据库: mydatabase
-- ============================================================

-- ============================================================
-- 1. 用户表 (users)
-- 用于存储系统用户信息，包括普通用户和影子用户
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
-- 2. 用户上传文件表 (user_uploads)
-- 用于记录用户上传的文件信息
-- ============================================================
CREATE TABLE IF NOT EXISTS user_uploads (
  id CHAR(32) NOT NULL,
  user_id CHAR(36) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  file_path VARCHAR(1024) NOT NULL,
  uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_uploads_user_id ON user_uploads(user_id);

-- ============================================================
-- 3. 任务表 (tasks)
-- 用于存储各种任务（generate/docking/peptide等）的状态信息
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
-- 4. Docking 任务参数表 (docking_task_params)
-- 用于存储 Docking 任务的详细参数和计算量预测
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
-- 5. Peptide 任务参数表 (peptide_task_params)
-- 用于存储 Peptide 优化任务的详细参数和计算量预测
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
-- 6. 服务用户映射表 (service_user_mappings)
-- 用于映射第三方服务的用户与内部用户的关系
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
-- 验证表结构
-- ============================================================
SELECT 'Database initialized successfully!' AS message;
