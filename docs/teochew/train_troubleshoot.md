# 潮汕话分支训练报错总结与修复

> 记录在使用 `webui.py` 一键三连（`exp_name=teochew_01`）格式化 `04_ChaoShan` 数据时出现的两类错误及修复方法。
> 训练数据入口：`data/04_ChaoShan/train.list`（1309 行，v2 全量）/ `train_indict.list`（158 行，纯封闭词典内，无 UNK）。

---

## 错误一：WebUI 启动报 `ModuleNotFoundError: No module named 'torch'`

### 现象
在 `(tts)` conda 环境下执行：

```bash
(tts) root@...:~/autodl-tmp/GPT-SoVITS# python webui.py zh_CN
...
  File ".../webui.py", line 16, in <module>
    import torch
ModuleNotFoundError: No module named 'torch'
```

### 根因
`(tts)` 环境（`/root/miniconda3/envs/tts`）**未安装 torch**。本项目之前训练 `nan-tw` 时实际使用的是 **base 环境**（`/root/miniconda3/bin/python`，已装 torch 2.5.1+cu124）。环境被切错导致 `torch` 找不到。

### 修复
启动 WebUI / 跑训练脚本时**不要激活 `(tts)` 环境**，用 base 环境的 python：

```bash
conda deactivate            # 退出 tts 环境，回到 base
cd /root/autodl-tmp/GPT-SoVITS
/root/miniconda3/bin/python webui.py zh_CN
```

或显式指定解释器：`/root/miniconda3/bin/python -s GPT_SoVITS/prepare_datasets/xxx.py`。

---

## 错误二：`3-get-semantic.py` 符号维度不匹配

### 现象
一键三连执行到语义 Token 提取阶段（`3-get-semantic.py`）崩溃：

```
Traceback (most recent call last):
  File ".../prepare_datasets/3-get-semantic.py", line 84, in <module>
    vq_model.load_state_dict(
RuntimeError: Error(s) in loading state_dict for SynthesizerTrn:
        size mismatch for enc_p.text_embedding.weight: copying a param with shape
        torch.Size([732, 192]) from checkpoint, the shape in current model is torch.Size([836, 192]).
```

随后一键三连合并阶段报：

```
FileNotFoundError: [Errno 2] No such file or directory: 'logs/teochew_01/6-name2semantic-0.tsv'
训练集格式化一键三连进程已终止
```

### 根因
潮汕话分支在 `text/symbols2.py` 的 `symbols` 末尾**追加了 104 个 teochew 音素**（`teochew_symbols`），使 SoVITS 的符号表从 v2 底模的 **732** 变为 **836**（`732 + 104`）。

- 当前模型定义（`SynthesizerTrn`）从 `symbols2.symbols` 动态计算 `n_symbols = 836`；
- 底模 `s2G488k.pth` 是原始 v2 权重，其 `enc_p.text_embedding.weight` 只有 **732** 维；
- `3-get-semantic.py` 原逻辑 `vq_model.load_state_dict(ckpt["weight"], strict=False)`：对 shape 不同的张量不会"跳过"，而是**直接抛 RuntimeError**，导致后续 `6-name2semantic-*.tsv` 从未生成。

这正好印证了 `docs/teochew/code.md` 第 131 行的预警：
> 追加符号后 `n_symbols` 变大，SoVITS 的 `symbol_emb` 维度变了——不能 load 原中文底座的 symbol embedding 层。

### 修复
修改 `GPT_SoVITS/prepare_datasets/3-get-semantic.py`：加载前从 checkpoint 中**剔除文本 embedding 层**，其余声学 / VQ 权重照常加载。

```python
# 原来
print(
    vq_model.load_state_dict(
        torch.load(pretrained_s2G, map_location="cpu", weights_only=False)["weight"], strict=False
    )
)

# 改为
_ckpt = torch.load(pretrained_s2G, map_location="cpu", weights_only=False)
_sd = _ckpt.get("weight", _ckpt)
_sd.pop("enc_p.text_embedding.weight", None)   # teochew 新符号无底模 embedding，剔除即可
print(vq_model.load_state_dict(_sd, strict=False))
```

