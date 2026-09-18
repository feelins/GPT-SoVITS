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

## 3. 阶段二：正字法 → 音素（进行中）

### 3.0 方案取舍：只剩自建规则这一条路

| 方案 | 实测结论 |
|---|---|
| A. `espeak-ng -v bo --ipa` | **不可行**。espeak-ng 官方没有藏语 voice，装了也只会按字母硬拼 |
| B. `botok` | **不可行**。是分词/词性标注库，不提供音标 |
| C. 自建拼读规则表 | 唯一可行，已实现 |

规则依据：Tournadre & Sangda Dorje, *Manual of Standard Tibetan* (1998) 拼读章节。
音素集用 IPA，声调用 4 个调值。

### 3.1 结构解析 `02_parse_syllable.py`

Wylie token **不等于**音节，先做两级处理：

```
token  "pa'i"
  │  ① 黏着语素切分
  ▼
"pa" + "'i"
  │  ② 结构解析（正字法 7 个位置）
  ▼
基字p + 元音a        基字' + 元音i
```

黏着助词 `'i 'u 'o 'e 'ang 'am 'us`、名物化 `ba/bar/bas`、数字前缀递归切分。
梵文叠字（`+`）、阿拉伯数字、英文专名单独分类，不按藏语正字法解析。

```
token 处理    pure_tibetan 77966 (99.57%) / foreign 133 / num 106 / sanskrit 94
单元级        1926 个需解析单元，成功 1926 (100.0%)
```

产出：`prepared/syllable_structure.tsv`、`prepared/token_split.tsv`

修复过的两个真实缺陷：`grwa` 误判为「前g+基r+下w」（应为「基g+下rw」）、
`rlung` 误判为「基r+下l」（应为「上r+基l」）。修正后上加字 `s` 识别量从 4200 涨到 5766。

### 3.2 发音规则 `04_wylie_to_phoneme.py`

三层规则，把握程度不同：

| 层 | 内容 | 把握 |
|---|---|---|
| 声母清化 | 浊塞音 `g j d b dz` 有前缀→清不送气；无前缀→清送气 | 稳 |
| 声调 | 清基字或有**带声**前缀→高；浊基字无前缀→低；促声尾使平调变降 | 稳 |
| 下加字 | `y` 腭化 / `r` 卷舌化 / `l` 边音化 | 音值待验 |
| 元音变音 | `a/o/u + {r,l}` → `ɛ/ø/y` | 触发集待验 |

**例外（已修）**：前加字 `འ`（a-chung）是不带声前缀，只把基字清化为不送气，
**不抬高声调**：

```
འདི 'di /tì/     འདུག 'dug /tùʔ/     འགྲོ 'gro /ʈʂò/     འབྲེལ 'brel /ʈʂèː/
```

原先一律按高调处理，`'di`（702 次）、`'dug`（411 次）这类超高频词全错，已修正。
修正后高/低调分布从 43832/37755 变为 40554/41033，趋于平衡。

产出：`prepared/phoneme_draft.tsv`、`phoneme_samples.txt`、`phoneme_todo.tsv`

### 3.3 句级转写 `05_build_transcript.py`

串联 02 + 04，对全语料逐句转写。**音节之间空格，与 Wylie 空格结构一一对应**：

```
gangs rin po che nas rgyal khams 'grim
kʰã12 rĩ13 po55 tɕʰe55 na12 tɕɛ55 kʰã53 ʈʂĩ13
```

非藏语成分保留为 `⟨foreign:xxx⟩` / `⟨num:1959⟩` 标记，不丢弃也不假装能转音素。

产出：
- `prepared/phoneme_transcript.tsv` — 5878 句的完整转写
- `音素索引.list` — `路径|Wylie|IPA` 三列，单文件可直接核对

```
句子      5878（含非藏语成分 389 = 6.6%，含未解析单元 0）
藏语音节  81587
```

### 3.4 决策记录（2026-09）

| 项 | 决定 | 理由 |
|---|---|---|
| 音素形式 | IPA 保留用于人工核对，另产 ASCII 映射串供训练 | 见 §4；IPA 留在 `音素索引_v2.list` 第 3 列 |
| 声调 | 保留 4 个调值 55/53/13/12 | 信息完整，符合拉萨话实际 |
| 元音变音缺口 | **暂不实现** | 触发集不完整，贸然补会引入新错误 |
| 准确性验证 | 先接受草案，靠训练效果倒推 | 优先打通链路 |

### 3.5 已知缺口（待文献核实）

登记在 `prepared/phoneme_todo.tsv`，**389 种 / 13770 次 / 占藏语音节 16.9%**。
当前这些音节用的是未修正的读音：

