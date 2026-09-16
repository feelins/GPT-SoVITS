# -*- coding: utf-8 -*-
import os
p = r"E:\008-datasets\mcv-scripted-nan-tw-v23.0\cv-corpus-23.0-2025-09-05\nan-tw\single_speaker\train.list"
lines = open(p, encoding="utf-8").read().splitlines()[:3]
out = ["=== train.list 前3行 (格式: 路径|spk|yue|汉字) ===", ""]
for ln in lines:
    out.append(ln)
# 检查是否还有台罗括号残留
bad = [ln for ln in open(p, encoding="utf-8").read().splitlines() if "（" in ln or "）" in ln]
out.append("")
out.append(f"含残留括号的行数: {len(bad)}")
open("E:/008-datasets/_tmp/check_train.txt", "w", encoding="utf-8").write("\n".join(out))
