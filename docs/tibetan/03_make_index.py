#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""藏语语料 · 数据索引：生成 <音频绝对路径>|<Wylie 文本> 的 .list

放进 docs/tibetan/ 与脚本同目录，方便直接查看/贴命令行，不必来回切目录。

行格式：
    E:\\008-datasets\\藏语-疑问\\wav\\wav\\SP02-OTR002-01-A-0001.wav|gangs rin po che nas ...

用法
----
    python 03_make_index.py
    python 03_make_index.py --field uni_text      # 导藏文 Unicode 而非 Wylie
    python 03_make_index.py --out D:\\x.list
"""

import argparse
import csv
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = r"E:\008-datasets\藏语-疑问"
WAV_SUBDIR = os.path.join("wav", "wav")
FIELDS = ["wylie_norm", "wylie_raw", "uni_text"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成音频索引 .list")
    ap.add_argument("--data-root", default=os.environ.get("TIBETAN_DATA_ROOT", DEFAULT_ROOT))
    ap.add_argument("--out", default=os.path.join(HERE, "数据索引.list"))
    ap.add_argument("--field", default="wylie_norm", choices=FIELDS,
                    help="冒号后的文本取哪个字段，默认 wylie_norm")
    ap.add_argument("--check-exists", action="store_true", help="校验音频文件是否存在")
    args = ap.parse_args(argv)

    ann = os.path.join(args.data_root, "prepared", "annotations.tsv")
    if not os.path.exists(ann):
        print(f"[FAIL] 找不到 {ann}，请先运行阶段一 01_build_annotations.py")
        return 1

    lines, missing = [], []
    with open(ann, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            path = os.path.join(args.data_root, WAV_SUBDIR, r["audio"])
            if args.check_exists and not os.path.exists(path):
                missing.append(path)
            lines.append(f"{path}|{r[args.field]}")

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    total_chars = sum(len(x.split("|", 1)[1]) for x in lines)
    print(f"数据根目录 : {args.data_root}")
    print(f"文本字段   : {args.field}")
    print(f"条目       : {len(lines)}")
    print(f"平均长度   : {total_chars / max(len(lines), 1):.1f} 字符/句")
    if args.check_exists:
        print(f"缺失音频   : {len(missing)}")
        for m in missing[:5]:
            print(f"   {m}")
    print(f"产出       : {args.out}")
    print()
    print("前 3 行:")
    for x in lines[:3]:
        print(f"   {x[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
