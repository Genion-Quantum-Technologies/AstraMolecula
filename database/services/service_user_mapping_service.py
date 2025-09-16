import uuid
from typing import Optional
from datetime import datetime

from database.models.service_user_mapping import ServiceUserMapping
from database.repositorys.service_user_mapping_repository import ServiceUserMappingRepository

class ServiceUserMappingService:
    
    @staticmethod
    def get_mapping(service_api_key: str, external_user_id: str) -> Optional[ServiceUserMapping]:
        """获取服务用户映射"""
        return ServiceUserMappingRepository.get_mapping(service_api_key, external_user_id)
    
    @staticmethod
    def create_mapping(service_api_key: str, external_user_id: str, internal_user_id: str) -> ServiceUserMapping:
        """创建服务用户映射"""
        # service_user_mappings表的id字段是char(32)，需要生成32字符的UUID（无连字符）
        mapping_id = str(uuid.uuid4()).replace('-', '')
        now = datetime.now()
        
        ServiceUserMappingRepository.create(
            id=mapping_id,
            service_api_key=service_api_key,
            external_user_id=external_user_id,
            internal_user_id=internal_user_id,
            created_at=now,
            updated_at=now
        )
        
        # 创建成功后，返回创建的映射对象
        result = ServiceUserMappingRepository.get_by_id(mapping_id)
        if result is None:
            raise Exception(f"Failed to create service user mapping with id: {mapping_id}")
        return result
    
    @staticmethod
    def update_mapping(service_api_key: str, external_user_id: str, new_internal_user_id: str) -> Optional[ServiceUserMapping]:
        """更新映射到新的内部用户"""
        return ServiceUserMappingRepository.update_mapping(
            service_api_key=service_api_key,
            external_user_id=external_user_id,
            new_internal_user_id=new_internal_user_id
        )
