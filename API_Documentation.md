# DockingVina API 接口文档

## 概述

DockingVina API 是一个分子计算、对接模拟和肽段优化的生物信息学计算服务系统，提供完整的任务生命周期管理和结果获取功能。

- **API版本**: 2.0.0
- **基础URL**: `http://your-server-url`
- **认证方式**: JWT Token / API Key

## 认证方式说明

DockingVina API 支持两种认证方式，除了登录/注册接口外，**所有业务接口都同时支持这两种认证方式**：

### 1. JWT Token 认证（用户认证）

**适用场景**: 终端用户直接访问API、Web应用、移动端应用

**认证流程**:
1. 通过 `POST /login` 接口使用用户名密码获取JWT访问令牌
2. 在后续请求的Header中添加：
   ```
   Authorization: Bearer <access_token>
   ```

**特点**:
- ✅ 标准OAuth2流程，用户会话管理
- ✅ Token有过期时间，安全性高  
- ✅ 适合用户交互式应用
- ❌ 需要登录流程，不适合服务间调用

**示例**:
```bash
# 登录获取Token
curl -X POST "/login" -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"password123"}'

# 使用Token访问API
curl -X GET "/tasks/" -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

### 2. API Key 认证（服务认证）

**适用场景**: 第三方服务集成、自动化系统、批量处理、服务间调用

**认证流程**:
直接在请求Header中添加以下参数：
```
X-API-Key: <your_service_api_key>
X-External-User-ID: <external_user_identifier>
Content-Type: application/json
```

**特点**:
- ✅ 无需登录流程，直接访问
- ✅ 永久有效，适合长期服务
- ✅ 自动用户映射，首次访问自动创建内部用户
- ✅ 支持多种外部用户标识
- ✅ 适合自动化和批量处理

**支持的API Key列表**:
- `third-party-service-key-123`
- `another-service-key-456`  
- `test-api-key-789`
- 环境变量 `SERVICE_API_KEYS` 中配置的其他密钥

**用户映射机制**:
- 系统自动将 `X-External-User-ID` 映射到内部用户ID
- 首次访问时自动创建影子用户
- 所有操作都关联到对应的内部用户账户

**示例**:
```python
import requests

# 配置API Key认证
session = requests.Session()
session.headers.update({
    "X-API-Key": "third-party-service-key-123",
    "X-External-User-ID": "user123@your-service",
    "Content-Type": "application/json"
})

