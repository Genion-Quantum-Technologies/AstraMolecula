# AstraMolecula API 接口文档

## 概述

AstraMolecula API 是一个分子计算、对接模拟和肽段优化的生物信息学计算服务系统，提供完整的任务生命周期管理和结果获取功能。

- **API版本**: 2.3.3
- **基础URL**: `http://your-server-url`
- **认证方式**: JWT Token / API Key

### 🆕 3D可视化增强 (v2.3.3)

- **Search Box可视化**: 3D查看器新增"Search Box"按钮，可视化显示对接搜索盒子
- **对接参数接口**: 新增 `GET /tasks/{task_id}/docking/params` 接口获取对接任务参数
- **盒子尺寸显示**: 在3D视图中显示对接盒子的中心坐标和尺寸信息

### 🆕 下载功能增强 (v2.3.2)

- **单独文件下载**: 支持下载单个对接结果文件（SDF/PDBQT）
- **选择性CSV下载**: Docking CSV下载支持indices参数，可下载选中结果
- **Binding Analysis下载**: 批量下载所有结合模式分析CSV文件
- **完整文档**: 补充所有下载接口的详细API文档

### 🆕 公开分享功能 (v2.3.1)

- **自动分享链接生成**: Docking和Peptide任务结果自动包含share_url字段
- **无需认证访问**: 分享链接可公开访问，无需登录或API Key
- **3D结构查看**: 支持完整的3D分子结构可视化功能
- **智能文件搜索**: 自动从input.json读取蛋白质文件路径
- **安全防护**: 文件类型限制、路径验证、任务验证等多重安全措施

### 🆕 新功能亮点 (v2.2.0)

- **服务端CSV生成**: 新增4个专用CSV下载端点，替代前端数据组装
- **性能优化**: 大数据量处理移至服务端，提升响应速度
- **安全增强**: 数据处理服务端化，减少敏感信息前端暴露
- **编码支持**: UTF-8 BOM编码确保中文字符完美显示
- **标准化**: 统一的CSV格式和文件命名规范

### 🔧 API接口优化 (v2.2.1)

- **统一CSV下载**: 推荐使用服务端生成的CSV接口，废弃客户端组装方式
- **接口清理**: 标记重复功能接口，优化API使用体验
- **向后兼容**: 保留原有接口以确保平滑迁移

### 🎯 肽段优化简化 (v2.3.0)

- **系统固定配置**: 肽段优化接口简化用户决策，使用系统最优配置
- **自动完整流程**: 默认执行完整优化流程，无需用户选择步骤
- **强制最佳实践**: cores=12, cleanup=True, proteinmpnn_enabled=True, n_poses=10
- **向后兼容**: 旧参数仍被接受但会被忽略，系统使用固定配置

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
- [新增的CSV下载接口](#新增的csv下载接口)
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
      "smiles": "string",  // 配体的SMILES表达式
      "title": "string"    // 配体名称/标识符
    }
  ],
  "receptor_filename": "string (可选)",  // 用户上传的受体PDBQT文件名，不提供则使用默认
  
  // 对接中心坐标 (Docking Center Coordinates) - 必填
  "center_x": "float",  // X轴坐标 (单位: Å)
  "center_y": "float",  // Y轴坐标 (单位: Å)
  "center_z": "float",  // Z轴坐标 (单位: Å)
  
  // 搜索盒子尺寸 (Search Box Dimensions) - 必填
  "box_size_x": "float",  // X轴方向尺寸 (单位: Å)
  "box_size_y": "float",  // Y轴方向尺寸 (单位: Å)
  "box_size_z": "float",  // Z轴方向尺寸 (单位: Å)
  
  // 配体准备参数
  "min_ph": "float (默认6.0)",  // 配体质子化pH范围下限
  "max_ph": "float (默认8.0)",  // 配体质子化pH范围上限
  
  // 计算参数
  "n_jobs": "integer (默认8)",          // 并行作业数
  "exhaustiveness": "integer (默认4)",  // 搜索彻底程度 (1-8，越高越准确但越慢)
  "n_poses": "integer (默认20)"         // 生成的配体构象数量
}
```

**参数详细说明**:

| 参数组 | 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|--------|------|------|--------|------|
| **配体信息** | `ligands` | array | ✅ | - | 要对接的配体分子列表 |
| | `ligands[].smiles` | string | ✅ | - | 配体的SMILES表达式 |
| | `ligands[].title` | string | ✅ | - | 配体的名称或标识符 |
| **受体文件** | `receptor_filename` | string | ❌ | protein_7UDP.pdbqt | 用户已上传的受体PDBQT文件名 |
| **对接中心坐标** | `center_x` | float | ✅ | 61.1053 | 对接盒子中心的X坐标 (单位: Å) |
| | `center_y` | float | ✅ | 24.3245 | 对接盒子中心的Y坐标 (单位: Å) |
| | `center_z` | float | ✅ | 17.1610 | 对接盒子中心的Z坐标 (单位: Å) |
| **搜索盒子尺寸** | `box_size_x` | float | ✅ | 20.0 | X轴方向的盒子尺寸 (单位: Å) |
| | `box_size_y` | float | ✅ | 25.0 | Y轴方向的盒子尺寸 (单位: Å) |
| | `box_size_z` | float | ✅ | 30.0 | Z轴方向的盒子尺寸 (单位: Å) |
| **配体准备** | `min_ph` | float | ❌ | 6.0 | 配体质子化状态的pH下限 |
| | `max_ph` | float | ❌ | 8.0 | 配体质子化状态的pH上限 |
| **计算资源** | `n_jobs` | integer | ❌ | 8 | 并行处理的作业数量 |
| **对接质量** | `exhaustiveness` | integer | ❌ | 4 | 搜索彻底程度 (1-8推荐，越高结果越准确但计算越慢) |
| | `n_poses` | integer | ❌ | 20 | 每个配体生成的构象数量 (推荐10-20) |

**🎯 重要提示**:

1. **对接中心坐标 (Center Coordinates)**:
   - 指定对接盒子的中心位置，通常设置在受体的结合口袋中心
   - 坐标单位为埃（Angstrom, Å）
   - 可通过分子可视化工具（如PyMOL、Chimera）查看受体结构并确定合适的中心坐标
   - 建议：基于已知配体或结合位点的坐标来设置

2. **搜索盒子尺寸 (Box Dimensions)**:
   - 定义配体可以移动的空间范围
   - 单位为埃（Å），以中心坐标为原点向各方向延伸
   - 盒子太小可能遗漏正确构象，太大会增加计算时间且降低精度
   - 建议：
     * 小分子配体：20×20×20 Å 通常足够
     * 中等大小分子：25×25×25 Å
     * 大分子或多个结合位点：30×30×30 Å 或更大
     * 搜索体积 = box_size_x × box_size_y × box_size_z

3. **Exhaustiveness（搜索彻底程度）**:
   - 控制AutoDock Vina搜索算法的迭代次数
   - 推荐值：4-8
   - 较高值提高准确性但显著增加计算时间
   - 计算时间与exhaustiveness成线性关系

**请求示例**:

```bash
# 使用JWT Token认证
curl -X POST "http://your-server-url/docking" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ligands": [
      {
        "smiles": "CC(C)Cc1ccc(cc1)C(C)C(O)=O",
        "title": "ibuprofen"
      },
      {
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "title": "aspirin"
      }
    ],
    "receptor_filename": "protein_7UDP.pdbqt",
    "center_x": 61.1053,
    "center_y": 24.3245,
    "center_z": 17.1610,
    "box_size_x": 20.0,
    "box_size_y": 25.0,
    "box_size_z": 30.0,
    "min_ph": 6.0,
    "max_ph": 8.0,
    "n_jobs": 8,
    "exhaustiveness": 4,
    "n_poses": 20
  }'

