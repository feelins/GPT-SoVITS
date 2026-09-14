# -*- coding: utf-8 -*-
"""
build_full_dataset.py — 一次性产出「6388 新 + 1309 旧」全量可训练数据

阶段:
  1. 扩充潮汕词典 (char -> 旧体系音节), 基于 prosody 的 字<->音素 对齐 + 已确认的新->旧单元映射
     - 备份原件 字_allpinyin_20180312.txt / allpinyin_with_shengyun.txt 为 .bak
     - 把新字补进 字_allpinyin, 把缺失旧音节补进 allpinyin_with_shengyun
  2. 生成合并 train.list (标准 4 列: wav|speaker|teochew|汉字文本)
  3. 重新加载 teochew.g2p, 对合并 list 做 UNK 覆盖率校验

用法:
  python build_full_dataset.py            # 跑全部三阶段
  python build_full_dataset.py --no-write # 只做分析/校验, 不写词典与 list
"""
import os
import re
import sys
import shutil
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GPT = os.path.join(ROOT, "GPT_SoVITS")
sys.path.insert(0, os.path.join(GPT, "text"))

from text.symbols2 import teochew_symbols

PROSODY = os.path.join(HERE, "prosody_all_log.txt")
WAV_DIR = os.path.join(HERE, "new_chao_data_label_new")
OLD_DIR = os.path.join(ROOT, "data", "04_ChaoShan")
OLD_DICT = os.path.join(OLD_DIR, "字_allpinyin_20180312.txt")
OLD_SPLIT = os.path.join(OLD_DIR, "allpinyin_with_shengyun.txt")
OLD_LIST = os.path.join(OLD_DIR, "train.list")
OUT_LIST = os.path.join(HERE, "train_full.list")
SPEAKER = "chao_shan_01"
LANG = "teochew"

# 旧体系所有单元 (含停顿)
OLD_UNITS = set(teochew_symbols) | {"sil", "silv", "ds", "ts"}

# ===== 已确认的新->旧 单元映射 (auto + 人工确认) =====
UNIT_MAP = {
    # finals
    "aa": "a", "aah": "ah", "ainn": "ain", "ann": "an", "aonn": "aon",
    "enn": "en", "iaa": "ia", "iaah": "iah", "iann": "ian", "ienn": "iehn",
    "ii": "i", "iih": "ih", "inn": "in", "iunn": "iun", "iuw": "iu",
    "ngth": "ngt", "oinn": "oin", "ounn": "oun", "ow": "ou", "owh": "oh",
    "uainn": "uain", "uann": "uan", "ueg": "uehg", "uvg": "ug", "uvh": "uh",
    "uvng": "ung", "uw": "u", "uwh": "uh",
    "ieg": "iehg", "ieng": "iehng", "ueng": "ong", "uenn": "uehn", "uinn": "uin",
    "ei": "a",            # 英语 A 音, 近似为 a
    "v": "u",             # 汉语拼音 ü, 近似为 u
    "mmt": "mt",
    # initials
    "dz": "z", "hh": "h", "pb": "b", "pp": "p", "ss": "s", "td": "d", "tt": "t",
    "ll": "l", "mm": "m", "nn": "n",
    "bb": "b", "gg": "g", "kg": "k", "kk": "k",
}


def cjk(ch):
    return "\u4e00" <= ch <= "\u9fff"


def map_units_to_old(new_units):
    """new_units: list[str] (已剥调值). 返回 (old_units, ok). ok=False 表示有单元无法映射."""
    out = []
    for u in new_units:
        if u in OLD_UNITS:
            out.append(u)
            continue
        if u in UNIT_MAP:
            t = UNIT_MAP[u]
            if t in OLD_UNITS:
                out.append(t)
            else:
                return None, False
        else:
            return None, False
    return out, True


def new_syl_to_old(new_syl):
    """'ds ui53' -> ('zui', 'z', 'ui') 或 None"""
    s = re.sub(r"\d", "", new_syl).strip()
    units = s.split()
    old_units, ok = map_units_to_old(units)
    if not ok or not old_units:
        return None
    # 组装 sheng/yun: 末位为韵母, 其余为声母(合并)
    yun = old_units[-1]
    sheng_parts = old_units[:-1]
    if sheng_parts:
        sheng = "".join(sheng_parts)
        old_syl = sheng + yun
    else:
        sheng = "null"
        old_syl = yun
    return old_syl, sheng, yun


