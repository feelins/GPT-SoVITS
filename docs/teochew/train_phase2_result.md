# 第二阶段训练：成果总结与后续扩展路线

> 日期：2026-09-14
> 关联文档：`train_plan_phase2.md`（方案）、`train_troubleshoot.md`（排障）、`code.md`（代码改动）

---

## 1. 今天完成的事（按时间线）

| 步骤 | 动作 | 结果 |
|------|------|------|
| 1 | 理清新数据 6388 wav 与 prosody 文本编号映射 | 规则：音频前5位 == prosody 编号后5位，2378/2378 全命中 |
| 2 | 确认训练格式 | train.list 第4列放**汉字**，模型学音素（g2p 实时转），与旧 04_ChaoShan 同口径 |
| 3 | **扩充潮汕词典**（关键） | 发现新数据罗马字拼法（iaa/ainn/dz…）≠ 旧词表（iao/ian/z…），建「新→旧」单元映射表，从 prosody 提取 2798 字发音，追加 **+229 字 +34 音节** 进 `字_allpinyin_20180312.txt` 与 `allpinyin_with_shengyun.txt`（原件 `.bak` 备份） |
| 4 | 生成合并 train.list | `train_full.list` = 旧 1309 + 新 6388 = **7697 行** |
| 5 | UNK 校验 → 删除异常句 | 整体 UNK 率 **89.6% → 0.66%**；`--drop-unk` 删除 51 句，最终 **7646 行，零 UNK**（被删句备份于 `train_full.list.with_unk.bak`） |
| 6 | 训练 teochew_04（从官方底模重训） | SoVITS 8 epoch / GPT 15 epoch，batch 11，单卡 GPU 0 |
| 7 | **合成听感验证** | 比 1300 句时稳定很多、效果更好 → **数据量是决定性因素，假设成立** |

---

## 2. 核心结论

- **数据量主因**：1309 句 → 7646 句（约 6×），合成稳定性与音质明显提升，证明此前"多读半句/EOS 不准"主要是**数据不足 + 词典覆盖不全**导致，而非推理逻辑 bug。
- **词典扩充是必须的**：新数据 89.6% 句子含 OOV 字，若不扩词典直接训，数百个方言字坍缩成同一个 `UNK` token，会污染文本→音素对齐。扩词典后降到 0 UNK 是效果提升的另一半原因。
- **框架零改动**：GPT_SoVITS 代码（s1/s2_train、cleaner、teochew）一行未改；词表固定 836，不触发 embedding 扩维，之前的 resize 修复依然有效。

---

## 3. 后续扩展路线

### 3.1 继续加更多潮汕话音频（同逻辑）
流程与本次完全一致，重复即可：
1. 新音频 + 对应汉字/韵律文本 → 解析编号映射（每批编号规则可能不同，需先验证对齐，参考本次"前5位==prosody后5位"的核对方法）。
2. **务必注意词典收录**：新来源若用不同罗马字体系，先跑 `gen_mapping_candidates.py` 重新生成 `mapping_auto.txt` / `mapping_ambiguous.txt` 做人工核对，再扩词典。
3. 重新跑 `build_full_dataset.py --drop-unk` 合并生成新的 `train_full.list`。
4. 从底模（或 teochew_04 检查点）继续训新实验（如 teochew_05）。

> 提示：音频与文本编号的对齐是每批新数据的第一道关，必须先验证命中率再合并，避免音素配错音频。

### 3.2 增加几个发音人（多说话人）
这是下一步**质变**的方向，但有几条铁律：

1. **train.list 第2列 speaker 必须区分**：目前全是 `chao_shan_01`。新增发音人时，每人的句子该列填不同 ID（如 `chao_shan_02`、`chao_shan_03`），GPT-SoVITS 据此学多说话人音色。
2. **音素词表不变**：不同发音人共享同一套潮汕音素（836），无需改 `symbols2`；只需各自音频 + 同一 g2p 体系。
3. **词典/音素体系要统一**：所有发音人的文本必须走**同一套** `teochew.g2p` + 同一扩充词典。若新发音人带来新方言字，继续用 §3.1 的扩词典流程。
4. **数据均衡**：多说话人时尽量各人句数均衡，避免某一人主导导致其他人音色学偏。
5. **预期收益**：多发音人能提升模型对音色/韵律的泛化，推理时可通过参考音频灵活切换说话人；但单人数据已证明稳定性主要靠量，多加人主要是**音色多样性 + 鲁棒性**，不是解决 EOS 的必需。

### 3.3 风险提示
- **不要混用不同 romanization 不映射直接合并**：那会重新引入 UNK / 无效音素。每批新数据都要先过映射 + 词典收录。
- **多说话人勿共用 speaker ID**：否则音色互相污染。
- **词典回滚**：若扩词典出错，用 `字_allpinyin_20180312.txt.bak` / `allpinyin_with_shengyun.txt.bak` 还原。

---

## 4. 关键产物清单
- `data/new_chaoshan/train_full.list` —— 7646 行零 UNK 全量训练集
- `data/new_chaoshan/train_full.list.with_unk.bak` —— 被删的 51 句
- `data/new_chaoshan/build_full_dataset.py` —— 一步产出脚本（扩词典+合并+校验）
- `data/new_chaoshan/gen_mapping_candidates.py` —— 新→旧映射候选生成
- `data/new_chaoshan/mapping_auto.txt` / `mapping_ambiguous.txt` —— 映射核对表
- `data/04_ChaoShan/字_allpinyin_20180312.txt(.bak)` —— 已扩充的汉字词典
- `data/04_ChaoShan/allpinyin_with_shengyun.txt(.bak)` —— 已扩充的音节拆分表
- 实验模型：`teochew_04`（训练参数见 `train_plan_phase2.md` §8）
