-- =================================================================
-- AstraMolecula 数据库更新脚本
-- 根据新的DDL规范更新ID字段格式
-- 生成时间: 2025-09-14
-- =================================================================

-- 更新用户表ID字段为36字符UUID（包含连字符）
ALTER TABLE `users` MODIFY COLUMN `id` CHAR(36) NOT NULL COMMENT '用户ID，使用UUID';

-- 更新任务表的user_id字段为36字符，以匹配users表
ALTER TABLE `tasks` MODIFY COLUMN `user_id` CHAR(36) NOT NULL COMMENT '用户ID';

-- 更新用户上传表的user_id字段为36字符，以匹配users表  
ALTER TABLE `user_uploads` MODIFY COLUMN `user_id` CHAR(36) NOT NULL COMMENT '用户ID';

-- 注意：对接任务参数表、多肽任务参数表等其他表的task_id保持CHAR(32)不变，
-- 因为它们引用的是tasks.id，而tasks.id本身就是CHAR(32)

-- 验证外键约束
-- 确保所有外键关系正确
ALTER TABLE `tasks` DROP FOREIGN KEY IF EXISTS `tasks_ibfk_1`;
ALTER TABLE `tasks` ADD CONSTRAINT `tasks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

ALTER TABLE `user_uploads` DROP FOREIGN KEY IF EXISTS `user_uploads_ibfk_1`;
ALTER TABLE `user_uploads` ADD CONSTRAINT `user_uploads_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

-- 创建服务用户映射表（如果不存在）
CREATE TABLE IF NOT EXISTS `service_user_mappings` (
    `id` char(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '映射记录ID',
    `service_api_key` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '服务API密钥',
    `external_user_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '外部用户ID',
    `internal_user_id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '内部用户ID',
    `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_service_external_user` (`service_api_key`, `external_user_id`),
    KEY `idx_service_user_mappings_internal_user_id` (`internal_user_id`),
    KEY `idx_service_user_mappings_service_api_key` (`service_api_key`),
    CONSTRAINT `service_user_mappings_ibfk_1` FOREIGN KEY (`internal_user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '服务用户映射表';