# 使用API Key认证
curl -X POST "http://your-server-url/docking" \
  -H "X-API-Key: third-party-service-key-123" \
  -H "X-External-User-ID: external_user_123" \
  -H "Content-Type: application/json" \
  -d '{
    "ligands": [
      {
        "smiles": "CC(C)Cc1ccc(cc1)C(C)C(O)=O",
        "title": "ibuprofen"
      }
    ],
    "center_x": 61.1053,
    "center_y": 24.3245,
    "center_z": 17.1610,
    "box_size_x": 20.0,
    "box_size_y": 25.0,
    "box_size_z": 30.0,
    "exhaustiveness": 6,
    "n_poses": 15
  }'
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

**描述**: 提交肽段优化任务，系统将自动使用最优配置执行完整的优化流程

**认证要求**: JWT Token 或 API Key

**系统固定配置**: 
- `cores`: 12 (CPU核心数)
- `cleanup`: True (自动清理中间文件)
- `proteinmpnn_enabled`: True (启用ProteinMPNN优化)
- `n_poses`: 10 (对接构象数量)
- `step`: None (执行完整优化流程)

**请求参数**:
```json
{
  "peptide_sequence": "string (必需)",
  "receptor_pdb_filename": "string (必需)",
  "num_seq_per_target": "integer (默认10)",
  "proteinmpnn_seed": "integer (默认37)",
  "n_iterations": "integer (默认5)",
  "n_rosetta_runs": "integer (默认20)",
  
  // 以下参数为向后兼容保留，但会被系统忽略
  "cleanup": "boolean (废弃，系统固定为true)",
  "step": "integer (废弃，系统固定执行完整流程)",
  "proteinmpnn_enabled": "boolean (废弃，系统固定为true)",
  "cores": "integer (废弃，系统固定为12)",
  "n_poses": "integer (废弃，系统固定为10)"
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

**描述**: 获取肽段优化任务的配置参数。系统固定参数将显示为预设值，用户配置参数显示实际设置值

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**:
```json
{
  // 系统固定配置（始终显示这些值）
  "cores": 12,
  "cleanup": true,
  "proteinmpnn_enabled": true,
  "n_poses": 10,
  // 注意：无step字段表示执行完整流程
  
  // 用户配置参数
  "num_seq_per_target": "integer",
  "proteinmpnn_seed": "integer",
  "n_iterations": "integer",
  "n_rosetta_runs": "integer",
  
  // 任务信息
  "peptide_sequence": "string",
  "receptor_pdb_filename": "string"
}
```

**说明**: 
- 系统固定参数（cores、cleanup、proteinmpnn_enabled、n_poses）始终显示为预设值
- 如果配置中没有step参数，表示执行完整优化流程
- 用户配置参数反映实际提交的值

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

### 获取对接任务参数（Search Box可视化）

**接口地址**: `GET /tasks/{task_id}/docking/params`

**描述**: 获取指定对接任务的配置参数，包括对接盒子的中心坐标和尺寸。用于前端3D可视化中显示Search Box（搜索盒子）

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**:
```json
{
  "success": true,
  "params": {
    "center_x": 61.1053,
    "center_y": 24.3245,
    "center_z": 17.1610,
    "box_size_x": 20.0,
    "box_size_y": 25.0,
    "box_size_z": 30.0,
    "exhaustiveness": 4,
    "n_poses": 20,
    "n_ligands": 5,
    "min_ph": 6.0,
    "max_ph": 8.0,
    "n_jobs": 8
  }
}
```

**返回字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `center_x` | float | 对接盒子中心X坐标 (Å) |
| `center_y` | float | 对接盒子中心Y坐标 (Å) |
| `center_z` | float | 对接盒子中心Z坐标 (Å) |
| `box_size_x` | float | 对接盒子X轴尺寸 (Å) |
| `box_size_y` | float | 对接盒子Y轴尺寸 (Å) |
| `box_size_z` | float | 对接盒子Z轴尺寸 (Å) |
| `exhaustiveness` | int | 搜索彻底程度参数 |
| `n_poses` | int | 生成的配体构象数量 |
| `n_ligands` | int | 配体分子数量 |
| `min_ph` / `max_ph` | float | pH范围 |
| `n_jobs` | int | 并行作业数 |

**前端使用场景**:
- 3D分子查看器中的"Search Box"按钮使用此接口获取参数
- 在蛋白质-配体3D视图中绘制对接搜索区域的边界框
- 显示对接盒子的尺寸信息（如 "20.0×25.0×30.0 Å"）

**错误响应**:
- `404`: 任务不存在或对接参数未找到
- `400`: 任务类型不是docking

**示例**:
```bash
curl -X GET "/tasks/{task_id}/docking/params" \
  -H "Authorization: Bearer <token>"
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

