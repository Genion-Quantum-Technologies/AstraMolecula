# AstraMolecula 项目重构说明

## 重构概述

本次重构将 AstraMolecula 项目从传统的扁平化 Python 项目结构迁移到符合现代 Python 最佳实践的 **src 布局**，提升了项目的可维护性、可测试性和专业性。

**重构日期**: 2026年1月12日  
**项目版本**: 2.1.0

---

## 重构目标

1. ✅ 采用现代 Python 项目标准结构（src 布局）
2. ✅ 使用 `pyproject.toml` 作为项目配置文件（PEP 517/518）
3. ✅ 改善模块组织和职责划分
4. ✅ 统一命名规范（使用下划线命名法）
5. ✅ 优化导入路径，避免循环依赖
6. ✅ 提升代码的可测试性和可维护性

---

## 项目结构对比

### 旧结构 (Before)

```
AstraMolecula/
├── main.py                    # 应用入口（根目录）
├── middleware.py              # 中间件（根目录）
├── async_task_processor.py   # 任务处理器（根目录）
├── config/                    # 配置模块
├── database/                  # 数据库模块
│   ├── models/
│   ├── repositorys/          # ❌ 拼写错误
│   └── services/
├── routers/                   # API 路由（根目录）
├── security/                  # 安全模块（根目录）
├── services/                  # 业务服务
│   └── storage/
├── models/                    # ML 模型（根目录）
├── preprocess/                # 预处理（根目录）
├── requests/                  # 请求模型（根目录）
├── responses/                 # 响应模型（根目录）
├── utils/                     # 工具函数（根目录）
└── test/                      # 测试目录（非标准命名）
```

**问题**:
- ❌ 缺少 `pyproject.toml`，使用老式的 `setup.py`
- ❌ 代码直接散落在根目录，与配置文件混在一起
- ❌ 模块职责划分不清晰
- ❌ 导入路径容易冲突
- ❌ 不符合现代 Python 打包标准

### 新结构 (After)

```
AstraMolecula/
├── pyproject.toml             # ✅ 现代项目配置
├── run.py                     # ✅ 兼容性启动脚本
├── README.md
├── .env
├── .gitignore                 # ✅ 已优化
├── environment.yml
├── src/                       # ✅ 源代码目录
│   └── astra_molecula/        # ✅ 主包（统一命名）
│       ├── __init__.py        # 包初始化，定义 ROOT
│       ├── app.py             # FastAPI 应用入口
│       ├── middleware.py      # 认证中间件
│       ├── task_processor.py  # 异步任务处理
│       │
│       ├── api/               # ✅ API 模块
│       │   ├── __init__.py
│       │   └── routers/       # API 路由
│       │       ├── __init__.py
│       │       ├── auth.py
│       │       ├── tasks.py
│       │       ├── docking.py
│       │       ├── peptide.py
│       │       └── ...
│       │
│       ├── core/              # ✅ 核心模块
│       │   ├── __init__.py
│       │   ├── config/        # 配置管理
│       │   │   ├── __init__.py
│       │   │   ├── settings.py
│       │   │   ├── settings.yaml
│       │   │   ├── api_config.py
│       │   │   ├── database_config.py
│       │   │   ├── ml_config.py
│       │   │   └── logging_config.py
│       │   └── security/      # 安全认证
│       │       ├── __init__.py
│       │       └── auth.py
│       │
│       ├── db/                # ✅ 数据库模块（重命名）
│       │   ├── __init__.py
│       │   ├── db.py          # 数据库连接
│       │   ├── models/        # 数据模型
│       │   │   ├── __init__.py
│       │   │   ├── user.py
│       │   │   ├── task.py
│       │   │   ├── upload.py
│       │   │   └── ...
│       │   ├── repositories/  # ✅ 数据仓库（修正拼写）
│       │   │   ├── __init__.py
│       │   │   ├── user_repository.py
│       │   │   ├── task_repository.py
│       │   │   └── ...
│       │   └── services/      # 数据服务
│       │       ├── __init__.py
│       │       ├── user_service.py
│       │       ├── task_service.py
│       │       └── ...
│       │
│       ├── ml/                # ✅ 机器学习模块
│       │   ├── __init__.py
│       │   ├── models/        # ML 模型
│       │   │   ├── __init__.py
│       │   │   ├── dataset.py
│       │   │   └── transformer/
│       │   └── preprocess/    # 数据预处理
│       │       ├── __init__.py
│       │       ├── data_preparation.py
│       │       ├── vocabulary.py
│       │       └── property_change_encoder.py
│       │
│       ├── schemas/           # ✅ Pydantic 模型
│       │   ├── __init__.py
│       │   ├── requests/      # 请求模型
│       │   │   ├── __init__.py
│       │   │   └── basic_request.py
│       │   └── responses/     # 响应模型
│       │       ├── __init__.py
│       │       └── basic_response.py
│       │
│       ├── services/          # ✅ 业务服务
│       │   ├── __init__.py
│       │   └── storage/       # 存储服务
│       │       ├── __init__.py
│       │       └── seaweed_storage.py
│       │
│       └── utils/             # ✅ 工具函数
│           ├── __init__.py
│           ├── log.py
│           ├── tools.py
│           ├── chem.py
│           └── ...
│
├── tests/                     # ✅ 测试目录（标准命名）
│   ├── __init__.py
│   ├── test_peptide_optimization.py
│   └── ...
│
├── docs/                      # 文档
├── cicd/                      # CI/CD 配置
├── resource/                  # 静态资源
└── logs/                      # 日志目录
```

