# SMILES Transformer 模型结构

> 代码根：`src/astra_molecula/ml/models/transformer/`
> 本文所有行号均对照源码核实；超参数与参数量为**从生产 checkpoint 实测**，非代码默认值。
> 已知缺陷与修复建议见 [smiles-transformer-known-issues.md](smiles-transformer-known-issues.md)。
> 这个架构在 2023–2026 学术图景中的位置、以及升级该不该做，见 [molecular-generation-landscape-2026.md](molecular-generation-landscape-2026.md)。

---

## 1. 这是什么模型

**Harvard NLP《The Annotated Transformer》（Vaswani et al. 2017, *Attention Is All You Need*）的近乎逐行移植**，外加一个 **MMP（matched molecular pair）分子优化头**，血统上属于 AstraZeneca `deep-molecular-optimization` 那一支。

它**不是**「给一个种子 SMILES 续写」的 de-novo 生成模型，而是一个**条件化的类似物设计模型**：

| | |
|---|---|
| **输入** | 可变片段 SMILES + 恒定骨架 SMILES + 活性类别（`main_cls`/`minor_cls`）+ 期望的活性变化分桶（`Delta_Value`） |
| **输出** | 一个**新的可变片段** SMILES（自回归采样） |
| **后处理** | RDKit 把新片段接回用户的恒定骨架，再算描述符（`src/astra_molecula/utils/tools.py:89-99`） |

它是 AstraMolecula 后端**唯一在进程内自己跑的计算**（docking / peptide / SARM / HighFold 都甩给外部 worker），对应 `generate` 任务类型。

---

## 2. 生产实际配置

唯一的模型构造路径是 `EncoderDecoder.load_from_file()`（`encode_decode/model.py:63-73`），它把**全部 7 个超参从 checkpoint 的 `model_parameters` 字典显式传入**，因此 `make_model()` 签名里的默认值（`d_model=256`）和 CLI 里的默认值（`d_model=128`）**都不会被真正使用**。

从生产 checkpoint（`resource/model_20.pt`，由 `utils/tools.py:50,52` 的 `epoch=20` + `model_path=ROOT/resource` 定位）实测读出：

```python
model_parameters = {
    'vocab_size': 920, 'N': 6, 'd_model': 128,
    'd_ff': 2048, 'H': 8, 'dropout': 0.1,
}
```

| 项 | 值 |
|---|---|
| 编码器 / 解码器层数 `N` | 6 / 6 |
| 模型维度 `d_model` | **128** |
| 注意力头数 `H` | 8 → **`d_k` = 128/8 = 16** |
| FFN 隐层 `d_ff` | 2048 → **16× 膨胀比**（论文是 4×） |
| dropout | 0.1 |
| 词表 `vocab_size` | **920**（src 与 tgt 共用同一份词表） |
| **可训练参数** | **7,868,824（7.87 M）** |
| PE buffer | 1,280,000（两份 5000×128，不训练） |
| state_dict 条目 | 262 |
| 推理设备 | **硬编码 CPU** |

> ⚠️ 三套"默认值"务必区分：`make_model` 签名默认 `d_model=256`（`model.py:41`，死代码）；CLI 训练默认 `d_model=128`（`core/config/cli_opts.py:47`，但训练入口不在本仓库）；**checkpoint 实测 `d_model=128`（唯一真实生效的）**。

### 参数量算式

d_model=128, d_ff=2048, h=8, V=920：

```
每个 EncoderLayer = MHA  4×(128×128 + 128)              =    66,048
                  + FFN  (128×2048+2048)+(2048×128+128) =   526,464   ← 占 89%
                  + 2×LayerNorm  2×(128+128)            =       512
                  ────────────────────────────────────────────────────
                                                            593,024  × 6 = 3,558,144

每个 DecoderLayer = 2×MHA 132,096 + FFN 526,464 + 3×LN 768
                                                          =  659,328  × 6 = 3,955,968

Embeddings (src + tgt)   = 2 × (920×128)                                 =   235,520
Generator                = 920×128 + 920                                 =   118,680
Encoder/Decoder 出口 LayerNorm = 2×256                                    =       512
─────────────────────────────────────────────────────────────────────────────────────
合计                                                                       7,868,824  ✔
```

---

## 3. 整体结构与数据流

