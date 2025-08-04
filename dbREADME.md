
CREATE USER 'vina_user'@'%' 
  IDENTIFIED BY 'Aa7758258123';

GRANT ALL PRIVILEGES 
  ON project1.* 
  TO 'vina_user'@'%';

FLUSH PRIVILEGES;


GRANT ALL PRIVILEGES ON project1.*  TO 'vina_user'@'%' IDENTIFIED BY 'Aa7758258123';

#连接数据库
mysql -u vina_user -p -h 127.0.0.1 project1
Aa7758258123

CREATE TABLE `users` (
  `id` CHAR(36) NOT NULL,
  `username` VARCHAR(255) NOT NULL UNIQUE,
  `password_hash` VARCHAR(255) NOT NULL,
  `phone` VARCHAR(20) DEFAULT NULL,
  `email` VARCHAR(255) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE user_uploads (
  id CHAR(36)                NOT NULL PRIMARY KEY DEFAULT (UUID()),
  user_id CHAR(36)           NOT NULL,
  filename VARCHAR(255)      NOT NULL,
  file_path VARCHAR(1024)    NOT NULL,
  uploaded_at TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) 
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

# Task table for tracking generate/docking jobs
CREATE TABLE tasks (
  id CHAR(36)            NOT NULL PRIMARY KEY,
  user_id CHAR(36)       NOT NULL,
  task_type VARCHAR(20)  NOT NULL,
  job_dir VARCHAR(1024)  NOT NULL,
  status VARCHAR(20)     NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TIMESTAMP  NULL DEFAULT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 首先检查表是否存在
SHOW TABLES LIKE 'service_user_mappings';

-- 如果存在，删除表（注意：这会丢失现有数据）
DROP TABLE IF EXISTS `service_user_mappings`;

-- 重新创建表，修复ID字段
CREATE TABLE `service_user_mappings` (
    `id` VARCHAR(36) PRIMARY KEY DEFAULT (UUID()) COMMENT '映射记录的唯一标识符',
    `service_api_key` VARCHAR(255) NOT NULL COMMENT '服务API密钥',
    `external_user_id` VARCHAR(255) NOT NULL COMMENT '第三方服务中的用户标识',
    `internal_user_id` VARCHAR(36) NOT NULL COMMENT '内部系统的用户ID',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    UNIQUE KEY `uk_service_external_user` (`service_api_key`, `external_user_id`) COMMENT '确保同一服务的外部用户ID唯一',
    INDEX `idx_service_api_key` (`service_api_key`) COMMENT '服务API密钥索引',
    INDEX `idx_external_user_id` (`external_user_id`) COMMENT '外部用户ID索引',
    INDEX `idx_internal_user_id` (`internal_user_id`) COMMENT '内部用户ID索引',
    INDEX `idx_created_at` (`created_at`) COMMENT '创建时间索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='第三方服务用户映射表';

-- 验证表结构
DESCRIBE `service_user_mappings`;