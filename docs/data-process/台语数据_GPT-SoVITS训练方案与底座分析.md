# 台湾闽南语（nan-tw）数据训练 GPT-SoVITS：方案与底座分析

> 数据路径：`E:\008-datasets\mcv-scripted-nan-tw-v23.0\cv-corpus-23.0-2025-09-05\nan-tw`
> 目标：① 先验证 GPT-SoVITS 管线能跑通 + 音色像目标发音人；② 后续做真正台语发音的 TTS。
> 关联文档：`配置推理环境虚拟环境.md`（GPT-SoVITS 在 autoDL 搭建）、`GPT-SoVITS与Coqui-XTTS对比.md`（四框架对比）。

---

## 1. 数据真实规模（实测）

| 项 | 数值 |
|---|---|
| `validated.tsv` 有效音频数 | **29,287 条** |
| 唯一说话人数 | **273 位** |
| 单人最多 | 7,316 条（≈5.4 小时，远超微调所需） |
| 说话人 ≥1000 条 | 7 人 |
| 说话人 ≥3000 条 | 2 人 |
| 说话人 ≥500 条 | 9 人 |
| 说话人 ≥100 条 | 38 人 |
| `clip_durations.tsv` 总条数 | 31,951 条 |
| 总时长 | **≈23.4 小时**（均值 2.64s/条，单位 ms） |
| 自带标注 | `sentence` 字段内嵌台罗拼音(Tâi-lô)；`out_txts/`+`all_tokens.txt` 已含台语音素 token |

**关键结论**：单说话人资源极其充足——挑任意一位 ≥1000 条的发音人，都有 44 分钟~5.4 小时音频，远超微调所需（推荐 ≥1~2 分钟即可）。

---

## 2. 核心认知：音色 ≠ 发音（先理清，后面不纠结）

- **音色（谁在说话）100% 来自音频波形，与文本/音素表示无关。** 你之前满语实验已证明：合成出来"音色太像"，是因为训练音频本就是那个人读的，跟映射成 `AW AI EI` 无关。
- **发音（什么口音）才由音素表示决定。** 映射到英语音素→英语腔；映射到粤拼→粤语腔；用汉字走普通话前端→普通话腔。
- 所以"选哪种文本表示"只决定**用哪种腔念台语**，不影响**音色像不像那个人**。

---

## 3. 满语案例的类比（已验证可行）

你之前在别的机器：1000 句满语，把满语拉丁表示映射成英语式发音符号（`AW AI EI`…），基于**英语底座**训练。结果：音色极像满语发音人，只是带点英语味。

这证明了一件事：**"把一个语言映射到一个音系相近语言的音素词表"这条路走得通，且音色保真度很高。** 台语方案可直接套用此思路。

---

## 4. 三种训练路线

| 路线 | 文本表示 | 所需底座 | 音色 | 发音质量 | 工作量 |
|---|---|---|---|---|---|
| **A. 汉字走中文** | 汉字（去台罗括号） | 普通话底座（v2 自带） | ✅像 | ❌普通话腔念台语 | 最小 |
| **B. 映射粤拼** | 台语音节→jyutping | 粤语模式底座（v2 自带） | ✅像 | ⚠️粤语腔念台语（比 A 轻） | 中（建对照表） |
| **C. 台语原生** | `all_tokens.txt` 台语 token | 台语感知底座（需获得/训练） | ✅像 | ✅最准 | 需台语底座 |

### 直接回答你的疑问："要不要映射成粤语？"
- **不必映射成粤语**也能跑（路线 A，用汉字走普通话底座）——音色照样像。
- 但**映射成粤语（路线 B）是更优选择**，理由：
  1. 满语→英语的成功已验证"映射相近语言音素"可行；
  2. 闽南语在音系上（保留入声 -p/-t/-k、韵腹韵尾丰富）比"丢了入声、合并韵尾"的普通话**更接近粤语**，所以映射到粤拼的"串味"比映射到普通话拼音更轻。
- 结论：**路线 B 合理且推荐用于"先验证 + 音色像"**；它不是错误方向。

### 路线 B 的三个技术注意点
1. **是"音素翻译"不是"改标签"**：`ua5`(台罗)≠`ua`(粤拼)，要查表把每个台语音节翻成听感最接近的粤拼音节。
2. **调类系统不同**：台罗 1–8 调（2/4/6/8 多为入声），粤拼 1–6 调，需按调类对应（尤其入声尾）。
3. **必须用粤语模式底座**：GPT-SoVITS v2 自带 Cantonese(jyutping) mode，喂粤拼符号才在词表内；用普通话底座喂粤拼会 OOV。

