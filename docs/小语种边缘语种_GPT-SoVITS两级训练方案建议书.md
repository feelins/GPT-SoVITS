# 小语种 / 民族语种 / 边缘语种 GPT-SoVITS 语音合成：两级训练方案与建议书


## 1. 数据准备

> 以下全部为**模拟/示例数据**，仅用于演示"原始 IPA 标注 → 最终 train.list"的形态。合作者需替换为自己的真实语种与标注。

### 1.1 满语情况

`GPT-SoVITS\docs\00000008.wav` 是原始音频。
拉丁转写：beye beye aisilambi
在训练的时候是这样的形式：
```
/.../.../00000008.wav|manchu_speaker|man|P AH1 JH AE1 P AH1 JH AE1 AW1 JH S IY1 L AW1 M P IY1
```

合成样例：
GPT-SoVITS\docs\manchu_c4d3e3a76181_spec.png
GPT-SoVITS\docs\manchu_c4d3e3a76181.wav

### 1.2 台湾闽南语
是直接输入汉字，选择粤语底座，这样让这些汉字直接输出的是粤拼。当同样的jyo这样的拼音， 如果用来表征台闽语，有一些倾向会发出来台闽语的发音。结果证明这样肯定有比较浓的粤语发音味。就象刚才的满语，个别发音也能听出来有点象读英语单词。
```
/.../common_voice_nan-tw_32136499.wav|nan_tw_01|yue|一碗飯來分我好無？
```

### 1.3 进行的实验
将开源的台闽语273个人的数据， 约25小时数据，以speaker_id标记，然后用这个speaker_id去训练v2Pro的底座。相当于一个二级底座模型训练。训练好之后，再对一个目标发音人合成音频。目前仍然在运行中。结果有待验证。

### 1.4 建议的目录结构

```text
edge-lang-dataset/
├── wavs/                  # 32k 或 16k 单声道 wav/mp3，每人一个子目录
│   ├── spk_A/
│   │   ├── 0001.wav
│   │   └── 0002.wav
│   └── spk_B/
│       └── 0001.wav
├── ipa_labels.tsv         # 原始 IPA 标注（你已有）
├── arpa_labels.tsv        # IPA→ARPA 映射后的标注（脚本产出）
├── speaker_map.tsv        # 说话人 ↔ 整数 id
└── train.list             # 最终训练清单
```

### 1.5 原始 IPA 标注


```tsv
client_id	path	ipa
spk_A	0001	ǂʰòmà t͡ɬʼī
spk_A	0002	ɬíŋ kʼáá
spk_B	0001	ʁòò t͡ʃʼé
```

### 1.6 IPA → ARPABET 映射（核心步骤）

#### 1.6.1 映射表（模拟，需按目标语言音系校准）

| IPA | ARPABET | 说明 |
|---|---|---|
| t | T | 清塞音 |
| k | K | 清塞音 |
| p | P | 清塞音 |
| d | D | 浊塞音 |
| ɡ | G | 浊塞音 |
| b | B | 浊塞音 |
| s | S | 清擦音 |
| ʃ | SH | 清龈后擦音 |
| t͡ʃ | CH | 塞擦音 |
| m | M | 鼻音 |
| n | N | 鼻音 |
| ŋ | NG | 鼻音 |
| l | L | 边音 |
| r / ʁ | R | 英语无小舌音，近似映射 R（**有损**） |
| w | W | 半元音 |
| j | Y | 半元音 |
| h | HH | 喉擦音 |
| f | F | 清擦音 |
| i | IY | 高前元音 |
| e / ɛ | EH | 中前元音 |
| a / ɑ | AA | 低元音 |
| o | OW | 高后圆唇 |
| u | UW | 高后圆唇 |
| ə | AH | 中央元音 |
| ai | AY | 双元音 |
| au | AW | 双元音 |
| ╳ ǂ（嗒嘴音） | （丢弃） | 英语无对应，**直接丢**（**有损**） |
| ╳ ʼ（挤喉/声门化） | （丢弃） | 英语无对应，**直接丢**（**有损**） |
| ╳ ̀ ́ ̄（声调） | （丢弃或→重音） | 英语无声调，**直接丢**（**有损**） |
| ╳ ʰ（送气） | （丢弃） | 英语送气不区分音位，**直接丢** |