**优势**:
- ✅ 使用 `pyproject.toml` 符合 PEP 517/518 标准
- ✅ src 布局避免导入问题，支持可编辑安装
- ✅ 模块职责清晰，易于维护
- ✅ 统一的包命名（`astra_molecula`）
- ✅ 符合现代 Python 项目规范

---

## 主要变更

### 1. 项目配置文件

**新增 `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "astra-molecula"
version = "2.1.0"
description = "AstraMolecula - Molecular Design and Docking API Service"
requires-python = ">=3.10"

[project.scripts]
astra-molecula = "astra_molecula.app:main"
```

### 2. 包结构调整

| 旧路径 | 新路径 | 说明 |
|--------|--------|------|
| `main.py` | `src/astra_molecula/app.py` | FastAPI 应用入口 |
| `middleware.py` | `src/astra_molecula/middleware.py` | 认证中间件 |
| `async_task_processor.py` | `src/astra_molecula/task_processor.py` | 任务处理器 |
| `config/` | `src/astra_molecula/core/config/` | 配置模块 |
| `security/` | `src/astra_molecula/core/security/` | 安全模块 |
| `database/` | `src/astra_molecula/db/` | 数据库模块 |
| `database/repositorys/` | `src/astra_molecula/db/repositories/` | 修正拼写 |
| `routers/` | `src/astra_molecula/api/routers/` | API 路由 |
| `models/` | `src/astra_molecula/ml/models/` | ML 模型 |
| `preprocess/` | `src/astra_molecula/ml/preprocess/` | 预处理 |
| `requests/` | `src/astra_molecula/schemas/requests/` | 请求模型 |
| `responses/` | `src/astra_molecula/schemas/responses/` | 响应模型 |
| `services/storage/` | `src/astra_molecula/services/storage/` | 存储服务 |
| `utils/` | `src/astra_molecula/utils/` | 工具函数 |
| `test/` | `tests/` | 测试目录 |

### 3. 导入路径更新

所有 Python 文件的导入路径已更新为新的包结构：

**旧导入方式**:
```python
from config import ROOT, setup_logging
from database.services import TaskService
from security.auth import get_current_user
from routers import tasks
from responses.basic_response import TaskResponse
```

**新导入方式**:
```python
from astra_molecula.core.config import ROOT, setup_logging
from astra_molecula.db.services import TaskService
from astra_molecula.core.security.auth import get_current_user
from astra_molecula.api.routers import tasks
from astra_molecula.schemas.responses import TaskResponse
```

---

## 启动方式

### 方法 1: 使用兼容性脚本（推荐）

```bash
cd /home/songyou/projects/AstraMolecula
python run.py
```

### 方法 2: 使用 uvicorn 直接运行

```bash
cd /home/songyou/projects/AstraMolecula
PYTHONPATH=src uvicorn astra_molecula.app:app --host 0.0.0.0 --port 8000
```

### 方法 3: 安装后运行

```bash
# 开发模式安装
pip install -e .

# 运行
astra-molecula
```

### 方法 4: 使用现有的 service 脚本

需要更新 `service` 脚本中的启动命令：

```bash
#!/bin/bash
cd /home/songyou/projects/AstraMolecula
PYTHONPATH=src uvicorn astra_molecula.app:app --host 0.0.0.0 --port 8000
```

---

## 测试运行

### 运行测试

```bash
cd /home/songyou/projects/AstraMolecula

# 运行所有测试
PYTHONPATH=src pytest tests/

# 运行单个测试文件
PYTHONPATH=src pytest tests/test_peptide_optimization.py

# 带覆盖率报告
PYTHONPATH=src pytest --cov=astra_molecula tests/
```

### 健康检查

```bash
# 启动应用后访问
curl http://localhost:8000/health

# 预期响应
{
  "status": "healthy",
  "message": "AstraMolecula API is running",
  "version": "2.1.0"
}
```

---

## 开发指南

### 添加新的 API 路由

1. 在 `src/astra_molecula/api/routers/` 创建新的路由文件
2. 在 `src/astra_molecula/api/routers/__init__.py` 中导出
3. 在 `src/astra_molecula/app.py` 中注册路由

