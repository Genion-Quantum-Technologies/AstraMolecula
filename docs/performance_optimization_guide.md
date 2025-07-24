
# AutoDock Vina 性能优化指南

## 🚀 速度模式选择

### 1. ultra_fast (超快模式)
- **适用场景**: 快速概念验证，初步筛选
- **参数**: exhaustiveness=2, n_poses=3
- **特点**: 最快速度，较低精度
- **推荐**: 大批量初筛（>10000个化合物）

### 2. fast (快速模式)  
- **适用场景**: 大批量筛选，初步对接
- **参数**: exhaustiveness=4, n_poses=5
- **特点**: 平衡速度和基本精度
- **推荐**: 虚拟筛选，高通量对接

### 3. balanced (平衡模式) ⭐ 推荐
- **适用场景**: 日常对接任务
- **参数**: exhaustiveness=8, n_poses=10
- **特点**: 速度与精度的良好平衡
- **推荐**: 大多数研究场景

### 4. accurate (精确模式)
- **适用场景**: 重要化合物分析
- **参数**: exhaustiveness=16, n_poses=20
- **特点**: 高精度，较慢速度
- **推荐**: 先导化合物优化，重要结果验证

## ⚙️ 并行度优化

### 自动检测（推荐）
```python
# 设置 n_jobs=None 让系统自动检测最佳并行度
{
    "n_jobs": None,  # 自动检测
    "speed_mode": "balanced"
}
```

### 手动设置
```python
# 根据系统配置手动设置
{
    "n_jobs": 8,     # CPU核心数
    "speed_mode": "fast"
}
```

## 💾 内存优化建议

### 监控内存使用
- 每个Vina进程约需要100-200MB内存
- 16GB内存系统建议最大并行数: 50-80

### 内存不足时的优化
1. 减少并行数: `n_jobs = 4`
2. 使用更快模式: `speed_mode = "fast"`
3. 分批处理大量配体

## 🖥️ CPU优化建议

### 最佳实践
- 单个Vina实例使用1个CPU核心
- 通过多进程实现并行（而非多线程）
- 避免超过物理CPU核心数

### 超线程注意事项
- 16核CPU通常可以安全使用16个并行进程
- 避免使用超过物理核心数的进程数

## 📊 性能基准参考

| 模式 | 单配体时间 | 100配体时间(16核) | 适用场景 |
|------|-----------|------------------|----------|
| ultra_fast | ~5秒 | ~31秒 | 快速验证 |
| fast | ~10秒 | ~62秒 | 初步筛选 |
| balanced | ~20秒 | ~125秒 | 日常研究 |
| accurate | ~40秒 | ~250秒 | 精确分析 |

## 🔧 API使用示例

### 快速筛选
```bash
curl -X POST "http://localhost:8000/docking?speed_mode=fast" \
     -H "Content-Type: application/json" \
     -d '{
       "ligands": [...],
       "n_jobs": null
     }'
```

### 精确对接
```bash
curl -X POST "http://localhost:8000/docking?speed_mode=accurate" \
     -H "Content-Type: application/json" \
     -d '{
       "ligands": [...],
       "n_jobs": 8
     }'
```

## 📈 监控和诊断

### 系统资源监控
```bash
# CPU使用率
top -p `pgrep vina`

# 内存使用
free -h

# 进程数量
pgrep vina | wc -l
```

### 性能分析工具
```bash
python utils/performance_analyzer.py --ligands 100 --report
```

## ⚠️ 常见问题

### 1. 内存不足
**症状**: 系统变慢，进程被杀死
**解决**: 减少n_jobs或使用fast模式

### 2. CPU使用率不高
**症状**: CPU使用率低于预期
**解决**: 检查并行数设置，确保有足够配体

### 3. 结果精度不够
**症状**: 对接分数异常
**解决**: 使用balanced或accurate模式

### 4. 任务超时
**症状**: 长时间无响应
**解决**: 检查系统资源，分批处理

## 🎯 推荐配置

### 开发/测试环境
```json
{
    "speed_mode": "fast",
    "n_jobs": 4
}
```

### 生产环境（中等规模）
```json
{
    "speed_mode": "balanced", 
    "n_jobs": null
}
```

### 高性能集群
```json
{
    "speed_mode": "accurate",
    "n_jobs": 32
}
```