---

## 5. 关于"台语底座"的核心问题

### 5.1 是不是从零训练？
**不是。** 从零训练 SoVITS+GPT 需要数百~数千小时、大量说话人，这份 23.4 小时 / 273 人的语料远远不够。GPT-SoVITS 本质是**微调/适配框架**，不是从零造底座的工具。

### 5.2 有没有"通用语音底座"？
**有。** 你手上的 GPT-SoVITS v2 / v2pro 整合包**本身就是通用多语种底座**（已在中文、日文、英文、韩文、粤语等大量说话人上预训练），已具备：
- 通用语音表征能力（音频→隐空间）；
- 内容/音色解耦结构（SoVITS + GPT）；
- 一套固定音素词表（含普通话拼音、粤语 jyutping 等，**不含台语音节**）。

所以"底座"不用你从零造，你只需决定**怎么把台语接进这个通用底座**。

### 5.3 用这份数据库"全部"训练台语底座可行吗？
可行，但方式是**继续预训练 / 词表扩展**，不是从零：
1. 以通用多语种底座初始化；
2. 扩展其音素词表，加入台语音节（来自 `all_tokens.txt`：`uinn1 in1 ah1 ui2 aunn1 …`）；
3. 用全部 23.4 小时 / 273 人台语语料**继续训练**，让底座"认识"台语音素并学会台语声学规律；
4. 产出"台语感知底座"——之后单人微调只需喂该人数据即可。

**判定**：23.4h / 273 人 对"适配"足够，对"从零"不够。这就是现实边界。

### 5.4 训练/获得台语底座的其它方案
1. **找现成台语 GPT-SoVITS checkpoint（最快，优先）**：`all_tokens.txt` 强烈暗示它由一个特定台语 tokenizer 项目生成——找到该项目，很可能直接附带**台语底座 + tokenizer 配置**，复用即可，省去自己扩展词表与继续预训练。
2. **用其它已训台语 TTS 作底座**：存在独立的台语(Taigi/台语) TTS 项目，可作为底座或参考。
3. **通用底座 + 继续预训练**（见 5.3）。
4. **从零训练**（不推荐，数据量不足）。

---

## 6. 给你的分步路径建议

### 短期：验证管线 + 锁定音色（1~2 小时 GPU）
- 选 1 位 ≥1000 条的发音人（数据已自带，无需自己录）；
- 用**路线 B**（台语音节→粤拼 + 粤语模式底座），或**路线 A**（汉字 + 普通话底座）先跑通；
- `mp3`→`wav`（32k 单声道），过滤时长 3–12s、up_votes 高的干净句；
- 训练清单：`wav路径|说话人名|文本`；WebUI 预处理时**关 ASR**（已有文本）；
- 目标只是"能跑、音色像"，发音带点粤/普通话腔可接受。

### 长期：真正台语发音
- 优先**找现成台语底座**（顺着 `all_tokens.txt` 的 tokenizer 线索）；
- 或拿通用底座 + 全部 23.4h 台语语料做**继续预训练**，得到台语感知底座；
- 之后单人微调即可得到"音色像 + 真台语发音"的模型。

---

## 7. 一个易踩的坑（数据侧）
- `out_txts/` 文件名（`30885968` 类）与 `validated.tsv` 的 `path`（`41569747` 类）**对不上**，说明两者不是按文件名直连，需确认 join key（如 `sentence_id` 或另一套 clip id），否则台语音素 token 接不到对应音频。路线 A/B 不依赖此对接，可暂缓。

---

## 8. 训练台语"二级底座"（语言适配底座）详细方案

> 本节回应：能否在 GPT-SoVITS 框架下，用现有**多人的**台语数据先训一个"二级底座"，再在其上做单人微调，以摆脱粤语/普通话底座的声学底色？

### 8.1 为什么"二级底座"是正解

