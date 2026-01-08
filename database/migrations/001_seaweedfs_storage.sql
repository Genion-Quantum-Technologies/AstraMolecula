-- SeaweedFS 存储迁移 - 数据库表结构更新
-- 执行时间：2025-01-04
-- 目的：为 user_uploads 和 tasks 表添加存储相关字段
-- 数据库：PostgreSQL

-- =====================================================
-- 1. 更新 user_uploads 表
-- =====================================================

-- 添加文件大小字段（字节）
ALTER TABLE user_uploads 
ADD COLUMN IF NOT EXISTS file_size BIGINT DEFAULT NULL;

-- 添加 MIME 类型字段
ALTER TABLE user_uploads 
ADD COLUMN IF NOT EXISTS content_type VARCHAR(128) DEFAULT NULL;

-- 添加字段注释
COMMENT ON COLUMN user_uploads.file_size IS '文件大小（字节）';
COMMENT ON COLUMN user_uploads.content_type IS 'MIME 类型';

-- 注意：file_path 字段现在存储的是 SeaweedFS 的 remote_key
-- 格式为: uploads/{user_id}/{filename}
-- 无需修改字段类型，但含义已变更

-- =====================================================
-- 2. 更新 tasks 表（可选，用于追踪存储位置）
-- =====================================================

-- 添加存储前缀字段
ALTER TABLE tasks 
ADD COLUMN IF NOT EXISTS storage_prefix VARCHAR(512) DEFAULT NULL;

-- 添加字段注释
COMMENT ON COLUMN tasks.storage_prefix IS 'SeaweedFS 存储路径前缀';

-- =====================================================
-- 3. 创建索引（提升查询性能）
-- =====================================================

-- 为 file_path 创建索引（如果不存在）
-- CREATE INDEX IF NOT EXISTS idx_user_uploads_file_path ON user_uploads(file_path);

-- =====================================================
-- 4. 数据迁移说明
-- =====================================================
-- 
-- 对于已有数据，file_path 仍然是本地路径格式
-- 新上传的文件将使用 SeaweedFS remote_key 格式
-- 
-- 可以通过以下查询识别旧数据：
-- SELECT * FROM user_uploads WHERE file_path LIKE '/%';
-- 
-- 如需迁移历史数据，请运行单独的迁移脚本
-- =====================================================

-- 验证更新（PostgreSQL 语法）
\d user_uploads
\d tasks
