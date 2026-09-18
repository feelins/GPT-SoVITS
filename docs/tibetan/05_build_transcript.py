#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""藏语语料 · 阶段二收口：句子级 Wylie -> 音素转写

把 02 的结构解析和 04 的发音规则串起来，对全语料逐句转写。

已定的三个取舍（2026-09）
------------------------
  · 音素保持 IPA，**此处不做符号表映射** —— 等音素表定稿后统一步骤，
    避免现在就把符号选择焊死（对应决策「先 IPA，最后一步再映射」）
  · 声调保留 4 个调值 55 / 53 / 13 / 12（对应决策「保留 4 个调值」）
  · 元音变音缺口 **暂不实现** —— a+{s,d,b,g}->ɛ、o+{s,d,b,g}->ø 两条
    影响面见 04 产出的 phoneme_todo.tsv（389 种 / 13770 次 / 18.0%），
    决策是「先接受草案，靠训练效果倒推」，故此处保持现状并逐句统计命中量

转写粒度
--------
**音节**。音节之间空格，token 之间也空格，与 Wylie 的空格结构一一对应，
便于把 Wylie 行和 IPA 行并排核对：

    gangs rin po che
    kʰã53 rĩ13 po55 tɕʰe55

非藏语成分（梵文叠字 / 阿拉伯数字 / 英文专名）保留为 ⟨kind:原文⟩ 标记，
既不在这步丢弃，也不假装能转音素——它们的处理属于后续单独决策。

输入 : <DATA_ROOT>/prepared/annotations.tsv        （阶段一产物）
输出 : <DATA_ROOT>/prepared/phoneme_transcript.tsv
       docs/tibetan/音素索引.list                  路径|Wylie|IPA 三列，单文件可核对
