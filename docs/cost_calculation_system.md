# 成本计算系统使用说明

## 概述

本系统实现了基于理论计算总量模型的分子对接任务成本评估功能，为用户提供不依赖具体硬件的、纯理论的计算复杂度评分。

## 核心特性

### 1. 理论计算单元 (Compute Unit, CU)

系统定义了抽象的计算单位"计算单元 (CU)"，用于量化分子对接任务的总计算量。

**基准配置** (1 CU/分子):
- 彻底性 (`exhaustiveness`): 8
- 盒子体积: 8000 Ų (20×20×20)
- 姿态数 (`n_poses`): 10

### 2. 计算公式

```
总计算单元 = (配体数量 × pH因子) × [核心对接因子 + 姿态生成因子]
```

其中:
- **pH因子**: 固定为 1.5 (平均每个SMILES生成1.5个变体)
- **核心对接因子**: `(exhaustiveness/8)² × (box_volume/8000)`
- **姿态生成因子**: `0.05 × (n_poses/10)`

### 3. 复杂度分类

- **Low**: < 1 CU
- **Medium**: 1-10 CU
- **High**: 10-100 CU  
- **Very High**: 100-1000 CU
- **Extreme**: > 1000 CU

## 数据库结构

### docking_task_params 表

存储每个docking任务的详细参数和计算量预测:

```sql
CREATE TABLE docking_task_params (
    id CHAR(32) PRIMARY KEY,
    task_id CHAR(32) NOT NULL,
    n_ligands INT NOT NULL,
    min_ph DECIMAL(3,1) NOT NULL,
    max_ph DECIMAL(3,1) NOT NULL,
    ph_factor DECIMAL(3,1) NOT NULL DEFAULT 1.5,
    center_x DECIMAL(10,3) NOT NULL,
    center_y DECIMAL(10,3) NOT NULL,
    center_z DECIMAL(10,3) NOT NULL,
    box_size_x DECIMAL(10,3) NOT NULL,
    box_size_y DECIMAL(10,3) NOT NULL,
    box_size_z DECIMAL(10,3) NOT NULL,
    box_volume DECIMAL(15,3) NOT NULL,
    exhaustiveness INT NOT NULL,
    n_poses INT NOT NULL,
    n_jobs INT NOT NULL,
    total_molecules DECIMAL(10,3) NOT NULL,
    core_docking_factor DECIMAL(15,6) NOT NULL,
    pose_generation_factor DECIMAL(10,6) NOT NULL,
    total_compute_units DECIMAL(20,6) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
```

## API 端点

### 1. 成本预估 (无需创建任务)

**POST** `/docking/estimate-cost`

用于在提交任务前预览成本。

**请求体**: DockingRequest

**响应示例**:
```json
{
  "status": "success",
  "message": "成本预估完成",
  "cost_estimate": {
    "task_id": "preview",
    "is_preview": true,
    "compute_units": {
      "total": 2.25,
      "per_ligand": 1.13,
      "baseline": "1 CU = standard config (exhaustiveness=8, box=20x20x20, poses=10)"
    },
    "input_summary": {
      "ligands": 2,
      "estimated_molecules": 3.0,
      "ph_range": "6.0 - 8.0",
      "box_volume": "15000 Ų",
      "exhaustiveness": 8,
      "poses": 15,
      "parallel_jobs": 4
    },
    "complexity_factors": {
      "exhaustiveness_impact": "1.00x",
      "box_volume_impact": "1.88x",
      "poses_impact": "1.50x"
    },
    "time_estimate": {
      "estimated_time": "2m",
      "total_minutes": 2.3,
      "note": "Estimation based on standard hardware"
    }
  }
}
```

### 2. 任务提交 (自动计算成本)

**POST** `/docking`

提交对接任务时会自动计算并保存成本信息。

**响应中新增字段**:
```json
{
  "task_id": "abc123",
  "cost_estimate": {
    "total_compute_units": 2.25,
    "per_ligand_cost": 1.13,
    "complexity_category": "Medium",
    "estimated_molecules": 3.0
  },
  "next_steps": {
    "get_cost_info": "/tasks/abc123/cost"
  }
}
```

### 3. 获取任务详细成本信息

**GET** `/tasks/{task_id}/cost`

获取已提交任务的详细成本分析。

