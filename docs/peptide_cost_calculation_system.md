# Peptide优化成本计算系统使用说明

## 概述

本系统实现了基于理论计算总量模型的Peptide优化任务成本评估功能，为用户提供不依赖具体硬件的、纯理论的计算复杂度评分。

## 核心特性

### 1. 理论计算单元 (Compute Unit, CU)

系统定义了抽象的计算单位"计算单元 (CU)"，用于量化Peptide优化任务的总计算量。

**基准配置** (1 CU):
- 标准多肽长度: 10个氨基酸
- 单次Rosetta ddG评估
- 1次迭代，1次Rosetta运行

### 2. 计算公式

```
总计算单元 = (n_iterations × n_rosetta_runs) × (peptide_length / 10) ** 1.5
```

其中:
- **总计算次数**: `n_iterations × n_rosetta_runs`
- **复杂度因子**: `(peptide_length / 10) ** 1.5`
- **复杂度指数**: 1.5 (介于线性和二次方之间，模拟生物分子相互作用的非线性增长)

### 3. 复杂度分类

- **Low**: < 1 CU
- **Medium**: 1-10 CU
- **High**: 10-100 CU  
- **Very High**: 100-1000 CU
- **Extreme**: > 1000 CU

### 4. 复杂度因子解释

不同长度多肽的复杂度因子:
- 5氨基酸: `(5/10)^1.5 ≈ 0.354`
- 10氨基酸: `(10/10)^1.5 = 1.000` (基准)
- 15氨基酸: `(15/10)^1.5 ≈ 1.837`
- 20氨基酸: `(20/10)^1.5 ≈ 2.828`
- 30氨基酸: `(30/10)^1.5 ≈ 5.196`

## 数据库结构

### peptide_task_params 表

存储每个peptide优化任务的详细参数和计算量预测:

```sql
CREATE TABLE peptide_task_params (
    id CHAR(32) PRIMARY KEY,
    task_id CHAR(32) NOT NULL,
    peptide_sequence TEXT NOT NULL,
    peptide_length INT NOT NULL,
    n_iterations INT NOT NULL,
    n_rosetta_runs INT NOT NULL,
    total_calculations INT NOT NULL,
    complexity_factor DECIMAL(15,6) NOT NULL,
    total_compute_units DECIMAL(20,6) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
```

## 字段说明

| 字段 | 类型 | 说明 | 数据来源 |
|------|------|------|----------|
| `id` | CHAR(32) | 主键，唯一标识 | 系统生成UUID |
| `task_id` | CHAR(32) | 关联任务ID | 外键关联tasks表 |
| `peptide_sequence` | TEXT | 多肽序列 | 用户输入的氨基酸序列 |
| `peptide_length` | INT | 序列长度 | `len(peptide_sequence)` |
| `n_iterations` | INT | 迭代次数 | 用户设定的优化迭代总数 |
| `n_rosetta_runs` | INT | 每次迭代Rosetta运行数 | 用户设定的每次迭代Rosetta运行次数 |
| `total_calculations` | INT | 总计算次数 | `n_iterations × n_rosetta_runs` |
| `complexity_factor` | DECIMAL(15,6) | 复杂度因子 | `(peptide_length / 10) ** 1.5` |
| `total_compute_units` | DECIMAL(20,6) | 总计算单元 | `total_calculations × complexity_factor` |

## API 端点 (计划实现)

### 1. 成本预估 (无需创建任务)

**POST** `/peptide/estimate-cost`

用于在提交任务前预览成本。

**请求体示例**:
```json
{
  "peptide_sequence": "MKTAYIAKQRQISFVKSHFSRQLE",
  "n_iterations": 20,
  "n_rosetta_runs": 5
}
```

**响应示例**:
```json
{
  "status": "success",
  "message": "成本预估完成",
  "cost_estimate": {
    "task_id": "preview",
    "is_preview": true,
    "compute_units": {
      "total": 371.806401,
      "per_iteration": 3.718064,
      "per_rosetta_run": 0.743613,
      "baseline": "1 CU = single Rosetta run on 10-residue peptide"
    },
    "input_summary": {
      "peptide_sequence": "MKTAYIAKQRQISFVKSHFSRQLE",
      "peptide_length": "24 residues",
      "total_iterations": 20,
      "rosetta_runs_per_iteration": 5,
      "total_rosetta_runs": 100
    },
    "complexity_factors": {
      "length_impact": "3.72x",
      "length_explanation": "Length factor: (24/10)^1.5",
      "total_runs_impact": "100x"
    },
    "comparison": {
      "vs_standard_single_run": "371.8x",
      "category": "Very High",
      "equivalent_standard_runs": 371.8
    },
    "time_estimate": {
      "estimated_time": "6.2h",
      "total_minutes": 371.81,
      "breakdown": {
        "per_iteration": 18.59,
        "per_rosetta_run": 3.72
      }
    }
  }
}
```

### 2. 获取任务详细成本信息