"""

import argparse
import collections
import csv
import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = r"E:\008-datasets\藏语-疑问"
WAV_SUBDIR = os.path.join("wav", "wav")

# ---------------------------------------------------------------------------
# IPA -> ASCII 符号映射（供 GPT-SoVITS 符号表使用）
#
# 约定：
#   · 统一加 T 前缀（Tibetan），避免与普通话/粤语符号重名 —— 粤语用的是 Y
#   · 送气 = 后缀 h；卷舌 = 后缀 r；腭化 = 单字母 c / ch / x / zh
#   · 鼻化元音 = 对应大写；r/l 变音 = 二合字母 ae / oe / ue
#   · 声调保留调值数字（55/53/13/12）
#   · 零声母不产出 token（与普通话零声母音节一致）
#
# 映射是**双射**：反查表可由本表直接生成，不损失信息。
# 注意映射对象是「音素单元」（29 声母 + 13 韵母 + 4 声调 = 46 个），
# 不是 Unicode 字符 —— 后者会把 ʈʂʰ 拆成 ʈ + ʂ + ʰ 三个假音素。
# ---------------------------------------------------------------------------
SYM_PREFIX = "T"

ONSET_MAP = {
    "":   "",                                   # 零声母
    "p":  "p",   "pʰ": "ph",
    "t":  "t",   "tʰ": "th",
    "k":  "k",   "kʰ": "kh",
    "ts": "ts",  "tsʰ": "tsh",
    "tɕ": "c",   "tɕʰ": "ch",
    "ʈʂ": "tr",  "ʈʂʰ": "trh",
    "m":  "m",   "n":  "n",   "ŋ": "ng", "ɲ": "ny", "ɳ": "nr",
    "s":  "s",   "ɕ":  "x",   "ʂ": "sr",
    "z":  "z",   "ʑ":  "zh",
    "h":  "h",   "ʔ":  "q",
    "j":  "y",   "r":  "r",   "l": "l",   "w": "w",
}

VOWEL_MAP = {
    "a": "a",  "ã": "A",
    "e": "e",  "ẽ": "E",
    "i": "i",  "ĩ": "I",
    "o": "o",  "õ": "O",
    "u": "u",  "ũ": "U",
    "ɛ": "ae", "ø": "oe", "y": "ue",
}

TONE_MAP = {"55": "55", "53": "53", "13": "13", "12": "12"}


def map_syllable(on, vo, tone):
    """(声母, 韵母, 声调) -> 映射后的 token 列表

    与普通话一致的「声母 + 韵母带调」两段式：
        (h, ĩ, 55) -> ["Th", "TI55"]
    零声母退化为一段：
        ("", a, 55) -> ["Ta55"]
    """
    out = []
    if on:
        out.append(SYM_PREFIX + ONSET_MAP[on])
    out.append(SYM_PREFIX + VOWEL_MAP[vo] + TONE_MAP[tone])
    return out


def load_sibling(name, filename):
    """加载同目录脚本（文件名以数字开头，无法直接 import）"""
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


P02 = load_sibling("tib_parse_syllable", "02_parse_syllable.py")
P04 = load_sibling("tib_wylie_to_phoneme", "04_wylie_to_phoneme.py")


def token_to_ipa(tok):
    """Wylie token -> (音素片段列表, 结构列表, 备注列表)

    结构列表与音素片段一一对应：藏语单元记 (声母, 韵母, 声调)，
    非藏语/未解析单元记 None。
    """
    parts, structs, notes = [], [], []
    for unit, kind in P02.split_token(tok):
        if kind not in P02.TIBETAN_KINDS:
            parts.append(f"⟨{kind}:{unit}⟩")
            structs.append(None)
            notes.append(kind)
            continue
        st, probs = P02.parse_syllable(unit)
        if st is None or probs:
            parts.append(f"⟨bad:{unit}⟩")
            structs.append(None)
            notes.append("未解析")
            continue
        on, vo, tone, ns = P04.syllable_parts(st)
        if not vo:
            parts.append(f"⟨bad:{unit}⟩")
            structs.append(None)
            notes.append("空音素")
            continue
        parts.append(f"{on}{vo}{tone}")
        structs.append((on, vo, tone))
        notes.extend(ns)
    return parts, structs, notes


def sentence_to_ipa(wylie):
    """整句 Wylie -> (IPA 串, 结构列表, 备注列表)"""
    parts, structs, notes = [], [], []
    for tok in wylie.split():
        p, s, n = token_to_ipa(tok)
        parts.extend(p)
        structs.extend(s)
        notes.extend(n)
    return " ".join(parts), structs, notes


def main(argv=None):
    ap = argparse.ArgumentParser(description="句子级 Wylie -> 音素转写")
    ap.add_argument("--data-root", default=os.environ.get("TIBETAN_DATA_ROOT", DEFAULT_ROOT))
    ap.add_argument("--out-list", default=os.path.join(HERE, "音素索引.list"),
                    help="三列对照 list 的输出位置")
    ap.add_argument("--sample", type=int, default=40, help="展示的对照样例条数")
    ap.add_argument("--drop-flags", default="",
                    help="逗号分隔的 flag 名，命中即整句丢弃（如 foreign / foreign,num）；"
                         "默认空 = 全部保留")
    ap.add_argument("--emit-mapped", action="store_true",
                    help="额外产出 音素索引_v2.list（第 4 列 = ASCII 映射串）"
                         "和 音素映射表.tsv")
    ap.add_argument("--map-sep", default="-",
                    help="映射串里音节内各 token 的分隔符（默认 -，便于可视化）；"
                         "送进 GPT-SoVITS 训练前需换成空格")
    args = ap.parse_args(argv)
    drop_set = {s.strip() for s in args.drop_flags.split(",") if s.strip()}

    ann = os.path.join(args.data_root, "prepared", "annotations.tsv")
    if not os.path.exists(ann):
        print(f"[FAIL] 找不到 {ann}，请先运行 01_build_annotations.py")
        return 1

    todo_units = set()
    todo_path = os.path.join(args.data_root, "prepared", "phoneme_todo.tsv")
    if os.path.exists(todo_path):
        with open(todo_path, encoding="utf-8") as f:
            todo_units = {r["unit"] for r in csv.DictReader(f, delimiter="\t")}

    rows, list_lines, mapped_lines = [], [], []
    note_counter = collections.Counter()
    bad_counter = collections.Counter()
    drop_counter = collections.Counter()
    onset_cnt = collections.Counter()
    vowel_cnt = collections.Counter()
    tone_cnt = collections.Counter()
    all_cps = set()
    n_syl_total = n_todo_hit = 0
    n_with_foreign = n_bad_sent = n_dropped = n_unmapped = 0

    with open(ann, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            wylie = r["wylie_norm"]
            ipa, structs, notes = sentence_to_ipa(wylie)
            wav = os.path.join(args.data_root, WAV_SUBDIR, r["audio"])
            all_cps.update(c for c in ipa if not c.isspace())

            foreign = [n for n in notes if n in P02.OTHER_KINDS]
            bad = [n for n in notes if n in ("未解析", "空音素")]

            hit = sorted(set(foreign) & drop_set)
            if hit:
                n_dropped += 1
                drop_counter.update(hit)
                continue

            for tok in wylie.split():
                for unit, kind in P02.split_token(tok):
                    if kind in P02.TIBETAN_KINDS:
                        n_syl_total += 1
                        if unit in todo_units:
                            n_todo_hit += 1

            if foreign:
                n_with_foreign += 1
            if bad:
                n_bad_sent += 1
            for n in notes:
                note_counter[n] += 1
                if n in ("未解析", "空音素"):
                    bad_counter[n] += 1

            rows.append({
                "idx": r["idx"], "split": r["split"], "audio": r["audio"],
                "duration": r["duration"], "wylie": wylie, "ipa": ipa,
                "n_note": len(notes),
                "flags": ",".join(sorted(set(foreign))) if foreign else "",
            })
            list_lines.append(f"{wav}|{wylie}|{ipa}")

            if args.emit_mapped:
                segs = []
                for s in structs:
                    if s is None:
                        segs.append("<?>")
                        n_unmapped += 1
                        continue
                    onset_cnt[s[0]] += 1
                    vowel_cnt[s[1]] += 1
                    tone_cnt[s[2]] += 1
                    segs.append(args.map_sep.join(map_syllable(*s)))
                mapped_lines.append(f"{wav}|{wylie}|{ipa}|{' '.join(segs)}")

    prepared = os.path.join(args.data_root, "prepared")
    out_tsv = os.path.join(prepared, "phoneme_transcript.tsv")
    with open(out_tsv, "w", encoding="utf-8", newline="") as f:
        wtr = csv.DictWriter(f, delimiter="\t", fieldnames=[
            "idx", "split", "audio", "duration", "wylie", "ipa", "n_note", "flags"])
        wtr.writeheader()
        wtr.writerows(rows)

    os.makedirs(os.path.dirname(args.out_list), exist_ok=True)
    with open(args.out_list, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(list_lines) + "\n")

    v2_path = tbl_path = None
    if args.emit_mapped:
        v2_path = os.path.join(HERE, "音素索引_v2.list")
        with open(v2_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(mapped_lines) + "\n")

        tbl_path = os.path.join(HERE, "音素映射表.tsv")
        NOTE = {"onset": "独立 token",
                "vowel": "与声调拼成 1 个 token（如 TA + 55 = TA55）",
                "tone": "拼在韵母 token 末尾"}
        with open(tbl_path, "w", encoding="utf-8", newline="") as f:
            wtr = csv.writer(f, delimiter="\t")
            wtr.writerow(["kind", "ipa", "ascii", "count", "note"])
            for kind, mp, cnt in (("onset", ONSET_MAP, onset_cnt),
                                  ("vowel", VOWEL_MAP, vowel_cnt),
                                  ("tone", TONE_MAP, tone_cnt)):
                # 声调不单独成 token，它拼在韵母代号末尾，故不加 T 前缀
                pre = "" if kind == "tone" else SYM_PREFIX
                for ipa, asc in mp.items():
                    note = "零声母，不产出 token" if (kind == "onset" and not asc) else NOTE[kind]
                    wtr.writerow([kind, ipa if ipa else "(零声母)",
                                  pre + asc if asc else "-",
                                  cnt.get(ipa, 0), note])

    print(f"语料根目录 : {args.data_root}")
    print(f"句子       : {len(rows)}")
    if drop_set:
        detail = "、".join(f"{k}×{v}" for k, v in sorted(drop_counter.items()))
        print(f"  已丢弃     : {n_dropped}（--drop-flags {args.drop_flags}；{detail}）")
    print(f"  含非藏语成分 : {n_with_foreign}"
          f"（{n_with_foreign / max(len(rows), 1) * 100:.1f}%，多为梵文/数字）")
    print(f"  含未解析单元 : {n_bad_sent}")
    print()
    kept_cps = {c for r in rows for c in r["ipa"] if not c.isspace()}
    print(f"符号集     : 保留后 {len(kept_cps)} 个（全量 {len(all_cps)} 个）")
    if drop_set and all_cps - kept_cps:
        gone = sorted(all_cps - kept_cps)
        print(f"  只出现在被丢弃句中 : {len(gone)} 个 -> "
              f"{' '.join(gone[:30])}{' ...' if len(gone) > 30 else ''}")
    print()
    print(f"藏语音节总数 : {n_syl_total}")
    print(f"  命中元音变音缺口 : {n_todo_hit}"
          f"（{n_todo_hit / max(n_syl_total, 1) * 100:.1f}%"
          f"，这些音节当前用的是未修正的读音）")
    print()
    print("== 备注分布 top12（音节级） ==")
    for k, v in note_counter.most_common(12):
        print(f"  {k:14s} {v}")
    print()
    print(f"== 对照样例（前 {args.sample} 句） ==")
    for r in rows[:args.sample]:
        print(f"  {r['audio']}")
        print(f"    Wylie : {r['wylie']}")
        print(f"    IPA   : {r['ipa']}")
    print()
    print(f"产出: {out_tsv}")
    print(f"      {args.out_list}")
    if args.emit_mapped:
        n_unit = len(ONSET_MAP) + len(VOWEL_MAP) + len(TONE_MAP)
        print(f"      {v2_path}")
        print(f"      {tbl_path}")
        print(f"  映射单元 : {len(ONSET_MAP)} 声母 + {len(VOWEL_MAP)} 韵母 "
              f"+ {len(TONE_MAP)} 声调 = {n_unit} 个"
              f"（音节内分隔符 {args.map_sep!r}）")
        # 双射自检：韵母+声调的组合不得碰撞，否则反查会丢信息
        combos = {VOWEL_MAP[v] + TONE_MAP[t] for v in VOWEL_MAP for t in TONE_MAP}
        if len(combos) != len(VOWEL_MAP) * len(TONE_MAP):
            print("  [WARN] 韵母+声调组合存在碰撞，映射不是双射")
        else:
            print("  双射自检 : 通过（韵母×声调 组合无碰撞）")
        if n_unmapped:
            print(f"  [WARN] 未映射单元 {n_unmapped} 个（应为 0）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
