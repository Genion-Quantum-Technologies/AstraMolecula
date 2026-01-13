"""
数据库配置模块
从 settings.yaml 加载配置，提供兼容的 DB_CONFIG 和 POOL_CONFIG 字典
"""

from .settings import get_settings


class DatabaseConfig:
    """数据库配置类"""
    
    def __init__(self):
        settings = get_settings()
        db_settings = settings.get('database', {})
        
        self.host = db_settings.get('host', '127.0.0.1')
        self.port = db_settings.get('port', 5432)
        self.user = db_settings.get('user', 'admin')
        self.password = db_settings.get('password', 'secret')
        self.database = db_settings.get('database', 'mydatabase')
        
        # 连接池配置
        pool_settings = db_settings.get('pool', {})
        self.pool_min_size = pool_settings.get('min_size', 1)
        self.pool_max_size = pool_settings.get('max_size', 10)
    
    def to_dict(self) -> dict:
        """返回数据库连接配置字典（兼容旧代码）"""
        return {
            'host': self.host,
            'port': self.port,
            'user': self.user,
            'password': self.password,
            'database': self.database,
        }
    
    def get_pool_config(self) -> dict:
        """返回连接池配置字典（兼容旧代码）"""
        return {
            'min_size': self.pool_min_size,
            'max_size': self.pool_max_size,
        }


# 单例实例
_config = None

def get_database_config() -> DatabaseConfig:
    """获取数据库配置单例"""
    global _config
    if _config is None:
        _config = DatabaseConfig()
    return _config


# 兼容旧代码的字典形式
# 直接导出字典（用于兼容 from config.database_config import DB_CONFIG, POOL_CONFIG）
def _get_db_config():
    return get_database_config().to_dict()

def _get_pool_config():
    return get_database_config().get_pool_config()

# 模块级别的配置字典（延迟加载）
class _LazyDict(dict):
    def __init__(self, loader):
        super().__init__()
        self._loader = loader
        self._loaded = False
    
    def _ensure_loaded(self):
        if not self._loaded:
            self.update(self._loader())
            self._loaded = True
    
    def __getitem__(self, key):
        self._ensure_loaded()
        return super().__getitem__(key)
    
    def get(self, key, default=None):
        self._ensure_loaded()
        return super().get(key, default)
    
    def __repr__(self):
        self._ensure_loaded()
        return super().__repr__()
    
    def __iter__(self):
        self._ensure_loaded()
        return super().__iter__()
    
    def keys(self):
        self._ensure_loaded()
        return super().keys()
    
    def values(self):
        self._ensure_loaded()
        return super().values()
    
    def items(self):
        self._ensure_loaded()
        return super().items()
    
    def __len__(self):
        self._ensure_loaded()
        return super().__len__()

DB_CONFIG = _LazyDict(_get_db_config)
POOL_CONFIG = _LazyDict(_get_pool_config)
