-- =================================================================
-- 数据库结构检查脚本
-- 用于诊断当前数据库状态
-- =================================================================

-- 1. 检查所有表是否存在
SELECT 
    table_name as '表名',
    table_comment as '表注释',
    engine as '存储引擎',
    table_collation as '字符集'
FROM information_schema.tables 
WHERE table_schema = DATABASE()
ORDER BY table_name;

-- 2. 检查 tasks 表的字段结构
SELECT 
    column_name as '字段名',
    data_type as '数据类型',
    is_nullable as '可空',
    column_default as '默认值',
    column_comment as '注释'
FROM information_schema.columns 
WHERE table_schema = DATABASE() AND table_name = 'tasks'
ORDER BY ordinal_position;

-- 3. 检查 users 表的字段结构
SELECT 
    column_name as '字段名',
    data_type as '数据类型',
    is_nullable as '可空',
    column_default as '默认值',
    column_comment as '注释'
FROM information_schema.columns 
WHERE table_schema = DATABASE() AND table_name = 'users'
ORDER BY ordinal_position;

-- 4. 检查外键关系
SELECT 
    constraint_name as '约束名',
    table_name as '表名',
    column_name as '字段名',
    referenced_table_name as '引用表',
    referenced_column_name as '引用字段'
FROM information_schema.key_column_usage 
WHERE table_schema = DATABASE() 
  AND referenced_table_name IS NOT NULL;

-- 5. 检查索引
SELECT 
    table_name as '表名',
    index_name as '索引名',
    column_name as '字段名',
    non_unique as '非唯一',
    index_type as '索引类型'
FROM information_schema.statistics 
WHERE table_schema = DATABASE()
ORDER BY table_name, index_name, seq_in_index;
