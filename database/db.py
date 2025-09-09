from mysql.connector import pooling
import logging

from database.config import DB_CONFIG

logger = logging.getLogger(__name__)

# 延迟初始化的连接池
_pool = None

def _get_pool():
    """获取或创建连接池（延迟初始化）"""
    global _pool
    if _pool is None:
        try:
            logger.info("Creating MySQL connection pool...")
            _pool = pooling.MySQLConnectionPool(
                pool_name="project_pool",
                pool_size=5,
                **DB_CONFIG
            )
            logger.info("MySQL connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create MySQL connection pool: {e}")
            raise
    return _pool

def get_connection():
    """从连接池获取一个连接"""
    pool = _get_pool()
    return pool.get_connection()