`EncoderDecoder`（`encode_decode/model.py:15`）是个纯组合容器，五个部件全部由 `__init__` 注入（`model.py:20-26`）：`encoder / decoder / src_embed / tgt_embed / generator`。

```
==== 编码侧 ====
src ids [B,S]  =  ^ tok(可变片段) $ · main_cls · minor_cls · Δ活性桶 · ^ tok(恒定骨架) $
   │                                    ↑ 注意：两组 ^/$，条件 token 夹在中间（见 §5）
   ├─ Embeddings          nn.Embedding(920,128) × sqrt(d_model)      embeddings.py:9,13
   ├─ PositionalEncoding  + 固定正弦 buffer[1,5000,128] → Dropout     positional_encoding.py:19-27
   │                      （两者由 nn.Sequential 串起来，model.py:51）
   ▼ [B,S,128]
 ┌─────────────────── Encoder × N=6 ───────────────────┐   encoder.py:12
 │  EncoderLayer（2 个 SublayerConnection）：             │
 │    x = x + Drop( SelfAttn( LN(x),LN(x),LN(x), src_mask ) )   encoder_layer.py:19
 │    x = x + Drop( FFN( LN(x) ) )                              encoder_layer.py:20
 └──────────────────────────────────────────────────────┘
   ▼  最终 LayerNorm（pre-norm 架构必需）                  encoder.py:20
memory [B,S,128] ───────────────────────────┐
                                            │
==== 解码侧 ====                             │
tgt ids [B,T]（推理时 = 已生成前缀 ys，起始 id=1 '^'）
   │                                        │
   ├─ Embeddings × sqrt(d_model)（独立权重）  │   model.py:52
   ├─ PositionalEncoding（独立 deepcopy 副本）│
   ▼ [B,T,128]                              │
 ┌────────────── Decoder × N=6 ─────────────┼──────────────┐   decoder.py:12
 │  DecoderLayer（3 个 SublayerConnection）： │              │
 │   ① x = x + Drop( SelfAttn(LN(x),LN(x),LN(x), tgt_mask) )   decoder_layer.py:22-23  ← 因果掩码
 │   ② x = x + Drop( SrcAttn (LN(x), m, m,      src_mask) ) ◄─┘ decoder_layer.py:24-25  ← q=解码器, k=v=memory
 │   ③ x = x + Drop( FFN( LN(x) ) )                             decoder_layer.py:27
 └───────────────────────────────────────────────────────────┘
   ▼  最终 LayerNorm                                            decoder.py:23
   ▼ [B,T,128]
 Generator: nn.Linear(128 → 920) → F.log_softmax(dim=-1)        generator.py:10,13
   ▼ [B,T,920] 对数概率
 decode.py: prob = exp(log_prob) → multinomial 采样 / argmax     decode.py:18-25
```

### ⚠️ `forward()` 返回的是 hidden states，不是 logits

```python
# encode_decode/model.py:28-37
def forward(self, src, tgt, src_mask, tgt_mask):
    return self.decode(self.encode(src, src_mask), src_mask, tgt, tgt_mask)
def encode(self, src, src_mask):
    return self.encoder(self.src_embed(src), src_mask)
def decode(self, memory, src_mask, tgt, tgt_mask):
    return self.decoder(self.tgt_embed(tgt), memory, src_mask, tgt_mask)
```

`self.generator` 虽然注册为子模块（权重进 state_dict、也被 xavier 初始化），但 **`forward` 里从不调用它** —— 调用方必须自己调 `model.generator(...)`（推理时在 `module/decode.py:18`）。

---

## 4. 各组件的精确实现

### 4.1 SublayerConnection —— **pre-norm，不是论文的 post-norm**

```python
# encode_decode/sublayer_connection.py:16-18
def forward(self, x, sublayer):
    return x + self.dropout(sublayer(self.norm(x)))
```

顺序是 **norm → sublayer → dropout → 残差相加**，而**不是**论文的 `LayerNorm(x + Sublayer(x))`（Add & Norm）。这是 Annotated Transformer 有名的「为代码简洁而偏离」——类 docstring（`sublayer_connection.py:6-9`）自己都承认了："Note for code simplicity the norm is first as opposed to last."

**后果**：残差主干（residual stream）自始至终没被归一化过，所以 `Encoder`（`encoder.py:20`）和 `Decoder`（`decoder.py:23`）出口各补了一次 `self.norm(x)`。