- 路线 A（汉字+普通话底座）、路线 B（台罗→粤拼+粤语底座）的共同局限：**合成始终由现成底座的声学模型完成**，粤/普的声道建模与韵律先验去不掉 → 串味（你已实测：选粤语底座，汉字被按粤语念，出来一股粤语味）。
- "二级底座"= **在通用多语种底座上做"继续预训练 / 语言适配"**：保留通用语音表征（音频→隐空间、音色-内容解耦结构），只把"拼音先验 + 声学规律"往台语挪。
- 它不是从零造底座（那需数百~数千小时），而是**适配**——这正是 GPT-SoVITS 这类微调框架的定位。

### 8.2 数据规模评估（针对"适配"而非"从零"）

| 维度 | 你的资源 | 是否够（适配用途） |
|---|---|---|
| 总时长 | 23.4h | ✅ 足够 |
| 说话人数 | 273 人 | ✅ 多样性好（底座需要说话人无关规律） |
| 单人均值 | ~5 min | ⚠️ 偏薄，但底座不要求单人说好，只要求跨人学音系 |
| 目标单人微调数据 | ≥1000 条（最多 5.4h） | ✅ 远超微调所需（1~2h 即可） |

**结论**：23.4h / 273 人对"从零造底座"❌ 不够，但对"在通用底座上适配出台语感知底座"✅ 足够。多人数据的稀疏反而是底座的**优势**（学到说话人无关的台语音系），不是缺点。

### 8.3 两段式流程（推荐）

**阶段一：训二级底座（多说话人、说话人无关）**
1. 以 GPT-SoVITS v2 通用多语种底座（`GPT_SoVITS/base/s1bert25hz-*.pth`、`s2G488k.pth`）初始化；
2. 用**全部 23.4h / 273 人**台语数据做 SoVITS + GPT 继续预训练；
3. 文本侧喂**台语音素 token**（见 8.4，用 CharsiuG2P 的 `nan` G2P 产出 IPA 序列）；
4. 产出 `s2G-台语.ckpt` + `s1-台语.ckpt`（台语感知底座）。

**阶段二：单人微调（说话人相关）**
1. 取目标发音人（≥1000 条，最多 5.4h）；
2. 以阶段一底座为初始化，微调 SoVITS（音色来自此步音频）+ GPT；
3. 得到"音色像目标人 + 真台语发音"的最终模型。

> 这样**音色**由阶段二音频保证（已验证保真度高），**发音**由阶段一台语底座保证（解决粤语味）。两头都解决。

### 8.4 关键瓶颈：台语 G2P / tokenizer —— 与 CharsiuG2P 的关系

训练原生台语底座，文本侧必须喂**台语音素**（不能喂粤拼/拼音，否则又回到路线 A/B）。这里涉及两个容易混为一谈的概念：

- **G2P（grapheme→phoneme）**：把文字（汉字/台罗）转成音素序列。这是"语言学前端"。
- **GPT-SoVITS 的 tokenizer / vocab**：把音素符号映射成整数 token，供 GPT/SoVITS 神经网络消费。可在 `config.json` 的 `symbols` 里自定义一套音素表。

二者**角色等同但产物不同**：G2P 给"音素序列"，tokenizer 把它变成"模型能吃的整数 ID"。

**CharsiuG2P 恰好能当这个台语 G2P 前端**（本地已存在：`E:\003_ProgramLanguage\CharsiuG2P-main`）：
- `lang_list.txt` 含 `nan`（ISO 639-3 的闽南语/台语代码），`dicts/nan.tsv`（1.43MB）是现成的汉字→IPA 发音词典；
- 预训练 ByT5 多语模型原生支持 `nan`（`<nan>: 詞` 前缀即可推理）；
- `src/train.py` 支持在 `nan` 上**微调/训练**自己的 G2P。

**与 `all_tokens.txt` 的差异（重要）**：
- `all_tokens.txt` 用的是某个特定台语 TTS 项目的**自定义 token 词表**（如 `uinn1 in1 ah1`），与 CharsiuG2P 的 **IPA** 表示不是同一套符号。
- 因此两条路二选一：
  - **路线 C1（找原 tokenizer）**：复用 `all_tokens.txt` 背后的项目（最可能直接附带现成台语底座+配置），token 完全对齐；
  - **路线 C2（用 CharsiuG2P 当 G2P）**：用 `nan` G2P 把台语汉字→IPA 音素序列，再把 GPT-SoVITS 的自定义音素表定义为 CharsiuG2P 产出的 IPA 符号集。**这是一条自包含、可立即落地的路**，不依赖找到神秘项目。