### 新增的CSV下载接口（服务端生成）

> **⭐ 新功能**: 以下接口替代了前端数据组装的方式，提供更好的性能、安全性和一致性
> 
> **⚠️ 重要**: 推荐使用以下服务端CSV生成接口，客户端CSV组装方式已标记为废弃

| 接口 | 描述 | 适用任务类型 | 返回格式 | 状态 |
|------|------|-------------|---------|------|
| `GET /tasks/{task_id}/generate/results/csv` | 下载分子生成结果CSV | generate | CSV | ✅ 推荐 |
| `GET /tasks/{task_id}/docking/results/csv?indices=0,1,2` | 下载分子对接结果CSV（支持选择性下载） | docking | CSV | ✅ 推荐 |
| `GET /tasks/{task_id}/peptide/optimization/csv` | 下载肽优化详细结果CSV | peptide_optimization | CSV | ✅ 推荐 |
| `GET /tasks/{task_id}/peptide/results/csv` | 下载肽优化简化结果CSV | peptide_optimization | CSV | ✅ 推荐 |

### 对接任务专用下载接口

| 接口 | 描述 | 返回格式 |
|------|------|---------|
| `GET /tasks/{task_id}/sdf/{filename}` | 下载单个对接结果文件（SDF/PDBQT格式） | SDF/PDBQT |
| `GET /tasks/{task_id}/protein` | 下载蛋白质受体文件 | PDBQT |
| `GET /tasks/{task_id}/docking/binding-analysis/csv/download` | 下载所有结合模式分析CSV文件 | ZIP |

### 肽段优化任务专用下载接口

| 接口 | 描述 | 返回格式 |
|------|------|---------|
| `GET /tasks/{task_id}/peptide/result/download` | 下载结果CSV文件（原始） | CSV |
| `GET /tasks/{task_id}/peptide/output` | 下载整个输出文件夹 | ZIP |
| `GET /tasks/{task_id}/peptide/download/{filename}` | 下载单个结构文件 | PDB/SDF/MOL等 |
| `GET /tasks/{task_id}/peptide/protein` | 下载受体蛋白文件 | PDB |

### 下载单个对接结果文件（SDF/PDBQT）

**接口地址**: `GET /tasks/{task_id}/sdf/{filename}`

**描述**: 下载对接任务生成的单个结构文件，支持SDF和PDBQT格式

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID
- `filename`: 文件名（支持.sdf和.pdbqt后缀）

**返回值**: 文件流（SDF或PDBQT格式）

**使用场景**:
- 下载单个对接结果的SDF文件（如 `ligand_001.sdf`）
- 下载单个对接结果的PDBQT文件（如 `ligand_001.pdbqt`）
- 支持前端单独下载功能

**说明**: 仅适用于docking任务，文件位于任务的output/docked目录下

**示例**:
```bash
# 下载SDF文件
curl -X GET "/tasks/{task_id}/sdf/ligand_001.sdf" \
  -H "Authorization: Bearer <token>" \
  -o ligand_001.sdf

# 下载PDBQT文件
curl -X GET "/tasks/{task_id}/sdf/ligand_001.pdbqt" \
  -H "Authorization: Bearer <token>" \
  -o ligand_001.pdbqt
```

