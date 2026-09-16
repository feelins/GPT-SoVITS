# 第二阶段训练方案：GPT-SoVITS 框架不动，并入新 6000 条潮汕数据

> 决策日：2026-09-14（2026-09-15 修订：词典扩充由"备选"升为"必须前置步骤"）
> 目标：在 **不改 GPT_SoVITS 代码** 的前提下，把 `data/new_chaoshan` 的约 6000 条音频并入训练，观察 EOS（多读半句）是否改善。

---

## 0. 结论（一句话）

按规划执行**第二阶段**：GPT_SoVITS 代码一行不改，仅扩充数据与词典。
`train.list` 第4列继续放**汉字**（与旧 `04_ChaoShan` 完全一致），音素由 `teochew.g2p` 在预处理阶段从汉字转换，模型实际学音素。
新实验名 **`teochew_04`**，从**官方底模重训**（与 teochew_03 干净 A/B 对比）。
**前置必须项：扩充潮汕词典**，否则 6000+ 句主训练会被 UNK 拖垮。

> **✅ 已验证（2026-09-14）**：teochew_04 合成比 1300 句时稳定很多、效果更好 → 数据量是决定性因素，假设成立。完整成果与后续路线见 `train_phase2_result.md`。

---

## 1. 汉字 vs 音素：澄清

| 环节 | 内容 | 说明 |
|------|------|------|
| `train.list` 第4列 | **汉字**（如 `一念之慈，顶上生出…`） | 与旧 `04_ChaoShan/train.list` 完全一致 |
| 预处理 `cleaner.clean_text` | 调用 `teochew.g2p(汉字)` | 汉字→音节→声母/韵母音素 |
| 模型（GPT/SoVITS）输入 | **音素序列** | 由 g2p 实时生成，落在 `symbols2`（836 个）封闭集 |

- "用汉字训练" = list 里写汉字；"用音素训练" = 模型学音素。二者同一流程两端，不冲突。
- 新数据直接放汉字进 list，跟旧数据同口径。

---

## 2. 数据现状核对

| 数据集 | 路径 | 句数 | 说明 |
|--------|------|------|------|
| 旧训练集 | `data/04_ChaoShan/` | **1309** 句 | speaker `chao_shan_01`，已训出 teochew_03 |
| 新数据音频 | `data/new_chaoshan/new_chao_data_label_new/` | **6388** 个 wav | 同一发音人，重复录音：2378 独立文本，每句 1–8 遍 |
| 新数据汉字+音素 | `data/new_chaoshan/prosody_all_log.txt` | 2381 句 | 含汉字原文 + 带调音素（韵律标注） |

**编号映射（已验证 2378/2378 全命中）**：音频 `00001001.wav` 前 5 位 `00001` == `prosody_all_log.txt` 编号 `00000001` 的**后 5 位**。同句多遍（`001/002/003`）对应同一句汉字。

---

## 3. 执行步骤（词典扩充为必须前置）

### 3.0 【必须】扩充潮汕词典（PATH A：保留旧体系，做新→旧拼写映射）
> 为什么必须：新数据约 89.6% 句子含 `teochew.g2p` 查不到的字 → 全部坍缩成同一个 `UNK` token
> （`symbols2.py` 第4行 `UNK` 在词表，故**不崩**，但数百个不同方言字共用一 token，污染文本→音素对齐，
> 反而恶化 EOS/多读半句）。主训练必须把 OOV 字补出正确发音。

**关键坑（已核实）**：新数据 prosody 的罗马字拼法 **≠** 训练词表 `symbols2.teochew_symbols` 的拼法。
- 旧体系（训练用）：`iao / ian / uain / z / g / h …`
- 新数据（prosody）：`iaa / ainn / uainn / dz / gg / hh / kg …`（见 `system_diff.txt` 新有/旧无清单，约 50 个新特有音素）

→ 不能把"字→新拼写"直接塞进词典（查 `allpinyin_with_shengyun` 会落空）。必须做 **新拼写→旧拼写** 音节映射。

**做法**：
1. 脚本从 `prosody_all_log.txt` 提取 `字 ↔ 新拼写音节`（按词对齐、字/音节等长时逐字取）。
2. 建 `新拼写→旧拼写` 映射表（约 50 音素：`aa→a`、`iaa→ia`、`ainn→ain`、`uainn→uain`、`dz→z`、`gg→g`、`hh→h`、`kg→k`… 部分 finals 如 `ieng/ienn` 对应旧 `iem/iehn` 有歧义，需核对）。
3. 追加进 `data/04_ChaoShan/字_allpinyin_20180312.txt`；`allpinyin_with_shengyun.txt` 旧音节已齐，一般不动；`symbols2.py` **不动**。
4. 覆盖率检查：新数据 UNK 率应降到接近 0，再继续。

> PATH A 好处：旧 1309 句零影响，新旧数据走同一音素词表，GPT_SoVITS 代码零改动。

### 3.1 生成新数据 train.list（标准 4 列）
改写 `data/new_chaoshan/build_train_list.py`，输出：
```
{new_chao_data_label_new 绝对路径}.wav|chao_shan_01|teochew|{prosody 汉字原文}
```
- 汉字原文取自 `prosody_all_log.txt` 每块第 2 行（已去分词 `*`）。
- **保留全部 6388 个 wav**（重复遍数 = 数据增强）。
- 音素不写进 list（交给 g2p）。