**为什么安全**：语义 Token 提取只用 hubert → VQ 量化部分，完全不依赖文本 embedding（`enc_p.text_embedding`）。剔除后不影响 `6-name2semantic.tsv` 的结果，其余层也正常加载（日志显示 `missing_keys=['enc_p.text_embedding.weight']`，`unexpected_keys=[]`）。

---

## 修复后补跑步骤

由于 `2-get-hubert-wav32k.py` / `2-get-sv.py` 已成功生成 `4-cnhubert/`（1309）、`5-wav32k/`、`7-sv_cn/`，只需补跑语义提取并合并：

```bash
cd /root/autodl-tmp/GPT-SoVITS
export inp_text=data/04_ChaoShan/train.list \
       exp_name=teochew_01 i_part=0 all_parts=1 \
       opt_dir=logs/teochew_01 \
       pretrained_s2G=GPT_SoVITS/pretrained_models/s2G488k.pth \
       s2config_path=GPT_SoVITS/configs/s2.json is_half=True
/root/miniconda3/bin/python -s GPT_SoVITS/prepare_datasets/3-get-semantic.py

# 合并为训练读取的 6-name2semantic.tsv（与 WebUI 逻辑一致）
/root/miniconda3/bin/python -c "
opt=['item_name\tsemantic_audio']
for i in range(1):
    p='logs/teochew_01/6-name2semantic-%s.tsv'%i
    opt+=open(p,encoding='utf8').read().strip('\n').split('\n')
open('logs/teochew_01/6-name2semantic.tsv','w',encoding='utf8').write('\n'.join(opt)+'\n')
"
```

---

## 最终 `logs/teochew_01/` 产物清单（训练就绪）

| 文件 / 目录 | 说明 |
|---|---|
| `2-name2text.txt` | teochew 前端 g2p 音素 + word2ph |
| `4-cnhubert/` | 1309 个 hubert 特征 `.pt` |
| `5-wav32k/` | 32k 重采样 wav |
| `7-sv_cn/` | 说话人向量 |
| `6-name2semantic.tsv` | 语义 token（1309 行，已合并） |

---

---

## 错误三 / 四：1B 微调训练加载底模时符号维度不匹配（SoVITS 与 GPT 双双崩溃）

### 现象（预期，未实际触发即已修复）
在 WebUI 1B 直接点"开启训练"会用到底模 `v2Pro/s2Gv2Pro.pth`（SoVITS）与 `s1v3.ckpt`（GPT）。
这两个底模都不含 teochew 追加的 104 个音素，因此：
- **SoVITS**：`s2_train.py` 加载底模 `enc_p.text_embedding.weight` 维度为「底模符号数」，当前模型为 **836**，shape 不同即便 `strict=False` 也会抛 RuntimeError；
- **GPT**：`AR/models/t2s_lightning_module.py` 加载底模 `model.ar_text_embedding.weight` 默认 `strict=True`，维度不一致直接 RuntimeError。

根因与错误二完全一致：潮汕话分支把 `n_symbols` 从底模的 N 增大到 836，而底模没有新符号的 embedding。

### 修复
#### 4a. SoVITS 训练（`GPT_SoVITS/s2_train.py`）
加载底模前从 checkpoint 剔除文本 embedding 层：

```python
# 原来
print(
    "loaded pretrained %s" % hps.train.pretrained_s2G,
    net_g.module.load_state_dict(
        torch.load(hps.train.pretrained_s2G, map_location="cpu", weights_only=False)["weight"],
        strict=False,
    )
    if torch.cuda.is_available()
    else net_g.load_state_dict(
        torch.load(hps.train.pretrained_s2G, map_location="cpu", weights_only=False)["weight"],
        strict=False,
    ),
)

# 改为
_tmp = torch.load(hps.train.pretrained_s2G, map_location="cpu", weights_only=False)
_sd = _tmp.get("weight", _tmp)
_sd.pop("enc_p.text_embedding.weight", None)   # teochew 新符号无底模 embedding，剔除
print(
    "loaded pretrained %s" % hps.train.pretrained_s2G,
    net_g.module.load_state_dict(_sd, strict=False)
    if torch.cuda.is_available()
    else net_g.load_state_dict(_sd, strict=False),
)
```