### 下载分子对接结果CSV（支持选择性下载）

**接口地址**: `GET /tasks/{task_id}/docking/results/csv`

**描述**: 下载分子对接任务的结果CSV文件，支持下载全部结果或选中的结果

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**查询参数**:
- `indices` (可选): 结果索引，用逗号分隔（如 "0,2,5"），不传则下载所有结果

**返回值**: CSV文件流（UTF-8 BOM编码）

**CSV格式**:
```csv
Rank,Name,SMILES,Docking Score,File,Protein Path
1,ligand_001,CC(C)CC1=CC=C(C=C1)C(C)C(=O)O,-8.5,ligand_001.sdf,/path/to/protein.pdbqt
2,ligand_002,CC1=CC=C(C=C1)C(C)C,-7.8,ligand_002.sdf,/path/to/protein.pdbqt
```

**使用场景**:
- 下载所有对接结果: `GET /tasks/{task_id}/docking/results/csv`
- 下载选中结果: `GET /tasks/{task_id}/docking/results/csv?indices=0,2,5`
- 支持前端批量选择下载功能

**文件命名**:
- 下载全部: `docking_results_{task_id}.csv`
- 下载选中: `docking_results_{task_id}_selected.csv`

**示例**:
```bash
# 下载所有结果
curl -X GET "/tasks/{task_id}/docking/results/csv" \
  -H "Authorization: Bearer <token>" \
  -o docking_results.csv

# 下载索引为0,2,5的结果
curl -X GET "/tasks/{task_id}/docking/results/csv?indices=0,2,5" \
  -H "Authorization: Bearer <token>" \
  -o docking_results_selected.csv
```

### 下载结合模式分析文件

**接口地址**: `GET /tasks/{task_id}/docking/binding-analysis/csv/download`

**描述**: 下载分子对接任务中所有的结合模式分析CSV文件（打包为ZIP）

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: ZIP文件流，包含所有 `*_binding_mode_summary.csv` 文件

**ZIP内容**:
```
binding_analysis_{task_id}.zip
├── ligand_001_binding_mode_summary.csv
├── ligand_002_binding_mode_summary.csv
└── ligand_003_binding_mode_summary.csv
```

**CSV文件内容**:
每个CSV文件包含该化合物的结合模式分析结果，包括：
- 氢键信息
- 疏水相互作用
- π-π堆积
- 盐桥
- 其他相互作用类型

**使用场景**:
- 批量分析多个对接结果的结合模式
- 比较不同化合物的相互作用模式
- 导出用于发表或报告的分析数据

**说明**: 
- 仅适用于docking任务
- 需要任务状态为 `finished`
- CSV文件位于 `output/docked/binding_analysis/` 目录
- 使用BINANA工具生成的结合分析结果

**示例**:
```bash
curl -X GET "/tasks/{task_id}/docking/binding-analysis/csv/download" \
  -H "Authorization: Bearer <token>" \
  -o binding_analysis.zip
```

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
    "share_url": "string (🆕 v2.3.1)",
    "ligand_properties": "object (可选)",
    "docking_parameters": "object (可选)",
    "file_size": "integer (可选)",
    "creation_time": "datetime (可选)"
  }
]
```

**🆕 v2.3.1 新增字段**:
- `share_url`: 公开分享链接，无需登录即可访问3D结构查看器
  - 格式示例: `http://106.14.212.218/public/docking-viewer?taskId=xxx&filename=xxx.sdf`
  - 由后端自动生成，使用前端域名（不含端口号）
  - 支持通过公开API访问配体和蛋白质文件

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
        "values": {"column_name": "value"},
        "share_url": "string (🆕 v2.3.1)"
      }
    ]
  }
}
```

**🆕 v2.3.1 新增字段**:
- `rows[].share_url`: 公开分享链接，无需登录即可访问3D结构查看器
  - 格式示例: `http://106.14.212.218/public/peptide-viewer?taskId=xxx&filename=complex1.pdb`
  - 由后端自动生成，使用数字索引（complex1.pdb, complex2.pdb等）
  - 支持通过公开API访问完整的肽段-蛋白质复合物结构

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

## 🆕 公开分享功能 (v2.3.1)

### 概述

公开分享功能允许用户生成无需登录即可访问的分享链接，方便与他人分享分子对接和肽段优化的3D结构查看结果。

### 特性

- ✅ **无需认证**: 分享链接可以公开访问，接收者无需登录或API Key
- ✅ **自动生成**: 后端在返回任务结果时自动为每条记录生成share_url
- ✅ **3D可视化**: 支持完整的3D分子结构查看功能
- ✅ **安全防护**: 后端验证任务存在性、文件类型、路径安全等
- ✅ **自动搜索**: 对接任务自动从input.json读取蛋白质文件路径

### 分享链接格式

#### Docking任务分享链接
```
http://106.14.212.218/public/docking-viewer?taskId={task_id}&filename={sdf_filename}
```

**示例**:
```
http://106.14.212.218/public/docking-viewer?taskId=7cbd61b3aafb4d4489f4ba1eda58dab4&filename=analog_1-1-p0.sdf
```

#### Peptide任务分享链接
```
http://106.14.212.218/public/peptide-viewer?taskId={task_id}&filename={pdb_filename}
```

