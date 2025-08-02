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
        mapping_id = str(uuid.uuid4())
        now = datetime.now()
        
        ServiceUserMappingRepository.create(
            id=mapping_id,
            service_api_key=service_api_key,
            external_user_id=external_user_id,
            internal_user_id=internal_user_id,
            created_at=now,
            updated_at=now
        )
        
        return ServiceUserMappingRepository.get_by_id(mapping_id)
    
    @staticmethod
    def update_mapping(service_api_key: str, external_user_id: str, new_internal_user_id: str) -> Optional[ServiceUserMapping]:
        """更新映射到新的内部用户"""
        return ServiceUserMappingRepository.update_mapping(
            service_api_key=service_api_key,
            external_user_id=external_user_id,
            new_internal_user_id=new_internal_user_id
        )
