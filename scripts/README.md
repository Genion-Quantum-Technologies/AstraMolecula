# Peptide API 客户端使用指南

这个目录包含了通过API提交Peptide优化任务的Python脚本。

## 📁 文件说明

### 核心脚本
- **`peptide_api_client.py`** - 完整的API客户端类，支持所有功能
- **`peptide_examples.py`** - 使用示例和快速入门脚本

### 功能特性
✅ **完整工作流程支持**：登录 → 上传文件 → 创建任务 → 监控状态 → 获取结果  
✅ **多种使用模式**：命令行工具、Python模块、交互式示例  
✅ **错误处理**：完善的异常处理和状态检查  
✅ **日志记录**：详细的操作日志，支持文件和控制台输出  
✅ **参数验证**：输入参数的完整性检查  

## 🚀 快速开始

### 1. 确保服务正在运行

确保以下服务已启动：
```bash
# dockingVina API服务 (端口8000)
cd /home/davis/projects/AstraMolecula/dockingVina
conda activate dockingvina_final
uvicorn main:app --host 0.0.0.0 --port 8000

# peptide_opt处理服务 (端口8001)
cd /home/davis/projects/AstraMolecula/peptide_opt
conda activate peptide
python main.py
```

### 2. 运行示例

```bash
# 进入scripts目录
cd /home/davis/projects/AstraMolecula/dockingVina/scripts

# 运行交互式示例
python peptide_examples.py

# 或直接运行特定示例
python peptide_examples.py 1  # 基础任务
python peptide_examples.py 2  # 分步骤执行
python peptide_examples.py 3  # 从docking结果创建
```

### 3. 命令行工具使用

```bash
# 基本用法
python peptide_api_client.py \
    --sequence "MKFLVNVAL" \
    --receptor "../test/5ffg.pdb"

# 完整参数示例
python peptide_api_client.py \
    --sequence "ANAERIVRT" \
    --receptor "/path/to/receptor.pdb" \
    --cores 4 \
    --cleanup \
    --n-poses 10 \
    --max-wait 60

# 只运行特定步骤
python peptide_api_client.py \
    --sequence "MKFLVNVAL" \
    --receptor "../test/5ffg.pdb" \
    --step 3 \
    --no-proteinmpnn

# 查看帮助
python peptide_api_client.py --help
```

## 📋 参数说明

### 必需参数
- `--sequence` / `-s`: 肽段序列（氨基酸单字母缩写）
- `--receptor` / `-r`: 受体PDB文件路径

### 可选参数
- `--base-url`: API服务器地址（默认: http://127.0.0.1:8000）
- `--username`: 用户名（默认: admin）
- `--password`: 密码（默认: Admin#2024）
- `--cores`: CPU核心数（默认: 4）
- `--cleanup`: 完成后清理中间文件
- `--step`: 只运行指定步骤（1-8），不指定则运行完整流程
- `--no-proteinmpnn`: 禁用ProteinMPNN优化
- `--n-poses`: 对接构象数量（默认: 10）
- `--max-wait`: 最大等待时间/分钟（默认: 60）

### 工具功能
- `--only-upload`: 只上传文件，不创建任务
- `--only-status TASK_ID`: 只查询指定任务的状态
- `--list-files`: 列出已上传的文件

## 🧬 Peptide优化流程说明

### 8个优化步骤
1. **结构预测** - 使用OmegaFold预测肽段3D结构
2. **氢原子添加** - 为受体和肽段添加氢原子
3. **分子对接** - 执行肽段与受体的分子对接
4. **原子排序** - 对结果进行原子排序和处理
5. **结合评分** - 计算结合亲和力评分
6. **结构合并** - 合并肽段和蛋白质结构
7. **ProteinMPNN优化** - 使用AI进行序列优化
8. **最终分析** - 生成最终分析报告

### 参数建议
- **快速测试**: `cores=2, n_poses=3, no-proteinmpnn`
- **标准运行**: `cores=4, n_poses=10, proteinmpnn_enabled`
- **高精度**: `cores=8, n_poses=20, proteinmpnn_enabled`

## 💡 使用技巧

### 1. 序列长度建议
- **测试**: 5-10个氨基酸
- **实际应用**: 10-50个氨基酸
- **注意**: 序列越长，计算时间越长

### 2. 文件管理
```bash
# 查看已上传的文件
python peptide_api_client.py --list-files

# 只上传文件（用于预先准备）
python peptide_api_client.py --only-upload --receptor file.pdb
```

### 3. 任务监控
```bash
# 查询特定任务状态
python peptide_api_client.py --only-status <task_id>

# 监控日志
tail -f peptide_api_client.log
```

### 4. 从Docking结果开始
如果你有docking结果，可以先用格式转换工具：
```bash
cd /home/davis/projects/AstraMolecula/dockingVina
python utils/format_converter.py \
    --peptide_pdbqt test/user3.pdbqt \
    --receptor_pdbqt test/user3.pdbqt \
    --output_dir test/converted_input

# 然后使用转换后的文件
python scripts/peptide_api_client.py \
    --sequence "$(head -2 test/converted_input/peptide.fasta | tail -1)" \
    --receptor "test/converted_input/5ffg.pdb"
```

## 🔧 故障排除

### 常见问题

1. **连接失败**
   ```
   ❌ 登录请求失败: Connection refused
   ```
   - 检查API服务是否启动
   - 确认端口8000可访问

2. **文件上传失败**
   ```
   ❌ 文件上传失败: 不支持的文件类型
   ```
   - 确保文件是.pdb或.pdbqt格式
   - 检查文件路径是否正确

3. **任务创建失败**
   ```
   ❌ 任务创建失败: Receptor PDB file not found
   ```
   - 确保受体文件已上传
   - 检查文件名是否正确

4. **任务超时**
   ```
   ⏰ 监控超时 (60 分钟)
   ```
   - 增加等待时间：`--max-wait 120`
   - 检查peptide_opt服务是否正常

### 调试技巧

1. **启用详细日志**
   ```python
   import logging
   logging.getLogger().setLevel(logging.DEBUG)
   ```

2. **检查任务状态**
   ```bash
   # 查看任务详细状态
   python peptide_api_client.py --only-status your_task_id
   ```

3. **检查服务日志**
   ```bash
   # dockingVina服务日志
   tail -f /home/davis/projects/AstraMolecula/dockingVina/logs/tasks.log
   
   # peptide_opt服务日志
   tail -f /home/davis/projects/AstraMolecula/peptide_opt/logs/peptide_optimization.log
   ```

## 📊 结果文件

任务完成后，结果文件位于：
```
jobs/peptide_optimization/{task_id}/
├── input/
│   ├── 5ffg.pdb           # 受体文件
│   └── peptide.fasta      # 肽段序列
├── output/
│   └── result.csv         # 最终分析结果
└── optimization_config.txt # 任务配置
```

## 🔗 相关文档

- [API文档](../API_Documentation.md)
- [Peptide优化系统说明](../docs/peptide_cost_calculation_system.md)
- [格式转换工具](../utils/format_converter.py)
- [完整工作流程测试](../test/test_full_peptide_workflow.py)