```python
# 示例: src/astra_molecula/api/routers/new_feature.py
from fastapi import APIRouter

router = APIRouter(prefix="/new-feature", tags=["New Feature"])

@router.get("/")
async def get_feature():
    return {"message": "New feature"}
```

### 添加新的数据模型

1. 在 `src/astra_molecula/db/models/` 创建模型文件
2. 在 `src/astra_molecula/db/repositories/` 创建仓库文件
3. 在 `src/astra_molecula/db/services/` 创建服务文件

### 添加新的工具函数

在 `src/astra_molecula/utils/` 中添加工具函数，并在 `__init__.py` 中导出：

```python
# src/astra_molecula/utils/__init__.py
from .new_util import new_function

__all__ = ['get_logger', 'run_generate_runner', 'new_function']
```

---

## 代码质量工具

### 格式化代码

```bash
# 使用 black 格式化
black src/astra_molecula/

# 使用 isort 排序导入
isort src/astra_molecula/
```

### 代码检查

```bash
# 使用 flake8 检查代码风格
flake8 src/astra_molecula/

# 使用 mypy 检查类型
mypy src/astra_molecula/
```

---

## 迁移检查清单

- [x] 创建 `pyproject.toml` 配置文件
- [x] 创建 `src/astra_molecula/` 目录结构
- [x] 移动所有源代码文件到新结构
- [x] 更新所有导入路径
- [x] 创建各模块的 `__init__.py` 文件
- [x] 更新 `.gitignore` 文件
- [x] 创建兼容性启动脚本 `run.py`
- [x] 删除旧的目录和文件
- [x] 清理 `__pycache__` 目录
- [x] 更新测试目录结构

---

## 注意事项

### 1. PYTHONPATH 设置

如果直接运行应用，需要设置 `PYTHONPATH`：

```bash
export PYTHONPATH=/home/songyou/projects/AstraMolecula/src
```

或在启动命令中指定：

```bash
PYTHONPATH=src uvicorn astra_molecula.app:app
```

### 2. 配置文件路径

配置文件 `settings.yaml` 位于 `src/astra_molecula/core/config/settings.yaml`，ROOT 路径已自动调整为项目根目录。

### 3. 静态资源路径

静态文件应放在项目根目录的 `static/` 目录中（如果需要）。

### 4. 日志文件

日志文件默认保存在项目根目录的 `logs/` 目录中。

### 5. 环境变量

`.env` 文件仍然在项目根目录，配置加载会自动查找。

---

## 向后兼容性

### 兼容性脚本

`run.py` 提供了向后兼容的启动方式，自动设置 `PYTHONPATH`。

### 渐进式迁移

如果有外部脚本或服务依赖旧的启动方式，可以：

1. 使用 `run.py` 作为入口点
2. 创建软链接（不推荐）
3. 更新启动脚本中的路径

---

## 常见问题

### Q1: 启动时提示 "No module named 'astra_molecula'"

**解决方案**: 设置 PYTHONPATH 或安装包

```bash
# 方法1: 设置环境变量
export PYTHONPATH=/home/songyou/projects/AstraMolecula/src

# 方法2: 安装包
pip install -e .
```

### Q2: 导入错误 "ImportError: attempted relative import beyond top-level package"

**解决方案**: 确保使用正确的导入路径，从 `astra_molecula` 开始。

### Q3: 如何在其他项目中使用这个包？

**解决方案**: 安装包后导入

```bash
# 安装
pip install -e /home/songyou/projects/AstraMolecula

# 在其他项目中使用
from astra_molecula.db.services import TaskService
from astra_molecula.core.config import setup_logging
```

---

## 性能影响

本次重构 **不影响运行时性能**，仅改变了代码组织方式。所有业务逻辑保持不变。

---

## 后续优化建议

1. **添加类型注解**: 为所有函数添加完整的类型注解
2. **完善测试**: 提高测试覆盖率到 80% 以上
3. **添加文档**: 使用 Sphinx 生成 API 文档
4. **配置管理**: 考虑使用 Pydantic Settings 管理配置
5. **依赖管理**: 考虑使用 Poetry 或 PDM 管理依赖
6. **CI/CD**: 更新 CI/CD 配置以适应新的项目结构

---

## 参考资料

- [PEP 517 - A build-system independent format for source trees](https://peps.python.org/pep-0517/)
- [PEP 518 - Specifying Minimum Build System Requirements](https://peps.python.org/pep-0518/)
- [Python Packaging User Guide](https://packaging.python.org/)
- [src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)

---

## 总结

本次重构成功将 AstraMolecula 项目迁移到现代 Python 项目标准结构，提升了项目的专业性和可维护性。所有功能保持不变，导入路径已全部更新，旧的目录和文件已清理。

**重构完成时间**: 2026年1月12日  
**影响文件数**: 100+ Python 文件  
**代码质量**: 符合 PEP 8 和现代 Python 最佳实践

---

*如有问题，请参考本文档或联系项目维护者。*