# 直接访问业务接口
response = session.get("/tasks/")
results = session.get("/tasks/{task_id}/dockRes")
```

### 3. 开放接口（无需认证）

以下实用工具接口无需任何认证即可访问：
- `GET /smiles2img` - SMILES转分子结构图片
- `GET /fragmentize` - 分子片段化处理

### 认证方式对比

| 认证方式 | 适用场景 | 优势 | 限制 | 推荐用途 |
|---------|----------|------|------|---------|
| **JWT Token** | 终端用户、Web/移动应用 | 标准流程、会话管理、高安全性 | 需要登录、Token过期 | 用户交互应用 |
| **API Key** | 第三方服务、自动化系统 | 无需登录、永久有效、自动映射 | 需要预配置Key | 服务间集成 |
| **开放访问** | 公共工具接口 | 无需认证、快速访问 | 功能受限 | 实用工具 |

### 认证优先级

中间件认证检查优先级：
1. **JWT Token**: 如果请求包含 `Authorization: Bearer <token>`，优先使用JWT认证
2. **API Key**: 如果没有JWT Token但包含 `X-API-Key` 和 `X-External-User-ID`，使用API Key认证
3. **开放接口**: 特定路径无需认证直接访问
4. **拒绝访问**: 如果以上都不满足，返回401未授权错误

**重要**: 现有JWT认证完全不受影响，API Key认证是额外增加的选项，两者可以并存使用。

## 目录

- [认证方式说明](#认证方式说明)
- [认证接口](#认证接口)
- [文件上传接口](#文件上传接口)  
- [分子相关接口](#分子相关接口)
- [对接计算接口](#对接计算接口)
- [肽段优化接口](#肽段优化接口)
- [任务管理接口](#任务管理接口)
- [数据结构说明](#数据结构说明)
- [认证说明](#认证说明)
- [任务状态说明](#任务状态说明)

## 认证接口

> **注意**: 以下认证接口仅用于获取JWT Token，不支持API Key认证方式。

### 用户登录

**接口地址**: `POST /login`

**描述**: 用户登录接口，校验用户名/密码后返回JWT访问令牌

**认证要求**: 无（使用用户名密码直接认证）

**请求参数**:
```json
{
  "username": "string",
  "password": "string"
}
```

**返回值**:
```json
{
  "access_token": "string",
  "token_type": "bearer"
}
```

### 用户注册

**接口地址**: `POST /signup`

**描述**: 用户注册接口，创建新用户账户

**认证要求**: 无（创建新账户）

**请求参数**:
```json
{
  "username": "string",
  "password": "string",
  "phone": "string (可选)",
  "email": "string (可选)"
}
```

**返回值**:
```json
{
  "message": "User created successfully"
}
```

## 文件上传接口

### 查看上传文件列表

**接口地址**: `GET /users/me/uploads`

**描述**: 获取当前用户的所有上传文件记录

**认证要求**: JWT Token 或 API Key

**请求参数**: 无

**返回值**:
```json
[
  {
    "id": "string",
    "filename": "string",
    "file_path": "string",
    "upload_time": "datetime",
    "file_size": "integer"
  }
]
```

### 上传分子结构文件

**接口地址**: `POST /upload_pdbqt`

**描述**: 上传分子结构文件（PDB/PDBQT格式）

**认证要求**: JWT Token 或 API Key

**请求参数**: 
- `files`: 文件列表（支持.pdb, .pdbqt格式）

**返回值**:
```json
{
  "message": "上传成功",
  "user_id": "string",
  "files": ["filename1.pdbqt", "filename2.pdb"]
}
```

## 分子相关接口

### SMILES转图片

**接口地址**: `GET /smiles2img`

**描述**: 将SMILES字符串转换为分子结构图片

**认证要求**: 无（开放接口）

**请求参数**:
- `smiles` (Query): SMILES分子字符串

**返回值**: PNG图片流

### 分子片段化

**接口地址**: `GET /fragmentize`

**描述**: 对分子进行片段化处理，返回分子片段信息

**认证要求**: 无（开放接口）

**请求参数**:
- `smiles` (Query): SMILES分子字符串

**返回值**:
```json
{
  "fragments": [
    {
      "variable_smiles": "string",
      "constant_smiles": "string",
      "record_id": "string",
      "normalized_smiles": "string",
      "attachment_order": "integer"
    }
  ]
}
```

### 分子生成任务

**接口地址**: `POST /generate`

**描述**: 提交分子生成任务，返回任务ID供后续查询

**认证要求**: JWT Token 或 API Key

**请求参数**:
```json
{
  "generateRequestList": [
    {
      "constSmiles": "string",
      "varSmiles": "string", 
      "mainCls": "string",
      "minorCls": "string",
      "deltaValue": "string",
      "num": "integer"
    }
  ]
}
```

**返回值**:
```json
{
  "task_id": "string"
}
```

## 对接计算接口

### 分子对接任务

**接口地址**: `POST /docking`

**描述**: 提交分子对接任务，支持自定义受体文件和对接参数

**认证要求**: JWT Token 或 API Key

**请求参数**:
```json
{
  "ligands": [
    {
      "smiles": "string",
      "title": "string"
    }
  ],
  "receptor_filename": "string (可选)",
  "center_x": "float",
  "center_y": "float", 
  "center_z": "float",
  "box_size_x": "float",
  "box_size_y": "float",
  "box_size_z": "float",
  "min_ph": "float (默认6.0)",
  "max_ph": "float (默认8.0)",
  "n_jobs": "integer (默认8)",
  "exhaustiveness": "integer (默认4)",
  "n_poses": "integer (默认20)"
}
```

**返回值**:
```json
{
  "task_id": "string",
  "status": "submitted",
  "message": "对接任务已成功提交",
  "details": {
    "job_id": "string",
    "job_directory": "string",
    "receptor_file": "string",
    "ligands_count": "integer",
    "ligand_titles": ["string"],
    "parameters": {
      "center": {"x": "float", "y": "float", "z": "float"},
      "box_size": {"x": "float", "y": "float", "z": "float"},
      "ph_range": {"min": "float", "max": "float"},
      "n_jobs": "integer",
      "exhaustiveness": "integer",
      "n_poses": "integer"
    }
  },
  "next_steps": {
    "check_status": "/tasks/{task_id}",
    "get_results": "/tasks/{task_id}/dockRes",
    "download_files": "/tasks/{task_id}/download"
  }
}
```

## 肽段优化接口

### 创建肽段优化任务

**接口地址**: `POST /peptide/optimize`

**描述**: 提交肽段优化任务，支持ProteinMPNN序列优化

**认证要求**: JWT Token 或 API Key

**请求参数**:
```json
{
  "peptide_sequence": "string",
  "receptor_pdb_filename": "string",
  "cores": "integer (默认12)",
  "cleanup": "boolean (默认true)",
  "step": "integer (可选，1-8)",
  "proteinmpnn_enabled": "boolean (默认true)",
  "n_poses": "integer (默认10)",
  "num_seq_per_target": "integer (默认10)",
  "proteinmpnn_seed": "integer (默认37)"
}
```

**返回值**:
```json
{
  "id": "string",
  "user_id": "string",
  "task_type": "peptide_optimization",
  "status": "pending",
  "job_dir": "string",
  "created_at": "datetime",
  "finished_at": null
}
```

### 获取肽段优化任务状态

**接口地址**: `GET /peptide/optimize/{task_id}`

**描述**: 获取指定肽段优化任务的状态

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: TaskResponse对象

### 获取肽段优化任务配置

**接口地址**: `GET /peptide/optimize/{task_id}/config`

**描述**: 获取肽段优化任务的配置参数

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**:
```json
{
  "cores": "integer",
  "cleanup": "boolean",
  "proteinmpnn_enabled": "boolean",
  "n_poses": "integer",
  "num_seq_per_target": "integer",
  "proteinmpnn_seed": "integer",
  "peptide_sequence": "string",
  "receptor_pdb_filename": "string"
}
```

## 任务管理接口

### 获取任务列表

**接口地址**: `GET /tasks/`

**描述**: 获取当前用户的所有任务列表（支持缓存优化）

**认证要求**: JWT Token 或 API Key

**返回值**: TaskResponse数组

### 获取任务详情

**接口地址**: `GET /tasks/{task_id}`

**描述**: 获取指定任务的详细状态和信息

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: TaskResponse对象

### 快速获取任务状态

**接口地址**: `GET /tasks/{task_id}/status`

**描述**: 快速获取任务状态（优化版本，用于轮询）

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**:
```json
{
  "status": "string",
  "progress": "integer", 
  "updated_at": "datetime",
  "poll_interval": "integer",
  "can_download": "boolean"
}
```

### 下载任务结果文件

**接口地址**: `GET /tasks/{task_id}/download`

**描述**: 下载任务所有结果文件的压缩包

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: ZIP文件流

### 获取分子生成结果

**接口地址**: `GET /tasks/{task_id}/geneRes`

**描述**: 获取分子生成任务的结果数据

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**:
```json
[
  {
    "smile": "string",
    "molwt": "float",
    "tpsa": "float", 
    "slogp": "float",
    "sa": "float",
    "qed": "float"
  }
]
```

### 获取分子对接结果

**接口地址**: `GET /tasks/{task_id}/dockRes`

**描述**: 获取分子对接任务的结果数据

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**:
```json
[
  {
    "title": "string",
    "pose": "integer",
    "score": "float",
    "smiles": "string", 
    "file": "string",
    "protein_path": "string",
    "ligand_properties": "object (可选)",
    "docking_parameters": "object (可选)",
    "file_size": "integer (可选)",
    "creation_time": "datetime (可选)"
  }
]
```

### 下载SDF结构文件

**接口地址**: `GET /tasks/{task_id}/sdf/{filename}`

**描述**: 下载对接任务生成的特定SDF结构文件

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID
- `filename`: SDF文件名

**返回值**: SDF文件流

### 下载蛋白质受体文件

**接口地址**: `GET /tasks/{task_id}/protein`

**描述**: 下载对接任务使用的蛋白质受体文件

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: PDBQT文件流

### 获取肽段优化结果数据

**接口地址**: `GET /tasks/{task_id}/peptide/result`

**描述**: 获取肽段优化任务的结果数据（JSON格式）

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**:
```json
{
  "task_id": "string",
  "task_status": "string",
  "created_at": "datetime",
  "finished_at": "datetime",
  "data": {
    "columns": ["string"],
    "index": ["string"],
    "rows": [
      {
        "index": "string",
        "values": {"column_name": "value"}
      }
    ]
  }
}
```

### 下载肽段优化结果CSV

**接口地址**: `GET /tasks/{task_id}/peptide/result/download`

**描述**: 下载肽段优化任务的结果CSV文件

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: CSV文件流

### 下载肽段优化输出文件夹

**接口地址**: `GET /tasks/{task_id}/peptide/output`

**描述**: 下载肽段优化任务的整个输出文件夹

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: ZIP文件流

## 数据结构说明

### TaskResponse
```json
{
  "id": "string",
  "user_id": "string", 
  "task_type": "string",
  "status": "string",
  "job_dir": "string",
  "created_at": "datetime",
  "finished_at": "datetime (可选)"
}
```

### MoleculeResponse  
```json
{
  "smile": "string",
  "molwt": "float",
  "tpsa": "float",
  "slogp": "float", 
  "sa": "float",
  "qed": "float"
}
```

### DockResponse
```json
{
  "title": "string",
  "pose": "integer",
  "score": "float",
  "smiles": "string",
  "file": "string",
  "protein_path": "string (可选)",
  "ligand_properties": "object (可选)",
  "docking_parameters": "object (可选)",
  "file_size": "integer (可选)",
  "creation_time": "datetime (可选)"
}
```

### Fragment
```json
{
  "variable_smiles": "string",
  "constant_smiles": "string", 
  "record_id": "string",
  "normalized_smiles": "string",
  "attachment_order": "integer"
}
```

## 认证说明

### JWT Token认证

1. 通过 `/login` 接口获取访问令牌
2. 在后续请求的Header中添加：
   ```
   Authorization: Bearer <access_token>
   ```

### API Key认证

部分接口支持API Key认证方式，在Header中添加：
```
X-API-Key: <your_api_key>
```

## 任务状态说明

| 状态 | 描述 | 轮询间隔建议 |
|------|------|-------------|
| `pending` | 任务已提交，等待处理 | 10秒 |
| `processing` | 任务正在执行中 | 5秒 |
| `finished` | 任务完成 | 停止轮询 |
| `failed` | 任务执行失败 | 停止轮询 |

## 错误处理

### 标准错误响应格式

```json
{
  "error": "string",
  "message": "string", 
  "path": "string",
  "method": "string",
  "error_code": "string",
  "details": "object (可选)",
  "suggestion": "string (可选)"
}
```

### 常见HTTP状态码

| 状态码 | 描述 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 202 | 任务处理中 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 404 | 资源未找到 |
| 410 | 任务失败 |
| 422 | 参数验证失败 |
| 425 | 任务待处理 |
| 500 | 服务器内部错误 |

## 使用示例

### 完整工作流示例

1. **用户注册和登录**
```bash
# 注册
curl -X POST "/signup" -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"password123","email":"test@example.com"}'

