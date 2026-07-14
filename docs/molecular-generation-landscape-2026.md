# 分子生成模型技术图景（2023–2026）与本仓模型的升级判断

> 配套文档：[smiles-transformer-architecture.md](smiles-transformer-architecture.md)（本仓模型结构） · [smiles-transformer-known-issues.md](smiles-transformer-known-issues.md)（三个待修问题）
> 调研日期：2026-07-13 · 方法：5 路并行检索 → 25 篇源文抓取 → 125 条候选事实 → **每条 3 票对抗性核查**（需 2/3 反对票才能杀死）→ 存活 18 条、被否决 7 条
> **本文所有结论都带可信度与票数标注。被否决的主张单列在 §7，不可当结论使用。**

---

## 0. 头条结论

> **在本仓模型所处的这一支——MMP / 条件化类似物设计——2023 到 2026 年没有出现任何一个被工业界采纳的、优于 2017 encoder-decoder 的新架构。**

这不是"没找到"，而是有正面证据的：AstraZeneca 自己的旗舰开源框架 **REINVENT 4**（*J Cheminform* 2024）到今天仍然**只用 RNN 和 Transformer 两种生成骨干**。

三条对决策最重要的事实：

| | 结论 | 可信度 |
|---|---|---|
| **架构没变** | REINVENT 4 生产框架里**不存在** diffusion / flow / 等变 3D 骨干；本仓模型的血脉（Mol2Mol）就是其中一种生成器 | **high** (3-0) |
| **大模型不占优** | 7B 化学 LLM 在与本仓最接近的 seq2seq 任务上**输给**小型专用模型（32.9% vs 47.0%），到 2026 年仍未反转 | **high** (3-0) |
| **现代组件无证据** | RoPE/RMSNorm/SwiGLU/GQA 在化学专用序列模型里**几乎零采纳**，且**无人做过消融** | **high** (3-0) |