> **迁移警告**：把这份权重搬到 `torch.nn.TransformerEncoder` 的默认配置（`norm_first=False`，即 post-norm）上会**静默得到错误输出**，不会报错。要设 `norm_first=True`。

每个 SublayerConnection 自带一个 `LayerNorm(size)` + `nn.Dropout(dropout)`（`sublayer_connection.py:13-14`）；这里的 dropout 概率**是**从 `make_model` 正确传入的。

### 4.2 LayerNorm —— 手写，且与 `nn.LayerNorm` **不等价**

```python
# encode_decode/layer_norm.py:8-17
def __init__(self, features, eps=1e-6):
    self.a_2 = nn.Parameter(torch.ones(features))    # gain
    self.b_2 = nn.Parameter(torch.zeros(features))   # bias
def forward(self, x):
    mean = x.mean(-1, keepdim=True)
    std  = x.std(-1, keepdim=True)                   # ← 无偏 (n-1) 标准差
    return self.a_2 * (x - mean) / (std + self.eps) + self.b_2   # ← eps 在 sqrt 之外
```

与 `nn.LayerNorm` 的三处差异：

1. 用 `torch.std`（**贝塞尔校正 n-1**），`nn.LayerNorm` 用**有偏方差**；
2. eps **加在 std 外面**（`/(std+eps)`），`nn.LayerNorm` 是 `sqrt(var+eps)`；
3. eps 默认 `1e-6`，`nn.LayerNorm` 默认 `1e-5`。

d_model=128 时 n vs n-1 的差异约 0.4%，数值上不致命，但**不能直接替换成 `nn.LayerNorm` 并声称权重兼容**。

### 4.3 MultiHeadedAttention

```python
# module/multi_headed_attention.py:24-33
def __init__(self, h, d_model, dropout=0.1):
    assert d_model % h == 0
    self.d_k = d_model // h                                # d_v 假定 == d_k
    self.h = h
    self.linears = clones(nn.Linear(d_model, d_model), 4)  # ← 4 个独立线性层
    self.attn = None
    self.dropout = nn.Dropout(p=dropout)
```

- **4 个 `nn.Linear(128,128)`**，由 `clones`（`encode_decode/clones.py:6-8`，`copy.deepcopy`）生成、**权重互相独立**：前 3 个投影 Q/K/V（`:43-45`），第 4 个是输出投影（`:55`）。
- `d_k = 128/8 = 16`（论文是 64）。
- reshape：`l(x).view(B,-1,h,d_k).transpose(1,2)` → `[B, h, L, d_k]`（`:44`）。
- mask 在 dim=1 上 unsqueeze，**同一 mask 广播到所有 head**（`:37-39`）。
- 拼头：`transpose(1,2).contiguous().view(B,-1,h*d_k)` 后过第 4 个线性层（`:52-55`）。

打分函数（`:10-20`）：

```python
d_k = query.size(-1)                                        # = 16
scores = torch.matmul(query, key.transpose(-2,-1)) / math.sqrt(d_k)
if mask is not None:
    scores = scores.masked_fill(mask == 0, -1e9)            # ← 有限负数，不是 -inf
p_attn = F.softmax(scores, dim=-1)                          # 对 key 维做 softmax
if dropout is not None:
    p_attn = dropout(p_attn)                                # ← 注意力权重上的 dropout，确实生效
return torch.matmul(p_attn, value), p_attn
```

> **注意力 dropout 生效，但不可配置**：`self.dropout` 是真实的 `nn.Dropout` 且确实作用在 softmax 后的概率上。但构造点 `model.py:44` 写的是 `MultiHeadedAttention(h, d_model)` —— **漏传第三个参数**，于是注意力 dropout 永远退回签名默认 0.1。详见 [known-issues §附录](smiles-transformer-known-issues.md)。

`self.attn` 每次 forward 都把 `[B,h,L,L]` 的注意力矩阵挂在模块上（`:32,:48`，原版为了可视化）。

### 4.4 PositionwiseFeedForward

```python
# module/positionwise_feedforward.py:14-15
def forward(self, x):
    return self.w_2(self.dropout(F.relu(self.w_1(x))))
```

`Linear(128,2048) → ReLU → Dropout → Linear(2048,128)`。激活是 **ReLU 不是 GELU**；只有一个 dropout，位于激活与第二个线性层之间，输出上不加。dropout 参数在这里**是**正确传入的（`model.py:45`）。

