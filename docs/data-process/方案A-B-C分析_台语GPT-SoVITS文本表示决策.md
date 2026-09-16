# 台语 GPT-SoVITS 训练：文本表示方案 A / B / C 分析与决策

> 整理日期：2026-07-29
> 数据：`E:\008-datasets\mcv-scripted-nan-tw-v23.0\cv-corpus-23.0-2025-09-05\nan-tw`
> 选定说话人：`7f33d4489734`（validated 1317 条，nan_tw_01）
> 底座：GPT-SoVITS v2pro，使用粤语 `yue` 模式（原生支持 jyutping）
> 关联文档：`台语数据_GPT-SoVITS训练方案与底座分析.md`、`GPT-SoVITS与Coqui-XTTS对比.md`、`配置推理环境虚拟环境.md`

---

## 0. 一句话背景

nan-tw 数据自带的 `sentence` 字段里，**括号内的就是台罗拼音（Tâi-lô）**，例如
`愛共兩台機器留一寡仔遊び（Ài kā nn̄g-tâi ki-khì lâu tsi̍t-kuá-á a-sóo-bih）`。

GPT-SoVITS 训练清单（四段式）第 4 字段"给什么文本"，决定了底座前端怎么把文字变成音素。由此产生 A/B/C 三种方案。

**关键事实（来自本项目 `text/cantonese.py` 第 180 行）**：yue 底座前端吃的是**汉字**，粤拼由内部 `ToJyutping.get_jyutping_list(text)` 现转。所以：
- 喂汉字 → 走 yue 后端 → 内部自动转粤拼 → 合法符号。
- 喂粤拼 → 需旁路 `ToJyutping`，直接喂粤拼符号 → 仍合法。
- 喂台罗 → 符号不在词表 / 声调格式不符 → 崩溃或 UNK。

---

## 1. 三种方案定义

| 方案 | 第 4 字段内容 | 底座 / 前端 | 符号是否合法 | BERT 语义特征 |
|---|---|---|---|---|
| **A. 汉字** | 汉字（去掉台罗括号） | `yue`（内部 `ToJyutping` 转粤拼） | ✅ 全部合法 | ✅ 中文 BERT 正常 |
| **B. 粤拼** | 台罗 → 粤拼映射结果 | `yue`（旁路 `ToJyutping`，直喂粤拼） | ✅ 全部合法 | ⚠️ 拉丁字母喂中文 BERT，语义退化 |
| **C. 台罗** | 台罗拼音原文 | `yue`（直喂台罗） | ❌ 崩溃 / UNK | ❌ 不可用 |

> 实现状态：方案 A 的 `train.list`（汉字版）**已生成**，位置见 §6。
> 方案 B 的 `train_jyutping.list`（粤拼版）也已生成，待需要时切换。
> 方案 C 不实现（理由见 §2）。

---

## 2. 核心机制：底座不认"字母组合"——为什么 C 不行

用户的疑问："拼音无非是字母组合，能不能借用底座模型的表征？"
**答案：不能。** 因为 GPT-SoVITS 的文本编码器是**离散符号查表（embedding lookup）**，不是字母级语义编码。

证据（`text/cantonese.py`）：

```161:173:E:\003_ProgramLanguage\GPT-SoVITS\GPT_SoVITS\text\cantonese.py
###魔改为辅音+带音调的元音
phones = []
for a, b in zip(initials_finals, tones):
    if b not in [-1, 0]:
        todo = "%s%s" % (a, b)
    else:
        todo = a
    if todo not in punctuation_set:
        todo = "Y%s" % todo
    phones.append(todo)
```

最终喂进模型的是 `Yg3`、`Yong2`、`Yaa1` 这种**整体符号**。底座 embedding 矩阵的每一行对应一个**完整符号**——`Yk` 和 `Ya` 是两行，彼此**没有"字母共享"**可言。

再看声调与格式的硬约束：

