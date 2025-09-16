-- 为users表添加新字段以支持外部用户和影子用户功能
-- 执行时间: 2025-09-13

-- 添加外部用户相关字段
ALTER TABLE users 
ADD COLUMN external_user_id VARCHAR(255) NULL COMMENT '外部系统用户ID',
ADD COLUMN source_system VARCHAR(100) NOT NULL DEFAULT 'internal' COMMENT '用户来源系统',
ADD COLUMN created_by_service VARCHAR(100) NULL COMMENT '创建此用户的服务标识',
ADD COLUMN is_shadow_user BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否为影子用户',
ADD COLUMN migrated_to VARCHAR(255) NULL COMMENT '迁移目标';

-- 为外部用户ID添加索引
CREATE INDEX idx_users_external_user_id ON users(external_user_id);

-- 为源系统添加索引  
CREATE INDEX idx_users_source_system ON users(source_system);

-- 为影子用户标记添加索引
CREATE INDEX idx_users_is_shadow_user ON users(is_shadow_user);