**16× 膨胀比**（论文 4×）：看起来是"保留了论文的 d_ff=2048、却把 d_model 砍到 1/4"。FFN 独吞每个 EncoderLayer 593,024 参数中的 526,464（**89%**）。若要重训，`d_ff=512` 才是与 d_model=128 匹配的选择。

### 4.5 Embeddings

```python
# module/embeddings.py:9,13
self.lut = nn.Embedding(vocab, d_model)          # (920, 128)
return self.lut(x) * math.sqrt(self.d_model)     # ← sqrt(d_model) 缩放（标准做法）
```

自身**无 dropout**；embedding 后的 dropout 全部来自 `nn.Sequential` 串在后面的 `PositionalEncoding`（`model.py:51-52`）。

### 4.6 PositionalEncoding —— 固定正弦，非学习式

```python
# module/positional_encoding.py:10-27
def __init__(self, d_model, dropout, max_len=5000):
    self.dropout = nn.Dropout(p=dropout)
    pe = torch.zeros(max_len, d_model)
    position = torch.arange(0, max_len).unsqueeze(1)                                  # ← int64
    div_term = torch.exp(torch.arange(0., d_model, 2) * -(math.log(10000.0)/d_model)) # ← float32
    pe[:, 0::2] = torch.sin(position * div_term)
    pe[:, 1::2] = torch.cos(position * div_term)
    self.register_buffer('pe', pe.unsqueeze(0))   # [1,5000,d_model]：随 .to(device) 走、进 state_dict、不训练
def forward(self, x):
    x = x + Variable(self.pe[:, :x.size(1)], requires_grad=False)   # ← 已废弃的 torch.autograd.Variable
    return self.dropout(x)                                          # dropout 作用在 (emb + PE) 之和上
```

- `max_len=5000` 但实际最长序列只有 256；又因 `make_model` 把 `position` **深拷贝进 src_embed 和 tgt_embed 两处**，checkpoint 里带了**两份 5000×128 的 pe buffer**（1,280,000 个浮点数，占 state_dict 总量的 14%）。
- `torch.autograd.Variable` 自 PyTorch 0.4 起已是 no-op，纯遗留。
- 潜在坑（当前未触发）：`d_model` 为奇数时 `pe[:,0::2]` 与 `pe[:,1::2]` 宽度不等会抛 shape error。128 是偶数，踩不到。

### 4.7 Generator

```python
# module/generator.py:10,13
self.proj = nn.Linear(d_model, vocab)             # 128 → 920
return F.log_softmax(self.proj(x), dim=-1)        # ← log_softmax，不是 softmax
```

输出**对数概率**（正好配 `KLDivLoss`/NLL）；推理时 `decode.py:19` 再 `torch.exp` 还原成概率。

### 4.8 subsequent_mask（因果掩码）

```python
# module/subsequent_mask.py:5-9
attn_shape = (1, size, size)
subsequent_mask = np.triu(np.ones(attn_shape), k=1).astype('uint8')
return torch.from_numpy(subsequent_mask) == 0     # bool: True = 可见（下三角含对角线）
```

极性与注意力约定一致（**True/1 = 保留**，注意力对 `mask == 0` 填 `-1e9`）。用的是 numpy `np.triu` 而非 `torch.triu`，每步都有一次 numpy→CPU tensor 往返。

---

## 5. 词表与输入序列格式

### 5.1 词表（920 tokens，`resource/vocab.pkl`）

| id | token | 含义 |
|---|---|---|
| 0 | `*` | padding（**同时也是合法的 SMILES 通配原子**，见 known-issues 问题三） |
| 1 | `^` | BOS / start |
| 2 | `$` | EOS / end |
| 919 | `default_key` | 静默 UNK（`ml/preprocess/vocabulary.py:58-62`，无告警） |

构成（`ml/preprocess/vocabulary.py:131-145` 的 `create_vocabulary`：先 `["*","^","$"] + sorted(化学 token)`，再 append `property_condition`）：

- **~231 个真正的化学 token**：单字符原子/键符、方括号原子（`[nH]`、`[C@@H]`…）、双位环闭合 `%10`..`%21`、`Cl`/`Br`（由 tokenizer 的 `brackets` / `2_ring_nums` / `brcl` 三条正则产生，`vocabulary.py:93-98`）
- **~670 个性质 / assay 名 token**（`activity`、`Ki`、`IC50`、`EC50`、`Stability`、大量 `toxcast-*`…）
- **18 个 Δ活性分桶 token**，id **898–915 连续无空洞**：`'(-inf, -10.5]'` … `'(10.5, inf]'`

