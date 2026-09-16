# -*- coding: utf-8 -*-
import csv, collections, re, unicodedata, os
BASE = os.path.dirname(os.path.abspath(__file__))
f = os.path.join(BASE, "single_speaker", "syllable_map.tsv")
cnt = collections.Counter()
with open(f, encoding="utf-8-sig") as fh:
    for r in csv.DictReader(fh):
        if r["flag"] in ("UNKNOWN_RHYME", "UNKNOWN"):
            cnt[(r["tailo_syllable"], r["jyutping"])] += int(r["count"])
out = []
for (syl, jy), n in cnt.most_common(120):
    out.append(f"{n:5d}  {syl}  ->  {jy}")
out.append(f"=== 未知总数(行次合计): {sum(cnt.values())}  不同未知音节: {len(cnt)}")
with open("E:/008-datasets/_tmp/unknown_syllables.txt", "w", encoding="utf-8") as g:
    g.write("\n".join(out))
