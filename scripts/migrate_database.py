"""
数据库迁移脚本：添加用户映射和迁移支持

此脚本将：
1. 为users表添加新字段
2. 创建service_user_mappings表
3. 创建user_migrations表
"""
import mysql.connector
from database.db import get_connection

def run_migration():
    """执行数据库迁移"""
    conn = get_connection()
    
    try:
        with conn.cursor() as cursor:
            print("开始数据库迁移...")
            
            # 1. 扩展users表
            print("1. 扩展users表...")
            alter_users_queries = [
                "ALTER TABLE users ADD COLUMN external_user_id VARCHAR(255) NULL",
                "ALTER TABLE users ADD COLUMN source_system VARCHAR(50) DEFAULT 'internal'",
                "ALTER TABLE users ADD COLUMN created_by_service VARCHAR(255) NULL",
                "ALTER TABLE users ADD COLUMN is_shadow_user BOOLEAN DEFAULT FALSE",
                "ALTER TABLE users ADD COLUMN migrated_to VARCHAR(36) NULL"
            ]
            
            for query in alter_users_queries:
                try:
                    cursor.execute(query)
                    print(f"  ✓ 执行: {query}")
                except mysql.connector.Error as e:
                    if "Duplicate column name" in str(e):
                        print(f"  - 跳过（字段已存在): {query}")
                    else:
                        raise e
            
            # 2. 创建service_user_mappings表
            print("2. 创建service_user_mappings表...")
            create_mapping_table = """
            CREATE TABLE IF NOT EXISTS service_user_mappings (
                id VARCHAR(36) PRIMARY KEY,
                service_api_key VARCHAR(255) NOT NULL,
                external_user_id VARCHAR(255) NOT NULL,
                internal_user_id VARCHAR(36) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (internal_user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE KEY unique_service_user (service_api_key, external_user_id)
            )
            """
            cursor.execute(create_mapping_table)
            print("  ✓ service_user_mappings表创建完成")
            
            # 3. 创建user_migrations表
            print("3. 创建user_migrations表...")
            create_migration_table = """
            CREATE TABLE IF NOT EXISTS user_migrations (
                id VARCHAR(36) PRIMARY KEY,
                shadow_user_id VARCHAR(36) NOT NULL,
                real_user_id VARCHAR(36) NOT NULL,
                migration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                migration_type ENUM('auto_merge', 'manual_merge', 'account_claim') DEFAULT 'auto_merge',
                FOREIGN KEY (shadow_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (real_user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
            cursor.execute(create_migration_table)
            print("  ✓ user_migrations表创建完成")
            
            # 4. 创建索引以提高查询性能
            print("4. 创建索引...")
            indexes = [
                "CREATE INDEX idx_users_external_id ON users(external_user_id)",
                "CREATE INDEX idx_users_source_system ON users(source_system)",
                "CREATE INDEX idx_users_is_shadow ON users(is_shadow_user)",
                "CREATE INDEX idx_mapping_external_user ON service_user_mappings(external_user_id)",
                "CREATE INDEX idx_mapping_internal_user ON service_user_mappings(internal_user_id)"
            ]
            
            for index_query in indexes:
                try:
                    cursor.execute(index_query)
                    print(f"  ✓ 创建索引: {index_query.split()[-1]}")
                except mysql.connector.Error as e:
                    if "Duplicate key name" in str(e):
                        print(f"  - 跳过（索引已存在): {index_query.split()[-1]}")
                    else:
                        raise e
            
        conn.commit()
        print("\n✅ 数据库迁移完成！")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 迁移失败: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