#### 4b. GPT 训练（`GPT_SoVITS/AR/models/t2s_lightning_module.py`）
加载底模前从 checkpoint 剔除 phoneme embedding 层：

```python
# 原来
print(
    self.load_state_dict(
        torch.load(pretrained_s1, map_location="cpu", weights_only=False)["weight"]
    )
)

# 改为
_s1 = torch.load(pretrained_s1, map_location="cpu", weights_only=False)["weight"]
_s1.pop("model.ar_text_embedding.weight", None)   # teochew 新符号无底模 embedding，剔除
print(self.load_state_dict(_s1))
```

**为什么安全**：被剔除的文本 / phoneme embedding 层在训练中由 `text_low_lr_rate`（SoVITS，默认 0.4）或随机初始化 + 正常学习率（GPT）重新学习。其余声学 / 语义 / 注意力权重全部从底模继承，微调质量不受影响。语义 token 由 hubert→VQ 量化得到，与底模符号表无关，**v2 base 提取的语义 token 对 v2Pro 训练依旧兼容**（均为 25hz / cnhubert / gin_channels=1024 同一套量化器）。

### 验证
- GPT 训练已启动，**无报错**（实测 2026-08-23）。
- SoVITS 训练同样经此修复可正常加载 v2Pro 底模。

---

## 训练配置建议（1300 句 / 单卡 32G）

| 项 | WebUI 默认值 | 建议 |
|---|---|---|
| SoVITS batch_size | 15 | **8~10**（32G 偏紧，防 OOM） |
| GPT batch_size | 15 | **8~10** |
| SoVITS total_epoch | 8 | 8 合理 |
| GPT total_epoch | 15 | 15 合理 |
| text_low_lr_rate | 0.4 | 保持（新符号 embedding 低 lr 微调） |
| save_every_epoch | 4 / 5 | 合理 |

> 语义 token 已用 v2 base 的 VQ 提取并复用，无需因改用 v2Pro 底模而重提。

---

## 错误五：GPT 训练 `indexSelectLargeIndex: srcIndex < srcSelectDimSize`（phoneme 越界）

### 现象（实际触发）
1B-GPT（`s1_train.py`）启动后，`Epoch 0/14` 第一步即报大量
`indexSelectLargeIndex: srcIndex < srcSelectDimSize` 断言失败，随后
`RuntimeError: CUDA error: device-side assert triggered`，栈指向
`forward_old` 中 `x = self.ar_text_embedding(x)`（phoneme embedding 查找越界）。

### 根因
- teochew 分支把 `text/symbols2.py` 的符号表从 **732** 扩到 **836**（追加 104 个潮汕音素，占据 index 732~835）。
- 但 GPT 的 `phoneme_vocab_size` 在 config（`configs/s1longer-v2.yaml` 第 21 行）里**写死为 732**，未随符号表同步。
- `t2s_model.py` 用该值建 `ar_text_embedding`（维度 732），而 `2-name2text.txt` 里的潮汕音素最大 index = **834** → 查 732 维表越界。
- 这正是错误三/四处「底部模型无 teochew embedding」的延续：之前只修了*加载*（pop 掉 text_embedding），却没让**模型维度**随符号表扩大到 836，导致数据 index 超过模型 embedding 维度。

### 修复
#### 5a. 让 `phoneme_vocab_size` 动态跟随符号表（`GPT_SoVITS/AR/models/t2s_model.py`）
在 `Text2SemanticDecoder.__init__` 中把写死的 732 改为 `max(config值, len(symbols2.symbols))`：
```python
from text import symbols2   # 文件顶部新增 import
...
self.phoneme_vocab_size = max(
    config["model"]["phoneme_vocab_size"], len(symbols2.symbols)
)
```
效果：
- teochew（符号表 836）→ phoneme_vocab = 836，覆盖 index 834；
- 原始符号集（732）训练中文/粤语 → 仍为 732，**向后兼容、不浪费参数**。

