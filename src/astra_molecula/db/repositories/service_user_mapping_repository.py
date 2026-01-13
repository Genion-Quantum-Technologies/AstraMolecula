from astra_molecula.db.db import get_connection
from astra_molecula.db.models.service_user_mapping import ServiceUserMapping
from typing import Optional
from datetime import datetime

class ServiceUserMappingRepository:
    
    @staticmethod
    def create(id: str, service_api_key: str, external_user_id: str, 
               internal_user_id: str, created_at: datetime, updated_at: datetime) -> None:
        """创建服务用户映射"""
        sql = """
        INSERT INTO service_user_mappings (id, service_api_key, external_user_id, 
                                         internal_user_id, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (id, service_api_key, external_user_id, 
                                internal_user_id, created_at, updated_at))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_mapping(service_api_key: str, external_user_id: str) -> Optional[ServiceUserMapping]:
        """获取服务用户映射"""
        sql = """
        SELECT id, service_api_key, external_user_id, internal_user_id, created_at, updated_at
          FROM service_user_mappings
         WHERE service_api_key = %s AND external_user_id = %s
        """
        conn = get_connection()
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(sql, (service_api_key, external_user_id))
                row = cur.fetchone()
            if row:
                return ServiceUserMapping(**row)
        finally:
            conn.close()
        return None

    @staticmethod
    def get_by_id(mapping_id: str) -> Optional[ServiceUserMapping]:
        """根据ID获取映射"""
        sql = """
        SELECT id, service_api_key, external_user_id, internal_user_id, created_at, updated_at
          FROM service_user_mappings
         WHERE id = %s
        """
        conn = get_connection()
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(sql, (mapping_id,))
                row = cur.fetchone()
            if row:
                return ServiceUserMapping(**row)
        finally:
            conn.close()
        return None

    @staticmethod
    def update_mapping(service_api_key: str, external_user_id: str, 
                      new_internal_user_id: str) -> Optional[ServiceUserMapping]:
        """更新映射到新的内部用户"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE service_user_mappings 
                       SET internal_user_id = %s, updated_at = %s
                       WHERE service_api_key = %s AND external_user_id = %s""",
                    (new_internal_user_id, datetime.now(), service_api_key, external_user_id)
                )
            conn.commit()
            
            # 返回更新后的映射
            return ServiceUserMappingRepository.get_mapping(service_api_key, external_user_id)
        finally:
            conn.close()