**推荐（Phase 2 升级项）**：先用 CharsiuG2P 的 `nan` 预训练 G2P（或在其上用你数据的 `sentence` 台罗做微调）生成 IPA 音素序列，作为台语底座训练文本。这样底座吃的是**原生台语音素**，腔调才真。

> ⚠️ 但 Phase 1（当前立即执行）**不引入 CharsiuG2P**：直接用现有数据 + 路线 B 的粤拼 token 先把二级底座训起来（见第 10 节）。CharsiuG2P 留到 Phase 2 升级发音时再接入。理由：不同记音法（台罗 / IPA / 自定义 token）核心音系相同、可互转，而 Phase 1 推理仅用集合内句子（文本已在 `train_jyutping.list` 中），无需外部 G2P 前端。

> 注意：CharsiuG2P 的 `nan` 输出带调值上标（如 `lan²⁴`、`tʰuã⁵³⁻⁴⁴t͡sʰaʊ⁵³`），台语声调是音位的，需把调值符号保留为独立 token（或归一化为调类 1–8），纳入音素表。

### 8.5 台语底座训练清单与命令（大纲）

```text
# 1) 用 CharsiuG2P 的 nan G2P 把训练文本的汉字转 IPA 音素
python E:\003_ProgramLanguage\CharsiuG2P-main\src\g2p.py --lang nan \
       --input train_chars.txt --output train_phones.txt

# 2) 组装底座训练清单 (多说话人)
#    格式: wav绝对路径|说话人id|language|nan|IPA音素序列
#    language 字段固定填 nan（需在 GPT-SoVITS 自定义语言里登记）

# 3) SoVITS 继续预训练（以通用底座初始化, symbols=IPA音素集）
python GPT_SoVITS/s2_train.py --config configs/s2_nan.json

# 4) GPT 继续预训练
python GPT_SoVITS/s1_train.py --config configs/s1_nan.json

# 5) 阶段二：取目标说话人, 以底座初始化做单人微调（同现有微调流程）
```

> 命令为大纲，实际需对齐你 autoDL 整合包的 `s1/s2` 训练脚本路径与 `config.json`（自定义 `symbols` / 自定义语言登记）。

### 8.6 预期与风险

- ✅ 二级底座能显著削弱粤/普串味，使阶段二微调产物的发音接近原生台语；
- ⚠️ 23.4h 偏少，底座可能偶有音质不稳/个别音素 OOV，靠阶段二足量单人数据（5.4h）补偿；
- ⚠️ IPA 音素表需与 CharsiuG2P 输出严格对齐，否则训练报 OOV；
- ✅ 即便底座不完美，"二级底座 + 单人微调"仍明显优于直接在粤/普底座上微调。

### 8.7 与路线 A/B 的总对照

| 路线 | 文本表示 | 底座 | 发音 | 是否还需训底座 |
|---|---|---|---|---|
| A 汉字+中文 | 汉字 | 普通话底座 | 普通话腔 | 否（直接用） |
| B 台罗→粤拼 | 粤拼 | 粤语底座 | 粤语腔（较轻） | 否（直接用） |
| C2 台语 G2P | IPA（CharsiuG2P nan） | **台语二级底座（需训）** | ✅ 近原生台语 | **是（Phase 2）** |

---

## 9. 实测结论纪要（2026-07-30 验证）

> 以下为实际跑通后确认的结论，作为后续方案的判断依据。

1. **实测（已验证）**：汉字输入 + 选**粤语底座** + 粤语参考音频 + 粤语推理目标 → 合成音频带**浓粤语味**。
   - 印证第 2 / 4 节核心论点：**发音腔调由"底座/音素表示"决定，与输入文本（汉字）无关**；汉字只是内容，粤语底座的前端把汉字按粤语读音念出。
2. **推论（已确认合理）**：方案 A 若选"中文/普通话底座"，合成大概率带**普通话腔**（第 48 行已写明）；方案 B（台罗→粤拼）仍受粤语底座声学底色影响，腔比 A 准但**非原生台语**。
3. **token 一致性原则**：训练底座与推理前端必须共用**同一套 token 词表**；模型学的是 `token-ID 序列 → 声学` 的映射，不"懂"抽象音系。不同记音法（台罗 / IPA / 自定义 token）只是同一套台语音系的三种拼写，可手工互转（仓库已有 `tailo2jyutping.py` 证明可行；`tailo2ipa` 更易，因台罗本就是音位化罗马字）。
4. **CharsiuG2P 关系澄清**：可当台语 G2P 推理前端（`lang_list.txt` 含 `nan`，`dicts/nan.tsv` 1.43MB，预训练 ByT5 原生支持）；但它输出 **IPA**，与 `all_tokens.txt` 的**自定义 token** 不是同一符号集。
   - C2 路线下，训练与推理**共走 CharsiuG2P 的 IPA**，天然同体系，**无需额外映射表**；
   - 仅当训练文本是台罗记音、想统一成 IPA 词表时才需 `tailo2ipa` 查表。