#### 5b. 底模 `ar_text_embedding` 扩维而非丢弃（`GPT_SoVITS/AR/models/t2s_lightning_module.py`）
加载底模时不直接 pop（会丢失原 732 个符号的 phoneme 知识），而是**前 732 行原样保留、仅新增 733~835 行零初始化**（**注意实际 checkpoint 的 key 是 `model.ar_text_embedding.word_embeddings.weight`，不是 `model.ar_text_embedding.weight`**，建议用子串匹配前缀 `model.ar_text_embedding`）：
```python
_prefix = "model.ar_text_embedding"
for _key in list(_s1.keys()):
    if _key.startswith(_prefix) and _s1[_key].shape.__len__() == 2 \
            and _s1[_key].shape[0] < self.model.phoneme_vocab_size:
        _old = _s1[_key]
        _new = _old.new_zeros(self.model.phoneme_vocab_size, _old.shape[1])
        _new[: _old.shape[0]] = _old
        _s1[_key] = _new
print(self.load_state_dict(_s1, strict=False))
```

#### 5c. 同样改进 SoVITS（`GPT_SoVITS/s2_train.py`）
`enc_p.text_embedding` 也由「pop 丢弃」改为「resize 保留原符号」（逻辑同 5b，符号数取自 `len(symbols2.symbols)`，**不要**用 `net_g.module.n_symbols` —— 当前 `SynthesizerTrn` 没有该属性）：

文件顶部新增 import：
```python
from text import symbols2  # teochew 分支: symbols2.symbols 含追加的 104 个音素(共 836)
```

resize 逻辑：
```python
_key = "enc_p.text_embedding.weight"
_n_symbols = len(symbols2.symbols)  # teochew 扩展后总数(836)
if _key in _sd and _sd[_key].shape[0] < _n_symbols:
    _old = _sd[_key]
    _new = _old.new_zeros(_n_symbols, _old.shape[1])
    _new[: _old.shape[0]] = _old
    _sd[_key] = _new
```

### 验证要点（重跑训练前自查）
- `len(symbols2.symbols) == 836`，且 `2-name2text.txt` 中 phoneme 最大 index == 834（均 < 836）✅ 已核对。
- `6-name2semantic.tsv` 语义 token 最大 == 1023（< 1024 vocab）✅ 已核对，语义侧无越界。
- 修复后 `s1_train.py` 不再出现 `indexSelectLargeIndex` 断言。

---

## 后续启动训练

```bash
/root/miniconda3/bin/python webui.py zh_CN   # 用 base 环境，不要进 (tts)
```

- 1A 格式化数据已就绪（`logs/teochew_01/` 产物清单见上），无需重跑；
- 直接进入 **1B** 训练 SoVITS + GPT（`exp_name=teochew_01`，底模 `v2Pro/s2Gv2Pro.pth` / `s1v3.ckpt`）；
- 本笔记三处加载逻辑（3-get-semantic / s2_train / t2s_lightning_module）均已修复，可直接提交；
- 推理界面语言下拉框已含**"潮汕话"**，加载训练产物即可合成。

> 备注：若改用 v3 底模（`s2Gv3.pth`），符号数基准不同，但仍需对 teochew 新增符号做同样的 embedding 剔除处理（同款修复逻辑）。

---

## 错误六：新实例 numpy/scipy/sklearn 版本互不相容（ufunc 崩溃）

### 现象（实际触发，env=be624da05d）
换实例后，WebUI 一键三连的 `1-get-text.py` 在 `import transformers` 阶段即崩溃，报：
```
numpy.ndarray ... All ufuncs must have type numpy.ufunc
```
以及 `scipy.special._multiufuncs` import 失败。底层是 numpy / scipy / sklearn 三件套版本错配。