| 组合 | 疑似音值 | 证据 |
|---|---|---|
| `a + {s,d,b,g}` | ɛ | པས/pɛː/ ལས/lɛː/ ནས/nɛː/ མཁས/kʰɛː/ |
| `o + {s,d,b,g}` | ø | བོད/pʰøː/ དགོས/køː/ |

高频受影响词：`yod`(1336) `nas`(1168) `gnas`(524) `bod`(489) `byas`(399) `thog`(389)。

另外两处未决：`n/m/ng` 前是否也发生同样的变音；`ལྷ` 类（上加字 l + 基字 h）
实际读 /ɬ/ 还是 /h/。

### 3.6 下一步

音素链路已打通，后续是：

1. 音素表定稿 → 映射到 GPT-SoVITS `symbols2.py`（扩展符号集）
2. 切片、切分训练集
3. 配置训练

缺口规则可在拿到文献后随时补，不影响链路先行跑通。

---

## 4. 阶段三：音素 → 符号表映射（已完成）

### 4.1 为什么不能直接喂 IPA

`音素索引.list` 里的 IPA 是**音节级连写**（`hĩ55`），喂模型前要切成 symbol。

**第一，连写串切不出边界。** `ʈʂʰa53` 里 `ʈʂʰ` 是一个声母，按字符切会变成
`ʈ`+`ʂ`+`ʰ` 三个假音素，送气符 `ʰ` 被当成能独立发音的单位。

边界信息**不存在于字符串里** —— `04` 内部本来就是分三步算的（声母/韵母/声调），
只是最后才拼成串：

```python
on, n1 = onset_ipa(pre, sup, base, sub)
vo, n2 = vowel_ipa(vowel, suf, suf2)
tone, n3 = tone_of(pre, sup, base, suf, suf2)
return f"{on}{vo}{tone}", ...
```

所以正确做法不是反推字符串，而是新增 `syllable_parts()` 直接返回三元组
（不改动 `syllable_to_phoneme()` 的原有行为）。

**第二，符号表是 ASCII。** `symbols2.py` 里中文/日文/粤语全是 ASCII 代号，
IPA 字符（ʈ ʂ ɕ ʑ ŋ ɲ ɳ ɛ ø…）混进去会让 tokenizer 与 `word2ph` 对齐出问题。

### 4.2 关键数字：46 个音素单元，不是 38 个 Unicode 字符

一开始按「符号集 38 个」理解，那是**字符数**，不是音素单元数：

| 口径 | 数量 | 说明 |
|---|---|---|
| Unicode 字符 | 38 | `ʈ` `ʂ` `ʰ` 各算 1 个 |
| **音素单元** | **46** | `ʈʂʰ` 整体算 1 个声母 |

按字符映射会把 `kʰ` 拆成 `k`+`ʰ`、`ʈʂʰ` 拆成三个字符，属于丢信息。
映射对象因此是**音素单元**：

```
声母 29（含零声母 ''）+ 韵母 13 + 声调 4 = 46
```

韵母是 13 不是 16，因为 `ɛ̃ ø̃ ỹ` 与 `ɛ ø y` 互斥（变音与鼻化不同现）。

### 4.3 映射规则

| 特征 | 记法 | 例 |
|---|---|---|
| 送气 | 后缀 `h` | `pʰ`→`Tph`、`kʰ`→`Tkh`、`ʈʂʰ`→`Ttrh` |
| 卷舌 | 后缀 `r` | `ʈʂ`→`Ttr`、`ʂ`→`Tsr`、`ɳ`→`Tnr` |
| 腭化 | 单字母 | `tɕ`→`Tc`、`tɕʰ`→`Tch`、`ɕ`→`Tx`、`ʑ`→`Tzh`、`ɲ`→`Tny` |
| 鼻化元音 | 大写 | `ã`→`TA`、`ĩ`→`TI`、`õ`→`TO`、`ẽ`→`TE`、`ũ`→`TU` |
| r/l 变音 | 二合字母 | `ɛ`→`Tae`、`ø`→`Toe`、`y`→`Tue` |
| 声调 | 调值原样 | 55 / 53 / 13 / 12 |
| 喉塞 | `Tq` | `ʔ`→`Tq` |

统一加 **`T` 前缀**，原因与粤语加 `Y` 相同：`symbols` 是全局符号表，
中/日/英/韩/粤符号都在里面，藏语裸写 `p` `t` `a` 会重名。

### 4.4 体系选择：韵母+声调粘成一个 symbol