---

## 10. 分阶段执行计划（修订）

> 决策：先不研究 CharsiuG2P，用现有数据把二级底座训起来；推理先用集合内句子。

### Phase 1（当前立即执行，不引入 CharsiuG2P）

- **目标**：用现有 Common Voice nan-tw 数据（273 人 / 23.4h）训一个「台语二级底座」；推理仅用集合内句子验证。
- **结论先说**：训练和单人微调**点同样的按钮**，没有"建底座开关"。所谓"底座 vs 微调"只差两处——① train.list 里 273 人用**不同 speaker_id**；② config 里 `n_speakers` 调大。
- **Step 1 · 准备 train.list（多人）**
  - 格式不变：`wav绝对路径|speaker_id|language|汉字文本`
  - `speaker_id`：**273 个不同整数**（按 CV 的 `client_id` 映射到 0~272，每人一个、互不相同）。
  - `language`：`yue`（粤语）。`汉字文本`：直接写台语汉字（昨天就是这么干的）。
  - ⚠️ 现有 `build_metadata.py` 的 `[A]` 模式是**按单人**设计的（写死 `nan_tw_01`、按 `DEFAULT_CID` 过滤单人），**不能直接**用于 273 人底座。请用专用脚本 `prepare_nan_tw_dataset.py`：
    ```
    # 在 data-process/ 目录运行 (默认源已指向 E:\008-datasets\...\nan-tw)
    python prepare_nan_tw_dataset.py            # 仅复制 16k mp3 到 prepared/wavs
    python prepare_nan_tw_dataset.py --to-wav   # 转 16k 单声道 wav (需 ffmpeg)
    ```
    产物：`prepared/wavs/`（音频目录）+ `prepared/train.list`（格式 `wav|speaker_id|yue|汉字`，273 人各不同 id）+ `prepared/speaker_map.tsv`（client_id↔整数 id 对照）。
  - ⚠️ **不要**生成/使用 `train_jyutping.list`（粤拼）：粤语前端 `g2p` 只吃汉字（`ToJyutping` + `text_normalize` 会把拉丁字母清空），粤拼直接喂进去会失效。
- **Token / 语种（⚠️ 代码核查后修正）**：
  - **粤语前端只吃汉字**：`text/cantonese.py` 的 `g2p` 走 `ToJyutping.get_jyutping_list(汉字)`，且 `text_normalize` 用正则 `[^\u4e00-\u9fa5…]` **把拉丁字母（粤拼）整段剥离**。所以**直接把粤拼写进 train.list 第 4 列、选粤语模式会失效**（文本被清空/二次转换报错）。`build_metadata.py --mode jyutping` 产出的 `train_jyutping.list`（粤拼）**不能**用于标准粤语模式预处理。
  - **Phase 1 正确做法**：train.list 第 4 列写**汉字**，语种选 **粤语（Cantonese）**；前端自动把汉字→粤拼 symbol（如 `Yaa1`）。这正是昨天跑通的路径，且粤拼 symbol 已在 vocab 内、不 OOV。
  - **不注册 `nan-tw` 新语种**：新增自定义语种需定义 G2P 前端 + 自定义 symbol 词表，属 Phase 2-C2 工作。
  - 备注：路线 B 的「人工粤拼」仅在 Phase 2「`cleaned_text=true` + 预先生成 GPT-SoVITS 符号序列」的人工路线下才可能用，非 Phase 1。
- **Step 2 · 改 config（`configs/s2.json` 或 WebUI 训练配置）**
  - `n_speakers`：设为 **≥273**（建议直接用默认 `300`，与通用底座一致，无需改模型结构）。这是**唯一和单人微调不同的关键项**（单人微调通常设 1）。
  - `pretrained_s2G` / `pretrained_s2D`：指向**通用多语种底座**的 `s2G488k.pth` / `s2D488k.pth`（单人微调也是从这初始化，所以此项一样）。
  - `epochs` / 训练步数：比单人微调**训更长**（底座要见更多人、更多步）。
