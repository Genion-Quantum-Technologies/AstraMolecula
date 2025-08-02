# 第三方服务调用示例

## 对外部系统的要求

为了支持统一用户身份映射系统，第三方服务在调用我们的API时需要遵循以下规范：

### 1. 必需的请求头

```python
headers = {
    "X-API-Key": "your_service_api_key",           # 必需：服务API密钥
    "X-External-User-ID": "user_123_external",     # 必需：外部系统中的用户标识
    "Content-Type": "application/json"
}
```

### 2. 调用示例

```python
import requests

# 配置
API_BASE_URL = "https://your-docking-api.com"
SERVICE_API_KEY = "your_service_api_key"
EXTERNAL_USER_ID = "user_123_from_external_system"

headers = {
    "X-API-Key": SERVICE_API_KEY,
    "X-External-User-ID": EXTERNAL_USER_ID,
    "Content-Type": "application/json"
}

# 1. 查看用户的任务列表
response = requests.get(
    f"{API_BASE_URL}/tasks",
    headers=headers
)
tasks = response.json()
print(f"用户 {EXTERNAL_USER_ID} 有 {len(tasks)} 个任务")

# 2. 获取特定任务状态
task_id = "some_task_id"
response = requests.get(
    f"{API_BASE_URL}/tasks/{task_id}",
    headers=headers
)
task_status = response.json()
print(f"任务状态: {task_status['status']}")

# 3. 提交新的对接任务
dock_data = {
    "protein_file": "protein.pdb",
    "ligand_smiles": "CCO",
    "task_name": "ethanol_docking"
}
response = requests.post(
    f"{API_BASE_URL}/docking",
    headers=headers,
    json=dock_data
)
new_task = response.json()
print(f"新任务ID: {new_task['task_id']}")
```

### 3. 用户迁移流程

当用户想要从第三方服务迁移到直接使用我们的系统时：

```python
# 用户在我们的系统注册后，可以声明之前的影子账户
import requests

# 用户使用JWT token认证
user_headers = {
    "Authorization": "Bearer <user_jwt_token>",
    "Content-Type": "application/json"
}

# 1. 检查是否有可迁移的影子账户
response = requests.get(
    f"{API_BASE_URL}/user-migration/check-shadow-account/{EXTERNAL_USER_ID}/{SERVICE_API_KEY}",
    headers=user_headers
)
migration_status = response.json()

if migration_status["has_shadow_account"]:
    print(f"发现影子账户，有 {migration_status['task_count']} 个任务可以迁移")
    
    # 2. 执行账户迁移
    claim_data = {
        "external_user_id": EXTERNAL_USER_ID,
        "service_name": SERVICE_API_KEY
    }
    response = requests.post(
        f"{API_BASE_URL}/user-migration/claim-account",
        headers=user_headers,
        json=claim_data
    )
    
    if response.status_code == 200:
        print("账户迁移成功！之前的任务和数据已合并到当前账户")
    else:
        print(f"迁移失败: {response.json()}")
```

### 4. 系统行为说明

#### 4.1 自动用户映射
- 第一次调用时，系统会自动为 `external_user_id` 创建影子用户
- 所有任务和数据都关联到这个影子用户
- 后续调用会使用相同的映射关系

#### 4.2 数据隔离
- 不同服务的用户数据完全隔离
- 相同 `external_user_id` 在不同服务中被视为不同用户

#### 4.3 用户迁移
- 用户可以随时声明影子账户并迁移数据
- 迁移后，服务调用会自动映射到真实用户账户
- 支持多个影子账户合并到一个真实账户

### 5. 错误处理

```python
def call_docking_api(external_user_id, task_data):
    headers = {
        "X-API-Key": SERVICE_API_KEY,
        "X-External-User-ID": external_user_id,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/docking",
            headers=headers,
            json=task_data,
            timeout=30
        )
        
        if response.status_code == 400:
            error = response.json()
            if error.get("error_code") == "AUTH_MISSING_EXTERNAL_USER_ID":
                print("错误：缺少外部用户ID头部")
                return None
        elif response.status_code == 401:
            error = response.json()
            if error.get("error_code") == "AUTH_INVALID_API_KEY":
                print("错误：API密钥无效")
                return None
        elif response.status_code == 500:
            error = response.json()
            if error.get("error_code") == "AUTH_SERVICE_ERROR":
                print("错误：服务认证错误")
                return None
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None
```

### 6. 最佳实践

1. **用户ID管理**：确保 `external_user_id` 在您的系统中是唯一且稳定的
2. **错误处理**：处理所有可能的认证错误响应
3. **重试机制**：对于临时错误实现指数退避重试
4. **日志记录**：记录API调用日志以便问题排查
5. **用户通知**：告知用户可以迁移数据到独立账户
