-- =================================================================
-- AstraMolecula 数据库完整创建脚本
-- 根据代码分析生成，包含所有必要的表和字段
-- 生成时间: 2025-09-13
-- =================================================================

-- 设置字符集和排序规则
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- =================================================================
-- 1. 用户表 (users)
-- =================================================================
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
    `id` CHAR(32) NOT NULL COMMENT '用户ID，使用UUID',
    `username` VARCHAR(100) NOT NULL COMMENT '用户名',
    `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
    `phone` VARCHAR(20) NULL COMMENT '手机号码',
    `email` VARCHAR(255) NULL COMMENT '电子邮箱',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `external_user_id` VARCHAR(255) NULL COMMENT '外部系统用户ID',
    `source_system` VARCHAR(100) NOT NULL DEFAULT 'internal' COMMENT '用户来源系统',
    `created_by_service` VARCHAR(100) NULL COMMENT '创建此用户的服务标识',
    `is_shadow_user` BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否为影子用户',
    `migrated_to` VARCHAR(255) NULL COMMENT '迁移目标',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    UNIQUE KEY `uk_email` (`email`),
    KEY `idx_users_external_user_id` (`external_user_id`),
    KEY `idx_users_source_system` (`source_system`),
    KEY `idx_users_is_shadow_user` (`is_shadow_user`),
    KEY `idx_users_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- =================================================================
