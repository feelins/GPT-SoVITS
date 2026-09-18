#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""藏语阶段二（预备）：Wylie 音节结构解析 + 黏着语素切分

两级处理：

    ① 黏着语素切分  —— token 并不等于音节
        pa'i      -> pa + 'i          属格 འི
        spre'us   -> spre + 'us       指小 འུ + 具格 ས
        na'ang    -> na + 'ang        འང "也"
        byungba   -> byung + ba       名物化
        1959lo'i  -> 1959 + lo + 'i   数字 + 属格

    ② 结构解析      —— 拆成正字法 7 个位置
        前加字 + 上加字 + 基字 + 下加字 + 元音 + 后加字 + 再后加字
        bsgyur -> b(前) s(上) g(基) y(下) u(元) r(后)
        byin   ->        b(基) y(下) i(元) n(后)

非藏语成分（梵文叠字 `+`、阿拉伯数字、英文专名音译）不做结构解析，
单独分类标记，避免污染音素表。

本脚本只做结构解析，**不做发音推导**（阶段二主体）。

输入 : <DATA_ROOT>/prepared/vocab_syllable.tsv     （阶段一产物）
输出 : <DATA_ROOT>/prepared/syllable_structure.tsv  单元级（去重累加）
       <DATA_ROOT>/prepared/token_split.tsv         token 级切分结果
