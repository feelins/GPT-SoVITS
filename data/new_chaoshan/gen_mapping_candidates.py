# -*- coding: utf-8 -*-
"""
gen_mapping_candidates.py
从 prosody_all_log.txt 提取新数据实际使用的音素单元(声母/韵母),
对照 symbols2.teochew_symbols 旧词表, 分类为:
  - AUTO : 可确定映射到旧体系单元
  - AMBIG: 歧义/旧词表缺失, 需人工确认
输出 mapping_auto.txt / mapping_ambiguous.txt 到本目录。
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GPT = os.path.join(ROOT, "GPT_SoVITS")
sys.path.insert(0, os.path.join(GPT, "text"))

from text.symbols2 import teochew_symbols  # 旧体系音素

PROSODY = os.path.join(HERE, "prosody_all_log.txt")
OUT_AUTO = os.path.join(HERE, "mapping_auto.txt")
OUT_AMBIG = os.path.join(HERE, "mapping_ambiguous.txt")

# 旧体系所有单元 (含停顿)
OLD_UNITS = set(teochew_symbols) | {"sil", "silv", "ds", "ts"}

# 新->旧 候选映射 (best-effort, 基于潮汕话罗马字规律)
#   finals / initials 分别处理
CAND = {
    # ---- finals (韵母) ----
    "aa": "a", "aah": "ah",
    "ainn": "ain", "ann": "an", "aonn": "aon",
    "enn": "en",
    "iaa": "ia", "iaah": "iah", "iann": "ian",
    "ii": "i", "iih": "ih", "inn": "in", "iunn": "iun", "iuw": "iu",
    "ngth": "ngt",
    "oinn": "oin", "ounn": "oun",
    "ow": "ou", "owh": "oh",
    "uainn": "uain", "uann": "uan",
    "uvg": "ug", "uvh": "uh", "uvng": "ung", "uw": "u", "uwh": "uh",
    "ienn": "iehn",
    "ueg": "uehg",
    # ---- initials (声母) ----
    "pb": "b", "pp": "p",
    "dz": "z", "gg": "g", "hh": "h",
    "kg": "k", "kk": "k", "ll": "l", "mm": "m",
    "nn": "n", "ss": "s", "td": "d", "tt": "t",
}

# 标记为歧义(多个候选/旧词表缺失)的项: 人工核对
# 格式: 单元 -> (说明, 建议旧体系目标)
AMBIG_OVERRIDE = {
    # 这些在旧词表里根本不存在 -> 无法直接映射, 必须决定"近似"还是"加进 symbols2"
    "ieg":   ("(旧词表缺失) 候选: iehg / 或新增 ieg 到 symbols2", "iehg"),
    "ieng":  ("(旧词表缺失) 候选: iehng / iem", "iehng"),
    "ueng":  ("(旧词表缺失) 候选: ong / ung", "ong"),
    "uv":    ("(旧词表缺失) 候选: u / uh", "u"),
    "uenn":  ("(旧词表缺失? ) 候选: uehn", "uehn"),
    "uinn":  ("候选: uin", "uin"),
    # 清浊/送气存疑的声母
    "bb":    ("浊音存疑: b 或 bh", "b"),
    "gg":    ("浊音存疑: g 或 gh", "g"),
    "kg":    ("与 kk 同指向 k? 需确认 kg/kk 区别", "k"),
    "kk":    ("与 kg 同指向 k? 需确认 kg/kk 区别", "k"),
}

# 仍无规则的"纯新"单元 (digit 已剥, 仅字母): 需人工定义
# 这里留空, 由脚本自动归到 ??? 类



def extract_units():
    units = set()
    with open(PROSODY, encoding="utf-8", errors="replace") as f:
        for line in f:
            # prosody 行格式不规整: 有 "][", "]ll iam35]]", "ienn35*[ts" 等
            # 先把 [ ] * 都替换成空格, 再按空白切分, 最后剥调值数字
            line2 = re.sub(r"[\[\]*]", " ", line)
            for tok in line2.split():
                tok = re.sub(r"\d", "", tok).strip()  # 剥调值
                if tok and re.fullmatch(r"[a-z]+", tok):
                    units.add(tok)
    return units


def main():
    new_units = extract_units()
    new_only = sorted(new_units - OLD_UNITS)
    print(f"[info] 新数据使用的音素单元总数: {len(new_units)}")
    print(f"[info] 旧词表(symbols2)单元数: {len(OLD_UNITS)}")
    print(f"[info] 新有/旧无 (需映射或新增): {len(new_only)}")

    auto_lines = []
    ambig_lines = []
    for u in new_only:
        if u in AMBIG_OVERRIDE:
            note, guess = AMBIG_OVERRIDE[u]
            ambig_lines.append(f"{u}\t->\t{guess}\t# {note}")
        elif u in CAND:
            old = CAND[u]
            if old in OLD_UNITS:
                auto_lines.append(f"{u}\t->\t{old}")
            else:
                ambig_lines.append(f"{u}\t->\t{old}\t# 映射目标 {old} 不在旧词表!")
        else:
            # 既无规则也无覆盖: 缺失
            ambig_lines.append(f"{u}\t->\t???\t# 无候选规则, 需人工定义")

    with open(OUT_AUTO, "w", encoding="utf-8") as f:
        f.write("# 新->旧 可确定映射 (teochew 音素单元级)\n")
        f.write("\n".join(auto_lines) + "\n")
    with open(OUT_AMBIG, "w", encoding="utf-8") as f:
        f.write("# 歧义 / 旧词表缺失 项 (需人工确认)\n")
        f.write("\n".join(ambig_lines) + "\n")

    print(f"[done] 确定映射 {len(auto_lines)} 条 -> {OUT_AUTO}")
    print(f"[done] 歧义/缺失 {len(ambig_lines)} 条 -> {OUT_AMBIG}")
    print("----- 歧义/缺失清单 -----")
    for l in ambig_lines:
        print(l)


if __name__ == "__main__":
    main()