**示例**:
```
http://106.14.212.218/public/peptide-viewer?taskId=6295f6e6506442019750e18a89671d6c&filename=complex1.pdb
```

### 公开访问API端点

以下API端点支持无需认证的公开访问，用于分享链接功能：

#### 获取Docking任务SDF文件

**接口地址**: `GET /public/docking/{task_id}/sdf/{filename}`

**描述**: 获取对接任务的配体SDF文件内容（公开访问）

**认证要求**: 无（公开访问）

**路径参数**:
- `task_id`: 任务ID
- `filename`: SDF文件名

**安全措施**:
- 文件名格式验证（仅允许字母、数字、下划线、连字符、点号）
- 文件类型限制（仅允许.sdf文件）
- 路径安全检查（防止路径遍历攻击）
- 搜索范围限制（仅在output/docked目录）

**返回值**: SDF文件内容（text/plain）

#### 获取Docking任务蛋白质文件

**接口地址**: `GET /public/docking/{task_id}/protein`

**描述**: 获取对接任务的蛋白质受体文件内容（公开访问）

**认证要求**: 无（公开访问）

**路径参数**:
- `task_id`: 任务ID

**工作流程**:
1. 验证任务是否存在且类型为docking
2. 从任务目录的input/input.json文件读取receptor_pdbqt路径
3. 如果input.json中没有，在任务目录中搜索常见蛋白质文件名
4. 返回蛋白质文件内容

**安全措施**:
- 任务类型验证
- 文件类型限制（仅允许.pdb/.pdbqt文件）
- 路径安全检查
- 搜索深度限制（最大深度2层）

**返回值**: 蛋白质文件内容（text/plain）

#### 获取Peptide任务PDB文件

**接口地址**: `GET /public/peptide/{task_id}/complex/{filename}`

**描述**: 获取肽段优化任务的复合物PDB文件内容（公开访问）

**认证要求**: 无（公开访问）

**路径参数**:
- `task_id`: 任务ID
- `filename`: PDB文件名（如complex1.pdb）

**安全措施**:
- 文件名格式验证
- 文件类型限制（仅允许.pdb文件）
- 路径安全检查
- 搜索范围限制（仅在output目录及其子目录）

**搜索目录**:
- `{job_dir}/output/`
- `{job_dir}/output/complexes/`
- `{job_dir}/output/complex/`
- `{job_dir}/output/pdb/`
- `{job_dir}/output/pdbs/`

**返回值**: PDB文件内容（text/plain）

### 前端路由

公开访问页面通过以下前端路由访问：

- **Docking查看器**: `/public/docking-viewer`
- **Peptide查看器**: `/public/peptide-viewer`

### 使用流程

#### 1. 获取任务结果（包含share_url）

**Docking任务**:
```bash
curl -X GET "/tasks/{task_id}/dockRes" -H "Authorization: Bearer <token>"
```

返回示例:
```json
[
  {
    "title": "analog_1",
    "pose": 1,
    "score": -7.5,
    "smiles": "CCO",
    "file": "analog_1-1-p0.sdf",
    "protein_path": "/path/to/protein.pdbqt",
    "share_url": "http://106.14.212.218/public/docking-viewer?taskId=7cbd61b3&filename=analog_1-1-p0.sdf"
  }
]
```

**Peptide任务**:
```bash
curl -X GET "/tasks/{task_id}/peptide/result" -H "Authorization: Bearer <token>"
```

返回示例:
```json
{
  "data": {
    "rows": [
      {
        "index": "1",
        "values": {
          "Optimal sequence": "ACDEFGH",
          "Global score": 8.5
        },
        "share_url": "http://106.14.212.218/public/peptide-viewer?taskId=6295f6e6&filename=complex1.pdb"
      }
    ]
  }
}
```

#### 2. 复制并分享链接

前端自动显示Share按钮，用户点击即可复制生成的share_url。

#### 3. 接收者访问

接收者打开分享链接后，无需登录即可：
- 查看3D分子结构
- 旋转、缩放、平移视图
- 切换显示样式（Cartoon、Stick、Surface等）
- 查看原子和残基详细信息

### 安全注意事项

1. **文件名验证**: 所有文件名经过严格的正则表达式验证，防止路径遍历攻击
2. **文件类型限制**: 仅允许访问特定类型的文件（SDF、PDB、PDBQT）
3. **路径安全检查**: 使用`os.path.realpath()`确保文件在任务目录内
4. **任务验证**: 确认任务存在且类型正确
5. **CORS支持**: 响应包含适当的CORS头部，支持跨域访问
6. **缓存优化**: 返回`Cache-Control`头部，提升访问速度

### 限制和注意事项

- 分享链接永久有效（只要任务和文件仍然存在）
- 不建议分享包含敏感数据的任务结果
- 公开API不记录访问者信息
- 文件删除后分享链接将失效（返回404）

### 下载肽段特定文件

**接口地址**: `GET /tasks/{task_id}/peptide/download/{filename}`

**描述**: 下载肽段优化任务输出目录中的特定文件

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID
- `filename`: 文件名

**返回值**: 文件流

## 新增的CSV下载接口

以下是新增的服务端CSV生成和下载接口，替代了前端数据组装的方式，提供更好的性能和安全性：