**推论**：升级的钱应该花在**推理工程 + 预训练规模 + 表示层**，而不是把骨干换成扩散/flow/等变模型或 7B LLM。详见 [§5](#5-务实升级路线)。

---

## 1. 先确定本仓模型在图景中的坐标

### 1.1 它不是过时的旁支，是工业主线的兄弟

**REINVENT 4: Modern AI-driven generative molecule design**
Loeffler, **He**, Tibo, Janet, Voronov, Mervin, Engkvist — AstraZeneca Molecular AI — *J Cheminform* 2024（PMID [38383444](https://pubmed.ncbi.nlm.nih.gov/38383444/)）· 代码：[MolecularAI/REINVENT4](https://github.com/MolecularAI/REINVENT4)

摘要原文：*"The software utilizes recurrent neural networks and transformer architectures to drive molecule generation."*

核查者核对了 2025–26 的 v4.7 代码库，五种生成器为：

| 生成器 | 骨干 | 任务 |
|---|---|---|
| Reinvent | LSTM | de novo 生成 |
| **Mol2Mol** | **Transformer seq2seq** | **分子优化 / 相似性约束下的类似物设计** ← 本仓的兄弟 |
| LibInvent | Transformer | 骨架修饰 |
| LinkInvent | Transformer | linker 设计 |
| PepInvent | Transformer | 多肽（论文后新增，arXiv 2409.14040） |

**仓库中不存在 diffusion / flow / E(3)-SE(3) 等变骨干。** 血脉可追溯性也已确认：REINVENT 4 的共同作者 **Jiazhen He 正是 `MolecularAI/deep-molecular-optimization` 的作者**（*J Cheminform* 2021 + 2022），Mol2Mol 是该血脉的产品化后继。

> **必须带的限定**：同一组人确实在做 flow matching 和等变 3D（SemlaFlow 的作者 Tibo、Janet 同时是 REINVENT 4 的作者），但那是**独立的研究代码库**（`github.com/rssrwn/semla-flow`），**没有进生产框架**。正确读法是「生产框架 = 只有 RNN/Transformer」，而**不是**「AZ 不做 3D 生成研究」。
>
> **另注**：Mol2Mol 的条件是**相似度约束**（ECFP4 Tanimoto ≥ 0.50 的分子对），属性优化靠 RL / curriculum 打分函数，而不是像本仓这样用属性变化 token 做输入条件。**它是本仓模型的兄弟，不是同一个东西。**

*可信度：**high**，3-0 通过对抗核查*

### 1.2 ⚠️ 本仓实现与其直系论文有两处偏离

**Transformer-based molecular optimization beyond matched molecular pairs**
He, Nittinger, Tyrchan, Czechtizky, Patronov, Bjerrum, Engkvist — *J Cheminform* 14:18 (2022) — [PMC8962145](https://pmc.ncbi.nlm.nih.gov/articles/PMC8962145/)

先确认相同的部分：**属性变化分桶 token 前置到源 SMILES 这个 conditioning 方案是 AZ 已发表的原版设计，不是本地发明**。论文 Methods 原文：*"The same Transformer neural network in [25, 29] is used in this study... The hyperparameters were set the same as [25]. The models were trained using a batch size of 128, Adam optimizer and the original learning rate schedule [29] with 4000 warmup steps."*（[29] = Vaswani 2017，[25] = He 2021）

代码级核对 `MolecularAI/deep-molecular-optimization` 确认：正弦 PE、`w_2(dropout(F.relu(w_1(x))))`、均值/标准差 LayerNorm（非 RMSNorm）、`noam_opt.py` + `label_smoothing.py`、vanilla MHA 无 GQA/flash、`sublayer_connection.py` = `x + self.dropout(sublayer(self.norm(x)))` → **pre-norm** —— **与本仓生产模型逐行一致**。

**但有两处偏离，引用论文效果数据时必须知道：**

1. **AZ 条件的是 ADMET / 理化属性**（logD 变化按 0.2 区间分桶；溶解度 / 肝微粒体清除率为 low→high / high→low / no_change 三分类），**不是活性 / 效价**。机制相同，但「活性变化分桶」是**本仓的本地改造**。
2. **AZ 的两篇论文都把整个源分子 SMILES 喂给 encoder**，MMP 只用于**构造训练对**，**不做「可变片段 + 恒定骨架」的分解输入**。本仓的 fragment-in / fragment-out I/O **更接近 LibINVENT / scaffold-decorator 风格**，不是这两篇论文做的事。

> → **本仓模型是个混血，不能直接引用 He 2022 的效果数据来背书自己。**

*可信度：**high**，2-1 ×2 通过（反对票针对措辞而非事实）*

---

## 2. 序列 / SMILES 派：架构几乎没动，创新搬去了「表示」和「规模」

这是本次调研最一致的发现。**近年三个代表作，没有一个是靠改骨干赢的。**

### 2.1 SAFE-GPT —— 架构新意约等于零，创新全在记法

**Gotta be SAFE: a new framework for molecular design**
Noutahi, Gabellini, Craig, Lim, Tossou — Valence Labs — *Digital Discovery* 2024 · [RSC](https://pubs.rsc.org/en/content/articlelanding/2024/dd/d4dd00019f) · [arXiv 2310.10773](https://arxiv.org/abs/2310.10773)

| 项 | 值 |
|---|---|
| 参数量 | 87.3M |
| 层 / 头 / hidden | 12 / 12 / 768 |
| 位置编码 | **学习式绝对位置编码**（GPT-2 `wpe`） |
| 归一化 / 激活 | **LayerNorm** / **GELU** |
| RoPE / ALiBi / RMSNorm / SwiGLU / GQA | **全部没有** |
| 目标函数 | 普通 next-token 交叉熵 |
| 训练 | AdamW，linear scheduler（10k warmup，lr=1e-4），4×A100，~1M 步 / 7 天，1.1B SAFE 串（ZINC + UniChem） |
| 分词 | BPE + SMILES-regex 预分词，词表 ~10³ 量级 |

论文原文：*"Our SAFE Generative model (SAFE-GPT) is a 87.3M parameters GPT2-like transformer... **All other model parameters adhere to the default settings of GPT-2**, as outlined in Hugging Face."*

**独立佐证（不靠论文自述）**：核查者直接拉了作者发布的权重 [`config.json`](https://huggingface.co/datamol-io/safe-gpt/raw/main/config.json)：`model_type=gpt2, n_layer=12, n_head=12, n_embd=768, n_positions=1024, activation=gelu_new, layer_norm_epsilon=1e-5`。**「架构新意 ≈ 0」不是评论，是 config 的字面事实。**

它的全部创新在**输入记法**：SAFE 把片段重排成连续子串，让 linker design / scaffold decoration 退化成普通自回归续写。

> ⚠️ **重要保守提示**：SAFE **记法本身**的能力主张（五任务统一、100% validity）在本轮对抗验证中**未通过**（分别 1-2 与 0-3 被否）。本文**只确认其架构事实，不背书其任务收益**。想用 SAFE，需自行复现。

*可信度：**high**（架构事实），3-0 · **任务收益：未通过验证**，见 §7*

### 2.2 SMI-TED289M —— 「继续 encoder-decoder + 加大规模」这条路

**A Large Encoder-Decoder Family of Foundation Models For Chemical Language**
Soares, Shirasuna, Vital Brazil, Cerqueira, Zubarev, Schmidt — IBM Research — [arXiv 2407.20267](https://arxiv.org/pdf/2407.20267) → *Communications Chemistry* 2025（数字扛住了 peer review，见 Table 4）

| 项 | 值 |
|---|---|
| hidden / 头 / 层 / dropout | 768 / 12 / 12 / 0.2 |
| 归一化 | **LayerNorm**（**不是** RMSNorm） |
| 位置编码 / 注意力 | **RoPE（RoFormer 式旋转位置编码）** ← 本轮唯一被化学专用模型采纳的现代组件 |
| 激活 | GELU |
| 词表 / 最长序列 | 2993 / 202 token |
| 参数切分 | **47M encoder + 242M decoder = 289M**（decoder 是 encoder 的 5 倍大，这个切分很不寻常） |
| 相对本仓 | **约 37×** |
| 预训练目标 | **双损失**：BERT 式 MLM（15% 选中，80/10/10）训 token encoder + 独立的 SMILES 重建损失训 encoder-decoder 潜空间瓶颈 |
| 数据 | 91M 条去重规范化 PubChem SMILES（从 113M 过滤），~4B token |
| **成本** | **40 epoch / batch 288 / lr 1.6e-4 / 24×V100-16G（4 节点 DDP）** ← 中小团队预算内 |

> **关键限定**：不要把它写成「守着 2017 老栈」——其 encoder 明确使用 *"a modified version of the RoFormer attention mechanism"*（继承自 IBM MoLFormer 血脉）。**RoPE 是被采纳的。** 正确表述是「LayerNorm + 双向 MLM encoder + RoPE 注意力 + GELU」。
> 另注：decoder 头仍是 token 级自回归（从潜向量重建 SMILES），所以它**不是**「非自回归」，只是缺少因果 LM 预训练目标。

*可信度：**high**，3-0 ×2*

### 2.3 LlaSMol —— 现代组件进入化学的唯一路径是「借通用 LLM 的底座」

**LlaSMol: Advancing LLMs for Chemistry with a Large-Scale, Comprehensive, High-Quality Instruction Tuning Dataset**
Yu, Baker, Chen, Ning, Sun — OSU NLP Group — COLM 2024 — [arXiv 2402.09391](https://arxiv.org/pdf/2402.09391)

**它没有提出任何新架构。** 就是 Mistral-7B + **LoRA**（r=16, alpha=16, 3 epoch, lr=1e-4，**仅 ~41.9M 可训练参数 = 0.58%**）在 330 万条化学指令（SMolInstruct，14 个任务）上微调。作者横向比了 Galactica-6.7B / Llama-2-7B / Code-Llama-7B / Mistral-7B 四个底座后**经验性地**选了 Mistral。

→ **它继承的 RoPE / GQA / SWA / RMSNorm / SwiGLU 全部来自 Mistral 本身，与化学无关**——论文完全没讨论过这些内部结构，**这恰恰是本条结论的要点**。

（唯一的化学特定设计是数据层面的：`<SMILES></SMILES>`、`<MOLFORMULA>`、`<NUMBER>` 标签 + SMILES 规范化——属于 prompt/数据约定，不是架构。）

*可信度：**high**，3-0*

### 2.4 ⭐ 对本仓决策价值最高的一条负面证据

> **即便在 330 万条化学指令上微调，7B 化学 LLM 在与本仓架构最接近的任务（逆合成，seq2seq 分子翻译）上，仍然打不过小型专用模型。**

| 模型 | 逆合成 exact-match |
|---|---|
| LlaSMol-Mistral (7B, LoRA) | **32.9%** |
| LlaSMol-Llama2 (7B) | 22.5% |
| **专用基线**（RSMILES / Molecular Transformer，作者**按原设置重新训练**） | **47.0%** |

这是 **apples-to-apples** 的对照——*"we re-train RSMILES and Molecular Transformer for the two tasks, respectively, following their reported settings"*（在 SMolInstruct/USPTO-full 上重训，不是跨论文抄数）。作者自认：*"Although LlaSMol models do not outperform SoTA models, they demonstrate considerable potential for further improvements."*

**时效性复核（核查者专门查了 2025–2026 有没有反转）：没有。**

- RetroDFM-R（7B 微调 LLM）USPTO-50k top-1 达 65.0%，但 **0.5B 的紧凑专用模型仍报 69.8%（不带 AAM）/ 75.1%（带 AAM）**；
- RxnNano（[arXiv 2603.02215](https://arxiv.org/abs/2603.02215)，2026）明说 *"chemical LLMs still perform far below smaller, specialized models on retrosynthesis benchmarks"*；
- 通用推理 LLM（o4-mini）top-1 仅 ~12%。

> → **把 7.87M encoder-decoder 换成指令微调的 7B LLM，没有证据支持会更强，却必然摧毁 CPU 推理约束。**

*可信度：**high**，3-0（含 2026 年时效性复核）*

---

## 3. 3D / 等变派：这不是「更好的架构」，这是另一个物种

**关键认知：这一支与序列派的差别在「表示」和「目标函数」层面，不在「更好的注意力」。**

### 3.1 EDM（锚点）—— 骨干根本不是 Transformer

**Equivariant Diffusion for Molecule Generation in 3D**
Hoogeboom, Satorras, Vignac, Welling — **ICML 2022** — [arXiv 2203.17003](https://arxiv.org/abs/2203.17003)

- 去噪骨干是 **E(3)-等变图神经网络 EGNN，不是 Transformer**：QM9 上仅 **9 层 / 每层 256 特征 / SiLU**；GEOM-Drugs 上只有 **4 层 / 256 特征**。
- 生成过程是**在连续原子坐标与离散原子特征（one-hot 原子类型 + 整数电荷）上的单一联合扩散**，由一个等变网络统一去噪。
- **等变性是硬架构约束，不是学出来的**：
  - 平移不变 ← 把噪声/隐空间限制在**零质心子空间**（∑xᵢ = 0），训练/采样算法均含 "Subtract center of gravity"；
  - 旋转等变 ← EGNN 沿相对位置向量 `(xᵢ − xⱼ)/(dᵢⱼ+1)` 更新坐标，消息 `m_ij = φ_e(hᵢ, hⱼ, dᵢⱼ², a_ij)` **只依赖不变的平方距离**。
  - 消融（EDM vs GDM vs GDM-aug）显示**硬等变优于旋转数据增强**。

> **三点限定**：(a) EGNN 并非完全无注意力——特征更新含逐边 sigmoid 门控（EGNN 原文称之为 attention），但**无 Q/K、无 softmax、无多头**，且与等变性无关；(b) 一个经验性 hack 是承重的：输入必须缩放为 `[x, 0.25·h_onehot, 0.1·h_charge]`，后续工作（EQGAT-diff, MiDi）改用真正的离散扩散并超越 EDM，反过来印证这个连续松弛是权宜之计；(c) 「等变 3D 都不用注意力」是**错的**——SemlaFlow / Equiformer 系 / diffusion-transformer 系都用注意力，本条只覆盖 EDM 及其直系后裔。

*可信度：**high**，3-0 ×3*

### 3.2 SemlaFlow —— 3D 派里最像 Transformer 的高影响力代表

**SemlaFlow: Efficient 3D Molecular Generation with Latent Attention and Equivariant Optimal Transport**
Irwin, **Tibo**, **Janet**, Olsson — AstraZeneca + Chalmers — **AISTATS 2025**（[PMLR v258](https://proceedings.mlr.press/v258/irwin25a.html)）· [arXiv 2406.07266](https://arxiv.org/abs/2406.07266)

| 项 | 值 |
|---|---|
| 骨干 | **Semla**：12 层 E(3)-等变**多头隐空间图注意力**栈 |
| 维度 | d_inv=384（不变标量）· d_equi=64（等变向量）· d_l=64（隐消息）· 32 头 |
| 参数量 | **~22M** |
| 归一化 | 不变特征走 **LayerNorm**；等变向量走 MiDi 改造的归一化 |
| 激活 / 位置编码 | SiLU 全程 / **无序列位置编码** |
| 目标函数 | 条件流匹配（坐标 MSE）+ **Discrete Flow Models**（原子类型/键级/形式电荷 CE）；网络**直接预测干净数据 x₁**（不是噪声、不是向量场）+ self-conditioning |

**核心架构创新 = latent attention**：先用可学习线性映射把不变节点特征压到很小的 `d_l`，再进 all-pairs message MLP，把成对消息代价从 **O(N²·d_inv²) 降到 O(N²·d_l²)**（d_l ≪ d_inv）。这**把模型宽度与消息传递代价解耦**，比 EQGAT/EGNN 推理快 3–5 倍。

论文原话：*"we first compress the invariant node features into a smaller latent space... It also allows us to scale the size of the invariant node features independently of the node latent dimension."*

*可信度：**high**，3-0 ×3（含对作者参考实现的逐行核对）*

### 3.3 FlowMol3 —— 3D 领域内部明确反对「上 Transformer + 堆规模」

**FlowMol3** — Dunn & Koes — Univ. of Pittsburgh — [arXiv 2508.12629](https://arxiv.org/abs/2508.12629) → *Digital Discovery* 2026

- 骨干**不是 Transformer**，是 **Geometric Vector Perceptron (GVP)** 搭的 **SE(3)-等变几何 GNN**：6 个 Molecule Update Block、每原子 256 标量 + 32 向量特征、边 128 特征，**总共仅 ~6M 参数**。
- **零自注意力、零位置编码、无 RoPE/RMSNorm/SwiGLU**（核查者对全 PDF 做穷举 grep：`attention` 的所有命中都指向他人工作）。
- 带叉乘的 GVP 变体把 E(3) 升级为 SE(3)，**使立体异构体获得不同似然**。
- 目标函数：坐标走欧氏 CFM（Kabsch 对齐 + 指派问题的类 OT 耦合、**endpoint 参数化**——预测 X̂₁ 而非速度场），原子类型/电荷/键级走离散 flow matching（CTMC），损失权重 (λX, λA, λC, λE) = (3, 0.4, 1, 2)。

**作者在论文里直接点名反驳 transformer-scaling 论**：

> *"More recent works have argued that relying on simplified, well-tested transformer-style architectures and scaling the size of the model will be essential... While scaling appears to have benefits, **we argue there are other pathologies that cannot be remedied by architecture choice and scale**."*

且其增益 *"achieved without changes to the graph neural network architecture"*（来自 self-conditioning、fake atoms、训练期几何扰动）。

> ⚠️ **保守提示**：FlowMol3「以 6M 参数在 PoseBusters validity 上全面击败更大基线」这一**性能主张在本轮被 0-3 否决**。本文**只确认其架构与目标函数事实，不背书其 head-to-head 优越性**。

*可信度：**high**（架构事实），3-0 ×2 · **性能优越性：被否决**，见 §7*

### 3.4 ⚠️ 指标陷阱：「flow matching 已全面取代 diffusion」是过度解读

SemlaFlow 用 **20 步 ODE** 打败 **500 步**的 EQGAT-diff（molecule stability 95.3 vs 93.4，strain energy 1.76 vs 3.23 kcal/mol/atom），生成 1000 个分子 **20.3s vs 2293.0s（~113×）**，训练也只用单张 A100 / 200 epoch（EQGAT-diff 需 4 GPU × 800 epoch）。**这些数字本身是真的**，但有三条必须带上的反证：

1. **稳定性指标有 bug。** *"GEOM-drugs revisited"*（*Digital Discovery* 2025, [arXiv 2505.00169](https://arxiv.org/abs/2505.00169)）证明 MiDi 血脉的代码**把芳香键键级四舍五入成 1 而非 1.5**，*"leading to inflated stability scores"* —— 这个 bug **传染了 EQGAT-Diff / SemlaFlow / Megalodon / FlowMol 全部**。修正后**排序仍成立**（SemlaFlow 0.969±0.012 vs EQGAT-Diff 0.899±0.007），但**不要再引用 95.3 / 93.4 这类绝对值**。
2. **strain energy 是 SemlaFlow 作者自己在同一篇论文里提出的指标。** 而在 QM 级（GFN2-xTB）指标下，SemlaFlow 平均弛豫能 **91.0±21.7** kcal/mol vs Megalodon **5.76±0.27** —— 3D 几何质量远非碾压。SemlaFlow 论文**自己承认**：*"molecules generated by EQGAT-diff have lower minimised energies than SemlaFlow."* 且 SemlaFlow 在 **validity 上其实略输**（93.0 vs 94.6）。
3. **NVIDIA 的 Megalodon 用同一架构做了受控对照**（[arXiv 2505.18392](https://arxiv.org/abs/2505.18392) / *Digital Discovery* 2026）：*"the diffusion model excels at structure and energy benchmarks, whereas the flow matching model yields better 2D stability and the ability to use 25× fewer inference steps."*

> **诚实的说法**：flow matching 买到的是**采样步数 / 速度的 1–2 个数量级**，代价是 **3D 几何 / 能量质量上仍不占优**。

*可信度：**medium**，2-1（数字 confirmed，「flow matching 是唯一站得住的选择」这个结论句被验证者判定为 overreach 并降级）*

---

## 4. 结构基础的口袋条件化生成（SBDD）

**⚠️ 本轮零覆盖。** 没有任何关于 TargetDiff / DiffSBDD / Pocket2Mol / DecompDiff 的 claim 通过（或被提出）验证。

**不要把「本文没提到」读成「它不重要」**——只是本轮没验成。若需要，应单独立项调研。

---

## 5. 务实升级路线

按性价比排序，**证据强度依次递减**：

### ✅ 1. 先补推理工程（最划算，几乎零风险）

本仓目前**无 KV cache、无 beam search**（见 [architecture §6.3](smiles-transformer-architecture.md)），而 **REINVENT 4 的 Mol2Mol 生产实现同时提供 multinomial 采样与 beam search**。叠加 [known-issues](smiles-transformer-known-issues.md) 里的三个问题（权重未版本化、每请求重载 95MB、无显式 EOS 截断），这一层的收益是纯工程性的、可预期的。

> **诚实声明**：**「beam search 会提升本仓的生成质量」本轮没有直接证据**——只确认了「工业实现里有它」。它是合理的工程默认，**不是被验证的性能结论**。

### ✅ 2. 规模 + 预训练（唯一有 peer-reviewed 先例、且不改变 seq2seq 契约的升级）

照 SMI-TED 路线：在 10⁷–10⁸ 量级分子上预训练一个 encoder-decoder，再在自己的 MMP 对上微调。**24×V100 / 40 epoch 完成 91M 分子预训练**——说明这条路在中小团队预算内。

### ⚠️ 3. 换记法（SAFE 之类）—— 机制合理，实证收益未通过验证

SAFE-GPT 的**架构事实**已确认，但其**任务能力主张**在对抗验证中分别以 1-2 和 0-3 **被否决**。

如果 SAFE 的收益真的**全部来自记法而非架构**，那「在现有 7.87M 架构上只换 tokenization / 记法」可能是**最便宜的升级路径**——但**目前缺乏可信证据，必须自己 A/B**。

### 🟡 4. 现代组件（RoPE / RMSNorm / SwiGLU / GQA / flash-attn）—— 顺手换可以，别指望它是「更强的架构」

工程代价极低、风险极低，但**没有任何化学论文证明它们在 ~10⁷ 参数量级带来收益**：

| 模型 | RoPE | RMSNorm | SwiGLU | GQA |
|---|---|---|---|---|
| He 2022（本仓血脉） | ✗ | ✗ | ✗ | ✗ |
| Chemformer | ✗ | ✗ | ✗ | ✗ |
| SAFE-GPT (2024) | ✗ | ✗ | ✗ | ✗ |
| SMI-TED (2024/25) | **✓** | ✗ | ✗ | ✗ |

**唯一的采纳者 SMI-TED 只用了 RoPE，且未做消融。** 可以顺手换，**但不要指望它是那个「更强的架构」**。

*可信度：**medium**（跨 claim 的综合工程判断，非单一 primary source 的直接引述）*

---

## 6. 明确不划算的（论文很热，但对本仓场景不划算）

### ❌ 3D 等变扩散 / flow（EDM、SemlaFlow、FlowMol3、EQGAT-diff、Megalodon、ADiT）

它们的输入输出是**带显式氢的全原子 3D 点云**，目标函数是**坐标 ODE + 离散 CTMC**——**没有 token、没有 next-token 似然、没有因果解码**。

- FlowMol3 的采样是 "Euler ODE steps + CTMC jumps"，全模型**不存在任何 token / next-token / 因果机制**；
- SemlaFlow 的损失是 `λx·MSE(坐标) + 3×λ·CE(类型/键/电荷)`。

→ **它们无法消费本仓的「可变片段 + 恒定骨架 + 活性变化分桶」输入，也无法输出片段 SMILES。迁移过去不是「换骨干」，是「换问题」**；且必然要求 GPU 推理（本仓约束是 CPU）。

### ❌ 指令微调的 7B 化学 LLM（LlaSMol 类）

见 [§2.4](#24--对本仓决策价值最高的一条负面证据)：在最接近的对照任务上输给小型专用 seq2seq，同时把 7.87M 的 CPU 模型变成 7B 的 GPU 模型。

### 📌 值得注意：连 3D 领域内部都还没就「换成 Transformer 并堆规模」形成共识

FlowMol3 用 6M 参数的 GVP-GNN **公开反驳**该论点，而 Semla / Megalodon / ADiT 站在注意力一侧。→ **「更大更 Transformer」在分子生成里尚未被证明是普适方向。**

> **诚实声明**：本节是基于已验证事实的**工程推断**。**没有一篇论文直接说「不要为 MMP 优化换成扩散模型」**——不存在这个对照实验（见 §8）。

*可信度：**medium**，综合判断（基于 3-0 的多条底层事实）*

---

## 7. ⚠️ 被否决的主张 —— 不可当作结论使用

以下主张在 3 票对抗核查中**被杀死**，本文不予背书：

| 被否决的主张 | 票数 |
|---|---|
| SAFE 记法把 linker/decoration/morphing **统一成普通自回归续写、100% validity**，且 Group-SELFIES 对照失败 | 1-2 / **0-3** |
| FlowMol3 以 6M 参数在 **PoseBusters validity 上全面击败** SemlaFlow/Megalodon/ADiT/EQGAT-Diff | **0-3** |
| REINVENT 4 把改进放在 **RL/scoring 层而非骨干**（→ 不要据此声称「工业界的边际收益在 RL 循环里」） | **0-3** |
| SMI-TED 保留 encoder-decoder 的**理由是可逆性 / 潜空间优化** | **0-3** |
| AZ 这条线**自 2022 年以来没有发布架构更新**（PepInvent 等后续工作存在） | **0-3** |
| SMI-TED 采纳 RoPE 的那条**过度具体的表述**（含 linear-attention kernel 细节）——**注意：RoPE 本身已在 §2.2 以 3-0 确认**，被否的是更细的措辞 | 0-3 |

**另有覆盖缺口需承认**：
- **SBDD / 口袋条件化生成：零覆盖**（见 §4）。
- **Equiformer / EquiformerV2 / SE(3)-Transformer：零覆盖**——只在核查者旁注里作为对比出现，层数/维度/张量积细节**未经核实**。
- **Chemformer / Molecular Transformer / MolGPT 的直系后继**：只被间接触及（Chemformer 的 pre-norm + LayerNorm + 正弦 PE 是在核查 He 2022 时顺带在代码里确认的），**没有独立立项验证**。

**时效性**：REINVENT 4 论文是 2024 年的，代码库到 2025–26 又新增了 PepInvent（仍是 Transformer），所以「四种生成器」对论文准确、对当前代码库已不完整（现为五种）。3D 生成这一支迭代极快（flow matching 在 2024→2025 一年内成为主流采样方案），**2026 下半年的结论可能再变**。相反，关于 He 2021/2022、SAFE-GPT、SMI-TED 的架构描述是稳定的。

---

## 8. Open questions（本轮找不到答案的，可能值得自己做）

1. **⭐ 没有任何一篇论文做过这个对照实验**：在同一批 MMP / 属性条件化数据上，比较 (a) 7.87M vanilla encoder-decoder、(b) 同架构换 RoPE+RMSNorm+SwiGLU、(c) 大规模预训练后微调的 100M+ encoder-decoder、(d) LoRA 微调的 7B LLM。
   → **这正是决定「该不该升级」的那个实验，而它似乎不存在。跑它可能比读更多论文更有价值。**
2. SAFE 记法在**条件化优化 / MMP 类似物设计**（而非无条件的 linker/decoration）上到底有多少实证收益？若其收益真的全部来自记法，「只换 tokenization」可能是最便宜的升级路径——但目前缺乏可信证据。
3. beam search / KV cache 相对纯 multinomial 采样，在 MMP 式条件化片段生成上的**实际质量与吞吐收益**有没有已发表的量化数据？本轮只确认了「生产实现里有」，没确认「有多大用」。
4. SBDD 模型是否已进入任何一家药企的**生产流程**，还是仍停留在 benchmark 阶段？
5. 3D 生成内部「Transformer + scaling」vs「小型等变 GNN」之争如何收场？FlowMol3 作者宣称 scaling 无法修复的 "pathologies" 具体是什么？

---

## 附录：论文速查表

| 模型 | 机构 | 年份 / 场所 | 骨干 | 规模 | 现代组件 | 与本仓的关系 |
|---|---|---|---|---|---|---|
| **He et al. 2022** | AstraZeneca | J Cheminform 14:18 | Transformer enc-dec (pre-norm) | 小 | **无** | **直系论文** |
| **REINVENT 4 / Mol2Mol** | AstraZeneca | J Cheminform 2024 | Transformer seq2seq | 小 | **无** | **产品化的兄弟** |
| **SAFE-GPT** | Valence Labs | Digital Discovery 2024 | GPT-2（现成） | 87.3M | **无** | 记法可借鉴（收益待验证） |
| **SMI-TED289M** | IBM Research | Comms Chem 2025 | Transformer enc-dec | 289M | **仅 RoPE** | **升级路线的先例** |
| **LlaSMol** | OSU NLP | COLM 2024 | Mistral-7B + LoRA | 7B | 全套（借底座） | **反面教材** |
| **EDM** | UvA | ICML 2022 | **EGNN**（非 Transformer） | 9 层 | — | 换问题，不划算 |
| **SemlaFlow** | AstraZeneca + Chalmers | AISTATS 2025 | 等变隐空间注意力 | 22M | — | 换问题，不划算 |
| **FlowMol3** | Pittsburgh | Digital Discovery 2026 | **GVP-GNN**（零注意力） | ~6M | — | 换问题，不划算 |
| **Megalodon** | NVIDIA | Digital Discovery 2026 | diffusion-transformer | 60M | — | 换问题，不划算 |

## 附录：核心来源

- REINVENT 4 — https://pubmed.ncbi.nlm.nih.gov/38383444/ · https://github.com/MolecularAI/REINVENT4
- He et al. 2022 — https://pmc.ncbi.nlm.nih.gov/articles/PMC8962145/ · https://github.com/MolecularAI/deep-molecular-optimization
- He et al. 2021 — https://pmc.ncbi.nlm.nih.gov/articles/PMC7980633/
- SAFE-GPT — https://pubs.rsc.org/en/content/articlelanding/2024/dd/d4dd00019f · https://arxiv.org/abs/2310.10773 · https://huggingface.co/datamol-io/safe-gpt
- SMI-TED — https://arxiv.org/pdf/2407.20267 · https://huggingface.co/ibm-research/materials.smi-ted
- LlaSMol — https://arxiv.org/pdf/2402.09391 · https://osu-nlp-group.github.io/LLM4Chem/
- EDM — https://arxiv.org/abs/2203.17003 · https://proceedings.mlr.press/v162/hoogeboom22a.html
- SemlaFlow — https://proceedings.mlr.press/v258/irwin25a.html · https://arxiv.org/abs/2406.07266 · https://github.com/rssrwn/semla-flow
- FlowMol3 — https://arxiv.org/abs/2508.12629 · https://doi.org/10.1039/D5DD00363F
- Megalodon — https://arxiv.org/abs/2505.18392
- GEOM-drugs revisited（指标 bug）— https://arxiv.org/abs/2505.00169

*调研统计：5 个检索角度 · 25 篇源文 · 125 条候选事实 · 25 条进入验证 · 18 条确认 · 7 条被否决 · 107 个 agent 调用*