def load_existing_dict(path):
    """返回 {char: 首个潮州音音节} , 以及原始行列表"""
    d = {}
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for ln in f:
                lines.append(ln.rstrip("\n"))
                m = re.match(r"^(.):\{潮州音:([^}]+)\}", ln)
                if m:
                    ch = m.group(1)
                    reading = m.group(2).strip()
                    if ch not in d and reading:
                        d[ch] = reading
    return d, lines


def load_split_map(path):
    """返回 {syllable: (sheng, yun)}"""
    m = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for ln in f:
                parts = ln.rstrip("\n").split("\t")
                if len(parts) >= 3:
                    m[parts[0].strip()] = (parts[1].strip(), parts[2].strip())
    return m


def parse_prosody_align(path):
    """返回 {char: set((old_syllable, sheng, yun))} — 仅取能干净转换的新字。
    按 * 分词, 逐词对齐(词内逐字), 解决多字词条对齐失败问题。"""
    char2old = {}
    n_utt = 0
    n_align_ok = 0
    n_align_skip = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().split("\n")
    i = 0
    n = len(lines)
    while i < n:
        l = lines[i].strip()
        if re.fullmatch(r"\d+", l):
            n_utt += 1
            if i + 2 < n:
                text = lines[i + 1].strip()
                phon = lines[i + 2].strip()
                # 按 * 分词, 两边词数应一致
                text_toks = text.split("*")
                phon_toks = phon.split("*")
                if len(text_toks) != len(phon_toks):
                    n_align_skip += 1
                    i += 3
                    continue
                ok = True
                for tt, pt in zip(text_toks, phon_toks):
                    chars = [c for c in tt if cjk(c)]
                    blocks = re.findall(r"\[([^\[\]]+)\]", pt)
                    if len(chars) != len(blocks):
                        ok = False
                        break
                    for ch, blk in zip(chars, blocks):
                        res = new_syl_to_old(blk)
                        if res is None:
                            continue
                        char2old.setdefault(ch, set()).add(res)
                if ok:
                    n_align_ok += 1
                else:
                    n_align_skip += 1
            i += 3
        else:
            i += 1
    return char2old, n_utt, n_align_ok, n_align_skip