```
hĩ55  ->  Th-TI55     2 个 symbol（声母 / 韵母带调）
a55   ->  Ta55        1 个 symbol（零声母）
```

不是 `Th-TI-55`（声调独立成第三段）。理由：

- 普通话 `zh`+`ang1`、粤语 `Yl`+`Yiu4` 都是**两段**，声调粘在韵母上
- `1-get-text.py` 的对齐约束 `assert len(word2ph) == len(text)` 与
  `assert bert_feature.shape[-1] == len(phones)` 是按这个结构设计的
- 声调独立成 symbol 要自己改对齐逻辑，收益不明

零声母退化成 1 段，与普通话零声母音节处理一致。

### 4.5 实现与产出

`04` 新增 `syllable_parts()`；`05` 新增 `--emit-mapped`。

```bash
python 05_build_transcript.py --drop-flags foreign,num,sanskrit --emit-mapped
```

| 文件 | 内容 |
|---|---|
| `音素索引_v2.list` | `路径\|Wylie\|IPA\|映射串` 四列，5489 行 |
| `音素映射表.tsv` | `kind / ipa / ascii / count / note`，46 行 |

样例：

```
kʰã12 rĩ13 po55 tɕʰe55 na12 tɕɛ55 kʰã53 ʈʂĩ13
  ↓
Tkh-TA12 Tr-TI13 Tp-To55 Tch-Te55 Tn-Ta12 Tc-Tae55 Tkh-TA53 Ttr-TI13
```

**分隔符**：文件里用 `-` 是为可视化、便于核对音节边界；`-` 不是 GPT-SoVITS 的
分隔符，送进训练前必须换成空格：

```
Th-TI55 Tz-Ta53 Tk-Tu55     # 核对用
Th TI55 Tz Ta53 Tk Tu55     # 训练用
```

脚本自带双射自检（韵母×声调组合无碰撞），反查表可由映射表直接生成。

### 4.6 symbols2.py 改动

在 `GPT_SoVITS/text/symbols2.py` 追加，位置在粤语之后：

```python
tibetan_c = [...]                        # 声母 28
tibetan_v_wo_tone = [...]                # 韵母 13
tibetan_tone = ["55", "53", "13", "12"]  # 声调 4
tibetan_symbols = tibetan_c + ["T%s%s" % (v, t) for v in ... for t in ...]
symbols += tibetan_symbols
```

| 项 | 值 |
|---|---|
| 符号表 | 732 → **812** |
| 藏语符号 | **80**（28 声母 + 13 韵母 × 4 声调） |
| 语料实际出现 | 74（`ɛ ø y` 的 12、53 调组合未出现） |
| 与已有符号重名 | 无（`T` 开头与中/日/英/韩/粤均不冲突） |

按**规则加满 80**而非只加出现的 74，避免后续语料出现未见组合时 OOV。

**顺序**：整体追加在末尾（`sorted(set(...))` 之后），不打乱已有符号索引 ——
符号索引决定 embedding 行号，改动顺序会让已有 checkpoint 错位。

### 4.7 对加载中文底模的影响

`GPT_SoVITS/utils.py` 的 `load_checkpoint()` 在 shape 不匹配时会打印 error 并
**保留新模型的随机初始化权重**，不会崩：

```41:48:GPT_SoVITS/utils.py
            assert saved_state_dict[k].shape == v.shape, (
                saved_state_dict[k].shape,
                v.shape,
            )
        except:
            traceback.print_exc()
            print("error, %s is not in the checkpoint" % k)  # shape不对也会
            new_state_dict[k] = v
```

- `enc_p.text_embedding` / `ar_text_embedding` 尺寸变了 → 随机重建
- 其余层（encoder / flow / decoder / quantizer）正常继承底模

**结论**：可以从中文底模微调。中文发音能力会丢（藏语本就没有预训练 embedding），
但声学部分仍然受益。

### 4.8 下一步

1. **切片 + 划分**：按 `音素索引_v2.list` 切音频、切 train/val
2. **生成训练三件套**（`1-get-text.py` 格式：`name\tphones\tword2ph\tnorm_text`）
   - `phones`：映射串把 `-` 换成空格
   - `word2ph`：每个 Wylie 音节对应 1~2 个 phone（零声母 1，有声母 2），
     满足 `len(word2ph) == 音节数` 且 `sum(word2ph) == len(phones)`
   - **待确认**：`1-get-text.py` 里只有 `lan == "zh"` 才调 `get_bert_feature()`
     生成 bert 文件，藏语走非 zh 分支时 bert 文件不产生，需确认训练端是填零
     还是需要占位文件
3. 配置训练