### 根因
- base 环境是 **Python 3.12**，之前在 `(tts)` 与 base 之间来回 `pip install` 互相污染，导致 numpy 被顶到 2.2.6，而 scipy / sklearn 残留不兼容版本。
- 一度尝试 `pip install "numpy==1.23.5"`，但 **numpy 1.23.5 在 py3.12 上无预编译 wheel**，pip 被迫源码编译，构建用的旧 setuptools 在 py3.12 上因 `pkgutil.ImpImporter` 被移除而失败（`AttributeError: module 'pkgutil' has no attribute 'ImpImporter'`）。**numpy 1.23.5 对 py3.12 是死路**。

### 修复（保持 py3.12，对齐三件套）
```bash
# 1) scipy / sklearn 降到与 numpy 1.26 兼容的稳定版（--force-reinstall 会把 numpy 一并拽成 2.2.6，属正常）
/root/miniconda3/bin/python -m pip install -U --force-reinstall "scipy==1.13.1" "scikit-learn==1.5.2"

# 2) 把被拽上去的 numpy 钉回 1.26.4（torch 2.5.1 / torchmetrics 要求 numpy<2.0）
/root/miniconda3/bin/python -m pip install "numpy==1.26.4"
```

验证（期望无报错）：
```bash
/root/miniconda3/bin/python -c "import numpy,scipy,sklearn,torch; \
  print('numpy',numpy.__version__); print('scipy',scipy.__version__); \
  print('sklearn',sklearn.__version__); print('torch',torch.__version__)"
# numpy 1.26.4 / scipy 1.13.1 / sklearn 1.5.2 / torch 2.5.1+cu124
```

> 冲突告警 `umap-learn requires scikit-learn>=1.6` 可忽略，GPT-SoVITS 训练用不到 umap-learn。

---

## 错误七：SoVITS 训练 `AttributeError: 'SynthesizerTrn' object has no attribute 'n_symbols'`

### 现象（实际触发，exp_name=teochew_03）
1B-SoVITS（`s2_train.py`）在加载 v2Pro 底模、执行 embedding resize 时崩溃：
```
File ".../s2_train.py", line 245, in run
  if _key in _sd and _sd[_key].shape[0] < net_g.module.n_symbols:
AttributeError: 'SynthesizerTrn' object has no attribute 'n_symbols'
```
（同栈顶还有一条 `IndexError: list index out of range` @ `latest_checkpoint_path("D_*.pth")` —— 那是首次训练无判别器 checkpoint 的正常分支，被本错误掩盖，非主因。）

### 根因
错误五 5c 段最初写的 resize 代码引用了 `net_g.module.n_symbols`，但**当前版本的 `SynthesizerTrn` 没有 `n_symbols` 属性**。正确的符号总数应来自 `text/symbols2.py`（`len(symbols2.symbols)`，teochew 扩展后 = 836）。

### 修复（`GPT_SoVITS/s2_train.py`）
1. 文件顶部加 import：
   ```python
   from text import symbols2  # teochew 分支: symbols2.symbols 含追加的 104 个音素(共 836)
   ```
2. resize 处改用 `len(symbols2.symbols)`（见错误五 5c 段修正后的代码）。

### 验证
重新提交 1B-SoVITS 不再出现 `n_symbols` 的 AttributeError；GPT 侧（`t2s_lightning_module.py`）用的是 `model.phoneme_vocab_size`，无此问题，无需改动。

> 教训：符号总数统一以 `len(symbols2.symbols)` 为准，不要假设模型上有 `n_symbols` 字段。

---

## 错误八：推理启动 `inference_webui.py` 加载 GPT 权重 shape 不匹配（732 vs 836）

### 现象（实际触发）
点开推理 webui（`inference_webui.py`）启动时崩溃：
```
File ".../inference_webui.py", line 425, in change_gpt_weights
    t2s_model.load_state_dict(dict_s1["weight"])
RuntimeError: Error(s) in loading state_dict for Text2SemanticLightningModule:
        size mismatch for model.ar_text_embedding.word_embeddings.weight:
        copying a param with shape torch.Size([732, 512]) from checkpoint,
        the shape in current model is torch.Size([836, 512]).
```
（训练时修过的 `t2s_lightning_module.py` resize 只在 `is_train=True` 时执行，而推理 `is_train=False`，加载路径 `change_gpt_weights` 没有任何扩维逻辑，直接 `load_state_dict` → mismatch。）