```134:134:E:\003_ProgramLanguage\GPT-SoVITS\GPT_SoVITS\text\cantonese.py
tone = int(syllable[-1])
```
```190:190:E:\003_ProgramLanguage\GPT-SoVITS\GPT_SoVITS\text\cantonese.py
if not re.search(r"^([a-z]+[1-6]+[ ]?)+$", syllable):
    raise ValueError(f"Failed to convert {word} to jyutping: {syllable}")
```

台罗（如 `kā`、`nn̄g-tâi`、`tsi̍t-kuá-á`）的问题：
1. **声调写在字母上的变音符号**（á à ǎ â、鼻化 ⁿ、连字符上的长音 ¯）—— 非 ASCII、且**没有末尾数字** → 第 190 行正则不匹配 → `raise ValueError` 直接崩溃，走不到训练。
2. 即便绕过 `g2p` 硬喂，台罗符号**根本不在 yue 音素表**里 → 变成 `UNK` → 没有预训练向量可用。
3. "字母组合"的直觉不成立：模型不按字母拼，而按整体符号查表。台罗里 `k` 和粤拼里 `k` 是不同上下文、不同符号，不存在跨语言共享。

**结论**：方案 C 无法借用文本侧表征。唯一能"借用"的是**声学骨架**（mel 编码器 / 解码器 / 声码器，语言无关，照常迁移），但"文本→音素"那段是废的。若要让 C 工作，只能**扩符号表**——而扩出来的新符号是随机初始化、无预训练知识，等于把文本侧从零训，失去"借底座"的意义。

---

## 3. 声调风险（用户提出：中在台罗是降调、粤拼给升调，相反了）

这是方案 A 最被担心的一点，但在**单人微调**里影响很小：

- 模型学到的不是"标签必须等于真实调"，而是"**看到某标签序列 → 输出该说话人的实际音高**"。
- 训练数据里，所有"中"的标签**恒为同一值**（如粤拼 `zung1`）、音频**恒为台语降调**；模型会自洽地把这个标签映射到这个音高。
- 音高由**音频波形**决定，文本标签只是条件输入，模型从数据里学对应关系并自行纠错。

所以方案 A 的声调"数字不准"在实践中被单说话人训练消化掉。真正的声调坑出现在**多说话人 / 跨说话人**场景（标签冲突），本任务不涉及。

---

## 4. 各方案权衡小结

- **方案 A（汉字）**：零风险、BERT 正常、单说话人自纠声调。**已生成 `train.list`，可直接开训。**
- **方案 B（粤拼）**：符号全合法，且**声调数字由你控制**（可把台罗降调映射到粤拼调型相近的数字），更贴近台语真实调型。需做 `g2p` 旁路（跳过 `ToJyutping` 的 2 行改动）。代价：拉丁字母喂给中文 BERT，语义特征退化（BERT 是辅助特征，影响有限但非零）。
- **方案 C（台罗）**：不推荐（见 §2）。

---

## 5. 决策与后续

1. **先用方案 A 跑通**管线 + 锁定音色（已就绪）。
2. 若跑出来**整体音高 / 语气明显不对**（该降的升了、该短的拖了），再切 **方案 B**：
   - 旁路 `g2p`（让 yue 后端直吃粤拼，跳过 `ToJyutping`）；
   - 用已写好的台罗→粤拼映射，把声调数字调到贴近台语调型；
   - 切换 `single_speaker/train_jyutping.list` 为训练清单。
3. 方案 C 不做。

---

## 6. 产物与脚本位置

数据目录 `...\nan-tw\` 下：
- 训练清单（方案 A，汉字版）：`single_speaker/train.list` ✅（198 KB，已核验无括号残留）
- 训练清单（方案 B，粤拼版）：`single_speaker/train_jyutping.list`
- 可读校对版：`single_speaker/metadata_full.csv`（汉字 + 粤拼 + 台罗 + 原文）
- 音节对照表（方案 B 用）：`single_speaker/syllable_map.tsv`
- 处理脚本：`extract_single_speaker.py`、`build_metadata.py`、`tailo2jyutping.py`

源数据（Common Voice）：`E:\008-datasets\mcv-scripted-nan-tw-v23.0\cv-corpus-23.0-2025-09-05\nan-tw`
