# 藏语（Tibetan）语料处理

本目录只保存**处理脚本与文档**。语料音频与中间产物一律留在数据盘，不进仓库。

```
仓库    E:\003_ProgramLanguage\GPT-SoVITS\docs\tibetan\   脚本 + 文档（入库）
数据    E:\008-datasets\藏语-疑问\                       音频 + 原始标注（不入库）
产物    E:\008-datasets\藏语-疑问\prepared\              标注表 + 音节表（不入库）
```

---

## 1. 语料概况

单一说话人（SP02）朗读语料，分 9 个章节段（`SP02-OTR002-<段>-<A|B>-<序号>.wav`）。

| 项 | 值 |
|---|---|
| 句数 | 5878（train 4702 / valid 588 / test 588，原始划分已随机交错） |
| 总时长 | 6.43 小时 |
| 音频 | 16 kHz / 单声道 / 16 bit wav，5923 个文件，0 损坏 |
| 时长范围 | 0.52s ~ 9.93s（中位 3.70s） |
| 标注 | 藏文 Unicode + Wylie 拉丁转写，二者严格一一对应 |

### Wylie 是正字法，不是音标

这是藏语实验的核心难点。Wylie 保留古藏语拼写，大量字母在现代拉萨话里已不发音：

```
bsgyur   →  /ɟyː/      b、s 不发音
blon     →  /lø̃/       b 不发音
phyi     →  /tɕʰi/
mtsho    →  /tsʰo/
'brel    →  /ɖʐɛː/
khas len →  /kʰɛ lɛ̃/
```

因此不能直接把 Wylie 当音素序列喂给模型，必须先做一层**正字法 → 读音**转换。

---

## 2. 阶段一：基础整合（已完成）

脚本：`01_build_annotations.py`

```bash
python 01_build_annotations.py
python 01_build_annotations.py --data-root E:\008-datasets\藏语-疑问
$env:TIBETAN_DATA_ROOT='E:\008-datasets\藏语-疑问'; python 01_build_annotations.py
```

### 做了什么

- 合并 6 个 tsv（train/valid/test × uni/wylie），按音频文件名对齐
- 归一化 Wylie：引号两侧补空格，修复 `'dug”ces` 这类黏连；**保留** `'`(a-chung) 与 `+`(梵文叠字)
- 读取 wav 头获取时长、采样率（不解码音频，秒级完成）
- 统计藏文侧与 Wylie 侧音节数是否一致
- 标记噪声但不静默丢弃

### 产物

| 文件 | 内容 |
|---|---|
| `prepared/annotations.tsv` | 5878 条合并标注 |
| `prepared/vocab_syllable.tsv` | 2279 个唯一音节及频次 |

`annotations.tsv` 字段：

```
idx  split  audio  duration  sample_rate
n_syl_uni  n_syl_wylie  sync_ok  flags
uni_text  wylie_norm  wylie_raw
```

- `split` 仅用于追溯来源，**本阶段不生成 train/val 切分**
- `sync_ok` = 藏文音节数与 Wylie 音节数是否相等
- `flags` 噪声标记：`digit`（含数字）、`cjk`（含中文字符）、`stack`（含梵文叠字 `+`）

### 输出基线

```
可整合记录            5878
总时长                385.6 分钟 (6.43 小时)
时长 P5/中位/P95      1.64s / 3.70s / 6.97s
音节数一致            5839/5878  (99.3%)
噪声    digit 93 / stack 86 / digit|stack 4 / cjk 2 → 干净 5693 (96.9%)
唯一音节              2279   总 token 78299
覆盖率  前 100 = 53.5%  前 500 = 86.7%  前 1000 = 96.2%  前 2000 = 99.6%
```

说明：磁盘上有 45 个 wav 无对应转写（含 2 个短音频、6 个超长音频），已自动排除，
因此总时长 6.43h 略低于扫描全部 5923 个文件时的 6.57h。

---

## 3. 下一步（阶段二，未开始）

建 **Wylie 音节 → 音素** 映射表。2279 个唯一音节，前 1000 个覆盖 96.2%，
与中文字表（2455 字）同一量级，建表工作量可控。

候选方案：

| 方案 | 做法 |
|---|---|
| A | `espeak-ng -v bo --ipa` 批量转 IPA，人工抽检高频音节 |
| B | `botok`（Python 藏文处理库） |
| C | 自建藏文拼读规则表（前缀/上缀/下缀/后加字/再后加字） |

阶段二产出后，再进入切片、切分训练集、配置训练等后续阶段。