### 下载分子生成结果CSV

**接口地址**: `GET /tasks/{task_id}/generate/results/csv`

**描述**: 下载分子生成任务结果的CSV文件，从服务端生成标准格式的CSV数据

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: CSV文件流

**CSV格式**:
```
SMILE,MolWt,TPSA,SLogP,SA,QED
CCO,46.07,20.23,-0.31,2.16,0.73
...
```

**说明**: 
- 仅适用于generate任务类型
- 从任务的output.json文件中读取分子数据并生成CSV
- 支持UTF-8 BOM编码，确保中文兼容性
- 文件命名格式：`generated_analogs_{task_id}.csv`

### 下载分子对接结果CSV

**接口地址**: `GET /tasks/{task_id}/docking/results/csv`

**描述**: 下载分子对接任务结果的CSV文件，从服务端生成标准格式的CSV数据。支持下载全部结果或仅下载选中的结果。

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**查询参数**:
- `indices` (可选): 选中的结果索引，用逗号分隔（如 "0,2,5"）
  - 不传此参数：下载所有结果
  - 传入索引：只下载指定索引的结果

**请求示例**:
```bash
# 下载所有结果
GET /tasks/{task_id}/docking/results/csv

# 只下载索引为 0, 2, 5 的结果
GET /tasks/{task_id}/docking/results/csv?indices=0,2,5
```

**返回值**: CSV文件流

**CSV格式**:
```
Ligand名称,SMILES表达式,对接评分 (Docking Score),SDF文件名
"ethanol","CCO",-5.20,"ligand_1.sdf"
...
```

**说明**: 
- 仅适用于docking任务类型
- 从任务的output/dockRes.json文件中读取对接数据并生成CSV
- 支持UTF-8 BOM编码，确保中文兼容性
- 文件命名格式：
  - 全部结果：`docking_results_{task_id}.csv`
  - 选中结果：`docking_results_{task_id}_selected.csv`
- 字符串字段自动添加引号并转义特殊字符
- 索引超出范围的会被忽略并记录警告日志

### 下载肽序列优化详细结果CSV

**接口地址**: `GET /tasks/{task_id}/peptide/optimization/csv`

**描述**: 下载肽序列优化任务的详细结果CSV文件，包含完整的优化分析数据

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: CSV文件流

**CSV格式**:
```
排名,原始序列,原始序列亲和力评分,原始序列总体评分,最优序列,总体评分,分子量,等电点,芳香性,不稳定指数,疏水性,亲水性,二级结构分数
1,"ACDEFG",1.23,4.56,"ACDEFH",7.89,750.5,7.2,0.15,25.3,-0.42,0.67,"{'helix': 0.3, 'sheet': 0.2}"
...
```

**说明**: 
- 仅适用于peptide_optimization任务类型
- 优先从output/result.json读取详细结果数据
- 如果result.json不存在，则返回现有的result.csv文件
- 支持UTF-8 BOM编码，确保中文兼容性
- 文件命名格式：`peptide_optimization_results_{task_id}.csv`

### 下载肽序列优化简化结果CSV

**接口地址**: `GET /tasks/{task_id}/peptide/results/csv`

**描述**: 下载肽序列优化任务的简化结果CSV文件，适用于主页面结果展示

**认证要求**: JWT Token 或 API Key

**路径参数**:
- `task_id`: 任务ID

**返回值**: CSV文件流

**说明**: 
- 仅适用于peptide_optimization任务类型
- 直接返回任务的output/result.csv文件
- 支持动态列结构，适配不同的结果格式
- 文件命名格式：`peptide_results_{task_id}.csv`
- 如果result.csv文件不存在，返回404错误

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

## 废弃接口说明

### 客户端CSV组装方式（已废弃）

以下前端实现的CSV组装方式已标记为废弃，建议迁移到对应的服务端生成接口：

| 废弃方式 | 替代接口 | 废弃原因 | 迁移建议 |
|---------|---------|---------|---------|
| 客户端组装对接结果CSV | `GET /tasks/{task_id}/docking/results/csv` | 大数据量性能问题 | 直接调用后端接口 |
| 客户端组装分子生成CSV | `GET /tasks/{task_id}/generate/results/csv` | 内存占用高 | 已在前端实现迁移 |

**迁移时间表**:
- v2.2.1: 标记为废弃，推荐新接口
- v2.3.0: 完全移除客户端CSV组装代码
- v3.0.0: 不再向后兼容

### 未使用但保留的接口

以下接口在前端暂未使用，但具有潜在价值，建议保留：

#### 高价值接口 ✅ 建议保留使用

| 接口 | 用途 | 建议使用场景 |
|------|------|-------------|
| `GET /tasks/{task_id}/cost` | 任务成本信息 | 用户查看计算成本 |
| `GET /docking/estimate-cost` | 对接成本预估 | 提交前成本评估 |
| `GET /tasks/{task_id}/input` | 任务输入参数 | 失败任务重新提交 |
| `GET /peptide/optimize/{task_id}/config` | 肽优化配置 | 调试和问题诊断 |

#### 管理员接口 ✅ 保留用于未来

| 接口 | 用途 | 计划 |
|------|------|------|
| `GET /admin/users` | 用户管理 | 未来管理后台 |
| `GET /admin/tasks` | 任务管理 | 系统监控 |
| `GET /admin/statistics` | 系统统计 | 运营分析 |

