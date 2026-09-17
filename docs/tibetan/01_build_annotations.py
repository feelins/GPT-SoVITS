#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""藏语（Tibetan）语料 · 阶段一：基础整合

作用
----
把数据盘上的 6 个 tsv（train/valid/test × uni/wylie）与音频对齐，合并成一份
统一标注表，并导出音节表。**只做整合与体检，不做训练/验证切分。**

数据来源（不入库，留在 E:\\008-datasets\\藏语-疑问）
------------------------------------------------
SP02 单一说话人朗读语料，5878 句，约 6.57 小时，单声道 16 kHz / 16 bit wav。

    <split>-uni.tsv      藏文 Unicode 转写
    <split>-wylie.tsv    Wylie 拉丁转写（正字法，非音标）

产物（同样留在数据盘）
----------------------
    <DATA_ROOT>/prepared/annotations.tsv      合并后的全量标注
    <DATA_ROOT>/prepared/vocab_syllable.tsv  音节表（阶段二建音素映射的输入）

设计约定
--------
1. 音频与产物一律留在数据盘，本仓库只保存脚本与文档。
2. 保留来源 split 列方便追溯，但本阶段**不生成 train/val 切分**。
3. Wylie 是正字法转写而非音标，本阶段只整理，不做音素推导。
4. 只标记噪声（digit / cjk / stack），不静默丢数据，过滤决策交给后续阶段。

用法
----
    python 01_build_annotations.py
    python 01_build_annotations.py --data-root E:\\008-datasets\\藏语-疑问
    $env:TIBETAN_DATA_ROOT = 'E:\\008-datasets\\藏语-疑问'; python 01_build_annotations.py