# 登录
curl -X POST "/login" -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"password123"}'
```

2. **上传受体文件**
```bash
curl -X POST "/upload_pdbqt" -H "Authorization: Bearer <token>" \
  -F "files=@protein.pdbqt"
```

3. **提交对接任务**
```bash
curl -X POST "/docking" -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "ligands": [{"smiles":"CCO","title":"ethanol"}],
    "receptor_filename": "protein.pdbqt", 
    "center_x": 10.0, "center_y": 15.0, "center_z": 20.0,
    "box_size_x": 20.0, "box_size_y": 20.0, "box_size_z": 20.0
  }'
```

4. **查询任务状态**
```bash
curl -X GET "/tasks/{task_id}/status" -H "Authorization: Bearer <token>"
```

5. **获取结果**
```bash  
curl -X GET "/tasks/{task_id}/dockRes" -H "Authorization: Bearer <token>"
```

### 第三方服务集成示例

使用API Key认证的完整工作流：

```python
import requests

# 配置API Key认证
session = requests.Session()
session.headers.update({
    "X-API-Key": "third-party-service-key-123",
    "X-External-User-ID": "user123@your-service",
    "Content-Type": "application/json"
})

# 1. 上传受体文件（无需登录）
with open("protein.pdbqt", "rb") as f:
    files = {"files": ("protein.pdbqt", f, "application/octet-stream")}
    upload_response = session.post("/upload_pdbqt", files=files)
    print("✅ 文件上传成功")