## 使用示例

### 新CSV下载功能示例

```python
import requests

# 使用JWT Token认证
headers = {"Authorization": "Bearer <your_jwt_token>"}

# 1. 下载分子生成结果CSV（推荐）
response = requests.get("/tasks/{task_id}/generate/results/csv", headers=headers)
if response.status_code == 200:
    with open("generated_molecules.csv", "wb") as f:
        f.write(response.content)
    print("✅ 分子生成结果CSV下载完成")

# 2. 下载对接结果CSV（推荐）
response = requests.get("/tasks/{task_id}/docking/results/csv", headers=headers)
if response.status_code == 200:
    with open("docking_results.csv", "wb") as f:
        f.write(response.content)
    print("✅ 对接结果CSV下载完成")

# 3. 下载肽优化详细结果CSV（推荐）
response = requests.get("/tasks/{task_id}/peptide/optimization/csv", headers=headers)
if response.status_code == 200:
    with open("peptide_optimization_detailed.csv", "wb") as f:
        f.write(response.content)
    print("✅ 肽优化详细结果CSV下载完成")

# 4. 下载肽优化简化结果CSV（推荐）
response = requests.get("/tasks/{task_id}/peptide/results/csv", headers=headers)
if response.status_code == 200:
    with open("peptide_results.csv", "wb") as f:
        f.write(response.content)
    print("✅ 肽优化简化结果CSV下载完成")
```

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

3. **提交肽段优化任务**
```bash
curl -X POST "/peptide/optimize" -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "peptide_sequence": "MKQIEDKIEEIESKQKKEIEALKMRESK",
    "receptor_pdb_filename": "protein.pdb",
    "num_seq_per_target": 10,
    "proteinmpnn_seed": 37,
    "n_iterations": 5,
    "n_rosetta_runs": 20
  }'
# 注意：系统将自动使用最优配置（cores=12, cleanup=true, proteinmpnn_enabled=true, 完整流程）
```

**或提交对接任务**
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

# 5. 🆕 下载CSV结果文件（新功能，推荐使用）
csv_response = session.get(f"/tasks/{task_id}/docking/results/csv")
if csv_response.status_code == 200:
    with open(f"docking_results_{task_id}.csv", "wb") as f:
        f.write(csv_response.content)
    print(f"📥 CSV文件下载完成: docking_results_{task_id}.csv")
else:
    print(f"❌ CSV下载失败: {csv_response.status_code}")

# 6. 🧬 提交肽段优化任务示例（系统自动最优配置）
peptide_data = {
    "peptide_sequence": "MKQIEDKIEEIESKQKKEIEALKMRESK",
    "receptor_pdb_filename": "protein.pdb",
    "num_seq_per_target": 10,
    "proteinmpnn_seed": 37,
    "n_iterations": 5,
    "n_rosetta_runs": 20
    # 注意：不需要指定cleanup、step、proteinmpnn_enabled等参数
    # 系统将自动使用最优配置：完整流程、启用ProteinMPNN、自动清理
}
peptide_response = session.post("/peptide/optimize", json=peptide_data)
peptide_task_id = peptide_response.json()["id"]
print(f"✅ 肽段优化任务提交成功: {peptide_task_id}")

# 下载肽段优化结果
peptide_csv = session.get(f"/tasks/{peptide_task_id}/peptide/optimization/csv")
if peptide_csv.status_code == 200:
    with open(f"peptide_results_{peptide_task_id}.csv", "wb") as f:
        f.write(peptide_csv.content)
    print(f"📥 肽段优化CSV下载完成: peptide_results_{peptide_task_id}.csv")
```

### 新CSV下载功能示例

```python
import requests

# 使用JWT Token认证
headers = {"Authorization": "Bearer <your_jwt_token>"}

# 1. 下载分子生成结果CSV
response = requests.get("/tasks/{task_id}/generate/results/csv", headers=headers)
if response.status_code == 200:
    with open("generated_molecules.csv", "wb") as f:
        f.write(response.content)
    print("✅ 分子生成结果CSV下载完成")

# 2. 下载对接结果CSV
response = requests.get("/tasks/{task_id}/docking/results/csv", headers=headers)
if response.status_code == 200:
    with open("docking_results.csv", "wb") as f:
        f.write(response.content)
    print("✅ 对接结果CSV下载完成")

# 3. 下载肽优化详细结果CSV
response = requests.get("/tasks/{task_id}/peptide/optimization/csv", headers=headers)
if response.status_code == 200:
    with open("peptide_optimization_detailed.csv", "wb") as f:
        f.write(response.content)
    print("✅ 肽优化详细结果CSV下载完成")

# 4. 下载肽优化简化结果CSV
response = requests.get("/tasks/{task_id}/peptide/results/csv", headers=headers)
if response.status_code == 200:
    with open("peptide_results_simple.csv", "wb") as f:
        f.write(response.content)
    print("✅ 肽优化简化结果CSV下载完成")