> ⚠️ **映射是有损的**：声调、嗒嘴音、挤喉音、小舌音等英语没有的特征会被丢弃或近似。这意味着模型能"学出该说话人的音色 + 大致可懂的音节"，但**原生腔调/对立特征会失真**。这是用英语底座的固有代价，需在预期里写明。

#### 1.6.2 映射脚本骨架（模拟，可直接改成真实实现）

```python
# ipa_to_arpa.py  (示例骨架, 非完整实现)
IPA2ARPA = {
    # 辅音
    "t":"T","k":"K","p":"P","d":"D","ɡ":"G","b":"B",
    "s":"S","ʃ":"SH","ʒ":"ZH","t͡ʃ":"CH","d͡ʒ":"JH",
    "m":"M","n":"N","ŋ":"NG","l":"L","r":"R","w":"W","j":"Y","h":"HH",
    "f":"F","v":"V","θ":"TH","ð":"DH",
    # 元音 (示例, 必须按目标语言音系校准!)
    "i":"IY","e":"EH","ɛ":"EH","a":"AA","ɑ":"AA","o":"OW","u":"UW",
    "ə":"AH","ɪ":"IH","ʊ":"UH","æ":"AE",
    "ai":"AY","au":"AW","oi":"OY","ei":"EY",
}

def ipa_to_arpa(ipa: str):
    out, i = [], 0
    while i < len(ipa):
        two = ipa[i:i+2]
        if two in IPA2ARPA:              # 先试双字符 (如 t͡ʃ)
            out.append(IPA2ARPA[two]); i += 2; continue
        one = ipa[i]
        if one in IPA2ARPA:             # 再试单字符
            out.append(IPA2ARPA[one]); i += 1; continue
        # 声调/送气/挤喉/嗒嘴等超音段或英语无对应音 -> 丢弃
        i += 1
    return " ".join(out)

# 真实落地建议: 用现成库而非手写
#   - `ipa2arpa` (PyPI): 直接 IPA -> ARPABET
#   - `panphon`: 用特征向量找"最近的 ARPABET 音", 映射更系统
#   - `espeak-ng`: 可作兜底/对照
if __name__ == "__main__":
    for line in ["ǂʰòmà t͡ɬʼī", "ɬíŋ kʼáá", "ʁòò t͡ʃʼé"]:
        print(repr(line), "->", ipa_to_arpa(line))
    # 输出(示意, 修饰符被丢): 'ǂʰòmà t͡ɬʼī' -> 'K OW0 M AA0 CH IY1'
```

#### 1.6.3 映射产物

```tsv
client_id	path	arpa
spk_A	       0001	M AH0 K AA1 R AA0 CH IY1
spk_A	       0002	S IY1 NG K AA1
spk_B	       0001	R OW0 OW0 CH EH1
```

> 注意：示例里 `ǂʰ`（嗒嘴+送气）、`ʼ`（挤喉）、声调全部被丢弃，边擦音 `ɬ` 被近似成 `S`。这就是**有损**的直观体现。

### 1.7 组装 train.list

格式（与 nan-tw 一致，仅语种列改为 `en`，第 4 列为 ARPABET）：

```text
# 绝对路径|speaker_id|语种|ARPABET音素序列
/data/edge-lang-dataset/wavs/spk_A/0001.wav|0|en|M AH0 K AA1 R AA0 CH IY1
/data/edge-lang-dataset/wavs/spk_A/0002.wav|0|en|S IY1 NG K AA1
/data/edge-lang-dataset/wavs/spk_B/0001.wav|1|en|R OW0 OW0 CH EH1
```

- `speaker_id`：每个说话人一个**不同整数**（0,1,2…），写在 `speaker_map.tsv` 里对照 `client_id`。
- `语种`：固定 `en`（英语前端，因为第 4 列已是英语 ARPABET 符号）。
- ⚠️ **不要**把原始 IPA 直接写进第 4 列——英语前端不认识 IPA，会 OOV。


> 训练侧提示（GPT-SoVITS\docs\train.png）：第 4 列已是 ARPABET 音素。若自动 G2P 再次处理导致异常，可**预先生成 `2-name2text.txt`**（每行一条 ARPABET 序列，与 train.list 顺序对应），让训练直接读音素、跳过 G2P。这是小语种用英语底座的稳妥兜底。

---
下面依次点：
GPT-SoVITS\docs\train2.png
GPT-SoVITS\docs\train3.png

推理：
GPT-SoVITS\docs\eval1.png
GPT-SoVITS\docs\eval2.png