### 3.2 合并
新 list 与 `data/04_ChaoShan/train.list`（1309 行）首尾拼接 → 新 `train.list`（约 6388+1309，同一 speaker `chao_shan_01`）。

### 3.3 重跑训练流水线（框架不动）
沿用 `docs/teochew/train_troubleshoot.md` 一键三连 / `s1_train.py`+`s2_train.py`：
1. `1-get-text.py`：汉字 → 音素（走 `teochew.g2p`，已扩充词典）
2. `2-get-hubert/2-get-sv.py`：提取 hubert / speaker embedding
3. `3-get-semantic.py`：音频 → 语义 token
4. 训练：实验名 **`teochew_04`**，从官方预训练底模微调（与 teochew_03 A/B 对比）。

> 词表固定 836，不触发 embedding 扩维，之前修过的 resize 逻辑无需再动。

---

## 4. 验证 EOS 是否改善
1. 用 `data/04_ChaoShan/scan_semantic_quality.py` 扫描合并 list 的 token 分布 / 尾部重复 / 序列内 EOS。
2. 推理参数建议：`top_k=5`、`temperature=0.3–0.5`（见 troubleshoot 文档"效果调优：EOS学不准"）。
3. 对比 teochew_03 vs teochew_04 在同样测试句上的"多读半句"发生率。

---

## 5. 风险与分阶段（已更新）

| 步骤 | 动作 | 状态 |
|------|------|------|
| **3.0 词典扩充** | 字→旧体系音节映射，消除新数据 UNK | **必须前置** |
| 3.1–3.3 合并+重训 | 6388+1309 合并，teochew_04 从底模重训 | 主流程 |
| 2c 去重 | 若重复遍数导致过拟合/单句权重过高 | 视情况 |

**词典扩充素材已在手边**：`prosody_all_log.txt` 每行"汉字 ↔ 带调音素"可提取 `字→音节` 映射。
仅追加"字→已有旧体系音素"的映射，不引入新音素，故不触碰 `symbols2`，框架仍不动。

---

## 6. 用户已拍板项
- [x] 合并全部：**6388 + 原来 1309** 全部合并成一个最新最全 train.list
- [x] 新实验：**teochew_04 从底模重训**
- [x] 词典：**必须扩充**（否则 6000+ 主训练被 UNK 拖垮）
- [ ] "新→旧"罗马字映射表的具体条目（见 3.0 第2步），需逐条核对/确认

---

## 7. 实际脚本（已落地）
- [x] `data/new_chaoshan/build_full_dataset.py` → 一步完成：扩充词典 + 生成合并 list + UNK 校验
  - `--no-write` 只分析不写；`--drop-unk` 删除含 UNK 句生成零 UNK 的 list
  - 产物：`train_full.list`（7646 行，零 UNK）、词典已 +229 字 +34 音节（原件 `.bak` 备份）

---

## 8. WebUI 一键三连训练参数与注意事项（teochew_04）

### 8.1 必填（与 train.list 区分）
| 项 | 填什么 | 说明 |
|----|--------|------|
| **实验名称** | `teochew_04` | 即 exp_name，填在 WebUI「实验名称」输入框，**不是 train.list 第2列** |
| **训练集路径** | `data/new_chaoshan/train_full.list` | 指向生成的零 UNK 全量 list |
| **预训练底模** | 官方底模 | **不要选 teochew_03**，否则不是"从底模重训" |
| 说话人(speaker) | 保持 `chao_shan_01` | train.list 第2列，同一人，不动 |

### 8.2 SoVITS 参数（你截图的值）
- 每张显卡 batch_size：**11**（单卡 GPU=0；若 OOM 降到 8/6）
- 总训练轮数 total_epoch：**8**（数据量已 6× 旧集，8 轮足够，不宜太高防过拟合）
- 文本模块学习率权重：**0.4**（音节映射是新扩的，0.4 适中；想让文本前端更快学新字可略升 0.5）
- 保存频率 save_every_epoch：**4**
- 仅保存最新权重：✅（省盘）｜同时每次保存导出到 weights 文件夹：✅
- GPU 卡号：**0**

### 8.3 GPT 参数（你截图的值）
- 每张显卡 batch_size：**11**
- 总训练轮数 total_epoch：**15**
- 保存频率 save_every_epoch：**5**
- DPO 训练（实验性）：❌ 不勾
- 仅保存最新权重：✅
- GPU 卡号：**0**

### 8.4 注意事项
1. **数据量 7646 句 ≫ 旧 1309**，每 epoch 步数约 6×，15(GPT)/8(SoVITS) 轮通常已充分；盯 GPU loss，平台期可提前停，不必硬跑满。
2. **单发音人**，无多说话人冲突；但单人也更易过拟合，留意重建/对齐 loss 是否过拟合。
3. **EOS 是本次验证重点**：训完用 `top_k=5 / temperature=0.3–0.5` 推理，对比 teochew_03 的"多读半句"是否改善（见 §4）。
4. **显存不够的兜底**：先降 batch_size，再考虑降 total_epoch；不要动 phoneme_vocab_size（代码已动态取 836，config 里写 512 会被覆盖）。
5. **词典已扩**：本次训练 g2p 走扩充后的 `字_allpinyin`（+229 字），零 UNK；若日后想回滚，用 `.bak` 还原即可。