- **Step 3 · 训练（同单人微调的按钮）**
  - WebUI「1B 文本转音素」：自动把汉字→粤拼 symbol，生成 `2-name2text.txt`（多人各自带 speaker_id）。
  - WebUI「SoVITS训练」+「GPT训练」：从通用底座继续训，学 273 人的台语声学。**没有 base/finetune 切换，区别只在 Step 1–2 的数据与 n_speakers。**
- **Step 4 · 产物 = 二级底座**：得到 `logs_s2_*/G_*.pth`（SoVITS）+ GPT 权重，即新台语二级底座。之后单人微调：挑目标说话人（≥1000 条），以该底座初始化再训一遍。
- **推理（集合内验证）**：汉字 + 粤语模式，复用 train.list 中该说话人的汉字文本 → 无需外部 G2P 前端。
- **价值 / 局限**：底座从 273 台语说话人音频学到台语声学先验，优于通用粤语 base；但文本被粤语前端读成粤语，仍带**粤语腔**、非原生台语——由 Phase 2 解决。

### Phase 2（后续升级，二选一，均基于 Phase 1 底座继续预训练）

- **C1（对齐原生 token）**：解决第 7 节 join key 问题，把 `all_tokens.txt` / `out_txts/` 的**原生台语 token** 对齐到音频，用其续训底座 → token 完全对齐、最正宗。
- **C2（引入 CharsiuG2P）**：用 CharsiuG2P `nan` 生成 **IPA** 作为训练 + 推理前端，底座 token 换 IPA → 自包含、可落地。
- 两者都让发音接近原生台语；Phase 1 的二级底座作初始化，**不浪费**。

### 阶段总览

| 阶段 | 是否引入 CharsiuG2P | Token | 底座来源 | 发音 | 推理范围 |
|---|---|---|---|---|---|
| Phase 1 | 否 | 汉字（粤语模式内部转粤拼） | 通用底座 + 23.4h 继续预训练 | 粤语腔 | 仅集合内句子 |
| Phase 2-C1 | 否 | 原生台语 token | Phase 1 底座 + 原生 token 续训 | ✅ 近原生台语 | 可扩展 |
| Phase 2-C2 | 是（nan G2P） | IPA | Phase 1 底座 + IPA 续训 | ✅ 近原生台语 | 可扩展 |

---

## 11. 模型权重文件结构与加载坑（2026-07-31 实测）

> 本次把 273 人二级底座（`nan-tw-base-2nd`，v2Pro）训完、并准备做第三级微调（`nan_tw_02`）时，集中踩了"权重格式"的坑。根因都在 GPT-SoVITS 对 v2Pro 权重的存盘/读取约定，下面一次说清。

### 11.1 三种 SoVITS 权重文件格式

| 来源文件 | 顶层键 | 是否有 `05` 版本头 | 谁能读 |
|---|---|---|---|
| 训练日志 `logs/.../logs_s2_v2Pro/G_*.pth`、`D_*.pth` | `model`（含 `optimizer` 等） | 无 | **谁都读不了**（`torch.load[...]["weight"]` 会 `KeyError`） |
| 导出到 `SoVITS_weights_v2Pro/*.pth`（WebUI "save small final model" 产出） | `weight` | **有（v2Pro 被 `savee` 前插 2 字节 `05` 头）** | 仅**推理** `load_sovits_new` 能读；1A/1B 的裸 `torch.load` 报 `UnpicklingError` |
| 原始预训练 `GPT_SoVITS/pretrained_models/v2Pro/s2Gv2Pro.pth`、`s2Dv2Pro.pth` | `weight` | 无（裸 zip） | **1A / 1B / 1C 都能读** |

- 代码证据：训练存盘 `utils.save_checkpoint`（`utils.py:75-86`）写 `{"model": state_dict, "optimizer": ...}`；导出 `process_ckpt.savee`（`process_ckpt.py:41-58`）对 v2Pro 走 `my_save2`（`process_ckpt.py:30-38`）前插 `05` 头；裸 `torch.load` 读取方：`3-get-semantic.py:85`、`s2_train.py:238/243/257/261`。
- 注：本仓库文档前文第 10 节提到的 `s2G488k.pth`/`s2D488k.pth` 是 **v2 通用底座**；用 **v2Pro** 时对应换成 `s2Gv2Pro.pth`/`s2Dv2Pro.pth`（本节均按 v2Pro 叙述）。

