#!/usr/bin/env python3
"""
One-time script to extract word->CMUdict mapping from the full Manchu dictionary.
Run from any directory; produces manchu_cmudict.txt next to this file.
"""
import os

SRC = '/Users/feelins/works/CharsiuG2P/src_manchu/data/满语常用词典20251228_add_corpus_划分音节版_G2P版_v4_english.txt'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'manchu_cmudict.txt')

written = 0
with open(SRC, encoding='utf-8') as fin, open(OUT, 'w', encoding='utf-8') as fout:
    for line in fin:
        parts = line.strip().split('\t')
        if len(parts) >= 3:
            word = parts[0].strip()
            cmu  = parts[2].strip()
            fout.write(f"{word}\t{cmu}\n")
            written += 1

print(f"Done: {written} entries written to {OUT}")

# Spot-check words from sentence 00000003
d = {}
with open(OUT, encoding='utf-8') as f:
    for row in f:
        w, c = row.strip().split('\t', 1)
        d[w] = c

test_words = (
    'ere be age de bumbi tere deu si a laubdu ningge '
    'aijige komso ning ge amba oho beye bahambi aijigen '
    'eniye ama dahvha jiyalaktan suwen ji faili er jiu sin bi'
).split()
missing = [w for w in test_words if w not in d]
print(f"Missing words: {missing if missing else 'none - full coverage!'}")
