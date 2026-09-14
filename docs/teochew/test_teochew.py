# -*- coding: utf-8 -*-
"""潮汕话集成验证脚本 (运行: cd GPT_SoVITS && python ../docs/teochew/test_teochew.py)"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "GPT_SoVITS"))

ok = True
def check(name, cond, detail=""):
    global ok
    mark = "PASS" if cond else "FAIL"
    if not cond:
        ok = False
    print(f"[{mark}] {name} {detail}")

# 1. symbols2 包含全部 teochew 音素
from text import symbols2
teochew_in_symbols = [s for s in symbols2.teochew_symbols if s in symbols2.symbols]
check("symbols2.symbols 包含全部 teochew 音素",
      len(teochew_in_symbols) == len(symbols2.teochew_symbols),
      f"({len(teochew_in_symbols)}/{len(symbols2.teochew_symbols)})")

# 2. teochew.g2p 输出
from text import teochew
test_text = "一念之慈"
phones, word2ph = teochew.g2p(test_text)
print(f"    g2p('{test_text}') -> {phones}  word2ph={word2ph}")
check("g2p 输出非空", len(phones) > 0)
check("len(phones)==sum(word2ph)", len(phones) == sum(word2ph))
check("len(word2ph)==len(字符数)", len(word2ph) == len(test_text))
unknown = [p for p in phones if p == "UNK"]
check("无 UNK (词典覆盖)", len(unknown) == 0, f"UNK数={len(unknown)}")
not_in_symbols = [p for p in phones if p not in symbols2.symbols]
check("g2p 输出全部在 symbols2.symbols 中", len(not_in_symbols) == 0, f"缺失={not_in_symbols}")

# 3. 词典覆盖率
from text.teochew import _load_char_dict, _load_syllable_split, _load_valid_phones
cd = _load_char_dict()
ss = _load_syllable_split()
vp = _load_valid_phones()
print(f"    汉字词典: {len(cd)} 字 | 音节拆分表: {len(ss)} 音节 | 音素白名单: {len(vp)}")
check("汉字词典非空", len(cd) > 0)
check("音节拆分表非空", len(ss) > 0)
check("白名单含停顿符", {"sil","silv","ds","ts"}.issubset(vp))

# 4. cleaner 全链路
from text.cleaner import clean_text
res = clean_text(test_text, "teochew")
print(f"    clean_text('{test_text}','teochew') -> phones={res[0]}")
check("clean_text 返回三元组", isinstance(res, tuple) and len(res) == 3)
check("clean_text phones 全在符号集", all(p in symbols2.symbols for p in res[0]),
      f"phones={res[0]}")

print()
print("总体:", "全部通过" if ok else "存在失败项")
sys.exit(0 if ok else 1)