### 11.2 加载坑速查表

| 现象 | 成因 | 正确做法 |
|---|---|---|
| `KeyError: 'weight'`（1Ac / 1B） | 把训练日志 `G_*.pth`/`D_*.pth`（顶层是 `model`）喂给需要 `weight` 键的读取方 | 不要用 logs 里的 G/D；用 `SoVITS_weights/` 导出文件或原始预训练 |
| `UnpicklingError: unpickling stack underflow`（1Ac / 1B） | 把 v2Pro 导出文件（带 `05` 头）喂给裸 `torch.load` | 1A 用原始 `s2Gv2Pro.pth`；1B 用"裸权重"文件（见 11.4 / 脚本） |
| 推理下拉能列出某 `.pth` 但 1A/1B 报错 | 推理用 `load_sovits_new` 能剥 `05` 头，1A/1B 不能 | 别把 `SoVITS_weights/` 导出文件当 1A/1B 的预训练 |

### 11.3 各阶段 Pretrained 框正确填法（v2Pro）

**1A 数据预处理（1Aa/1Ab/1Ac/1Aabc）**
- `Pretrained SoVITS-G Model Path` → **`GPT_SoVITS/pretrained_models/v2Pro/s2Gv2Pro.pth`**（原始预训练，裸 `weight` zip）。
- ⚠️ 1Ac 语义 token 提取用的是"预训练 SoVITS 编码器"把 HuBERT 特征量化成 VQ 码，**不是你的训练目标模型**，所以永远填原始 `s2Gv2Pro.pth`，与你要训什么底座无关。
- 1Aa 用 `chinese-roberta-wwm-ext-large`，1Ab 用 `chinese-hubert-base`，均不受影响。

**1B 训练（底座 / 三级微调）**
- `Pretrained GPT Model Path` → 通用底座或上一级底座的 GPT（`weight` 键裸 zip，可直接用，如 `GPT_weights_v2Pro/nan-tw-base-2nd-e18.ckpt`）。
- `Pretrained SoVITS-G Model Path` → **裸 `weight` 文件**（见 11.4，不能用带 `05` 头的导出文件）。
- `Pretrained SoVITS-D Model Path` → **`GPT_SoVITS/pretrained_models/v2Pro/s2Dv2Pro.pth`**（原始预训练裸 zip；logs 的 `D_*.pth` 是 `model` 键、不可用；D 不承载音色，用原始 D 即可）。

**1C 推理**
- 直接在顶部下拉选 `GPT_weights_v2Pro/...ckpt` 与 `SoVITS_weights_v2Pro/...pth`（导出文件带 `05` 头，推理加载器能剥），**不要动顶部 Pretrained 框**。

### 11.4 三级微调（以 273 底座为起点训 `nan_tw_02`）的预训练框

训练前先确认：`train.list` 已换成目标说话人单人数据、`n_speakers=1`，且对应 1A 已用新数据重跑完。

| 框 | 值 |
|---|---|
| Version | `v2Pro` |
| GPU number | `0` |
| Pretrained GPT | `GPT_weights_v2Pro/nan-tw-base-2nd-e18.ckpt` |
| Pretrained SoVITS-G | `SoVITS_weights_v2Pro/nan-tw-base-2nd_e18_raw.pth`（裸权重，由脚本转出） |
| Pretrained SoVITS-D | `GPT_SoVITS/pretrained_models/v2Pro/s2Dv2Pro.pth` |

> `nan-tw-base-2nd_e18_raw.pth` 是用下面脚本从 `logs/.../G_233333333333.pth` 转出的裸 `weight` 文件（无 `05` 头，1B 能读）。

### 11.5 把 v2Pro 训练日志 G 转成裸权重的脚本

`docs/data-process/convert_v2pro_s2g_to_raw.py`（在仓库根目录执行）：把 `logs/.../G_*.pth`（`model` 键）转成 1B 可直接加载的裸 `weight` zip。

```bash
cd /root/autodl-tmp/GPT-SoVITS
python docs/data-process/convert_v2pro_s2g_to_raw.py
```

（脚本内 `LOGS_G` / `OUT_PATH` 两个变量按需改；`s2Dv2Pro.pth` 本身就是裸 zip，无需转换。）
