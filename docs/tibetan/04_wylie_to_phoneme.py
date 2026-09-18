#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""藏语语料 · 阶段二（草案）：Wylie 音节 → 音素

方案取舍
--------
README 列的三条路实测后只剩 C：

    A. espeak-ng   未安装；且 espeak-ng 官方**没有藏语(bo) voice**，装了也转不出
    B. botok       未安装；且它是分词/词性标注库，不提供音标
    C. 自建拼读规则 唯一可行

本脚本是 C 的**第一版草案**：拿 02 的结构解析结果，按**拉萨话**规则推导音素。

规则依据
--------
Tournadre & Sangda Dorje, *Manual of Standard Tibetan* (1998) 拼读章节。

把握程度分三档，代码中用标记体现：

    [稳] 声母清化（浊塞音 + 有无前加字 → 送气/不送气）—— 规则明确
    [稳] 声调高低（清基字或有前加字 → 高；浊基字无前加字 → 低）—— 规则明确
    [待验] 下加字的具体音值（卷舌/腭化/边音化的实际产物）
    [待验] 元音受后加字 r/l 的变音（a→ɛ / o→ø / u→y）

音素集：IPA。声调用数字调值（55/53/13/12），便于后续自由映射到 GPT-SoVITS 的符号表。

输出
----
    <DATA_ROOT>/prepared/phoneme_draft.tsv    音节 -> 音素（按频次排序）
    <DATA_ROOT>/prepared/phoneme_samples.txt  高频抽样，供母语者核对
