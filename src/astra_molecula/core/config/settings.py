"""
配置加载器 - 从 settings.yaml 加载配置
支持环境变量覆盖: ASTRA_<SECTION>_<KEY>
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

# 配置文件路径
_CONFIG_DIR = Path(__file__).resolve().parent
_SETTINGS_FILE = _CONFIG_DIR / "settings.yaml"

# 缓存配置
_settings_cache: Optional[Dict[str, Any]] = None


def _load_yaml() -> Dict[str, Any]:
    """加载 YAML 配置文件"""
    if _SETTINGS_FILE.exists():
        with open(_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}


def _get_env_override(section: str, key: str) -> Optional[str]:
    """获取环境变量覆盖值"""
    env_key = f"ASTRA_{section.upper()}_{key.upper()}"
    return os.environ.get(env_key)


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """应用环境变量覆盖"""
    for section, values in config.items():
        if isinstance(values, dict):
            for key, value in values.items():
                env_value = _get_env_override(section, key)
                if env_value is not None:
                    # 尝试转换类型
                    if isinstance(value, bool):
                        config[section][key] = env_value.lower() in ('true', '1', 'yes')
                    elif isinstance(value, int):
                        config[section][key] = int(env_value)
                    elif isinstance(value, float):
                        config[section][key] = float(env_value)
                    else:
                        config[section][key] = env_value
    return config


def get_settings() -> Dict[str, Any]:
    """获取完整配置（带缓存）"""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = _apply_env_overrides(_load_yaml())
    return _settings_cache


def reload_settings() -> Dict[str, Any]:
    """重新加载配置"""
    global _settings_cache
    _settings_cache = None
    return get_settings()


def get(section: str, key: str = None, default: Any = None) -> Any:
    """
    获取配置值
    
    Args:
        section: 配置节名称 (如 'database', 'api')
        key: 配置键名 (可选，不提供则返回整个节)
        default: 默认值
    
    Examples:
        get('database', 'host')  # 返回 database.host
        get('database')          # 返回整个 database 节
        get('api', 'cache')      # 返回 api.cache 子节
    """
    settings = get_settings()
    section_data = settings.get(section, {})
    
    if key is None:
        return section_data if section_data else default
    
    # 支持嵌套键 (如 'cache.file_cache_duration')
    if '.' in key:
        keys = key.split('.')
        result = section_data
        for k in keys:
            if isinstance(result, dict):
                result = result.get(k)
            else:
                return default
        return result if result is not None else default
    
    return section_data.get(key, default)


# ============ 便捷访问器 ============

class ServerConfig:
    """服务器配置便捷访问"""
    
    @property
    def host(self) -> str:
        return get('server', 'host', '0.0.0.0')
    
    @property
    def port(self) -> int:
        return get('server', 'port', 8000)
    
    @property
    def title(self) -> str:
        return get('server', 'title', 'DockingVina API')
    
    @property
    def description(self) -> str:
        return get('server', 'description', '')
    
    @property
    def version(self) -> str:
        return get('server', 'version', '2.1.0')


class CorsConfig:
    """CORS 配置便捷访问"""
    
    @property
    def allow_origins(self) -> list:
        return get('cors', 'allow_origins', ['*'])
    
    @property
    def allow_credentials(self) -> bool:
        return get('cors', 'allow_credentials', True)
    
    @property
    def allow_methods(self) -> list:
        return get('cors', 'allow_methods', ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    
    @property
    def allow_headers(self) -> list:
        return get('cors', 'allow_headers', ['*'])


class DatabaseConfig:
    """数据库配置便捷访问"""
    
    @property
    def host(self) -> str:
        return get('database', 'host', '127.0.0.1')
    
    @property
    def port(self) -> int:
        return get('database', 'port', 5432)
    
    @property
    def user(self) -> str:
        return get('database', 'user', 'admin')
    
    @property
    def password(self) -> str:
        return get('database', 'password', 'secret')
    
    @property
    def database(self) -> str:
        return get('database', 'database', 'mydatabase')
    
    @property
    def pool_min_size(self) -> int:
        return get('database', 'pool.min_size', 1)
    
    @property
    def pool_max_size(self) -> int:
        return get('database', 'pool.max_size', 10)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（兼容旧代码）"""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
        }
    
    def pool_to_dict(self) -> Dict[str, int]:
        """连接池配置字典"""
        return {
            "min_size": self.pool_min_size,
            "max_size": self.pool_max_size,
        }


