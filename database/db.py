import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import logging

from database.config import DB_CONFIG, POOL_CONFIG

logger = logging.getLogger(__name__)

# 延迟初始化的连接池
_pool = None

def _get_pool():
    """获取或创建连接池（延迟初始化）"""
    global _pool
    if _pool is None:
        try:
            logger.info("Creating PostgreSQL connection pool...")
            _pool = pool.ThreadedConnectionPool(
                minconn=POOL_CONFIG.get("min_size", 1),
                maxconn=POOL_CONFIG.get("max_size", 10),
                host=DB_CONFIG["host"],
                port=DB_CONFIG.get("port", 5432),
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                database=DB_CONFIG["database"],
            )
            logger.info("PostgreSQL connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL connection pool: {e}")
            raise
    return _pool


class PostgresConnection:
    """PostgreSQL 连接包装器，支持上下文管理器和自动提交"""
    
    def __init__(self, conn):
        self._conn = conn
        self._conn.autocommit = True
    
    def cursor(self, dictionary=False):
        """获取游标，支持dictionary参数以兼容MySQL风格"""
        if dictionary:
            return self._conn.cursor(cursor_factory=RealDictCursor)
        return self._conn.cursor()
    
    def commit(self):
        self._conn.commit()
    
    def rollback(self):
        self._conn.rollback()
    
    def close(self):
        """将连接返回到连接池"""
        pool = _get_pool()
        pool.putconn(self._conn)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def get_connection():
    """从连接池获取一个连接"""
    pool = _get_pool()
    conn = pool.getconn()
    return PostgresConnection(conn)