"""

import argparse
import collections
import csv
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_ROOT = r"E:\008-datasets\藏语-疑问"

# ---------------------------------------------------------------------------
# 1. 基字表
#    vl = 清音基字          → 声母即本音，高调
#    vd = 古浊塞音/塞擦音    → 现代清化，送气与否看有无前加字
#    sn = 古浊响音(鼻/边/半元音/浊擦) → 保持浊音
#    zr = 零声母
# ---------------------------------------------------------------------------
BASE_TABLE = {
    "k": ("vl", "k"),    "kh": ("vl", "kʰ"),   "g": ("vd", None),
    "ng": ("sn", "ŋ"),
    "c": ("vl", "tɕ"),   "ch": ("vl", "tɕʰ"),  "j": ("vd", None),
    "ny": ("sn", "ɲ"),
    "t": ("vl", "t"),    "th": ("vl", "tʰ"),   "d": ("vd", None),
    "n": ("sn", "n"),
    "p": ("vl", "p"),    "ph": ("vl", "pʰ"),   "b": ("vd", None),
    "m": ("sn", "m"),
    "ts": ("vl", "ts"),  "tsh": ("vl", "tsʰ"), "dz": ("vd", None),
    "w": ("sn", "w"),    "zh": ("sn", "ʑ"),    "z": ("sn", "z"),
    "'": ("sn", "ʔ"),    "y": ("sn", "j"),     "r": ("sn", "r"),   "l": ("sn", "l"),
    "sh": ("vl", "ɕ"),   "s": ("vl", "s"),     "h": ("vl", "h"),
    "a": ("zr", ""),
    "": ("zr", ""),      # 零声母：02 允许元音直接起头（如 in / i）
}

# 古浊塞音/塞擦音的**古音值**（先还原浊音，再按规则清化）
BASE_VOICED = {"g": "g", "j": "dʑ", "d": "d", "b": "b", "dz": "dz"}

# 浊音 → (不送气清音, 送气清音)。键是"经下加字改造后"的浊音值
DEVOICE = {
    "g":  ("k",   "kʰ"),
    "dʑ": ("tɕ",  "tɕʰ"),
    "d":  ("t",   "tʰ"),
    "b":  ("p",   "pʰ"),
    "dz": ("ts",  "tsʰ"),
    "ɖʐ": ("ʈʂ",  "ʈʂʰ"),   # g/j/d/b/dz + 下加字 r 的产物
}

# ---------------------------------------------------------------------------
# 2. 下加字改造表  [待验]
#    下加字只改造**发音部位**，不决定清浊；清浊与送气由第 3 步（清化）负责
# ---------------------------------------------------------------------------
RETROFLEX_MAP = {           # 下加字 r (ྲ)：卷舌化
    "k": "ʈʂ",   "kh": "ʈʂʰ", "g": "ɖʐ",
    "t": "ʈʂ",   "th": "ʈʂʰ", "d": "ɖʐ",
    "p": "ʈʂ",   "ph": "ʈʂʰ", "b": "ɖʐ",
    "s": "ʂ",    "h": "ʂ",
    "m": "ɳ",    "n": "ɳ",
}
PALATAL_MAP = {             # 下加字 y (ྱ)：腭化
    "k": "tɕ",   "kh": "tɕʰ", "g": "dʑ",
    "p": "tɕ",   "ph": "tɕʰ", "b": "dʑ",
    "m": "ɲ",    "s": "ɕ",    "h": "ɕ",
}
LATERAL_MAP = {             # 下加字 l (ླ)：边音化
    "k": "l", "g": "l", "b": "l", "d": "l",
    "s": "l", "z": "l", "r": "l", "h": "l",
}

# ---------------------------------------------------------------------------
# 3. 元音与后加字  [稳] 鼻化 / [待验] r·l 变音
# ---------------------------------------------------------------------------
VOWEL_BASE = {"a": "a", "i": "i", "u": "u", "e": "e", "o": "o"}
NASAL_SUFFIX = {"n", "ng", "m"}                 # 使元音鼻化
R_ISH_SUFFIX = {"r", "l"}                       # 使元音变音
CHECKED_SUFFIX = {"g", "d", "b", "s", "'"}      # 促声尾：不发音，但压缩声调
R_SHIFT = {"a": "ɛ", "o": "ø", "u": "y"}        # [待验]
NASAL_TILDE = {"a": "ã", "i": "ĩ", "u": "ũ", "e": "ẽ", "o": "õ",
               "ɛ": "ɛ̃", "ø": "ø̃", "y": "ỹ"}

# ---------------------------------------------------------------------------
# 已知缺口（2026-09 决策：暂不实现，等文献核实）
#
# 以下组合疑似应发生元音变音，但**触发集不完整**，贸然实现会引入新错误，
# 因此当前只实现证据最硬的 {r,l} 两条，其余登记在此，由 --todo 输出清单：
#
#     a + {s,d,b,g} -> ɛ ?    证据: པས/pɛː/ ལས/lɛː/ ནས/nɛː/ མཁས/kʰɛː/
#     o + {s,d,b,g} -> ø ?    证据: བོད/pʰøː/ དགོས/køː/
#
# 待确认的关键点：n / m / ng 前是否也发生同样的变音（若发生，规则要扩到鼻音尾）。
# ---------------------------------------------------------------------------
SUSPECT_SHIFT = {
    ("a", "s"): "ɛ", ("a", "d"): "ɛ", ("a", "b"): "ɛ", ("a", "g"): "ɛ",
    ("o", "s"): "ø", ("o", "d"): "ø", ("o", "b"): "ø", ("o", "g"): "ø",
}


def onset_ipa(pre, sup, base, sub):
    """声母推导 —— 返回 (ipa, notes)"""
    notes = []
    if base not in BASE_TABLE:
        return "", ["未知基字"]
    cls, plain = BASE_TABLE[base]

    # (1) 取古音：浊塞音先还原为浊音，其余用本音
    ipa = BASE_VOICED.get(base, plain) if cls == "vd" else plain

    # (2) 下加字改造发音部位
    if "r" in sub and base in RETROFLEX_MAP:
        ipa = RETROFLEX_MAP[base]
        notes.append("卷舌")
    elif "y" in sub and base in PALATAL_MAP:
        ipa = PALATAL_MAP[base]
        notes.append("腭化")
    elif "l" in sub and base in LATERAL_MAP:
        ipa = LATERAL_MAP[base]
        notes.append("边音化")
        if cls == "vd":
            cls = "sn"      # 塞音已被边音化成响音 /l/，此后不再参与清化
    if "w" in sub:
        notes.append("圆唇")

    # (3) 清化：浊塞音/塞擦音按有无前加字决定送气
    if cls == "vd":
        pair = DEVOICE.get(ipa)
        if pair is None:
            notes.append(f"未覆盖的浊音清化[{ipa}]")
        else:
            has_pre = bool(pre or sup)
            ipa = pair[1] if not has_pre else pair[0]   # 无前加→送气；有前加→不送气
            notes.append("送气" if not has_pre else "不送气")
    return ipa, notes


def vowel_ipa(vowel, suf, suf2):
    """韵母推导 —— 返回 (ipa, notes)"""
    notes = []
    v = VOWEL_BASE.get(vowel, vowel)

    if suf in R_ISH_SUFFIX:
        v2 = R_SHIFT.get(v)
        if v2:
            v = v2
            notes.append("r/l变音")
    if suf in NASAL_SUFFIX:
        v = NASAL_TILDE.get(v, v)
        notes.append("鼻化")
    return v, notes


def tone_of(pre, sup, base, suf, suf2):
    """声调推导 —— 返回 (调值, notes)

    高调 ⟺ 清音基字 或 有**带声**前缀（前加字 ག ད བ མ、上加字 ར ལ ས）
    低调 ⟺ 浊音基字 且 无带声前缀
    促声尾(g/d/b/s/')使平调变降调

    例外：前加字 འ (a-chung) 是**不带声**前缀 —— 它只把基字清化为
    不送气，**不抬高声调**。证据（拉萨话实际读音）：
        འདི   'di    /tì/      而非 /tí/
        འདུག  'dug   /tùʔ/
        འགྲོ  'gro   /ʈʂò/
        འབྲེལ 'brel  /ʈʂèː/
    这四条都是超高频词（'di 702 次 / 'dug 411 次），原先一律按高调处理是错的。
    """
    cls = BASE_TABLE.get(base, ("", ""))[0]
    voiced_pre = bool(sup) or bool(pre and pre != "'")
    high = (cls in ("vl", "zr")) or voiced_pre
    checked = (suf in CHECKED_SUFFIX) or (suf2 in {"s", "d"})
    if high:
        return ("53" if checked else "55"), (["高调"] + (["促声"] if checked else []))
    return ("12" if checked else "13"), (["低调"] + (["促声"] if checked else []))


def syllable_parts(st):
    """结构字典 -> (声母, 韵母, 声调, 备注列表)

    与 syllable_to_phoneme 同源，只是不把三部分拼成一个串。
    供下游按「声母 / 韵母+声调」划分 token 并映射成符号表代号使用 ——
    拼成连写串后再反推边界是不可靠的（ʈʂʰa53 切不出 ʈʂʰ | a | 53）。
    """
    pre, sup = st.get("prefix", ""), st.get("super", "")
    base, sub = st.get("base", ""), st.get("sub", "")
    vowel, suf, suf2 = st.get("vowel", ""), st.get("suffix", ""), st.get("suffix2", "")

    if not vowel:
        return "", "", "", ["无元音"]

    on, n1 = onset_ipa(pre, sup, base, sub)
    vo, n2 = vowel_ipa(vowel, suf, suf2)
    tone, n3 = tone_of(pre, sup, base, suf, suf2)
    return on, vo, tone, n1 + n2 + n3


def syllable_to_phoneme(st):
    """结构字典 -> (音素串, 备注列表)"""
    on, vo, tone, notes = syllable_parts(st)
    if not vo:
        return "", notes
    return f"{on}{vo}{tone}", notes


def main(argv=None):
    ap = argparse.ArgumentParser(description="Wylie 音节 -> 音素（草案）")
    ap.add_argument("--data-root", default=os.environ.get("TIBETAN_DATA_ROOT", DEFAULT_ROOT))
    ap.add_argument("--top", type=int, default=120, help="抽样条数")
    args = ap.parse_args(argv)

    src = os.path.join(args.data_root, "prepared", "syllable_structure.tsv")
    if not os.path.exists(src):
        print(f"[FAIL] 找不到 {src}，请先运行 02_parse_syllable.py")
        return 1

    with open(src, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f, delimiter="\t")
                if r["kind"] == "syllable"]

    out_rows = []
    note_counter = collections.Counter()
    tone_counter = collections.Counter()
    onset_counter = collections.Counter()
    unknown = []
    suspect = []
    for r in rows:
        ipa, notes = syllable_to_phoneme(r)
        tone = ipa[-2:] if ipa and ipa[-2:].isdigit() else ""
        tone_counter[tone] += int(r["count"])
        for n in notes:
            note_counter[n] += 1
        if "未知基字" in notes or any(n.startswith("未覆盖") for n in notes):
            unknown.append((r["unit"], r["count"], notes))
        # 登记疑似应发生元音变音、但当前未实现的音节（见 SUSPECT_SHIFT）
        key = (r["vowel"], r["suffix"])
        if key in SUSPECT_SHIFT:
            suspect.append((r["unit"], r["count"], ipa,
                            f"{r['vowel']}+{r['suffix']} 疑似 -> {SUSPECT_SHIFT[key]}"))
        onset_counter[ipa[: -len(tone)] if tone else ipa] += int(r["count"])
        out_rows.append({
            "unit": r["unit"],
            "count": r["count"],
            "structure": f"{r['prefix']}+{r['super']}+{r['base']}+{r['sub']}"
                         f"+{r['vowel']}+{r['suffix']}+{r['suffix2']}",
            "ipa": ipa,
            "notes": ";".join(notes),
        })

    prepared = os.path.join(args.data_root, "prepared")
    out_tsv = os.path.join(prepared, "phoneme_draft.tsv")
    with open(out_tsv, "w", encoding="utf-8", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=["unit", "count", "structure", "ipa", "notes"],
                             delimiter="\t")
        wtr.writeheader()
        wtr.writerows(out_rows)

    out_txt = os.path.join(prepared, "phoneme_samples.txt")
    with open(out_txt, "w", encoding="utf-8", newline="\n") as f:
        f.write("Wylie -> 音素 抽样（按频次降序）\n")
        f.write("=" * 78 + "\n")
        for r in out_rows[:args.top]:
            f.write(f"{r['unit']:16s} x{r['count']:<6s} {r['ipa']:14s} "
                    f"{r['structure']:20s} {r['notes']}\n")

    # 待核实清单：拿去和文献/词典对照，确认后再决定是否补规则
    out_todo = os.path.join(prepared, "phoneme_todo.tsv")
    suspect.sort(key=lambda x: -int(x[1]))
    with open(out_todo, "w", encoding="utf-8", newline="") as f:
        wtr = csv.writer(f, delimiter="\t")
        wtr.writerow(["unit", "count", "current_ipa", "suspect"])
        wtr.writerows(suspect)

    print(f"输入音节 : {len(rows)} 种")
    print()
    print("== 声调分布（按 token 频次） ==")
    total = sum(tone_counter.values())
    for k, v in tone_counter.most_common():
        print(f"  {k or '(无)':8s} {v:6d}  ({v / total * 100:5.1f}%)")
    print()
    print("== 推导备注分布 ==")
    for k, v in note_counter.most_common(12):
        print(f"  {k:16s} {v}")
    print()
    print("== 高频音节音值 top15（无调，按频次） ==")
    for k, v in onset_counter.most_common(15):
        print(f"  {k or '(零声母)':10s} {v}")
    if unknown:
        print()
        print(f"== 未覆盖 {len(unknown)} 种 ==")
        for u, c, n in sorted(unknown, key=lambda x: -int(x[1]))[:15]:
            print(f"  {u:16s} x{c:<6s} {n}")
    print()
    print(f"== 待核实：元音变音缺口 {len(suspect)} 种 ==")
    tot_suspect = sum(int(c) for _, c, _, _ in suspect)
    print(f"  涉及 token {tot_suspect} 次"
          f"（占藏语单元 {tot_suspect / sum(int(r['count']) for r in rows) * 100:.1f}%）")
    for u, c, ipa, s in suspect[:8]:
        print(f"  {u:16s} x{c:<6s} 当前 {ipa:10s} {s}")
    print()
    print(f"产出: {out_tsv}")
    print(f"      {out_txt}")
    print(f"      {out_todo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