"""

import argparse
import collections
import csv
import glob
import os
import re
import sys
import wave

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_ROOT = r"E:\008-datasets\藏语-疑问"
SPLITS = ["train", "valid", "test"]

# 需要识别的噪声来源
DIGIT_RE = re.compile(r"\d")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
QUOTES = "\u201c\u201d\u2018\u2019\u300c\u300d\u300e\u300f"
STRIP = set(QUOTES + '".,!?;:()[]{}<>\u2014-\u2026\u3001\u3002\uff0c\uff1b\uff1a\uff01\uff1f \t')

ANNOTATION_FIELDS = [
    "idx", "split", "audio", "duration", "sample_rate",
    "n_syl_uni", "n_syl_wylie", "sync_ok", "flags",
    "uni_text", "wylie_norm", "wylie_raw",
]


# ----------------------------------------------------------------------------
# 读取
# ----------------------------------------------------------------------------
def read_tsv(path):
    """读取 <idx>\\t<audio>\\t<sentence> 形式的 tsv，跳过表头。"""
    out = []
    with open(path, encoding="utf-8") as f:
        next(f, None)
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            out.append((parts[0], parts[1], parts[2]))
    return out


def load_annotations(root):
    uni, wylie = {}, {}
    for sp in SPLITS:
        u_path = os.path.join(root, f"{sp}-uni.tsv")
        w_path = os.path.join(root, f"{sp}-wylie.tsv")
        if os.path.exists(u_path):
            for idx, audio, sent in read_tsv(u_path):
                uni[audio] = (sp, idx, sent)
        if os.path.exists(w_path):
            for idx, audio, sent in read_tsv(w_path):
                wylie[audio] = (sp, idx, sent)
    return uni, wylie


# ----------------------------------------------------------------------------
# 文本处理
# ----------------------------------------------------------------------------
def normalize_wylie(text):
    """Wylie 归一化：引号两侧补空格（修 'dug\"ces 这类黏连），折叠空白。

    保留 `'`(a-chung) 与 `+`(梵文叠字)，它们是 Wylie 的合法成分，不是噪声。
    """
    t = re.sub("([" + QUOTES + '"])', r" \1 ", text)
    return re.sub(r"\s+", " ", t).strip()


def tokenize_wylie(text):
    return [w for w in (x.strip("".join(STRIP)) for x in text.split()) if w]


def tokenize_uni(text):
    """藏文按 \\u0f0b(་) / 空白 / །༎ 切分。"""
    return [w for w in (x.strip("".join(STRIP)) for x in re.split(r"[\s\u0f0b\u0f0d\u0f0e]+", text)) if w]


def flags_of(tokens):
    """返回该句携带的噪声标记，多个用 | 连接，无噪声为空串。"""
    flags = []
    if any(DIGIT_RE.search(t) for t in tokens):
        flags.append("digit")
    if any(CJK_RE.search(t) for t in tokens):
        flags.append("cjk")
    if any("+" in t for t in tokens):
        flags.append("stack")
    return "|".join(flags)


# ----------------------------------------------------------------------------
# 音频
# ----------------------------------------------------------------------------
def scan_audio(root):
    """返回 {文件名: (时长秒, 采样率, 声道, 位深)}，不可读则为 None。"""
    info = {}
    for p in glob.glob(os.path.join(root, "wav", "**", "*.wav"), recursive=True):
        name = os.path.basename(p)
        try:
            with wave.open(p, "rb") as f:
                rate = f.getframerate() or 1
                info[name] = (f.getnframes() / rate, f.getframerate(), f.getnchannels(), f.getsampwidth())
        except Exception:
            info[name] = None
    return info


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="藏语语料阶段一：基础整合")
    ap.add_argument("--data-root",
                    default=os.environ.get("TIBETAN_DATA_ROOT", DEFAULT_ROOT),
                    help="语料根目录（含 wav/ 与 6 个 tsv）")
    ap.add_argument("--out-dir", default=None, help="产物目录，默认 <data-root>/prepared")
    ap.add_argument("--min-duration", type=float, default=0.5, help="体检用的最短时长（秒），仅统计不删除")
    ap.add_argument("--max-duration", type=float, default=15.0, help="体检用的最长时长（秒），仅统计不删除")
    args = ap.parse_args(argv)

    root = args.data_root
    out_dir = args.out_dir or os.path.join(root, "prepared")

    if not os.path.isdir(root):
        print(f"[FAIL] 数据根目录不存在: {root}")
        return 1

    print(f"数据根目录: {root}")
    print(f"产物目录  : {out_dir}")
    print()

    # 1. 标注
    print("== 1. 读取标注 ==")
    for sp in SPLITS:
        u = os.path.join(root, f"{sp}-uni.tsv")
        w = os.path.join(root, f"{sp}-wylie.tsv")
        u_n = len(read_tsv(u)) if os.path.exists(u) else 0
        w_n = len(read_tsv(w)) if os.path.exists(w) else 0
        mark = "" if u_n == w_n else "   <-- 数量不一致"
        print(f"   {sp}: uni={u_n}  wylie={w_n}{mark}")
    uni, wylie = load_annotations(root)
    print(f"   合计: 藏文 {len(uni)} 条 / Wylie {len(wylie)} 条")

    # 2. 音频
    print()
    print("== 2. 扫描音频 ==")
    audio = scan_audio(root)
    readable = [v for v in audio.values() if v]
    print(f"   wav 文件: {len(audio)}   可读: {len(readable)}   损坏: {len(audio) - len(readable)}")
    if readable:
        _, rate, ch, sw = readable[0]
        print(f"   格式: {rate} Hz / {ch}ch / {sw * 8}bit")

    # 3. 整合
    print()
    print("== 3. 整合 ==")
    records = []
    miss_audio, miss_uni, miss_wylie = [], [], []

    order = sorted(set(uni) | set(wylie))
    for i, name in enumerate(order):
        u = uni.get(name)
        w = wylie.get(name)
        if u is None:
            miss_uni.append(name)
            continue
        if w is None:
            miss_wylie.append(name)
            continue
        a = audio.get(name)
        if not a:
            miss_audio.append(name)
            continue

        dur, rate, ch, sw = a
        sp = u[0]
        uni_text = u[2].strip()
        wylie_raw = w[2].strip()
        wylie_norm = normalize_wylie(wylie_raw)
        uni_toks = tokenize_uni(uni_text)
        wylie_toks = tokenize_wylie(wylie_norm)

        records.append({
            "idx": i,
            "split": sp,
            "audio": name,
            "duration": round(dur, 3),
            "sample_rate": rate,
            "n_syl_uni": len(uni_toks),
            "n_syl_wylie": len(wylie_toks),
            "sync_ok": int(len(uni_toks) == len(wylie_toks)),
            "flags": flags_of(wylie_toks),
            "uni_text": uni_text,
            "wylie_norm": wylie_norm,
            "wylie_raw": wylie_raw,
            "_toks": wylie_toks,
        })

    print(f"   可整合记录: {len(records)}")
    if miss_uni:
        print(f"   缺藏文转写: {len(miss_uni)}  例: {miss_uni[:3]}")
    if miss_wylie:
        print(f"   缺 Wylie  : {len(miss_wylie)}  例: {miss_wylie[:3]}")
    if miss_audio:
        print(f"   缺/坏音频 : {len(miss_audio)}  例: {miss_audio[:3]}")

    if not records:
        print("[FAIL] 没有可整合的记录")
        return 1

    # 4. 音节表
    vocab = collections.Counter()
    for r in records:
        vocab.update(r["_toks"])

    # 5. 写出
    print()
    print("== 4. 写出产物 ==")
    os.makedirs(out_dir, exist_ok=True)

    ann_path = os.path.join(out_dir, "annotations.tsv")
    with open(ann_path, "w", encoding="utf-8", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=ANNOTATION_FIELDS, delimiter="\t",
                             extrasaction="ignore")
        wtr.writeheader()
        wtr.writerows(records)
    print(f"   {ann_path}")

    vocab_path = os.path.join(out_dir, "vocab_syllable.tsv")
    with open(vocab_path, "w", encoding="utf-8", newline="") as f:
        wtr = csv.writer(f, delimiter="\t")
        wtr.writerow(["rank", "syllable", "count", "flags"])
        for rank, (syl, cnt) in enumerate(vocab.most_common(), 1):
            wtr.writerow([rank, syl, cnt, flags_of([syl])])
    print(f"   {vocab_path}")

    # 6. 体检报告
    durations = sorted(r["duration"] for r in records)
    total_dur = sum(durations)

    def pct(p):
        return durations[min(int(len(durations) * p), len(durations) - 1)]

    print()
    print("== 5. 体检报告 ==")
    print(f"   句数        : {len(records)}")
    print(f"   总时长      : {total_dur / 60:.1f} 分钟 ({total_dur / 3600:.2f} 小时)")
    print(f"   时长 P5/中位/P95 : {pct(0.05):.2f}s / {pct(0.5):.2f}s / {pct(0.95):.2f}s")
    print(f"   时长范围    : {durations[0]:.2f}s ~ {durations[-1]:.2f}s")

    too_short = sum(1 for d in durations if d < args.min_duration)
    too_long = sum(1 for d in durations if d > args.max_duration)
    print(f"   短于 {args.min_duration}s : {too_short}    长于 {args.max_duration}s : {too_long}")

    sync_bad = [r for r in records if not r["sync_ok"]]
    print()
    print(f"   藏文/Wylie 音节数一致: {len(records) - len(sync_bad)}/{len(records)}"
          f"  ({(len(records) - len(sync_bad)) / len(records) * 100:.1f}%)")
    for r in sync_bad[:5]:
        print(f"      {r['audio']}: uni={r['n_syl_uni']} wylie={r['n_syl_wylie']}")

    print()
    print("   噪声标记分布:")
    fc = collections.Counter(r["flags"] for r in records if r["flags"])
    for k, v in fc.most_common():
        print(f"      {k or '(无)':16s} {v}")
    clean = sum(1 for r in records if not r["flags"])
    print(f"      无标记(干净)      {clean}")

    print()
    print("   音节表:")
    total_tok = sum(vocab.values())
    print(f"      唯一音节: {len(vocab)}   总 token: {total_tok}")
    cum = 0
    for i, (_, cnt) in enumerate(vocab.most_common(), 1):
        cum += cnt
        if i in (100, 500, 1000, 1500, 2000):
            print(f"      前 {i:5d} 个音节覆盖 {cum / total_tok * 100:5.1f}%")

    print()
    print("   来源 split 分布:")
    for k, v in collections.Counter(r["split"] for r in records).most_common():
        print(f"      {k:8s} {v}")
    print()
    print("   注: 本阶段不生成 train/val 切分，split 列仅用于追溯来源。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