"""

import argparse
import collections
import csv
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_ROOT = r"E:\008-datasets\藏语-疑问"

VOWELS = "aeiou"

PREFIX = ["g", "d", "b", "m", "'"]                                  # 前加字 སྔོན་འཇུག
SUPER = ["r", "l", "s"]                                              # 上加字 མགོ་ཅན
BASE = [                                                             # 基字 མིང་གཞི
    "tsh", "dz", "zh", "kh", "ph", "th", "ng", "ny", "ts",
    "k", "g", "c", "ch", "j", "t", "d", "n", "p", "b", "m",
    "w", "z", "'", "y", "r", "l", "sh", "s", "h", "a",
]
SUB = ["y", "r", "l", "w"]                                           # 下加字 འདོགས་ཅན
SUFFIX = ["ng", "g", "d", "n", "b", "m", "'", "r", "l", "s"]         # 后加字 རྗེས་འཇུག
SUFFIX2 = ["s", "d"]                                                 # 再后加字 ཡང་འཇུག

# 黏着助词：按长度降序，贪心最长匹配
ENCLITICS = ["'ang", "'am", "'us", "'i", "'u", "'o", "'e"]
# 名物化 / 助动词后缀：切分前提是词干能被解析为合法音节
PARTICLES = ["bas", "bar", "ba"]

# 需要参与藏语结构解析的类别
TIBETAN_KINDS = {"syllable", "clitic", "particle"}
# 不参与结构解析的类别
OTHER_KINDS = {"num", "sanskrit", "foreign"}


def parse_onset(p):
    """解析元音之前的部分 -> (前加字, 上加字, 基字, 下加字)

    Wylie 拼写顺序为 前加字 + 上加字 + 基字 + 下加字，但两种辅音位置都会
    和基字本身混淆，需要分别处理：

      · 上加字 r/l/s 若出现，必在**最左**（其后还须有基字）
            rlung -> 上r + 基l      而非 基r + 下l
            slob  -> 上s + 基l
      · 下加字 y/r/l/w 在**最右**，最多两个
            grwa  -> 基g + 下rw     （གྲྭ）
            phywa -> 基ph + 下yw
      · 前加字在最左，上加字紧邻基字之左
            bsgyur -> 前b + 上s + 基g + 下y
    """
    if not p:
        return "", "", "", ""

    def take_subs(s):
        subs = []
        while len(s) > 1 and s[-1] in SUB and len(subs) < 2:
            subs.insert(0, s[-1])
            s = s[:-1]
        return "".join(subs), s

    def take_base(s):
        for b in sorted(BASE, key=lambda x: -len(x)):
            if s.endswith(b):
                return b, s[: -len(b)]
        return "", s

    if len(p) >= 2 and p[0] in SUPER:
        # 上加字 + 基字 [+ 下加字]，此时不存在前加字
        sup, rest = p[0], p[1:]
        sub, rest = take_subs(rest)
        base, rest = take_base(rest)
        return "", sup, base, sub

    sub, rest = take_subs(p)
    base, rest = take_base(rest)
    sup = ""
    if rest and rest[-1] in SUPER:
        sup = rest[-1]
        rest = rest[:-1]
    return rest, sup, base, sub


def parse_coda(s):
    """解析元音之后的部分 -> (后加字, 再后加字)"""
    if not s:
        return "", ""
    if s.startswith("ng"):
        return "ng", s[2:]
    return s[0], s[1:]


def parse_syllable(s):
    """解析单个藏语音节 -> (结构字典, 问题列表)

    零声母 ཨ 的处理：Wylie 中基字 a 后不再重复写元音 a，
    因此 `ang` = 基字 a + 元音 a(隐含) + 后加字 ng，而非 a + ng 无元音。
    """
    if not s:
        return None, ["空"]
    problems = []

    if s[0] == "a" and (len(s) == 1 or s[1] not in VOWELS):
        # 零声母 ཨ：a 同时充当基字，元音 a 隐含
        pre, sup, base, sub, vowel, coda = "", "", "a", "", "a", s[1:]
    else:
        i = -1
        for j, c in enumerate(s):
            if c in VOWELS:
                i = j
                break
        if i < 0:
            return None, ["无元音"]
        pre, sup, base, sub = parse_onset(s[:i])
        vowel, coda = s[i], s[i + 1:]

    suf, suf2 = parse_coda(coda)

    # 基字缺失：仅在零声母（无前加、无上加）时允许，如 in / i
    if not base and (pre or sup):
        problems.append("无基字")
    if pre and pre not in PREFIX:
        problems.append(f"非法前加字[{pre}]")
    if sup and sup not in SUPER:
        problems.append(f"非法上加字[{sup}]")
    for c in sub:
        if c not in SUB:
            problems.append(f"非法下加字[{c}]")
    if suf and suf not in SUFFIX:
        problems.append(f"非法后加字[{suf}]")
    if suf2 and suf2 not in SUFFIX2:
        problems.append(f"非法再后加字[{suf2}]")

    return {
        "prefix": pre, "super": sup, "base": base, "sub": sub,
        "vowel": vowel, "suffix": suf, "suffix2": suf2,
    }, problems


def split_token(tok):
    """把 token 切成若干单元 -> [(unit, kind), ...]

    kind: syllable / clitic / particle / num / sanskrit / foreign
    """
    if not tok:
        return []

    # 1) 阿拉伯数字前缀（年份、日期）：1959lo'i -> 1959 + lo'i
    m = re.match(r"^(\d+)(.+)$", tok)
    if m:
        return [(m.group(1), "num")] + split_token(m.group(2))

    # 2) 梵文叠字标记 + ：pan+di / g+haram，不按藏语正字法解析
    if "+" in tok:
        return [(tok, "sanskrit")]

    # 3) 黏着助词（最长匹配）
    for e in ENCLITICS:
        if tok.endswith(e) and len(tok) > len(e):
            return split_token(tok[: -len(e)]) + [(e, "clitic")]

    # 4) 名物化后缀：仅当词干本身是合法音节时才切，避免误伤 ba / bar 等普通音节
    for e in PARTICLES:
        if tok.endswith(e) and len(tok) > len(e):
            stem = tok[: -len(e)]
            st, probs = parse_syllable(stem)
            if st is not None and not probs:
                return [(stem, "syllable"), (e, "particle")]

    # 5) 普通音节
    st, probs = parse_syllable(tok)
    if st is not None and not probs:
        return [(tok, "syllable")]

    # 6) 英文专名音译 / 噪声
    return [(tok, "foreign")]


UNIT_FIELDS = ["unit", "kind", "count", "prefix", "super", "base", "sub",
               "vowel", "suffix", "suffix2", "ok", "problems"]
TOKEN_FIELDS = ["token", "count", "n_units", "units", "kinds", "ok", "problems"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Wylie 音节结构解析 + 黏着语素切分")
    ap.add_argument("--data-root", default=os.environ.get("TIBETAN_DATA_ROOT", DEFAULT_ROOT))
    ap.add_argument("--show-foreign", action="store_true", help="列出被判为外来词的样例")
    args = ap.parse_args(argv)

    vocab_path = os.path.join(args.data_root, "prepared", "vocab_syllable.tsv")
    if not os.path.exists(vocab_path):
        print(f"[FAIL] 找不到 {vocab_path}，请先运行阶段一 01_build_annotations.py")
        return 1

    with open(vocab_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    print(f"读入 token: {len(rows)}")

    unit_stat = collections.defaultdict(lambda: {"count": 0, "ok": 0, "problems": ""})
    token_rows = []
    tok_class = collections.Counter()
    kind_unit = collections.Counter()
    unit_token_total = 0
    unit_ok_total = 0
    prob_counter = collections.Counter()
    base_counter = collections.Counter()
    sub_counter = collections.Counter()
    sup_counter = collections.Counter()
    pre_counter = collections.Counter()
    suf_counter = collections.Counter()
    foreign_samples = []

    for r in rows:
        tok, cnt = r["syllable"], int(r["count"])
        units = split_token(tok)
        kinds = [k for _, k in units]
        tok_problems = []
        tok_ok = True

        for u, kind in units:
            kind_unit[kind] += cnt
            if kind in TIBETAN_KINDS:
                st, probs = parse_syllable(u)
                unit_token_total += cnt
                ok = not probs
                if ok:
                    unit_ok_total += cnt
                else:
                    tok_problems.append(f"{u}:{';'.join(probs)}")
                    tok_ok = False
                    for p in probs:
                        prob_counter[p.split("[")[0]] += 1
                rec = unit_stat[u]
                rec["count"] += cnt
                rec["kind"] = kind
                rec["ok"] = int(ok)
                rec["problems"] = ";".join(probs)
                if st:
                    rec.update({k: v for k, v in st.items()})
                    if st["base"]:
                        base_counter[st["base"]] += cnt
                    if st["sub"]:
                        sub_counter[st["sub"]] += cnt
                    if st["super"]:
                        sup_counter[st["super"]] += cnt
                    if st["prefix"]:
                        pre_counter[st["prefix"]] += cnt
                    if st["suffix"]:
                        suf_counter[st["suffix"]] += cnt
            else:
                if kind == "foreign":
                    foreign_samples.append((u, cnt))
                rec = unit_stat[u]
                rec["count"] += cnt
                rec["kind"] = kind
                rec["ok"] = ""
                rec["problems"] = ""

        non_tib = [k for k in kinds if k in OTHER_KINDS]
        tok_class[non_tib[0] if non_tib else "pure_tibetan"] += cnt
        token_rows.append({
            "token": tok, "count": cnt, "n_units": len(units),
            "units": "|".join(u for u, _ in units),
            "kinds": "|".join(kinds), "ok": int(tok_ok),
            "problems": ";".join(tok_problems),
        })

    prepared = os.path.join(args.data_root, "prepared")
    out_unit = os.path.join(prepared, "syllable_structure.tsv")
    with open(out_unit, "w", encoding="utf-8", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=UNIT_FIELDS, delimiter="\t")
        wtr.writeheader()
        for u, rec in sorted(unit_stat.items(), key=lambda x: -x[1]["count"]):
            wtr.writerow({
                "unit": u, "kind": rec["kind"], "count": rec["count"],
                "prefix": rec.get("prefix", ""), "super": rec.get("super", ""),
                "base": rec.get("base", ""), "sub": rec.get("sub", ""),
                "vowel": rec.get("vowel", ""), "suffix": rec.get("suffix", ""),
                "suffix2": rec.get("suffix2", ""),
                "ok": rec["ok"], "problems": rec["problems"],
            })

    out_token = os.path.join(prepared, "token_split.tsv")
    with open(out_token, "w", encoding="utf-8", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=TOKEN_FIELDS, delimiter="\t")
        wtr.writeheader()
        wtr.writerows(token_rows)

    n_unit = len(unit_stat)
    tib_units = sum(1 for r in unit_stat.values() if r["kind"] in TIBETAN_KINDS)
    tib_ok = sum(1 for r in unit_stat.values() if r["kind"] in TIBETAN_KINDS and r["ok"] == 1)

    print()
    print("== token 处理结果 ==")
    tt = sum(tok_class.values())
    for k, v in tok_class.most_common():
        print(f"  {k:14s} {v:6d}  ({v / tt * 100:5.2f}%)")
    print()
    print("== 单元级类别分布（频次累加） ==")
    tu = sum(kind_unit.values())
    for k, v in kind_unit.most_common():
        print(f"  {k:14s} {v:6d}  ({v / tu * 100:5.2f}%)")
    print()
    print("== 单元级 ==")
    print(f"  单元总数 {n_unit}，其中需藏语结构解析 {tib_units}")
    print(f"  藏语单元解析成功 {tib_ok}/{tib_units} ({tib_ok / tib_units * 100:.1f}%)")
    print(f"  按 token 覆盖     {unit_ok_total}/{unit_token_total} "
          f"({unit_ok_total / unit_token_total * 100:.1f}%)")

    if prob_counter:
        print()
        print("  剩余问题:")
        for k, v in prob_counter.most_common(10):
            print(f"    {k:16s} {v}")
        print("  未解析单元样例:")
        bad = [(u, r) for u, r in unit_stat.items()
               if r["kind"] in TIBETAN_KINDS and r["ok"] == 0]
        for u, r in sorted(bad, key=lambda x: -x[1]["count"])[:20]:
            print(f"    {u:16s} x{r['count']:<6d} {r['problems']}")

    if args.show_foreign and foreign_samples:
        print()
        print("  foreign 样例:")
        for u, c in sorted(foreign_samples, key=lambda x: -x[1])[:25]:
            print(f"    {u:20s} x{c}")

    print()
    print("== 结构分布（藏语单元） ==")
    print(f"  基字 top12 : {[(b, c) for b, c in base_counter.most_common(12)]}")
    print(f"  下加字     : {dict(sub_counter)}")
    print(f"  上加字     : {dict(sup_counter)}")
    print(f"  前加字     : {dict(pre_counter)}")
    print(f"  后加字     : {dict(suf_counter)}")
    print()
    print(f"  产出: {out_unit}")
    print(f"        {out_token}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
