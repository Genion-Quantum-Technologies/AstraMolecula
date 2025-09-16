-- =================================================================
-- AstraMolecula 数据库修复脚本
-- 修复 "Unknown column 'started_at'" 错误
-- 执行时间: 2025-09-13
-- =================================================================

-- 检查并添加缺失的字段到 tasks 表
-- 这个脚本是安全的，只会添加不存在的字段

-- 添加 started_at 字段（如果不存在）
SELECT COUNT(*) INTO @exist FROM information_schema.columns 
WHERE table_schema = DATABASE() AND table_name = 'tasks' AND column_name = 'started_at';

SET @sql = IF(@exist = 0, 
    'ALTER TABLE tasks ADD COLUMN started_at TIMESTAMP NULL COMMENT "任务开始时间"',
    'SELECT "started_at column already exists" as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 添加 updated_at 字段（如果不存在）
SELECT COUNT(*) INTO @exist FROM information_schema.columns 
WHERE table_schema = DATABASE() AND table_name = 'tasks' AND column_name = 'updated_at';

SET @sql = IF(@exist = 0, 
    'ALTER TABLE tasks ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT "最后更新时间"',
    'SELECT "updated_at column already exists" as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 检查表结构
DESCRIBE tasks;