> 即：**四分之三的词表是条件化 token，不是化学 token。**

### 5.2 编码器输入的真实形态（易错，务必看清）

`SMILESTokenizer.tokenize()` 默认 `with_begin_and_end=True`（`vocabulary.py:100,116-117`），而生产路径的 `utils/dataset.py:54,62` **两处都没关掉它** —— 于是两个片段各自被独立地加上 `^`/`$`：

```
encoder src = ['^'] + tok(fromVarSMILES) + ['$']
            + [main_cls] + [minor_cls] + [Delta_Value]
            + ['^'] + tok(constantSMILES) + ['$']
```

**序列里有两个 `^` 和两个 `$`**，三个条件 token 夹在第一个 `'$'` 和第二个 `'^'` 之间。`src_mask` 只屏蔽 id 0（`utils/dataset.py:104`：`(collated_arr_source != 0).unsqueeze(-2)`），所以**这些中间的哨兵 token 是被真实 attend 的输入**。任何按「tok(var) + cond + tok(const)」重建输入的做法都会喂进分布外序列。

> ⚠️ 仓库里有**两份互相分叉的 `Dataset` 类**：`utils/dataset.py`（生产走这条，经 `tools.py:69`）与 `ml/models/dataset.py`（CLI `generate.py:92` 走这条）。**两者的 token 拼接顺序不同** —— 后者是 `tok(var)+tok(const)` 在前、条件 token 在后，还额外追加 `list(target_name)`。需要人肉保持同步。

---

## 6. 训练与推理

### 6.1 初始化

```python
# encode_decode/model.py:57-59
for p in model.parameters():
    if p.dim() > 1:
        nn.init.xavier_uniform_(p)
```

Glorot/Xavier uniform，只作用于 **dim() > 1 的矩阵**；bias 和 LayerNorm 的 `a_2`/`b_2` 保持默认（1 / 0）。

> 注意 `load_from_file` 会**先跑一遍全模型 xavier 初始化，再立刻被 `load_state_dict` 覆盖** —— 每次加载都白做一次。

### 6.2 训练代码 **不在本仓库**

全仓 grep 确认：`LabelSmoothing` / `NoamOpt` / `SimpleLossCompute`（`module/` 下三个文件）**没有任何 import、实例化或引用**，`train_opts_transformer` 也零调用方，仓库里没有 `train.py`。**本服务是纯推理服务**，checkpoint 在别处训练好后拷进来。

这些死代码反映的是该 checkpoint **大概率的训练方式**：

- **NoamOpt**（`module/noam_opt.py:26-28`）：论文原版的逆平方根 + 线性 warmup —— `factor * d_model^-0.5 * min(step^-0.5, step * warmup^-1.5)`。意图中的 Adam 配置只能从 `cli_opts.py:69-73` 反推：`betas=(0.9,0.98)`, `eps=1e-9`, `factor=1.0`, `warmup=4000`。
- **LabelSmoothing**（`module/label_smoothing.py`）：`nn.KLDivLoss` + padding_idx 整行清零，`smoothing` 默认 0.00（即默认关闭）。配 Generator 的 `log_softmax` 正好构成 KLDiv 的输入契约。
- **SimpleLossCompute**：把 `loss.backward()` / `opt.step()` / `zero_grad()` 塞进了损失函数里 → 这个类下**无法做梯度累积**。

> **架构语义矛盾**：本模型是 **pre-norm**，而 pre-norm 的整个卖点就是训练更稳、**不需要 lr warmup**（Xiong et al. 2020）；配套的调度器却是给 **post-norm** 设计的 Noam warmup。这不算 bug（warmup 只是让 pre-norm 更保守），但若要重训，warmup 完全可以砍掉，直接上常规 cosine/linear decay。

### 6.3 推理解码 —— **没有 beam search**

全仓 grep `beam` 零命中。`module/decode.py` 只有两种策略，由字符串参数 `type` 选择：