def stage1_expand_dict(write):
    print("=== 阶段1: 扩充词典 ===")
    existing, dict_lines = load_existing_dict(OLD_DICT)
    split_map = load_split_map(OLD_SPLIT)
    char2old, n_utt, n_ok, n_skip = parse_prosody_align(PROSODY)
    print(f"  prosody 句数={n_utt} 对齐成功={n_ok} 跳过的句(字数≠音素数)={n_skip}")
    print(f"  从 prosody 提取到 {len(char2old)} 个不同字的可映射音节")

    new_entries = []        # 追加进 字_allpinyin 的行
    new_syllables = []      # 追加进 allpinyin_with_shengyun 的行
    added_chars = 0
    added_syl = 0

    for ch, entries in char2old.items():
        if ch in existing:
            continue
        # entries: set of (old_syl, sheng, yun)
        # 优先选已在 split_map 中的音节, 否则取首个
        chosen = None
        for e in entries:
            if e[0] in split_map:
                chosen = e
                break
        if chosen is None:
            chosen = next(iter(entries))
        syl, sheng, yun = chosen
        if syl not in split_map:
            split_map[syl] = (sheng, yun)
            new_syllables.append(f"{syl}\t{sheng}\t{yun}")
            added_syl += 1
        new_entries.append(f"{ch}:{{潮州音:{syl}}}{{文读:}}{{白读:}}{{俗读:}}{{拟读:}}{{姓读:}}{{训读:}}{{又读:}}")
        added_chars += 1

    print(f"  将新增字 {added_chars} 个, 新增音节 {added_syl} 个")
    if not write:
        print("  [--no-write] 未写入。")
        return

    # 备份
    shutil.copy(OLD_DICT, OLD_DICT + ".bak")
    shutil.copy(OLD_SPLIT, OLD_SPLIT + ".bak")
    with open(OLD_DICT, "w", encoding="utf-8") as f:
        f.write("\n".join(dict_lines + new_entries) + "\n")
    if new_syllables:
        with open(OLD_SPLIT, "a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(new_syllables) + "\n")
    print(f"  [done] 已备份原件(.bak)并写入扩充词典: +{added_chars}字 +{added_syl}音节")


def stage2_build_list(write, drop_unk=False):
    print("=== 阶段2: 生成合并 train.list ===")
    # 新数据: prosody 汉字 + wav 分组
    with open(PROSODY, encoding="utf-8", errors="replace") as f:
        lines = f.read().split("\n")
    prosody_text = {}
    i, n = 0, len(lines)
    while i < n:
        l = lines[i].strip()
        if re.fullmatch(r"\d+", l):
            idx5 = l[-5:]
            if i + 1 < n:
                txt = lines[i + 1].strip().replace("*", "").replace(" ", "")
                prosody_text[idx5] = txt
            i += 3
        else:
            i += 1

    # wav 按前5位分组
    wav_groups = {}
    for fn in os.listdir(WAV_DIR):
        if fn.endswith(".wav"):
            base = os.path.splitext(fn)[0]
            wav_groups.setdefault(base[:5], []).append(os.path.join(WAV_DIR, fn))

    new_lines = []
    missing = 0
    for idx5, wavs in wav_groups.items():
        txt = prosody_text.get(idx5)
        if not txt:
            missing += len(wavs)
            continue
        for wp in sorted(wavs):
            new_lines.append(f"{wp}|{SPEAKER}|{LANG}|{txt}")

    # 旧 list 直接并入
    old_lines = []
    if os.path.exists(OLD_LIST):
        with open(OLD_LIST, encoding="utf-8") as f:
            old_lines = [x.rstrip("\n") for x in f if x.strip()]

    all_lines = old_lines + new_lines
    print(f"  旧 list 行数={len(old_lines)}  新 list 行数={len(new_lines)}  合并={len(all_lines)}")
    print(f"  新数据中无对应汉字的 wav 数={missing}")

    if drop_unk:
        import importlib
        import text.teochew as teochew
        importlib.reload(teochew)
        teochew._ensure_loaded()
        kept, dropped = [], []
        for ln in all_lines:
            parts = ln.split("|")
            if len(parts) < 4:
                kept.append(ln)
                continue
            phones, _ = teochew.g2p(parts[3])
            (kept if "UNK" not in phones else dropped).append(ln)
        print(f"  [drop-unk] 保留 {len(kept)} 句, 删除含UNK {len(dropped)} 句")
        # 备份含UNK版
        with open(OUT_LIST + ".with_unk.bak", "w", encoding="utf-8") as f:
            f.write("\n".join(dropped) + "\n")
        all_lines = kept

    if not write:
        print("  [--no-write] 未写入。")
        return
    with open(OUT_LIST, "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines) + "\n")
    print(f"  [done] 写出 {OUT_LIST} ({len(all_lines)} 行)")


def stage3_verify(write):
    print("=== 阶段3: UNK 覆盖率校验 ===")
    import importlib
    import text.teochew as teochew
    importlib.reload(teochew)
    teochew._ensure_loaded()
    if not os.path.exists(OUT_LIST):
        print("  train_full.list 不存在, 先运行阶段2(--write)。")
        return
    total = 0
    unk_lines = 0
    with open(OUT_LIST, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                _, _, _, text = ln.split("|")
            except ValueError:
                continue
            total += 1
            phones, _ = teochew.g2p(text)
            if "UNK" in phones:
                unk_lines += 1
    print(f"  校验句子数={total}  含 UNK 句子数={unk_lines}  (UNK率 {100.0*unk_lines/max(1,total):.2f}%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write", action="store_true", help="只分析/校验, 不写文件")
    ap.add_argument("--drop-unk", action="store_true", help="删除含 UNK 的句子, 生成零 UNK 的 train_full.list")
    args = ap.parse_args()
    write = not args.no_write

    stage1_expand_dict(write)
    stage2_build_list(write, drop_unk=args.drop_unk)
    stage3_verify(write)


if __name__ == "__main__":
    main()