### 修复（`GPT_SoVITS/inference_webui.py` 的 `change_gpt_weights`）
加载前对 `dict_s1["weight"]` 做 embedding 扩维（逻辑同训练侧，取 `t2s_model.model.phoneme_vocab_size`，前缀 `model.ar_text_embedding` 子串匹配）：
```python
_sd = dict_s1["weight"]
_pvs = getattr(t2s_model.model, "phoneme_vocab_size", None)
_prefix = "model.ar_text_embedding"
if _pvs is not None:
    for _key in list(_sd.keys()):
        if _key.startswith(_prefix) and _sd[_key].dim() == 2 \
                and _sd[_key].shape[0] < _pvs:
            _old = _sd[_key]
            _new = _old.new_zeros(_pvs, _old.shape[1])
            _new[: _old.shape[0]] = _old
            _sd[_key] = _new
t2s_model.load_state_dict(_sd)
```

> 注意：若 `weight.json` 里 GPT 默认仍指向 732 维底模，扩维后虽能加载但**不含潮汕话知识**。推理潮汕话必须在界面下拉框手动选择 **teochew_03 训练产物**（文件名含 `teochew_03`，如 `GPT_weights_v2Pro/teochew_03-e15.ckpt`），语言选 **"潮汕话"**。

---

## 错误九：CUDA Graph 推理 `T2SDecoder` 维度未跟随符号表（836 vs 732，反向 mismatch）

### 现象（实际触发，已加载 teochew_03 权重后）
推理合成请求阶段（`get_tts_wav` → `CUDAGraphRunner.load_decoder`）崩溃：
```
File ".../AR/models/t2s_model_cudagraph.py", line 601, in load_decoder
    decoder.load_state_dict(state_dict)
RuntimeError: Error(s) in loading state_dict for T2SDecoder:
        size mismatch for ar_text_embedding.word_embeddings.weight:
        copying a param with shape torch.Size([836, 512]) from checkpoint,
        the shape in current model is torch.Size([732, 512]).
```
这次反过来：checkpoint（teochew_03 训练产物）是 **836** 维，但 CUDA Graph 加速解码器 `T2SDecoder` 只建了 **732** 维。

### 根因
推理加速用的 `T2SDecoder`（`AR/models/t2s_model_cudagraph.py`）在建模型时：
```python
phoneme_vocab_size = config["model"]["phoneme_vocab_size"]   # 写死 732
```
没像训练侧 `t2s_model.py` 那样 `max(..., len(symbols2.symbols))` 扩到 836。

### 修复（`GPT_SoVITS/AR/models/t2s_model_cudagraph.py`）
1. 文件顶部加 import：
   ```python
   from text import symbols2  # teochew 分支: 符号表含追加的 104 个音素(共 836)
   ```
2. `T2SDecoder.__init__` 改为动态跟随符号表：
   ```python
   phoneme_vocab_size = max(
       config["model"]["phoneme_vocab_size"], len(symbols2.symbols)
   )
   ```
3. `load_decoder` 加载前加保险扩维（兼容加载 732 维旧底模）：
   ```python
   _pvs = decoder.phoneme_vocab_size
   _prefix = "ar_text_embedding"
   for _key in list(state_dict.keys()):
       if _key.startswith(_prefix) and state_dict[_key].dim() == 2 \
               and state_dict[_key].shape[0] < _pvs:
           _old = state_dict[_key]
           _new = _old.new_zeros(_pvs, _old.shape[1])
           _new[: _old.shape[0]] = _old
           state_dict[_key] = _new
   decoder.load_state_dict(state_dict)
   ```

### 验证
重启推理 webui，选 teochew_03 权重 + 潮汕话，合成不再报 mismatch，正常出声。