# 2. 提交对接任务（无需登录）
docking_data = {
    "ligands": [{"smiles": "CCO", "title": "ethanol"}],
    "receptor_filename": "protein.pdbqt",
    "center_x": 10.0, "center_y": 15.0, "center_z": 20.0,
    "box_size_x": 20.0, "box_size_y": 20.0, "box_size_z": 20.0
}
task_response = session.post("/docking", json=docking_data)
task_id = task_response.json()["task_id"]
print(f"✅ 对接任务提交成功: {task_id}")

# 3. 查询任务状态（无需登录）
status_response = session.get(f"/tasks/{task_id}/status")
print(f"📊 任务状态: {status_response.json()}")

# 4. 获取结果（无需登录）
results_response = session.get(f"/tasks/{task_id}/dockRes")
results = results_response.json()
print(f"🎉 获取到 {len(results)} 个对接结果")
```

## 认证方式总结

✅ **API改进完成**: 除了登录/注册接口外，所有业务接口现在都支持JWT Token和API Key两种认证方式

✅ **向后兼容**: 现有使用JWT Token的客户端完全不受影响，继续正常工作

✅ **第三方友好**: 第三方服务可以通过API Key直接集成，无需复杂的登录流程

✅ **自动用户管理**: API Key认证自动处理用户映射和影子用户创建

✅ **统一架构**: 通过中间件统一处理两种认证方式，代码逻辑清晰

---

**文档版本**: v2.0.0  
**最后更新**: 2025年8月6日
