from mysql.connector import pooling

from database.config import DB_CONFIG

# 建立连接池，避免每次都新建连接
pool = pooling.MySQLConnectionPool(
    pool_name="project_pool",
    pool_size=5,
    **DB_CONFIG
)

def get_connection():
    """从连接池获取一个连接"""
    return pool.get_connection()
