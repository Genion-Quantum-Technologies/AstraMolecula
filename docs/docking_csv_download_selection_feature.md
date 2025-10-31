# 对接结果CSV下载 - 选中下载功能

## 功能概述

对接结果CSV下载接口现在支持**选择性下载**功能，用户可以：
- ✅ 下载所有对接结果
- ✅ 只下载选中的部分结果

## 更新内容

### 前端变更

#### 1. API函数更新 (`moleculeApi.ts`)

```typescript
/**
 * 下载分子对接结果CSV（推荐使用）
 * @param taskId 任务ID
 * @param selectedIndices 可选的选中结果索引数组，如果不传则下载所有结果
 */
export const downloadDockingResultsCSVFromBackend = async (
  taskId: string,
  selectedIndices?: number[]  // 新增参数
): Promise<{ success: boolean; message?: string; url?: string }>
```

**行为变化**:
- 不传 `selectedIndices`：下载所有结果（原有行为）
- 传入索引数组：只下载指定索引的结果（新功能）

#### 2. 组件更新 (`DockingTaskDetail/index.tsx`)

```typescript
const handleDownloadCSV = async () => {
  // 如果有选中的结果，传递索引；否则传递 undefined（下载全部）
  const selectedIndices = selectedResults.size > 0 
    ? Array.from(selectedResults) 
    : undefined;
  
  const response = await downloadDockingResultsCSVFromBackend(taskId, selectedIndices);
  
  // 文件名区分是全部还是选中的
  const filename = selectedIndices 
    ? `docking_results_${taskId}_selected.csv`
    : `docking_results_${taskId}.csv`;
  // ...
};
```

### 后端变更

#### API接口更新

**接口地址**: `GET /tasks/{task_id}/docking/results/csv`

**新增查询参数**:
```
indices (可选): 选中的结果索引，用逗号分隔
```

**示例**:
```bash
# 下载所有结果
GET /tasks/abc123/docking/results/csv

# 只下载索引 0, 2, 5 的结果
GET /tasks/abc123/docking/results/csv?indices=0,2,5
```

#### 实现逻辑

```python
@router.get("/{task_id}/docking/results/csv")
async def download_docking_results_csv(
    request: Request, 
    task_id: str,
    indices: Optional[str] = None  # 新增参数
):
    # 读取所有结果
    docking_results = json.loads(dockres_path.read_text(encoding="utf-8"))
    
    # 如果提供了索引参数，过滤结果
    if indices:
        selected_indices = [int(i.strip()) for i in indices.split(',')]
        filtered_results = [
            docking_results[idx] 
            for idx in selected_indices 
            if 0 <= idx < len(docking_results)
        ]
        docking_results = filtered_results
    
    # 生成CSV...
```

## 使用场景

### 场景1：下载所有结果

**前端操作**:
1. 不选择任何结果（或全选）
2. 点击 "Download CSV" 按钮

**结果**:
- 下载包含所有对接结果的CSV文件
- 文件名：`docking_results_{task_id}.csv`

### 场景2：下载选中的结果

**前端操作**:
1. 勾选想要下载的结果（如第1、3、6个）
2. 点击 "Download CSV" 按钮

**结果**:
- 只下载选中结果的CSV文件
- 文件名：`docking_results_{task_id}_selected.csv`
- CSV中只包含选中的结果

## 技术细节

### 索引处理

- **索引起始**: 0（第一个结果的索引为0）
- **索引格式**: 逗号分隔的数字字符串，如 "0,2,5"
- **URL编码**: 前端自动进行URL编码
- **超出范围**: 超出范围的索引会被忽略，记录警告日志但不报错

### 错误处理

| 情况 | 行为 | HTTP状态码 |
|------|------|-----------|
| 索引格式错误（包含非数字） | 返回错误信息 | 400 |
| 索引超出范围 | 忽略无效索引，继续处理 | 200 |
| 空索引列表 | 返回空CSV（只有表头） | 200 |
| 不传indices参数 | 返回所有结果 | 200 |

### 日志记录

```python
# 下载请求日志
logger.info("User %s downloading docking results CSV for task %s (indices: %s)", 
            user.username, task_id, indices or "all")

# 过滤后的结果数量
logger.info("Filtered to %d results from indices: %s", 
           len(docking_results), indices)

# 超出范围的索引警告
logger.warning("Index %d out of range for task %s (total results: %d)", 
              idx, task_id, len(docking_results))
```

## 测试

### 运行测试脚本

```bash
cd /home/davis/projects/AstraMolecula
python test/test_docking_csv_download_with_selection.py
```

### 手动测试

1. **准备工作**:
   - 确保有一个已完成的对接任务
   - 获取任务ID

2. **测试下载所有结果**:
   ```bash
   curl -X GET "http://localhost:8000/tasks/{task_id}/docking/results/csv" \
        -H "Authorization: Bearer {token}" \
        -o results_all.csv
   ```

3. **测试下载选中结果**:
   ```bash
   curl -X GET "http://localhost:8000/tasks/{task_id}/docking/results/csv?indices=0,2,5" \
        -H "Authorization: Bearer {token}" \
        -o results_selected.csv
   ```

4. **验证结果**:
   ```bash
   # 查看文件行数
   wc -l results_all.csv
   wc -l results_selected.csv
   
   # 查看文件内容
   cat results_selected.csv
   ```

## 兼容性

### 向后兼容

✅ **完全向后兼容**
- 不传 `indices` 参数时，行为与之前完全一致
- 现有的前端代码无需修改即可继续工作
- 只有在显式传入 `selectedIndices` 参数时才会启用过滤功能

### 前端兼容性

- ✅ 支持所有现代浏览器
- ✅ URL参数自动编码
- ✅ 文件名自动区分

### 后端兼容性

- ✅ 可选参数，不影响现有调用
- ✅ 支持 JWT Token 和 API Key 认证
- ✅ 保持与现有API的一致性

## 未来优化

可能的改进方向：

1. **前端UI优化**:
   - 显示已选中的结果数量
   - 添加"全选"/"反选"快捷按钮
   - 选中结果预览

2. **性能优化**:
   - 对于大量结果，考虑流式处理
   - 缓存常用的筛选结果

3. **功能扩展**:
   - 支持按评分范围筛选
   - 支持按SMILES模式筛选
   - 支持多种导出格式（Excel、JSON等）

## 相关文件

- 前端API: `/llm-front-docker-frontend-uni/src/api/moleculeApi.ts`
- 前端组件: `/llm-front-docker-frontend-uni/src/components/DockingTaskDetail/index.tsx`
- 后端路由: `/AstraMolecula/routers/tasks.py`
- API文档: `/AstraMolecula/API_Documentation.md`
- 测试脚本: `/AstraMolecula/test/test_docking_csv_download_with_selection.py`

## 更新日志

### v2.3.1 (2025-10-29)

**新增功能**:
- ✅ 支持选择性下载对接结果CSV
- ✅ 前端API函数支持可选的索引参数
- ✅ 后端接口支持indices查询参数
- ✅ 文件名自动区分全部/选中结果

**改进**:
- ✅ 增强的错误处理和日志记录
- ✅ 更详细的API文档说明
- ✅ 完整的测试脚本

**兼容性**:
- ✅ 完全向后兼容
- ✅ 不影响现有功能

---

**文档版本**: v1.0  
**最后更新**: 2025年10月29日  
**维护者**: 开发团队
