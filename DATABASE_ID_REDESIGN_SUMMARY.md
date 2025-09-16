# AstraMolecula 数据库ID字段重新设计修改总结

## 修改背景
根据新的数据库DDL设计，重新调整了各个表的ID字段格式，以确保数据一致性和外键关系的正确性。

## 新的ID字段规范

### 主键ID格式
- `users.id`: `CHAR(36)` - 36字符UUID（包含连字符）
- `tasks.id`: `CHAR(32)` - 32字符UUID（无连字符）
- `user_uploads.id`: `CHAR(32)` - 32字符UUID（无连字符）
- `service_user_mappings.id`: `CHAR(32)` - 32字符UUID（无连字符）

### 外键格式
- 所有引用 `users.id` 的外键字段都使用 `CHAR(36)` 格式：
  - `tasks.user_id`
  - `user_uploads.user_id`
  - `service_user_mappings.internal_user_id`

## 代码修改清单

### 1. 服务层修改

#### ServiceUserMappingService
- **文件**: `/home/davis/projects/AstraMolecula/database/services/service_user_mapping_service.py`
- **修改**: `create_mapping` 方法中的ID生成改为32字符格式
- **代码**: `mapping_id = str(uuid.uuid4()).replace('-', '')`

#### UploadService  
- **文件**: `/home/davis/projects/AstraMolecula/database/services/upload_service.py`
- **修改**: `record_upload` 方法现在返回upload_id

### 2. 仓储层修改

#### UploadRepository
- **文件**: `/home/davis/projects/AstraMolecula/database/repositorys/upload_repository.py`  
- **修改**: 
  - 添加UUID导入
  - `create` 方法现在显式生成32字符的upload_id
  - 修改SQL语句包含id字段
  - 返回生成的upload_id

### 3. 数据库Schema更新

#### 新建更新脚本
- **文件**: `/home/davis/projects/AstraMolecula/database_schema_update.sql`
- **内容**: 
  - 更新 `users.id` 为 `CHAR(36)`
  - 更新所有引用用户ID的外键字段为 `CHAR(36)`
  - 重新建立外键约束
  - 创建 `service_user_mappings` 表（如果不存在）

## UUID生成策略

### 36字符UUID（用于users表）
```python
user_id = str(uuid.uuid4())  # 例如: "12345678-1234-1234-1234-123456789abc"
```

### 32字符UUID（用于其他表）
```python
id = str(uuid.uuid4()).replace('-', '')  # 例如: "12345678123412341234123456789abc"
# 或者
id = uuid.uuid4().hex  # 例如: "12345678123412341234123456789abc"
```

## 已验证的兼容性

### 中间件兼容性
- `middleware.py` 中的用户认证逻辑无需修改
- 影子用户创建和映射逻辑正确处理新的ID格式

### 路由兼容性
- 所有路由中使用 `request.state.user.id` 的地方都能正确工作
- 任务创建和查询逻辑已经使用正确的UUID格式

### 现有代码兼容性
- `TaskService.create_task` 已经使用 `uuid.uuid4().hex` 生成32字符ID
- `UserService` 的用户创建方法已经使用36字符UUID格式

## 数据迁移注意事项

1. **在应用更新前**，确保运行 `database_schema_update.sql` 脚本
2. **现有数据**需要根据当前ID格式进行相应转换：
   - 如果现有 `users.id` 是32字符，需要转换为36字符格式
   - 相应更新所有外键字段
3. **建议备份**现有数据库再进行升级

## 测试建议

1. 测试新用户注册和影子用户创建
2. 测试服务API密钥认证和用户映射创建  
3. 测试任务创建和文件上传功能
4. 验证所有外键约束正常工作
5. 测试数据查询和关联查询的性能

## 完成状态

✅ ServiceUserMappingService 修改完成
✅ UploadService 和 UploadRepository 修改完成  
✅ 数据库Schema更新脚本创建完成
✅ UUID生成策略统一
✅ 外键关系正确配置
✅ 现有代码兼容性验证完成

所有修改都已完成，代码现在符合新的DDL规范。