```python
# module/decode.py:7-33
def decode(model, src, src_mask, max_len, type):
    ys = torch.ones(...)                                  # :8-9   起始 token 硬编码 id 1 ('^')
    encoder_outputs = model.encode(src, src_mask)         # :11    ⚠️ 在 no_grad 之外
    for i in range(max_len - 1):                          # :13
        with torch.no_grad():
            out  = model.decode(encoder_outputs, src_mask, ys, subsequent_mask(...))  # :15-16 全前缀重算，无 KV cache
            prob = torch.exp(model.generator(out[:, -1]))                             # :18-19
            if   type == 'greedy':      _, next_word = torch.max(prob, dim=1)         # :21-22
            elif type == 'multinomial': next_word = torch.multinomial(prob, 1)        # :24-25
            break_condition |= (next_word.to('cpu') == 2)                             # :29 终止 token 硬编码 2 ('$')
            if all(break_condition): break                                            # :30-31
    return ys                                                                          # :33 返回 token id
```

| 项 | 事实 |
|---|---|
| 生产默认策略 | **`multinomial`**（`utils/tools.py:48,84`）—— 从**完整分布**做祖先采样，**无 temperature / top-k / top-p** |
| `greedy` | 在采样循环层面被当作「单次射击」：`utils/generate.py:176-177` 把 `max_trials` 从 100000 压到 1 |
| `max_len` | **256**（`utils/generate.py:125` → `core/config/ml_config.py:9-11` → `settings.yaml:99 max_sequence_length`） |
| 上层重采样 | 最多 **100,000** 次，直到凑够 `num` 个**去重 + RDKit 合法**的分子（`utils/generate.py:170-177`） |
| KV cache | **无** —— 每步用完整前缀重跑整个 decoder 栈，O(L²) 次前向 |
| 停止条件 | **batch 级而非序列级**：`break_condition` 是 OR 累积，全 batch 都吐出 `'$'` 才退出 → 早完成的序列继续生成垃圾 token（下游 `untokenize` 会截断，**浪费算力但不产生错误输出**） |
| token → SMILES | `vocab.decode()` + `tokenizer.untokenize()`（`utils/generate.py:224`）；`untokenize` 遇 `'$'` 截断、跳过 `'^'`（`vocabulary.py:120-128`） |
| 设备 | **硬编码 CPU**（`generate.py:57,107`，CUDA 行被注释掉；`settings.yaml` 里的 `ml.gpu.cuda_visible_devices` 是死配置） |

特殊 token id **硬编码在 decode.py 里**（起始=1、终止=2），**不是从 vocab 对象读的**。对照当前 `vocab.pkl` 确认是对的（`create_vocabulary` 总是先塞 `["*","^","$"]`），但**只要有人用不同的特殊 token 顺序重建词表，decode.py 就会静默输出垃圾而不报错**。

---

## 7. 一页速查

| 维度 | 事实 |
|---|---|
| 血统 | Annotated Transformer（Vaswani 2017）逐行移植 + MMP 分子优化头 |
| 归一化 | **pre-norm**（`sublayer_connection.py:18`），encoder/decoder 出口各补一次 final LN |
| LayerNorm | **手写**，`x.std()`（n-1）+ eps 在 sqrt 外，eps=1e-6 → **与 `nn.LayerNorm` 不等价** |
| Attention | 4 个独立 `Linear(128,128)`，d_k=16，`QKᵀ/√d_k`，mask 填 `-1e9`，softmax(dim=-1) |
| FFN | `Linear(128,2048) → ReLU → Dropout → Linear(2048,128)`，**16× 膨胀** |
| PE | 固定正弦，`register_buffer`，max_len=5000（实际只用 256） |
| Generator | `Linear(128,920) → log_softmax`，**`forward()` 里不调用** |
| 生产超参 | N=6, d_model=128, h=8, d_ff=2048, dropout=0.1, vocab=920 |
| 参数量 | **7,868,824** 可训练（+1,280,000 PE buffer） |
| 权重共享 | **完全没有**（含无 embedding↔generator weight tying，可省 ~3% 参数） |
| 训练代码 | **不在本仓库**（NoamOpt / LabelSmoothing / SimpleLossCompute 全是死代码） |
| 解码 | **无 beam search**；生产 = multinomial 祖先采样（无 temperature/top-k），max_len=256 |
| 设备 | **硬编码 CPU** |
| 已知问题 | 见 [smiles-transformer-known-issues.md](smiles-transformer-known-issues.md) |
