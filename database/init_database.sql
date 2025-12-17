-- ============================================================
-- AstraMolecula 数据库初始化脚本
-- 数据库: project1
-- 字符集: utf8mb4
-- ============================================================

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS project1 
  CHARACTER SET utf8mb4 
  COLLATE utf8mb4_unicode_ci;

-- 创建用户（允许从任何主机连接）
CREATE USER IF NOT EXISTS 'vina_user'@'%' IDENTIFIED BY 'Aa7758258123';

-- 授权该用户对 project1 数据库的所有权限
GRANT ALL PRIVILEGES ON project1.* TO 'vina_user'@'%';

FLUSH PRIVILEGES;

-- 使用 project1 数据库
USE project1;

-- ============================================================
-- 1. 用户表 (users)
-- 用于存储系统用户信息，包括普通用户和影子用户
-- ============================================================
CREATE TABLE IF NOT EXISTS `users` (
  `id` CHAR(36) NOT NULL COMMENT '用户UUID',
  `username` VARCHAR(255) NOT NULL COMMENT '用户名',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
  `phone` VARCHAR(20) DEFAULT NULL COMMENT '手机号',
  `email` VARCHAR(255) DEFAULT NULL COMMENT '邮箱',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `external_user_id` VARCHAR(255) DEFAULT NULL COMMENT '外部用户ID（第三方系统）',
  `source_system` VARCHAR(50) DEFAULT 'internal' COMMENT '用户来源系统',
  `created_by_service` VARCHAR(255) DEFAULT NULL COMMENT '创建用户的服务名称',
  `is_shadow_user` TINYINT(1) DEFAULT 0 COMMENT '是否为影子用户 (0=否, 1=是)',
  `migrated_to` CHAR(36) DEFAULT NULL COMMENT '已迁移到的真实用户ID',
  `user_role` VARCHAR(20) DEFAULT 'user' COMMENT '用户角色 (user/admin)',
  `is_admin` TINYINT(1) DEFAULT 0 COMMENT '是否为管理员 (0=否, 1=是)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  INDEX `idx_external_user` (`external_user_id`, `source_system`),
  INDEX `idx_is_shadow_user` (`is_shadow_user`)
) ENGINE=InnoDB 
  DEFAULT CHARSET=utf8mb4 
  COLLATE=utf8mb4_unicode_ci 
  COMMENT='用户表';