-- 2. 任务表 (tasks)
-- =================================================================
DROP TABLE IF EXISTS `tasks`;
CREATE TABLE `tasks` (
    `id` CHAR(32) NOT NULL COMMENT '任务ID，使用UUID',
    `user_id` CHAR(32) NOT NULL COMMENT '用户ID',
    `task_type` VARCHAR(50) NOT NULL COMMENT '任务类型：generate, docking, peptide等',
    `job_dir` VARCHAR(500) NOT NULL COMMENT '任务工作目录路径',
    `status` VARCHAR(50) NOT NULL DEFAULT 'pending' COMMENT '任务状态：pending, queued, running, processing, finished, failed, cancelled, paused',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '任务创建时间',
    `started_at` TIMESTAMP NULL COMMENT '任务开始时间',
    `finished_at` TIMESTAMP NULL COMMENT '任务完成时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_tasks_user_id` (`user_id`),
    KEY `idx_tasks_status` (`status`),
    KEY `idx_tasks_task_type` (`task_type`),
    KEY `idx_tasks_created_at` (`created_at`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务表';

-- =================================================================
-- 3. 用户上传文件表 (user_uploads)
-- =================================================================
DROP TABLE IF EXISTS `user_uploads`;
CREATE TABLE `user_uploads` (
    `id` CHAR(32) NOT NULL COMMENT '上传记录ID，使用UUID',
    `user_id` CHAR(32) NOT NULL COMMENT '用户ID',
    `filename` VARCHAR(500) NOT NULL COMMENT '文件名',
    `file_path` VARCHAR(1000) NOT NULL COMMENT '文件存储路径',
    `uploaded_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_uploads_user_id` (`user_id`),
    KEY `idx_user_uploads_uploaded_at` (`uploaded_at`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户上传文件表';

-- =================================================================
-- 4. 对接任务参数表 (docking_task_params)
-- =================================================================
DROP TABLE IF EXISTS `docking_task_params`;
CREATE TABLE `docking_task_params` (
    `id` CHAR(32) NOT NULL COMMENT '参数记录ID',
    `task_id` CHAR(32) NOT NULL COMMENT '关联的任务ID',
    
    -- 分子数量参数
    `n_ligands` INT NOT NULL COMMENT '用户提交的配体分子数量',
    
    -- pH参数
    `min_ph` DECIMAL(3,1) NOT NULL COMMENT '最小pH值',
    `max_ph` DECIMAL(3,1) NOT NULL COMMENT '最大pH值',
    `ph_factor` DECIMAL(3,1) NOT NULL DEFAULT 1.5 COMMENT 'pH因子，固定为1.5',
    
    -- 对接盒子参数
    `center_x` DECIMAL(10,3) NOT NULL COMMENT '对接中心X坐标',
    `center_y` DECIMAL(10,3) NOT NULL COMMENT '对接中心Y坐标',
    `center_z` DECIMAL(10,3) NOT NULL COMMENT '对接中心Z坐标',
    `box_size_x` DECIMAL(10,3) NOT NULL COMMENT '盒子X尺寸',
    `box_size_y` DECIMAL(10,3) NOT NULL COMMENT '盒子Y尺寸',
    `box_size_z` DECIMAL(10,3) NOT NULL COMMENT '盒子Z尺寸',
    `box_volume` DECIMAL(15,3) NOT NULL COMMENT '盒子体积',
    
    -- 对接参数
    `exhaustiveness` INT NOT NULL COMMENT '搜索彻底性参数',
    `n_poses` INT NOT NULL COMMENT '生成姿态数量',
    `n_jobs` INT NOT NULL COMMENT '并行作业数',
    
    -- 计算量评估结果
    `total_molecules` DECIMAL(10,3) NOT NULL COMMENT '待处理分子总数',
    `core_docking_factor` DECIMAL(15,6) NOT NULL COMMENT '核心对接因子',
    `pose_generation_factor` DECIMAL(10,6) NOT NULL COMMENT '姿态生成因子',
    `total_compute_units` DECIMAL(20,6) NOT NULL COMMENT '总计算单元',
    
    -- 时间戳
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_task_id` (`task_id`),
    KEY `idx_docking_task_params_task_id` (`task_id`),
    FOREIGN KEY (`task_id`) REFERENCES `tasks`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对接任务参数表';

-- =================================================================
-- 5. 多肽任务参数表 (peptide_task_params)
-- =================================================================
DROP TABLE IF EXISTS `peptide_task_params`;
CREATE TABLE `peptide_task_params` (
    `id` CHAR(32) NOT NULL COMMENT '参数记录ID',
    `task_id` CHAR(32) NOT NULL COMMENT '关联的任务ID',
    
    -- 多肽序列参数
    `peptide_sequence` TEXT NOT NULL COMMENT '输入的多肽序列（氨基酸序列）',
    `peptide_length` INT NOT NULL COMMENT '多肽序列长度',
    
    -- 优化参数
    `n_iterations` INT NOT NULL COMMENT '优化迭代总次数',
    `n_rosetta_runs` INT NOT NULL COMMENT '每次迭代中Rosetta的运行次数',
    
    -- 计算量评估结果
    `total_calculations` INT NOT NULL COMMENT '总计算次数',
    `complexity_factor` DECIMAL(15,6) NOT NULL COMMENT '复杂度因子',
    `total_compute_units` DECIMAL(20,6) NOT NULL COMMENT '总计算单元',
    
    -- 时间戳
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_task_id` (`task_id`),
    KEY `idx_peptide_task_params_task_id` (`task_id`),
    FOREIGN KEY (`task_id`) REFERENCES `tasks`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='多肽任务参数表';

-- =================================================================
-- 6. 服务用户映射表 (service_user_mappings)
-- =================================================================
DROP TABLE IF EXISTS `service_user_mappings`;
CREATE TABLE `service_user_mappings` (
    `id` CHAR(32) NOT NULL COMMENT '映射记录ID',
    `service_api_key` VARCHAR(255) NOT NULL COMMENT '服务API密钥',
    `external_user_id` VARCHAR(255) NOT NULL COMMENT '外部用户ID',
    `internal_user_id` CHAR(32) NOT NULL COMMENT '内部用户ID',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_service_external_user` (`service_api_key`, `external_user_id`),
    KEY `idx_service_user_mappings_internal_user_id` (`internal_user_id`),
    KEY `idx_service_user_mappings_service_api_key` (`service_api_key`),
    FOREIGN KEY (`internal_user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服务用户映射表';

-- =================================================================
-- 恢复外键检查
-- =================================================================
SET FOREIGN_KEY_CHECKS = 1;

-- =================================================================
-- 插入默认管理员用户（可选）
-- =================================================================
-- 注意：请根据实际需求修改密码哈希
-- INSERT INTO `users` (`id`, `username`, `password_hash`, `created_at`, `updated_at`) 
-- VALUES ('admin001', 'admin', '$2b$12$YOUR_HASHED_PASSWORD_HERE', NOW(), NOW());

-- =================================================================
-- 脚本执行完成
-- =================================================================
SELECT 'Database schema created successfully!' as status;