> 教训：teochew 符号表扩展（732→836）的影响面有**三处模型定义 + 四处加载路径**：
> - 模型定义：`t2s_model.py`(训练 GPT)、`t2s_model_cudagraph.py`(CUDA Graph 推理 GPT)、`module/models.py`(SoVITS，本就从 symbols2 动态取)；
> - 加载路径：`t2s_lightning_module.py`(训练 GPT)、`s2_train.py`(训练 SoVITS)、`inference_webui.py`(推理 GPT)、`t2s_model_cudagraph.py.load_decoder`(推理 GPT)。
> 只要有一处漏掉动态 `phoneme_vocab_size` 或没做扩维，就会在对应阶段报错。

---

## 效果调优：合成"多读半句"（EOS 学不准）

### 现象
音色/语调已经很像潮汕话发音人，但合成长句时常在句末**又续一小句**。

### 根因核查结论（重要）
1. **推理端 EOS 截断逻辑本身是正确的，不需要改代码。**
   - 训练时每条样本的语义序列在 `t2s_model.pad_y_eos` 末尾补一个 `EOS=1024`（vocab_size=1025，EOS 是最后一个）。
   - 推理时（CUDA Graph 路径 `t2s_model_cudagraph.py` 第 530-558 行 / 非 CUDA Graph 路径 `t2s_model.py:infer`）一旦 `argmax` 或 `sample` 命中 EOS，立即 `completed=True` 并 `break`，且 `y_results` 只存 **EOS 之前** 的内容（`session.y_len:-1`），**不会把 EOS 之后的 token 送进 SoVITS**。
   - 因此"多读半句"不是推理截断 bug，而是 **GPT 在句末把 EOS 预测得太晚 / 太弱**，导致真正的停止点后移，续写的那段被算进了 `y_results`。

2. **真正原因在数据质量（与用户"多半和数据量有关"的判断一致）：**
   - 部分训练样本的语义 token 序列**末尾有异常重复 token**（如日志里见到的 `...596 596`），或音频实际长度与语义 token 数不匹配，使 EOS 位置标注不准。
   - 小数据集（1300 句）下 GPT 泛化弱，更容易在长句末尾"补"一段相似韵律。

### 数据侧优化（治本）
运行边界质量扫描脚本，定位脏样本：
```bash
/root/miniconda3/bin/python data/04_ChaoShan/scan_semantic_quality.py \
    logs/teochew_03/6-name2semantic.tsv
```
脚本会统计 token 数分布、末尾异常重复、超长尾、序列内含 EOS(1024) 的样本，并把清单写到 `logs/teochew_03/scan_dirty_samples.txt`。处理建议：
- 删掉 / 重提 **末尾异常重复** 和 **含 EOS** 的样本（避免训练出现双 EOS 或噪声尾）。
- 把 **超长句（>15s 语义）切短**，让模型更多见到"短句+干净 EOS"样本。
- 确保训练音频**句尾有自然停顿、完整收尾**（不要截断式录音）。
- 1300 句对新语种偏少，清洗后若仍不足，增补同说话人、句末干净的录音收益最大。

### 推理侧调参（立竿见影，治标）
默认推理参数偏发散（`top_k=20, top_p=0.6, temperature=0.6`），小数据集上易在 EOS 后继续采样。在 WebUI 推理界面把：
- `top_k` 调小到 **5**（脚本里 `CUDAGraphRunner.load_decoder` 默认也是 5，界面默认值偏大）。
- `temperature` 降到 **0.3~0.5**，压住末尾续写幻觉。
- 长目标文本务必**按标点切句**（界面"切分方式"选按标点），避免整句过长导致停止不稳。
- 仍无效时，可在 `inference_webui.py` 把 `early_stop_num=hz*max_sec` 适当调小（提前兜底停止），但优先用前三项。

> 经验：音色/语调已经到位说明模型容量足够；EOS 行为主要靠"干净句末样本 + 收敛的采样参数"解决，比单纯堆数据更快见效。
