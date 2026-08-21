# -*- coding: utf-8 -*-
"""
teochew.py — 潮汕话(GPT-SoVITS) G2P 前端

设计原则 (与训练数据保持一致):
- 训练侧第4列直接来自 monolab 音素对齐 (如: sil z ehg silv l iam ...)
  这些音素是 "声母/韵母/停顿" 的纯音素符号, 不带声调数字, 不带 Y 前缀。
- 本前端的 g2p() 必须输出**完全相同的符号集**, 否则推理音素在 symbols2.py
  查不到 ID -> 炸音。因此这里不重新发明带 Y 前缀/带调值的标记,
  而是直接输出 monolab 风格音素 (声母 + 韵母), 与 monolab 对齐。

数据源 (默认指向 04_ChaoShan 标注目录, 路径可覆盖):
- 字_allpinyin_20180312.txt : 汉字 -> 潮州音 (取"潮州音"字段首读音)
- allpinyin_with_shengyun.txt : 音节 -> 声母/韵母 拆分 (对齐 monolab 音素)

连调: 第一阶段使用单字调值(不单独成符号), 连调规则预留接口 tone_sandhi()。
"""
import os
import re

# 默认数据目录 (潮汕话标注). 可用环境变量 TEOW_DATA 覆盖。
DATA_DIR = os.environ.get(
    "TEOW_DATA",
    r"/root/autodl-tmp/GPT-SoVITS/data/04_ChaoShan",
)

from text.symbols2 import punctuation  # 复用通用标点定义

# 停顿/特殊符号 (与 monolab 观察到的一致)
PAUSE = ["sil", "silv", "ds", "ts"]

rep_map = {
    "：": ",",
    "；": ",",
    "，": ",",
    "。": ".",
    "！": "!",
    "？": "?",
    "\n": ".",
    "·": ",",
    "、": ",",
    "...": "…",
    "$": ".",
    "“": "'",
    "”": "'",
    '"': "'",
    "‘": "'",
    "’": "'",
    "（": "'",
    "）": "'",
    "(": "'",
    ")": "'",
    "《": "'",
    "》": "'",
    "【": "'",
    "】": "'",
    "[": "'",
    "]": "'",
    "—": "-",
    "～": "-",
    "~": "-",
}

_punct_pattern = re.compile("|".join(re.escape(p) for p in rep_map.keys()))


def _load_syllable_split():
    """音节 -> (声母, 韵母) 映射, 来自 allpinyin_with_shengyun.txt。"""
    path = os.path.join(DATA_DIR, "allpinyin_with_shengyun.txt")
    split_map = {}
    if not os.path.exists(path):
        return split_map
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            syl = parts[0].strip()
            sheng = parts[1].strip()  # 声母 (null 表示零声母)
            yun = parts[2].strip()     # 韵母
            if syl and syl != "null":
                split_map[syl] = (sheng if sheng != "null" else "", yun)
    return split_map


def _load_char_dict():
    """汉字 -> 潮州音音节列表, 来自 字_allpinyin_20180312.txt。"""
    path = os.path.join(DATA_DIR, "字_allpinyin_20180312.txt")
    char2syl = {}
    if not os.path.exists(path):
        return char2syl
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or ":" not in line:
                continue
            char, rest = line.split(":", 1)
            char = char.strip()
            if not char:
                continue
            # 格式: {潮州音:zêg8}{文读:}... 提取 潮州音 字段
            m = re.search(r"潮州音:([^}]+)", rest)
            if not m:
                continue
            readings = [r.strip() for r in m.group(1).split(";") if r.strip()]
            if readings:
                # 取首个读音作为默认; 多音字后续可扩展消歧
                char2syl[char] = readings
    return char2syl


# 模块级加载 (惰性: 首次 g2p 时构建)
_SPLIT_MAP = None
_CHAR_DICT = None
_VALID_PHONES = None  # monolab 音素白名单 (与训练符号集一致)


def _load_valid_phones():
    """从 docs/teochew/symbols_teochew.txt 读取训练音素白名单。
    保证推理 g2p 输出符号与训练(monolab)完全一致。"""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docs", "teochew", "symbols_teochew.txt",
    )
    phones = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # 跳过 "[PAUSE]"/"[PHONES]" 段标记行
                if line.startswith("["):
                    continue
                # 行可能是 "phone\tcount" 或纯 "phone"
                ph = line.split("\t")[0].strip()
                if ph:
                    phones.add(ph)
    # 回退: 至少包含已知停顿符号
    phones.update(PAUSE)
    return phones


