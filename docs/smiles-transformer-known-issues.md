# SMILES Transformer —— 三个待修问题

> 配套文档：[smiles-transformer-architecture.md](smiles-transformer-architecture.md)（模型结构）
> 审计日期：2026-07-13 · 分支 `feat/tasks-info-column` · 所有结论均已对照源码/git/checkpoint 实测核实

按严重度排序。**问题一是阻断级**（决定 `generate` 功能能不能跑），问题二是性能，问题三是**静默数据正确性问题**（最危险，因为它不报错）。

| # | 问题 | 类型 | 影响 |
|---|---|---|---|
| [一](#问题一模型权重未纳入版本控制且不在工作区) | 模型权重 `resource/model_20.pt` 未纳入版本控制，且不在工作区（**本机已应急恢复，但根因未解**） | 阻断 / 供应链 | 干净 clone 构建的镜像里**没有权重**，`generate` 任务必 `FileNotFoundError`；权重曾一度只剩一个可被 `git gc` 回收的悬空对象 |
| [二](#问题二每个请求都重新加载-95mb-模型) | 每个请求都重新加载 95 MB 模型 | 性能 | 每次 generate 都 `torch.load` 全量 checkpoint（含用不上的 optimizer state），无任何缓存 |
| [三](#问题三pad-token-是合法的-smiles-字符-导致截断分子静默变成合法但错误的结果) | pad token 是合法 SMILES 字符 `*` | **静默正确性** | 被截断的生成会退化成"合法但错误"的分子，RDKit 照收，不报错、不告警 |

---

## 问题一：模型权重未纳入版本控制，且不在工作区

### 事实

- 推理时加载的权重路径由 `src/astra_molecula/utils/tools.py:50,52` 确定：`model_path = ROOT/'resource'`、`epoch = 20` → `resource/model_20.pt`（`utils/generate.py:71`）。
- 该文件被 **`.gitignore:50` 明确忽略**：`/resource/model_20.pt`。
- **它曾经不在工作区**。`resource/` 下只有 `vocab.pkl` 和 `fpscores.pkl.gz`；`git ls-files resource/` 同样只有这两个。
- **全盘搜索确认它在本机不存在**（`find /` 排除 conda/site-packages/node_modules 后，全系统只有三个 `.pt`：`/usr/share/vim/.../tutor.pt`（vim 教程）、`HighFold_C2C/c2c_model.pt`（另一个项目）、以及从 git blob 导出的临时副本）。**这不是"没找到"，是确实不存在。**
- 它曾被提交、随后又被删除：

  ```
  933b01d  删除大文件-模型文件
  d8081e9  create from yichao mac and with latest code before 2025.7.18
  ```

- **唯一幸存的副本是一个 git 悬空对象**：blob `7c18ed6ef7827da1c92a214e7f005da47a90dc16`，99,869,595 字节。已验证它是完整可加载的 checkpoint：

  ```
  top-level keys : ['model_state_dict', 'optimizer_state_dict', 'model_parameters']
  model_parameters: {'vocab_size': 920, 'N': 6, 'd_model': 128,
                     'd_ff': 2048, 'H': 8, 'dropout': 0.1}
  EncoderDecoder.load_from_file() → OK，7,868,824 可训练参数
  ```

  > **悬空对象随时可能被 `git gc` 回收。**

### ✅ 已做的应急处置（2026-07-13）

权重已从悬空 blob 恢复到代码期望的位置 `resource/model_20.pt`：

```
sha256  ee4acd68600f5ffb4a7fadd889d8da756794dc3c7b827acb50629bb205146c2e   （与 blob 逐字节一致）
size    99,869,595 B
校验    git check-ignore 确认仍被 .gitignore:50 覆盖 → 不会误提交
验证    EncoderDecoder.load_from_file('resource/model_20.pt') → OK，7,868,824 params
```

**这只是止血，不是修复。** 它仍然是一份**未版本化、单副本、只存在于这台机器上**的关键产物——换一台机器、或这台机器磁盘故障，问题原样复现。下面的持久化方案仍然必须做。

### 影响

Dockerfile 是无差别 `COPY . /app/`（`cicd/docker/Dockerfile:39`），且 `.dockerignore` **没有**排除 `resource/`。

→ **镜像里有没有权重，完全取决于执行 `docker build` 的那台机器上碰巧有没有这个未跟踪的 95 MB 文件。** 从干净 clone 构建出的镜像，每个 `generate` 任务都会在 `utils/generate.py:71` 处 `FileNotFoundError`。

这是一个**未版本化、未文档化、单副本的关键产物**——构建的可复现性完全依赖某台开发机的本地状态。

### 建议修复

1. ~~**立刻抢救副本**（在 `git gc` 之前）~~ — **已完成**，见上方「已做的应急处置」。若需在另一台机器重做：

   ```bash
   git cat-file -p 7c18ed6ef7827da1c92a214e7f005da47a90dc16 > resource/model_20.pt
   sha256sum resource/model_20.pt   # 应为 ee4acd68...46c2e
   ```

2. **换一个正经的产物存储**，不要塞回 git（95 MB 的二进制不适合 git，`.gitignore` 当初排除它是对的）：
   - 优先复用平台已有的 **SeaweedFS**（`services/storage/seaweed_storage.py`），启动时按 key + sha256 拉取到本地缓存；
   - 或走 registry（`hub.genionaitech.com`）作为独立的 model layer；
   - 或最简：放进 **git-lfs**。
3. **让缺失变成显式失败**：在启动时（而不是第一个请求进来时）校验权重存在 + sha256 匹配，不匹配就拒绝启动。同时给 `.dockerignore` 加上 `resource/model_20.pt`，杜绝"镜像里碰巧有"这种不确定性。
4. 顺手把 checkpoint 里的 `optimizer_state_dict` 剥掉再存（见问题二）。

---

## 问题二：每个请求都重新加载 95 MB 模型

### 事实

```python
# src/astra_molecula/utils/tools.py:42-59
def run_generate_runner(const_smiles, var_smiles, main_cls, minor_cls, delta_value, num_samples):
    opt = { ..., 'epoch': 20, 'model_path': str(ROOT / 'resource'), ... }
    runner = GenerateRunner(opt)          # ← 每个 generate 请求都新建一次
```

`GenerateRunner.__init__`（`utils/generate.py:65-75`）每次都会：

1. `pkl.load()` 整个 `vocab.pkl`；
2. `EncoderDecoder.load_from_file()` → `torch.load()` 整个 **95 MB** 的 `model_20.pt`；
3. 在 `make_model()` 里对全模型跑一遍 **xavier 初始化**（`model.py:57-59`），紧接着被 `load_state_dict` 完全覆盖——纯白做。

**没有任何模型缓存 / 单例 / lru_cache。**

### 为什么是 95 MB 而不是 30 MB

checkpoint 里除了 `model_state_dict`，还存了 **`optimizer_state_dict`**（Adam 的一阶 + 二阶矩，约 3× 权重体积）：

| 内容 | 大小 |
|---|---|
| 可训练参数 7,868,824 × fp32 | ≈ 30 MB |
| PE buffer 1,280,000 × fp32（两份 5000×128，实际只用到 256） | ≈ 5 MB |
| `optimizer_state_dict`（推理**完全用不到**） | ≈ 60 MB |
| **实际文件** | **95 MB** |

→ **每个请求都在反序列化 60 MB 推理根本不需要的 Adam 动量，然后立刻扔掉。**

### 建议修复

1. **模型单例 / 进程级缓存**（收益最大、改动最小）：把 `GenerateRunner` 的模型 + 词表提到模块级 lazy singleton，或用 `functools.lru_cache`。注意 `AsyncTaskProcessor` 用了线程池 + 进程池，要么在每个 worker 进程里各持一份，要么在 FastAPI 的 lifespan 里预热一次。
2. **瘦身 checkpoint**：另存一份只含 `model_state_dict` + `model_parameters` 的推理专用权重（95 MB → ~35 MB）。顺便可以把两份 5000×128 的 PE buffer 重建为 256 长度（省下 ~5 MB，且 PE 是确定性函数，不必进 checkpoint）。
3. **跳过无用的 xavier 初始化**：`load_from_file` 里给 `make_model` 加个 `init=False` 开关，加载权重时不要先随机初始化一遍。

---

## 问题三：pad token 是合法的 SMILES 字符 `*`，导致截断分子静默变成"合法但错误"的结果

**这是三个问题里最危险的一个——因为它不抛异常、不打日志，用户拿到的是一个 RDKit 认可的分子。**

### 事实链

1. **pad = id 0 = `'*'`**。词表构造时硬性把 `["*", "^", "$"]` 塞在最前面（`ml/preprocess/vocabulary.py:138`），而 `'*'` 在 SMILES 里是**合法的通配原子**（dummy atom）。`settings.yaml:100` 的 `padding_value: 0` 也指向它。

2. **解码后的序列用 0 右填充到 `max_len`**：

   ```python
   # src/astra_molecula/utils/generate.py:207-209
   sequences = decode(model, src_current, mask_current, max_len, decode_type)
   padding = (0, max_len - sequences.shape[1], 0, 0)
   sequences = torch.nn.functional.pad(sequences, padding)   # ← 用 0 填充 = 用 '*' 填充
   ```

3. **`untokenize` 只在遇到 `'$'` 时才截断**（`ml/preprocess/vocabulary.py:120-128`）：

   ```python
   for token in tokens:
       if token == "$": break
       if token != "^": smi += token
   ```

4. → **如果某条序列在 256 步内没能吐出 `'$'`**（`decode.py:13` 的循环跑满 `max_len-1`），就永远不会触发 break，那些填充出来的 `'*'` 会**直接拼进 SMILES 字符串**。

5. **RDKit 照单全收**：`uc.is_valid(smi)`（`generate.py:228`）对带 `*` 的 SMILES 返回 True，于是这个分子被当作一次"成功生成"计入结果，进入 `connect_constVar_try` → 描述符计算 → 返回给用户。

代码**明知并依赖**这一点，注释写得明明白白：

```python
# src/astra_molecula/utils/generate.py:169
# zeros correspondes to ****** which is valid according to RDKit
```

### 影响

一次**被截断的生成**（模型没在 256 步内收尾）不会表现为失败，而是表现为一个**带 `*` 后缀的、合法但错误的分子**。它会：

- 通过 `is_valid` 检查；
- 进入去重集合；
- 被计入 `num_valid_batch`，占掉一个用户要的名额；
- 拿到一组算出来的描述符（molwt / tpsa / slogp / sa / qed）——**这些数值是基于一个被截断的分子算的**。

用户和日志里**都看不到任何异常信号**。

### 顺带一提的相关 bug

同一段代码 `generate.py:170` 的 `sequences_all = torch.ones(...)` 把未采样槽位预填成 **token id 1（`'^'`）**，与上一行注释里说的 "zeros" 自相矛盾——未填充的槽位解码出来是空字符串而不是 `*`。两处对"填充值是什么"的假设是打架的。

### 建议修复

**最小改动、立刻见效**——在 `untokenize` 之前显式截断，别依赖 `'$'`：

```python
# 在 generate.py 的 valid 检查之前
seq = sequences[ibatch]
eos = (seq == 2).nonzero()
if len(eos) == 0:
    continue                       # 没有 EOS = 生成被截断 → 丢弃，不要当成 valid
seq = seq[:eos[0].item()]          # 只保留 EOS 之前的部分
smi = self.tokenizer.untokenize(self.vocab.decode(seq.cpu().numpy()))
```

配套建议：

1. **把"未收尾"计为失败并打点**：记录截断率（truncation rate）。如果这个比例不低，说明 `max_len=256` 对某些输入不够，或采样分布有问题——现在这个信号被完全掩盖了。
2. **长期**：换一个不与化学字符冲突的 pad token（如 `<pad>`）。但这会改变词表 → **使现有 checkpoint 失效、必须重训**，所以短期先做上面的显式截断。
3. 同时清理 `generate.py:170` 的 `torch.ones` / "zeros" 注释矛盾。

---

## 附录：其余较小的问题（不构成上述三项，但值得知道）

| 问题 | 位置 | 说明 |
|---|---|---|
| **注意力 dropout 不可配置，被钉死在 0.1** | `encode_decode/model.py:44` | `MultiHeadedAttention(h, d_model)` **漏传第三个参数** `dropout`，退回签名默认 0.1。残差 / FFN / PE 的 dropout 都是正常传入的，**只有注意力权重上的那个** dropout 受影响。不影响权重加载、不影响推理（`eval()` + `no_grad()`），**只在用 ≠0.1 的 dropout 重训/微调时静默偏差**。这是忠实复制的上游 harvardnlp sloppiness，不是本地回归。修法一行：`MultiHeadedAttention(h, d_model, dropout)`，**不会使现有 checkpoint 失效**。 |
| **完全没有权重共享** | `model.py:43,51-53` | `src_embed` / `tgt_embed` / `generator.proj` 是**三个独立的 920×128 矩阵**，尽管 src 和 tgt **共用同一份词表**。做 weight tying 可省 ~236K / 7.87M ≈ **3% 参数**，通常还能提点。 |
| **两份互相分叉的 `Dataset` 类** | `utils/dataset.py` vs `ml/models/dataset.py` | 生产走前者（经 `tools.py:69`），CLI 走后者（`generate.py:92`）。**token 拼接顺序不同**：前者是 `tok(var) + 条件 + tok(const)`，后者是 `tok(var) + tok(const) + 条件 + list(target_name)`。需要人肉保持同步，改一个忘另一个就会喂进分布外序列。 |
| **特殊 token id 硬编码在 decode.py** | `module/decode.py:8,29` | 起始 = `torch.ones(...)` = 1、终止 = 字面量 2，**都不是从 vocab 读的**。对当前词表是对的，但只要有人换了特殊 token 顺序重建词表，就会**静默输出垃圾**。 |
| **静默 UNK** | `ml/preprocess/vocabulary.py:58-62` | 未见 token 回退到 `default_key`（id 919），**无任何告警**——一个罕见的方括号原子会静默变成 UNK。 |
| **`load_from_file` 不自足** | `model.py:63-73` | 里面没有 `.eval()`、没有 `.to(device)`。目前两个调用点都在外面补上了（`generate.py:73-75,116-118`），所以推理时 dropout 确实是关的。但这是"未来有人直接调它会忘记 eval"的隐患。 |
| **AMP / fp16 隐患** | `multi_headed_attention.py:16` | mask 填充值是**有限的 `-1e9`** 而非 `-inf`。fp32 下没问题；一旦开 fp16 autocast，`-1e9` 超出 fp16 上限（~65504）会溢出成 `-inf`，全掩码行 softmax 后出 NaN。**想开 AMP 第一件事就是改这行。** |
| **无 KV cache** | `module/decode.py:15-16` | 每步用完整前缀重跑整个 decoder 栈，并用 numpy `np.triu` 在 CPU 上重建一次因果掩码。max_len=256 / d_model=128 的规模下能忍，但这是生成延迟优化的第一目标。 |
| **停止条件是 batch 级而非序列级** | `module/decode.py:29-31` | `break_condition` 是 OR 累积，全 batch 都吐出 `'$'` 才退出 → 早完成的序列继续被喂回去生成垃圾 token，直到最慢的那条完成。下游会截断，所以**是浪费算力，不是错误输出**。 |
| **`GenerateRunner.generate()` 是坏的** | `utils/generate.py:97-155` | `:153` 引用 `self.save_path`，但赋值语句在 `__init__` 里被注释掉了（`:49-53`）→ 一旦调用必 `AttributeError`；它还会**第二次加载模型**（`:116`）。生产不走这条（`tools.py` 直接调 `runner.sample`）。 |
| **默认 `deltaValue` 方向可疑** | `task_processor.py:198,218` | 兜底值是 `'(-inf, -10.5]'`——把模型条件化到"活性下降 10+ 个 log 单位"。对一个类似物设计产品来说是很怪的默认（"变好"的桶应该是 `'(10.5, inf]'`）。所幸 `GenerateRequest` 里这些字段全部必填无默认（`schemas/requests/basic_request.py:14-20`），API 路径走不到兜底。 |
| **CPU-only 硬编码** | `utils/generate.py:57,107` | `torch.device('cpu')`，GPU 代码被注释掉；`settings.yaml` 里的 `ml.gpu.cuda_visible_devices: "0"` 是死配置。 |
| 遗留 API | 多处 | `torch.autograd.Variable`（`positional_encoding.py:4,25`、`decode.py:2,15-16`、`label_smoothing.py:3,29`）自 PyTorch 0.4 起已是 no-op；`nn.KLDivLoss(size_average=False)`（`label_smoothing.py:11`）应为 `reduction='sum'`。 |