-- ============================================================
-- 2. 用户上传文件表 (user_uploads)
-- 用于记录用户上传的文件信息
-- ============================================================
CREATE TABLE IF NOT EXISTS `user_uploads` (
  `id` CHAR(32) NOT NULL COMMENT '上传记录ID（32位UUID无连字符）',
  `user_id` CHAR(36) NOT NULL COMMENT '用户ID',
  `filename` VARCHAR(255) NOT NULL COMMENT '文件名',
  `file_path` VARCHAR(1024) NOT NULL COMMENT '文件存储路径',
  `uploaded_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
  PRIMARY KEY (`id`),
  INDEX `idx_user_id` (`user_id`),
  CONSTRAINT `fk_user_uploads_user` FOREIGN KEY (`user_id`) 
    REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB 
  DEFAULT CHARSET=utf8mb4 
  COLLATE=utf8mb4_unicode_ci 
  COMMENT='用户上传文件表';

-- ============================================================
-- 3. 任务表 (tasks)
-- 用于存储各种任务（generate/docking/peptide等）的状态信息
-- ============================================================
CREATE TABLE IF NOT EXISTS `tasks` (
  `id` CHAR(36) NOT NULL COMMENT '任务ID',
  `user_id` CHAR(36) NOT NULL COMMENT '用户ID',
  `task_type` VARCHAR(50) NOT NULL COMMENT '任务类型 (generate/docking/peptide等)',
  `job_dir` VARCHAR(1024) NOT NULL COMMENT '任务工作目录',
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '任务状态 (pending/queued/running/processing/finished/failed/cancelled/paused)',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `started_at` TIMESTAMP NULL DEFAULT NULL COMMENT '开始执行时间',
  `finished_at` TIMESTAMP NULL DEFAULT NULL COMMENT '完成时间',
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_status` (`status`),
  INDEX `idx_task_type` (`task_type`),
  INDEX `idx_created_at` (`created_at`),
  CONSTRAINT `fk_tasks_user` FOREIGN KEY (`user_id`) 
    REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB 
  DEFAULT CHARSET=utf8mb4 
  COLLATE=utf8mb4_unicode_ci 
  COMMENT='任务表';

-- ============================================================
-- 4. Docking 任务参数表 (docking_task_params)
-- 用于存储 Docking 任务的详细参数和计算量预测
-- ============================================================
CREATE TABLE IF NOT EXISTS `docking_task_params` (
  `id` CHAR(32) NOT NULL COMMENT '记录ID',
  `task_id` CHAR(32) NOT NULL COMMENT '关联的任务ID',
  `n_ligands` INT NOT NULL COMMENT '用户提交的配体分子数量',
  `min_ph` DECIMAL(3,1) NOT NULL COMMENT '最小pH值',
  `max_ph` DECIMAL(3,1) NOT NULL COMMENT '最大pH值',
  `ph_factor` DECIMAL(3,1) NOT NULL DEFAULT 1.5 COMMENT 'pH因子（平均每个SMILES生成1.5个变体）',
  `center_x` DECIMAL(10,3) NOT NULL COMMENT '对接中心X坐标',
  `center_y` DECIMAL(10,3) NOT NULL COMMENT '对接中心Y坐标',
  `center_z` DECIMAL(10,3) NOT NULL COMMENT '对接中心Z坐标',
  `box_size_x` DECIMAL(10,3) NOT NULL COMMENT '盒子X尺寸',
  `box_size_y` DECIMAL(10,3) NOT NULL COMMENT '盒子Y尺寸',
  `box_size_z` DECIMAL(10,3) NOT NULL COMMENT '盒子Z尺寸',
  `box_volume` DECIMAL(15,3) NOT NULL COMMENT '盒子体积 = box_size_x * box_size_y * box_size_z',
  `exhaustiveness` INT NOT NULL COMMENT '搜索彻底性参数',
  `n_poses` INT NOT NULL COMMENT '生成姿态数量',
  `n_jobs` INT NOT NULL COMMENT '并行作业数',
  `total_molecules` DECIMAL(10,3) NOT NULL COMMENT '待处理分子总数 = n_ligands * ph_factor',
  `core_docking_factor` DECIMAL(15,6) NOT NULL COMMENT '核心对接因子 = (exhaustiveness/8)² * (box_volume/8000)',
  `pose_generation_factor` DECIMAL(10,6) NOT NULL COMMENT '姿态生成因子 = 0.05 * (n_poses/10)',
  `total_compute_units` DECIMAL(20,6) NOT NULL COMMENT '总计算单元',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_task_id` (`task_id`),
  CONSTRAINT `fk_docking_params_task` FOREIGN KEY (`task_id`) 
    REFERENCES `tasks`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB 
  DEFAULT CHARSET=utf8mb4 
  COLLATE=utf8mb4_unicode_ci 
  COMMENT='Docking任务参数表';

-- ============================================================
-- 5. Peptide 任务参数表 (peptide_task_params)
-- 用于存储 Peptide 优化任务的详细参数和计算量预测
-- ============================================================
CREATE TABLE IF NOT EXISTS `peptide_task_params` (
  `id` CHAR(32) NOT NULL COMMENT '记录ID',
  `task_id` CHAR(32) NOT NULL COMMENT '关联的任务ID',
  `peptide_sequence` TEXT NOT NULL COMMENT '输入的多肽序列（氨基酸序列）',
  `peptide_length` INT NOT NULL COMMENT '多肽序列长度',
  `receptor_pdb_filename` VARCHAR(255) NOT NULL COMMENT '受体蛋白PDB文件名',
  `n_iterations` INT NOT NULL COMMENT '优化迭代总次数',
  `n_rosetta_runs` INT NOT NULL COMMENT '每次迭代中Rosetta的运行次数',
  `num_seq_per_target` INT NOT NULL COMMENT 'ProteinMPNN每个目标生成的序列数',
  `proteinmpnn_seed` INT NOT NULL COMMENT 'ProteinMPNN随机数种子',
  `total_calculations` INT NOT NULL COMMENT '总计算次数 = n_iterations * n_rosetta_runs',
  `complexity_factor` DECIMAL(15,6) NOT NULL COMMENT '复杂度因子 = (peptide_length / 10) ** 1.5',
  `total_compute_units` DECIMAL(20,6) NOT NULL COMMENT '总计算单元',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_task_id` (`task_id`),
  CONSTRAINT `fk_peptide_params_task` FOREIGN KEY (`task_id`) 
    REFERENCES `tasks`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB 
  DEFAULT CHARSET=utf8mb4 
  COLLATE=utf8mb4_unicode_ci 
  COMMENT='Peptide任务参数表';

-- ============================================================
-- 6. 服务用户映射表 (service_user_mappings)
-- 用于映射第三方服务的用户与内部用户的关系
-- ============================================================
CREATE TABLE IF NOT EXISTS `service_user_mappings` (
  `id` VARCHAR(36) NOT NULL DEFAULT (UUID()) COMMENT '映射记录的唯一标识符',
  `service_api_key` VARCHAR(255) NOT NULL COMMENT '服务API密钥',
  `external_user_id` VARCHAR(255) NOT NULL COMMENT '第三方服务中的用户标识',
  `internal_user_id` VARCHAR(36) NOT NULL COMMENT '内部系统的用户ID',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_service_external_user` (`service_api_key`, `external_user_id`) COMMENT '确保同一服务的外部用户ID唯一',
  INDEX `idx_service_api_key` (`service_api_key`) COMMENT '服务API密钥索引',
  INDEX `idx_external_user_id` (`external_user_id`) COMMENT '外部用户ID索引',
  INDEX `idx_internal_user_id` (`internal_user_id`) COMMENT '内部用户ID索引',
  INDEX `idx_created_at` (`created_at`) COMMENT '创建时间索引'
) ENGINE=InnoDB 
  DEFAULT CHARSET=utf8mb4 
  COLLATE=utf8mb4_unicode_ci 
  COMMENT='第三方服务用户映射表';

-- ============================================================
-- 验证表结构
-- ============================================================
SELECT '数据库初始化完成！以下是创建的表:' AS message;
SHOW TABLES;
