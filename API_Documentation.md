# AstraMolecula API 接口文档

## 概述

AstraMolecula API 是一个分子计算、对接模拟和肽段优化的生物信息学计算服务系统，提供完整的任务生命周期管理和结果获取功能。

- **API版本**: 2.1.0
- **基础URL**: `http://your-server-url`
- **认证方式**: JWT Token / API Key

## 认证方式说明

AstraMolecula API 支持两种认证方式，除了登录/注册接口外，**所有业务接口都同时支持这两种认证方式**：

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
- ❌ 不支持管理员接口访问（管理员功能仅限JWT Token）

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
- `GET /logs/` - 查看系统日志（实时监控）

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
- [管理员接口](#管理员接口)
- [日志查看接口](#日志查看接口)
- [数据结构说明](#数据结构说明)
- [认证说明](#认证说明)
- [任务状态说明](#任务状态说明)

## 健康检查接口

### 健康检查

**接口地址**: `GET /health`

**描述**: API健康状态检查端点

**认证要求**: 无（开放接口）

**请求参数**: 无

**返回值**:
```json
{
  "status": "healthy",
  "message": "DockingVina API is running",
  "timestamp": "2025-08-27T14:40:00Z",
  "version": "2.0.0"
}
```

### 根路径访问

**接口地址**: `GET /`

**描述**: 根路径重定向到日志查看器

**认证要求**: 无（开放接口）

**返回值**: 重定向到 `/static/log-viewer.html`

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

### 获取当前用户信息

**接口地址**: `GET /me`

**描述**: 获取当前登录用户的详细信息

**认证要求**: JWT Token（不支持API Key认证）

**请求参数**: 无

**返回值**:
```json
{
  "id": "string",
  "username": "string",
  "email": "string",
  "phone": "string",
  "user_role": "string",
  "is_admin": "boolean",
  "created_at": "datetime",
  "updated_at": "datetime"
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

**描述**: 上传分子结构文件（PDB/PDBQT格式），用于分子对接和肽段优化

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

**说明**: 此接口支持上传PDB和PDBQT格式文件，可用于：
- 分子对接任务的受体文件
- 肽段优化任务的受体蛋白文件

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

### 分子对接成本估算

**接口地址**: `POST /docking/estimate-cost`

**描述**: 对分子对接任务进行成本预估，不实际提交任务

**认证要求**: JWT Token 或 API Key

**请求参数**: 与`/docking`接口相同的DockingRequest格式

**返回值**:
```json
{
  "status": "success",
  "message": "成本预估完成",
  "cost_estimate": {
    "estimated_compute_units": "float",
    "n_ligands": "integer",
    "parameters": "object",
    "calculation_details": "object"
  }
}
```

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
  "proteinmpnn_seed": "integer (默认37)",
  "n_iterations": "integer (默认5)",
  "n_rosetta_runs": "integer (默认20)"
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
  "finished_at": null,
  "total_compute_units": "float (可选)"
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
  "receptor_pdb_filename": "string",
  "n_iterations": "integer",
  "n_rosetta_runs": "integer"
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

### 获取任务详细成本信息

**接口地址**: `GET /tasks/{task_id}/cost`

**描述**: 获取任务的详细成本计算信息和计算单元消耗

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**:
```json
{
  "task_id": "string",
  "task_type": "string",
  "cost_summary": {
    "total_compute_units": "float",
    "calculation_details": "object",
    "parameters": "object"
  },
  "created_at": "datetime"
}
```

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

**说明**: 支持所有类型的任务（docking、generate、peptide_optimization）

## 文件下载接口总览

### 通用下载接口

| 接口 | 描述 | 适用任务类型 | 返回格式 |
|------|------|-------------|---------|
| `GET /tasks/{task_id}/download` | 下载任务所有结果文件 | 所有类型 | ZIP |

### 对接任务专用下载接口

| 接口 | 描述 | 返回格式 |
|------|------|---------|
| `GET /tasks/{task_id}/sdf/{filename}` | 下载特定SDF结构文件 | SDF |
| `GET /tasks/{task_id}/protein` | 下载蛋白质受体文件 | PDBQT |

### 肽段优化任务专用下载接口

| 接口 | 描述 | 返回格式 |
|------|------|---------|
| `GET /tasks/{task_id}/peptide/result/download` | 下载结果CSV文件 | CSV |
| `GET /tasks/{task_id}/peptide/output` | 下载整个输出文件夹 | ZIP |
| `GET /tasks/{task_id}/peptide/download/{filename}` | 下载单个结构文件 | PDB/SDF/MOL等 |
| `GET /tasks/{task_id}/peptide/protein` | 下载受体蛋白文件 | PDB |

### 下载对接任务SDF文件

**接口地址**: `GET /tasks/{task_id}/sdf/{filename}`

**描述**: 下载对接任务生成的特定SDF结构文件

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID
- `filename`: SDF文件名（必须以.sdf结尾）

**返回值**: SDF文件流

**说明**: 仅适用于docking任务，文件位于任务的output/docked目录下

### 下载对接任务蛋白质受体文件

**接口地址**: `GET /tasks/{task_id}/protein`

**描述**: 下载对接任务使用的蛋白质受体文件

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: PDBQT文件流

**说明**: 仅适用于docking任务，从dockRes.json中获取protein_path

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

**描述**: 下载肽段优化任务的结果CSV文件（原始文件下载）

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: CSV文件流

**说明**: 仅适用于peptide_optimization任务，下载output/result.csv文件

### 下载肽段优化输出文件夹

**接口地址**: `GET /tasks/{task_id}/peptide/output`

**描述**: 下载肽段优化任务的整个输出文件夹（ZIP压缩包）

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: ZIP文件流

**说明**: 仅适用于peptide_optimization任务，递归打包output目录下的所有文件

### 获取任务输入参数

**接口地址**: `GET /tasks/{task_id}/input`

**描述**: 获取任务的原始输入参数，用于重新提交或分析

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**支持的任务类型**: `docking`, `generate`

**返回值**: JSON对象（原始输入参数）

### 下载肽段优化单个文件

**接口地址**: `GET /tasks/{task_id}/peptide/download/{filename}`

**描述**: 下载肽段优化任务生成的单个结构文件（PDB/SDF/MOL/MOL2等）

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID
- `filename`: 文件名

**返回值**: 文件流（根据文件类型自动设置MIME类型）

**说明**: 支持多层目录搜索，包括output、middlefiles、input等目录

### 获取肽段优化受体蛋白文件

**接口地址**: `GET /tasks/{task_id}/peptide/protein`

**描述**: 获取肽段优化任务中的受体蛋白文件（5ffg.pdb），用于3D可视化

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: PDB文件流

## 管理员接口

> **注意**: 以下管理员接口仅支持JWT Token认证，不支持API Key认证。需要管理员权限的用户才能访问。

### 获取所有用户列表

**接口地址**: `GET /admin/users`

**描述**: 获取系统中所有用户的详细信息，包括影子用户

**认证要求**: JWT Token（需要管理员权限）

**请求参数**:
- `limit` (Query, 可选): 返回用户数量限制，默认100，最大1000

**返回值**:
```json
[
  {
    "id": "string",
    "username": "string",
    "email": "string",
    "phone": "string",
    "created_at": "datetime",
    "updated_at": "datetime",
    "is_shadow_user": "boolean",
    "source_system": "string",
    "external_user_id": "string",
    "created_by_service": "string",
    "user_role": "string",
    "is_admin": "boolean",
    "migrated_to": "string"
  }
]
```

### 获取所有任务列表

**接口地址**: `GET /admin/tasks`

**描述**: 获取系统中所有任务的详细信息，支持多维度筛选

**认证要求**: JWT Token（需要管理员权限）

**请求参数**:
- `limit` (Query, 可选): 返回任务数量限制，默认100，最大1000
- `user_id` (Query, 可选): 筛选特定用户的任务
- `task_type` (Query, 可选): 筛选特定类型的任务
- `status` (Query, 可选): 筛选特定状态的任务

**返回值**:
```json
[
  {
    "id": "string",
    "user_id": "string",
    "username": "string",
    "user_email": "string",
    "user_type": "string",
    "source_system": "string",
    "task_type": "string",
    "status": "string",
    "job_dir": "string",
    "created_at": "datetime",
    "started_at": "datetime",
    "finished_at": "datetime",
    "updated_at": "datetime",
    "progress_info": "object"
  }
]
```

### 获取系统统计信息

**接口地址**: `GET /admin/statistics`

**描述**: 获取系统整体运行统计数据，包括用户数量、任务分布等

**认证要求**: JWT Token（需要管理员权限）

**请求参数**: 无

**返回值**:
```json
{
  "users": {
    "total": "integer",
    "regular_users": "integer",
    "shadow_users": "integer",
    "admin_users": "integer"
  },
  "tasks": {
    "total": "integer",
    "by_status": {
      "pending": "integer",
      "processing": "integer",
      "finished": "integer",
      "failed": "integer"
    },
    "by_type": {
      "docking": "integer",
      "generate": "integer",
      "peptide_optimization": "integer"
    }
  }
}
```

### 获取任务成本信息

**接口地址**: `GET /tasks/{task_id}/cost`

**描述**: 获取任务的成本计算详情

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**:
```json
{
  "task_id": "string",
  "total_compute_units": "float",
  "cost_breakdown": "object",
  "calculation_details": "object"
}
```

### 下载任务输入文件

**接口地址**: `GET /tasks/{task_id}/input`

**描述**: 下载任务的输入配置文件

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: JSON文件流

### 获取多肽任务受体蛋白文件

**接口地址**: `GET /tasks/{task_id}/peptide/protein`

**描述**: 获取多肽优化任务使用的受体蛋白文件

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: PDB文件流

### 下载肽段特定文件

**接口地址**: `GET /tasks/{task_id}/peptide/download/{filename}`

**描述**: 下载肽段优化任务输出目录中的特定文件

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID
- `filename`: 文件名

**返回值**: 文件流

## 管理员接口

> **注意**: 以下接口仅限管理员用户访问，需要JWT Token认证且用户必须具有管理员权限。

### 获取所有用户列表

**接口地址**: `GET /admin/users`

**描述**: 管理员获取系统中所有用户的列表，包括普通用户和影子用户

**认证要求**: JWT Token（仅限管理员）

**请求参数**:
- `limit` (Query, 可选): 返回用户数量限制，默认100，范围1-1000

**返回值**:
```json
[
  {
    "id": "string",
    "username": "string",
    "email": "string",
    "phone": "string",
    "created_at": "datetime",
    "updated_at": "datetime",
    "is_shadow_user": "boolean",
    "source_system": "string",
    "external_user_id": "string",
    "created_by_service": "string",
    "user_role": "string",
    "is_admin": "boolean",
    "migrated_to": "string"
  }
]
```

### 获取所有任务列表

**接口地址**: `GET /admin/tasks`

**描述**: 管理员获取系统中所有任务的列表，支持多种筛选条件

**认证要求**: JWT Token（仅限管理员）

**请求参数**:
- `limit` (Query, 可选): 返回任务数量限制，默认100，范围1-1000
- `user_id` (Query, 可选): 筛选特定用户的任务
- `task_type` (Query, 可选): 筛选特定类型的任务
- `status` (Query, 可选): 筛选特定状态的任务

**返回值**:
```json
[
  {
    "id": "string",
    "user_id": "string",
    "username": "string",
    "user_email": "string",
    "user_type": "string",
    "source_system": "string",
    "task_type": "string",
    "status": "string",
    "job_dir": "string",
    "created_at": "datetime",
    "started_at": "datetime",
    "finished_at": "datetime",
    "updated_at": "datetime",
    "progress_info": "string"
  }
]
```

### 获取系统统计信息

**接口地址**: `GET /admin/statistics`

**描述**: 管理员获取系统的整体统计信息

**认证要求**: JWT Token（仅限管理员）

**请求参数**: 无

**返回值**:
```json
{
  "users": {
    "total": "integer",
    "regular_users": "integer",
    "shadow_users": "integer",
    "admin_users": "integer"
  },
  "tasks": {
    "total": "integer",
    "by_status": {
      "pending": "integer",
      "processing": "integer",
      "finished": "integer",
      "failed": "integer"
    },
    "by_type": {
      "docking": "integer",
      "generate": "integer",
      "peptide_optimization": "integer"
    }
  }
}
```

## 日志查看接口

### 获取可查看的日志文件列表

**接口地址**: `GET /logs/`

**描述**: 获取系统中可以查看的日志文件列表

**认证要求**: 无（开放接口）

**请求参数**: 无

**返回值**:
```json
{
  "available_logs": [
    {
      "name": "docking_service.log",
      "size": 12345,
      "modified": 1693737600.0,
      "path": "/logs/docking_service.log"
    },
    {
      "name": "tasks.log", 
      "size": 6789,
      "modified": 1693737500.0,
      "path": "/logs/tasks.log"
    }
  ],
  "count": 2
}
```

### 查看对接服务日志

**接口地址**: `GET /logs/docking_service.log`

**描述**: 查看对接服务的实时日志，支持行数限制和格式选择

**认证要求**: 无（开放接口）

**请求参数**:
- `lines` (Query, 可选): 返回最后N行日志，默认100行
- `format` (Query, 可选): 返回格式，text或json，默认text

**返回值**: 
- format=text: 纯文本日志内容
- format=json: JSON格式的结构化日志数据

**JSON格式返回值**:
```json
{
  "log_file": "docking_service.log",
  "total_lines": 1000,
  "returned_lines": 100,
  "entries": [
    {
      "line_number": 901,
      "content": "2025-09-03 16:55:03 | INFO | main.py:26 | Starting application..."
    }
  ]
}
```

### 查看任务日志

**接口地址**: `GET /logs/tasks.log`

**描述**: 查看任务处理的日志

**认证要求**: 无（开放接口）

**请求参数**:
- `lines` (Query, 可选): 返回最后N行日志，默认100行
- `format` (Query, 可选): 返回格式，text或json，默认text

**返回值**: 日志内容（格式同上）

### 实时查看对接服务日志

**接口地址**: `GET /logs/live/docking_service`

**描述**: 获取对接服务日志的最新内容，适合用于实时监控，包含日志级别解析

**认证要求**: 无（开放接口）

**请求参数**:
- `lines` (Query, 可选): 返回最后N行日志，默认50行

**返回值**:
```json
{
  "status": "success",
  "log_file": "docking_service.log",
  "total_lines": 1000,
  "returned_lines": 50,
  "last_update": 1693737600.0,
  "entries": [
    {
      "line_number": 951,
      "level": "INFO",
      "content": "2025-09-03 16:55:03 | INFO | main.py:26 | Starting application...",
      "timestamp": "2025-09-03 16:55:03"
    },
    {
      "line_number": 952,
      "level": "WARNING", 
      "content": "2025-09-03 16:59:48 | WARNING | middleware.py:169 | Unauthenticated request...",
      "timestamp": "2025-09-03 16:59:48"
    }
  ]
}
```

### 查看指定日志文件

**接口地址**: `GET /logs/{log_name}`

**描述**: 查看指定的日志文件内容

**认证要求**: 无（开放接口）

**路径参数**:
- `log_name`: 日志文件名（仅允许访问预定义的安全日志文件）

**请求参数**:
- `lines` (Query, 可选): 返回最后N行日志，默认100行
- `format` (Query, 可选): 返回格式，text或json，默认text

**返回值**: 日志内容

**安全说明**: 
- 仅允许访问预定义的日志文件：`docking_service.log`, `tasks.log`
- 如果访问不存在或不允许的文件，返回404错误
- 所有日志内容经过安全过滤，避免敏感信息泄露

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
  "finished_at": "datetime (可选)",
  "total_compute_units": "float (可选)"
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
X-External-User-ID: <external_user_identifier>
```

**支持的API Key列表**:
- `third-party-service-key-123`
- `another-service-key-456`  
- `test-api-key-789`
- 环境变量 `SERVICE_API_KEYS` 中配置的其他密钥

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
| 403 | 权限不足（如非管理员访问管理员接口）|
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

✅ **管理员功能**: 新增完整的管理员接口，支持用户管理、任务监控和系统统计

✅ **成本计算**: 支持任务成本预估和详细的计算单元追踪

✅ **向后兼容**: 现有使用JWT Token的客户端完全不受影响，继续正常工作

✅ **第三方友好**: 第三方服务可以通过API Key直接集成，无需复杂的登录流程

✅ **自动用户管理**: API Key认证自动处理用户映射和影子用户创建

✅ **统一架构**: 通过中间件统一处理两种认证方式，代码逻辑清晰

---

**文档版本**: v2.1.2  
**最后更新**: 2025年9月23日
**校正说明**: 本次更新基于代码分析完成了完整的API文档校正，确保文档与实际实现完全一致。主要更新包括：
- 修正API版本号和标题
- 新增健康检查和管理员接口文档  
- 完善肽段优化和任务管理相关端点
- 更新认证方式说明和错误代码
- 补充遗漏的下载和查询接口
- **新增文件下载接口总览表格，详细说明所有下载选项**