**响应示例**:
```json
{
  "task_info": {
    "task_id": "abc123",
    "task_type": "docking",
    "status": "finished",
    "created_at": "2025-01-01T12:00:00",
    "finished_at": "2025-01-01T12:05:00"
  },
  "cost_details": {
    "compute_units": {
      "total": 2.25,
      "per_ligand": 1.13,
      "baseline": "1 CU = standard config"
    },
    "input_summary": {
      "ligands": 2,
      "estimated_molecules": 3.0,
      "ph_range": "6.0 - 8.0",
      "box_volume": "15000 Ų",
      "exhaustiveness": 8,
      "poses": 15,
      "parallel_jobs": 4
    },
    "complexity_factors": {
      "exhaustiveness_impact": "1.00x",
      "box_volume_impact": "1.88x", 
      "poses_impact": "1.50x"
    },
    "cost_breakdown": {
      "core_docking": 1.8750,
      "pose_generation": 0.0750,
      "total_per_molecule": 1.9500
    },
    "comparison": {
      "vs_standard_single_ligand": "2.3x",
      "category": "Medium"
    }
  }
}
```

## 核心模块

### 1. CostCalculator 类

位置: `utils/cost_calculator.py`

主要方法:
- `calculate_cost_factors()`: 计算所有成本相关因子
- `create_docking_task_params()`: 创建并保存任务参数
- `get_cost_estimate_summary()`: 生成格式化的成本摘要
- `estimate_execution_time()`: 预估执行时间

### 2. DockingTaskParamsService 类

位置: `database/services/docking_task_params_service.py`

主要方法:
- `create_task_params()`: 创建任务参数记录
- `get_cost_summary()`: 获取任务成本摘要
- `estimate_cost_before_submission()`: 任务提交前的成本预估

### 3. DockingTaskParamsRepository 类

位置: `database/repositorys/docking_task_params_repository.py`

负责数据库操作:
- `create_table_if_not_exists()`: 创建表结构
- `create()`: 插入新记录
- `get_by_task_id()`: 根据任务ID查询
- `delete_by_task_id()`: 删除记录

## 部署步骤

### 1. 初始化数据库

```bash
cd /path/to/dockingVina
python scripts/init_database.py
```

### 2. 测试成本计算功能

```bash
# 测试核心计算逻辑
python test/test_cost_calculation.py

# 测试API端点
python test/test_cost_api.py
```

### 3. 重启服务

```bash
# 重启应用服务以加载新功能
sudo systemctl restart your-app-service
```

## 使用示例

### Python 代码示例

```python
from utils.cost_calculator import CostCalculator

# 计算成本因子
cost_factors = CostCalculator.calculate_cost_factors(
    n_ligands=3,
    min_ph=6.0,
    max_ph=8.0,
    center_x=61.105,
    center_y=24.325,
    center_z=17.161,
    box_size_x=25.0,
    box_size_y=25.0,
    box_size_z=25.0,
    exhaustiveness=12,
    n_poses=15,
    n_jobs=6
)

print(f"总计算单元: {cost_factors['total_compute_units']:.2f} CUs")
```

### cURL 示例

```bash
# 成本预估
curl -X POST "http://localhost:8080/docking/estimate-cost" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ligands": [{"title": "test", "smiles": "CCO"}],
    "min_ph": 6.0,
    "max_ph": 8.0,
    "center_x": 61.105,
    "center_y": 24.325,
    "center_z": 17.161,
    "box_size_x": 20.0,
    "box_size_y": 25.0,
    "box_size_z": 30.0,
    "exhaustiveness": 8,
    "n_poses": 15,
    "n_jobs": 4
  }'

# 获取任务成本信息
curl -X GET "http://localhost:8080/tasks/{task_id}/cost" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 注意事项

1. **向后兼容**: 老任务没有成本信息，访问 `/tasks/{task_id}/cost` 会返回 404
2. **仅支持 docking 任务**: 其他任务类型访问成本API会返回 400 错误
3. **理论模型**: 成本计算基于理论模型，实际执行时间可能因硬件差异而有所不同
4. **数据库权限**: 确保应用有创建表和写入数据的权限

## 未来扩展

1. **实时硬件监控**: 结合实际硬件性能调整预估精度
2. **历史数据分析**: 基于历史执行记录优化预估算法
3. **成本优化建议**: 为用户提供参数调优建议
4. **批量任务成本**: 支持批量任务的成本汇总分析