```

## 认证方式总结

✅ **API改进完成**: 除了登录/注册接口外，所有业务接口现在都支持JWT Token和API Key两种认证方式

✅ **管理员功能**: 新增完整的管理员接口，支持用户管理、任务监控和系统统计

✅ **成本计算**: 支持任务成本预估和详细的计算单元追踪

✅ **向后兼容**: 现有使用JWT Token的客户端完全不受影响，继续正常工作

✅ **第三方友好**: 第三方服务可以通过API Key直接集成，无需复杂的登录流程

✅ **自动用户管理**: API Key认证自动处理用户映射和影子用户创建

✅ **统一架构**: 通过中间件统一处理两种认证方式，代码逻辑清晰

✅ **🆕 公开分享**: 任务结果自动生成分享链接，支持无需登录的3D结构查看

---

**文档版本**: v2.3.2  
**最后更新**: 2025年12月9日  
**更新说明**: 本次更新补充完善下载接口文档，支持更灵活的文件下载功能。主要更新包括：

### 📥 下载功能增强 (v2.3.2)
- **单独文件下载**: 新增单个对接结果文件下载功能
  - `GET /tasks/{task_id}/sdf/{filename}` 支持下载SDF和PDBQT格式
  - 前端实现每个结果行的独立下载按钮
- **选择性CSV下载**: Docking CSV下载接口支持indices参数
  - `GET /tasks/{task_id}/docking/results/csv?indices=0,2,5` 
  - 支持前端批量选择下载功能
  - 自动区分文件命名（全部 vs 选中）
- **Binding Analysis下载**: 新增结合模式分析批量下载
  - `GET /tasks/{task_id}/docking/binding-analysis/csv/download`
  - 打包所有binding_mode_summary.csv为ZIP
  - 便于批量分析和比较
- **文档完善**: 补充所有下载接口的详细说明
  - 接口参数、返回格式、使用场景
  - 示例代码和最佳实践
  - 更新接口总览表格

### 🔧 技术细节
- **统一接口**: 所有下载接口遵循相同的认证和错误处理机制
- **灵活参数**: 支持可选参数实现不同下载场景
- **文件命名**: 智能文件命名，区分不同下载类型
- **向后兼容**: 不影响现有功能，纯新增接口

---

**历史版本更新记录**:

**v2.3.1** (2025年11月19日): 公开分享功能
- **自动生成分享链接**: 后端在返回任务结果时自动为每条记录生成share_url字段
- **无需认证访问**: 分享链接可以公开访问，接收者无需登录或API Key
- **智能URL生成**: 使用前端域名（不含端口号），确保链接正确性
- **文件名规范化**: Peptide任务使用数字索引（complex1.pdb, complex2.pdb等）
- **安全防护措施**: 多重验证机制，包括文件类型限制、路径安全检查等

### 🔧 技术实现
- **后端自动生成**: 修改`/tasks/{task_id}/dockRes`和`/tasks/{task_id}/peptide/result`接口
- **公开API端点**: 新增3个公开访问端点（无需认证）
  - `GET /public/docking/{task_id}/sdf/{filename}` - 获取SDF文件
  - `GET /public/docking/{task_id}/protein` - 获取蛋白质文件
  - `GET /public/peptide/{task_id}/complex/{filename}` - 获取PDB文件
- **前端路由**: 新增`/public/docking-viewer`和`/public/peptide-viewer`路由
- **智能搜索**: Docking任务自动从input.json读取receptor_pdbqt路径

### 📚 文档更新
- 新增"公开分享功能"章节，详细说明使用方法和安全措施
- 更新DockResponse和PeptideResult数据结构，添加share_url字段
- 添加公开API端点文档和使用示例
- 说明分享链接格式和工作流程

### 🔒 安全措施
- 文件名正则验证，防止路径遍历攻击
- 文件类型白名单限制（SDF/PDB/PDBQT）
- 路径安全检查（realpath验证）
- 任务类型验证和搜索深度限制
- CORS支持和缓存优化

### 🔄 向后兼容性
- 不影响现有API调用
- share_url为可选字段
- 前端可选择性使用分享功能
- 支持降级方案（前端生成链接）

---

**历史版本更新记录**:

**v2.3.0** (2025年10月20日): 肽段优化简化
- **系统固定配置**: 肽段优化使用预设的最优配置，简化用户决策
- **自动完整流程**: 默认执行完整优化流程（8个步骤），无需用户选择
- **最佳实践强制**: cores=12, cleanup=True, proteinmpnn_enabled=True, n_poses=10
- **参数精简**: 用户只需配置核心参数（序列、文件、迭代参数等）
- **向后兼容**: 废弃的参数仍被接受但会被忽略

**v2.2.0** (2025年8月27日): 新增服务端CSV生成功能，替代前端数据组装方式
- **服务端CSV生成**: 新增4个专用CSV下载端点，替代前端数据组装
- **性能优化**: 大数据量处理移至服务端，提升响应速度  
- **安全增强**: 数据处理服务端化，减少敏感信息前端暴露
- **编码支持**: UTF-8 BOM编码确保中文字符完美显示
- **标准化**: 统一的CSV格式和文件命名规范

**v2.1.2** (2025年9月23日): 完整API文档校正，确保与实际实现一致
- 修正API版本号和标题
- 新增健康检查和管理员接口文档  
- 完善肽段优化和任务管理相关端点
- 更新认证方式说明和错误代码
- 补充遗漏的下载和查询接口
- 新增文件下载接口总览表格