**GET** `/tasks/{task_id}/cost`

获取已提交任务的详细成本分析。

## 核心模块

### 1. PeptideCostCalculator 类

位置: `utils/peptide_cost_calculator.py`

主要方法:
- `calculate_cost_factors()`: 计算所有成本相关因子
- `create_peptide_task_params()`: 创建并保存任务参数
- `get_cost_estimate_summary()`: 生成格式化的成本摘要
- `estimate_execution_time()`: 预估执行时间
- `estimate_cost_before_submission()`: 任务提交前的成本预估

### 2. PeptideTaskParamsService 类

位置: `database/services/peptide_task_params_service.py`

主要方法:
- `create_task_params()`: 创建任务参数记录
- `get_cost_summary()`: 获取任务成本摘要
- `estimate_cost_before_submission()`: 任务提交前的成本预估
- `get_simple_cost_info()`: 获取简化的成本信息

### 3. PeptideTaskParamsRepository 类

位置: `database/repositorys/peptide_task_params_repository.py`

负责数据库操作:
- `create_table_if_not_exists()`: 创建表结构
- `create()`: 插入新记录
- `get_by_task_id()`: 根据任务ID查询
- `delete_by_task_id()`: 删除记录

## 使用示例

### Python 代码示例

```python
from utils.peptide_cost_calculator import PeptideCostCalculator
from database.services.peptide_task_params_service import PeptideTaskParamsService

# 1. 成本预估（不保存到数据库）
estimate = PeptideTaskParamsService.estimate_cost_before_submission(
    peptide_sequence="MKTAYIAKQRQISFVKSHFSRQLE",
    n_iterations=20,
    n_rosetta_runs=5
)
print(f"预估成本: {estimate['compute_units']['total']:.2f} CUs")

# 2. 创建任务参数（保存到数据库）
params = PeptideTaskParamsService.create_task_params(
    task_id="your_task_id",
    peptide_sequence="ACDEFGHIKL",
    n_iterations=10,
    n_rosetta_runs=3
)

# 3. 获取任务成本摘要
cost_summary = PeptideTaskParamsService.get_cost_summary("your_task_id")
if cost_summary:
    print(f"任务成本: {cost_summary['compute_units']['total']} CUs")
```

### 计算示例

```python
# 示例1: 标准10氨基酸肽，单次运行
cost_factors = PeptideCostCalculator.calculate_cost_factors(
    peptide_sequence="ACDEFGHIKL",  # 10个氨基酸
    n_iterations=1,
    n_rosetta_runs=1
)
# 结果: 1.0 CU (基准)

# 示例2: 20氨基酸肽，复杂优化
cost_factors = PeptideCostCalculator.calculate_cost_factors(
    peptide_sequence="ACDEFGHIKLMNPQRSTVWY",  # 20个氨基酸
    n_iterations=50,
    n_rosetta_runs=10
)
# 结果: 约1414 CUs (500次计算 × 2.83复杂度因子)
```

## 部署步骤

### 1. 初始化数据库

```bash
cd /path/to/dockingVina
python scripts/init_peptide_database.py
```

### 2. 测试成本计算功能

```bash
# 测试核心计算逻辑
python test/test_peptide_cost_calculation.py
```

### 3. 验证数据库表

```sql
-- 查看表结构
DESCRIBE peptide_task_params;

-- 查看索引
SHOW INDEX FROM peptide_task_params;
```

## 理论模型说明

### 非线性复杂度因子

使用 `(length/10)^1.5` 的原因:

1. **生物分子复杂性**: 蛋白质折叠和相互作用的复杂度随长度非线性增长
2. **计算成本现实**: Rosetta等分子动力学软件的计算成本介于线性和二次方之间
3. **经验验证**: 1.5次方是分子模拟领域常用的复杂度近似

### 示例对比

| 序列长度 | 复杂度因子 | 相对于10氨基酸的倍数 |
|----------|------------|---------------------|
| 5        | 0.354      | 0.35x              |
| 10       | 1.000      | 1.00x (基准)       |
| 15       | 1.837      | 1.84x              |
| 20       | 2.828      | 2.83x              |
| 30       | 5.196      | 5.20x              |
| 50       | 11.180     | 11.18x             |

## 注意事项

1. **理论模型**: 成本计算基于理论模型，实际执行时间可能因硬件差异而有所不同
2. **氨基酸序列**: 仅支持标准20种氨基酸的单字母代码
3. **参数范围**: 建议迭代次数1-1000，Rosetta运行次数1-100
4. **数据库权限**: 确保应用有创建表和写入数据的权限

## 未来扩展

1. **实时硬件监控**: 结合实际硬件性能调整预估精度
2. **历史数据分析**: 基于历史执行记录优化预估算法
3. **参数优化建议**: 为用户提供迭代次数和Rosetta运行次数的建议
4. **批量任务成本**: 支持批量peptide优化任务的成本汇总分析
5. **API集成**: 与peptide优化服务的API端点集成