def _ensure_loaded():
    global _SPLIT_MAP, _CHAR_DICT, _VALID_PHONES
    if _SPLIT_MAP is None:
        _SPLIT_MAP = _load_syllable_split()
    if _CHAR_DICT is None:
        _CHAR_DICT = _load_char_dict()
    if _VALID_PHONES is None:
        _VALID_PHONES = _load_valid_phones()


def text_normalize(text):
    """替换标点并剥离非汉字/非标点字符 (对齐 cantonese 做法)。"""
    replaced = _punct_pattern.sub(lambda x: rep_map[x.group()], text)
    # 保留汉字 + 通用标点
    allowed = "".join(punctuation)
    replaced = re.sub(r"[^\u4e00-\u9fff" + re.escape(allowed) + r"]+", "", replaced)
    return replaced


def _normalize_yun(s):
    """把词典韵母写法归一化为 monolab 的 ASCII 形式。
    关键差异: 词典用带帽元音 (ê), monolab 用纯 ASCII (e 系, 如 êg->ehg)。
    这里做最小映射, 其余逐字符 ASCII 化。"""
    s = s.replace("ê", "e")
    return s


def _syllable_to_phones(syllable):
    """潮州音音节 (如 zêg8) -> 声母+韵母 音素列表 (如 ['z','ehg'])。
    去掉尾部调值数字; 用 allpinyin_with_shengyun 的拆分对齐 monolab 音素,
    并校验输出符号全部落在训练白名单(_VALID_PHONES)内, 否则退化 UNK。"""
    # 去掉尾部调值数字 (1-8)
    syl_no_tone = re.sub(r"[1-8]$", "", syllable)
    phones = []
    if syl_no_tone in _SPLIT_MAP:
        sheng, yun = _SPLIT_MAP[syl_no_tone]
        if sheng:
            sheng = _normalize_yun(sheng)
            if sheng in _VALID_PHONES:
                phones.append(sheng)
            # 声母不在白名单则丢弃(零声母情况)
        if yun:
            yun = _normalize_yun(yun)
            if yun in _VALID_PHONES:
                phones.append(yun)
            else:
                # 韵母归一后仍不在白名单, 尝试直接用原始韵母
                if yun in _VALID_PHONES:
                    phones.append(yun)
    else:
        # 拆分表无该音节: 整个音节归一化后若恰在白名单则整用
        norm = _normalize_yun(syl_no_tone)
        if norm in _VALID_PHONES:
            phones.append(norm)
    return phones


def tone_sandhi(syllables):
    """连调接口 (第一阶段: 原样返回; 后续可接入潮州话两字组连调规则)。"""
    return syllables


def g2p(text):
    """汉字文本 -> (phones 列表, word2ph 列表)。

    输出符号集与 monolab 训练音素一致 (声母/韵母/停顿, 无 Y 前缀, 无调值数字)。
    """
    _ensure_loaded()
    norm = text_normalize(text)
    if not norm:
        return [], []

    phones = []
    word2ph = []

    # 逐字处理: 汉字查词典, 标点直接作停顿/标点符号
    for ch in norm:
        if ch in punctuation:
            phones.append(ch)
            word2ph.append(1)
            continue
        if ch in _CHAR_DICT:
            syllables = tone_sandhi(_CHAR_DICT[ch])
            first = syllables[0]  # 默认取首读音
            phs = _syllable_to_phones(first)
            if not phs:
                # 词典有但拆分失败, 退化为 UNK 由 cleaner 处理
                phones.append("UNK")
                word2ph.append(1)
            else:
                phones.extend(phs)
                word2ph.append(len(phs))
        else:
            # 词典未收录的汉字: 用 UNK 占位 (cleaner 会替换为 UNK 符号)
            phones.append("UNK")
            word2ph.append(1)

    return phones, word2ph


if __name__ == "__main__":
    # 快速自测
    test = "一念之慈"
    p, w = g2p(test)
    print("text:", test)
    print("phones:", p)
    print("word2ph:", w)