class SecurityConfig:
    """安全配置便捷访问"""
    
    @property
    def jwt_secret_key(self) -> str:
        # 优先从环境变量获取
        import os
        return os.getenv('JWT_SECRET_KEY', get('security', 'jwt.secret_key', 'YOUR_RANDOM_SECRET_KEY_32+_CHARS'))
    
    @property
    def jwt_algorithm(self) -> str:
        return get('security', 'jwt.algorithm', 'HS256')
    
    @property
    def access_token_expire_minutes(self) -> int:
        return get('security', 'jwt.access_token_expire_minutes', 60)
    
    @property
    def service_api_keys(self) -> set:
        """获取所有服务 API keys（从配置文件和环境变量）"""
        import os
        # 从配置文件获取
        config_keys = set(get('security', 'service_api_keys', []))
        # 从环境变量获取（逗号分隔）
        env_keys = set(filter(None, os.getenv("SERVICE_API_KEYS", "").split(",")))
        return config_keys.union(env_keys)


class StorageConfig:
    """存储配置便捷访问 (SeaweedFS)"""
    
    @property
    def api_type(self) -> str:
        """API 类型: filer 或 s3"""
        import os
        return os.getenv('SEAWEED_API_TYPE', get('storage', 'api_type', 'filer'))
    
    @property
    def filer_endpoint(self) -> str:
        import os
        return os.getenv('SEAWEED_FILER_ENDPOINT', get('storage', 'filer_endpoint', 'http://localhost:8888'))
    
    @property
    def bucket(self) -> str:
        import os
        return os.getenv('SEAWEED_BUCKET', get('storage', 'bucket', 'astramolecula'))
    
    @property
    def s3_endpoint(self) -> str:
        import os
        return os.getenv('SEAWEED_S3_ENDPOINT', get('storage', 's3_endpoint', 'http://localhost:8333'))
    
    @property
    def access_key(self) -> str:
        import os
        return os.getenv('SEAWEED_ACCESS_KEY', get('storage', 'access_key', ''))
    
    @property
    def secret_key(self) -> str:
        import os
        return os.getenv('SEAWEED_SECRET_KEY', get('storage', 'secret_key', ''))
    
    @property
    def temp_dir(self) -> Path:
        import os
        return Path(os.getenv('TEMP_DIR', get('storage', 'temp_dir', '/tmp/astramolecula')))
    
    @property
    def presigned_url_expires(self) -> int:
        import os
        return int(os.getenv('PRESIGNED_URL_EXPIRES', get('storage', 'presigned_url_expires', 3600)))
    
    def ensure_temp_dir(self) -> Path:
        """确保临时目录存在"""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        return self.temp_dir
    
    def get_filer_base_url(self) -> str:
        """获取 Filer 的 bucket 基础 URL"""
        return f"{self.filer_endpoint}/buckets/{self.bucket}"


class APIConfig:
    """API 配置便捷访问"""
    
    @property
    def frontend_base_url(self) -> str:
        import os
        return os.getenv('FRONTEND_BASE_URL', get('api', 'frontend_base_url', ''))
    
    @property
    def file_cache_duration(self) -> int:
        return get('api', 'cache.file_cache_duration', 3600)
    
    @property
    def status_cache_duration(self) -> int:
        return get('api', 'cache.status_cache_duration', 60)
    
    @property
    def polling_min_interval(self) -> int:
        return get('api', 'polling.min_interval', 2)
    
    @property
    def polling_max_interval(self) -> int:
        return get('api', 'polling.max_interval', 30)
    
    @property
    def polling_backoff_factor(self) -> float:
        return get('api', 'polling.backoff_factor', 1.5)


class LoggingConfig:
    """日志配置便捷访问"""
    
    @property
    def level(self) -> str:
        return get('logging', 'level', 'INFO')
    
    @property
    def file(self) -> Optional[str]:
        return get('logging', 'file')


class MLConfig:
    """ML 模型配置便捷访问"""
    
    @property
    def max_sequence_length(self) -> int:
        return get('ml', 'data.max_sequence_length', 256)
    
    @property
    def padding_value(self) -> int:
        return get('ml', 'data.padding_value', 0)
    
    @property
    def properties(self) -> list:
        return get('ml', 'properties', ['pki'])
    
    @property
    def lod_min(self) -> float:
        return get('ml', 'test_property.lod_min', 1.0)
    
    @property
    def lod_max(self) -> float:
        return get('ml', 'test_property.lod_max', 3.4)
    
    @property
    def cuda_visible_devices(self) -> str:
        import os
        return os.getenv('CUDA_VISIBLE_DEVICES', get('ml', 'gpu.cuda_visible_devices', '0'))


# 单例实例
server = ServerConfig()
cors = CorsConfig()
database = DatabaseConfig()
security = SecurityConfig()
storage = StorageConfig()
api = APIConfig()
logging_config = LoggingConfig()
ml = MLConfig()
