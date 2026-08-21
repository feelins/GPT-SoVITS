# -*- coding: utf-8 -*-
"""
重建 / 改写 single_speaker 的 4 字段训练 metadata:
  {音频绝对路径}|{发音人id}|{底座模型语种id}|{文本(汉字 或 粤拼)}

两种用法:
  [A] 从源数据重建 (需 validated.tsv, 在 nan-tw 父目录运行):
        python build_metadata.py
        python build_metadata.py --mode jyutping     # Path B (台罗->粤拼)
  [B] 仅改写路径 (AutoDL 上, single_speaker/ 内运行, 无 validated.tsv):
        python build_metadata.py --from_list train.list
        python build_metadata.py --from_list train_jyutping.list

依赖(仅 [A] 模式): tailo2jyutping.py (同目录)
"""
import os, csv, re, argparse, collections, sys

BASE = os.path.dirname(os.path.abspath(__file__))

# 自适应目录: 脚本既可在 nan-tw/ 运行, 也可在 single_speaker/ 内运行
if os.path.isdir(os.path.join(BASE, "single_speaker", "wavs")):
    OUT_DIR = os.path.join(BASE, "single_speaker")
elif os.path.isdir(os.path.join(BASE, "wavs")):
    OUT_DIR = BASE
else:
    OUT_DIR = BASE  # 兜底

WAV_DIR = os.path.join(OUT_DIR, "wavs")
TRAIN_LIST = os.path.join(OUT_DIR, "train.list")
META_OUT = os.path.join(OUT_DIR, "metadata.csv")
META_FULL = os.path.join(OUT_DIR, "metadata_full.csv")
SYLL_MAP = os.path.join(OUT_DIR, "syllable_map.tsv")
TRAIN_JYUT = os.path.join(OUT_DIR, "train_jyutping.list")
META_JYUT = os.path.join(OUT_DIR, "metadata_jyutping.csv")

SPEAKER = "nan_tw_01"
LANG_ID = "yue"
DEFAULT_CID = "7f33d4489734"

PAREN_RE = re.compile(r'[（(]([^）)]*)[）)]')


def cross_basename(p):
    """跨平台 basename: 同时按 linux(/) 与 windows(\) 分隔符切分, 取末段。
    用于修复在 Linux 服务器上处理 Windows 路径(含反斜杠)时 os.path.basename 失效的问题。"""
    if not p:
        return p
    return p.replace("\\", "/").split("/")[-1]


def rewrite_paths(list_path, wav_root, out_path):
    """[B] 模式: 读取已有 train.list, 仅把第1列(wav绝对路径)换成 wav_root/同名文件, 其余不变。"""
    with open(list_path, encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    new = []
    for ln in lines:
        parts = ln.split("|")
        if len(parts) < 4:
            new.append(ln)
            continue
        fname = cross_basename(parts[0])
        parts[0] = os.path.join(wav_root, fname)
        new.append("|".join(parts))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new) + "\n")
    print(f"[done] 路径已改写: {len(new)} 行")
    print(f"       输入 : {list_path}")
    print(f"       输出 : {out_path}")
    print(f"       wav : {wav_root}")


def main():
    global SPEAKER, LANG_ID
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default=LANG_ID)
    ap.add_argument("--spk", default=SPEAKER)
    ap.add_argument("--cid", default=DEFAULT_CID)
    ap.add_argument("--mode", default="chars", choices=["chars", "jyutping"])
    # [B] 模式: 仅改写路径(用于 AutoDL, 无 validated.tsv)
    ap.add_argument("--from_list", default=None,
                    help="已有 train.list 路径; 仅重写 wav 绝对路径, 不依赖 validated.tsv")
    ap.add_argument("--wav_root", default=WAV_DIR,
                    help="[B] 模式下的 wav 目录(默认: 本脚本同级的 wavs/)")
    args = ap.parse_args()
    LANG_ID, SPEAKER = args.lang, args.spk

    # [B] 仅改写路径
    if args.from_list:
        rewrite_paths(args.from_list, args.wav_root, args.from_list)
        return

    # [A] 从源数据重建 (需要 validated.tsv 与 tailo2jyutping)
    sys.path.insert(0, BASE)
    import tailo2jyutping as tj
    VALIDATED = os.path.join(BASE, "validated.tsv")
    if not os.path.isfile(VALIDATED):
        sys.exit("[error] 未找到 validated.tsv, 无法从源重建。\n"
                 "        若在 single_speaker/ 内, 请用: python build_metadata.py --from_list train.list")

    rows = []
    with open(VALIDATED, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if (row.get("client_id") or "").strip().startswith(args.cid):
                rows.append(row)
    print(f"[info] 说话人 client_id 前缀 {args.cid} -> {len(rows)} 条")

    syll_cnt = collections.Counter()
    char_lines = []
    jyut_lines = []
    full_rows = []
    n_paren = 0
    for row in rows:
        path = (row.get("path") or "").strip()
        sentence = (row.get("sentence") or "").strip()
        if not path:
            continue
        audio = os.path.splitext(os.path.basename(path))[0] + ".wav"
        abs_path = os.path.join(WAV_DIR, audio)
        m = PAREN_RE.search(sentence)
        roman = m.group(1).strip() if m else sentence
        chars = PAREN_RE.sub("", sentence).strip()
        if m:
            n_paren += 1
        jyut = tj.to_jyutping(roman)
        for syl in re.split(r'[\s\-]+', roman):
            syl = re.sub(r'[，。、,.;:!?（）()"]', '', syl)
            if syl:
                syll_cnt[syl] += 1
        char_lines.append(f"{abs_path}|{SPEAKER}|{LANG_ID}|{chars}")
        jyut_lines.append(f"{abs_path}|{SPEAKER}|{LANG_ID}|{jyut}")
        full_rows.append([abs_path, SPEAKER, LANG_ID, chars, jyut, roman, sentence])

    with open(TRAIN_LIST, "w", encoding="utf-8") as f:
        f.write("\n".join(char_lines) + "\n")
    with open(META_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(char_lines) + "\n")
    with open(TRAIN_JYUT, "w", encoding="utf-8") as f:
        f.write("\n".join(jyut_lines) + "\n")
    with open(META_JYUT, "w", encoding="utf-8") as f:
        f.write("\n".join(jyut_lines) + "\n")
    with open(META_FULL, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["audio_path", "speaker", "language", "chars", "jyutping", "tailo_roman", "original_text"])
        w.writerows(full_rows)

    unknown = 0
    with open(SYLL_MAP, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tailo_syllable", "jyutping", "count", "flag"])
        for syl, n in sorted(syll_cnt.items(), key=lambda x: -x[1]):
            res = tj.parse_syllable(syl)
            if res is None:
                jy = syl
                flag = "UNKNOWN"
                unknown += 1
            else:
                oj, rj, tl = res
                jt = tj.TONE_TL2JYU.get(tl, 1)
                jy = f"{oj}{rj}{jt}"
                if rj not in tj.RHYME.values() and rj not in tj.RHYME_NASAL.values():
                    flag = "UNKNOWN_RHYME"
                    unknown += 1
                else:
                    flag = ""
            w.writerow([syl, jy, n, flag])

    print(f"[done] 训练行数={len(char_lines)} (含括号罗马字 {n_paren})")
    print(f"   不同音节={len(syll_cnt)}, 待核对未知韵母={unknown}")
    print(f"   [推荐] 汉字版 训练清单 : {TRAIN_LIST}")
    print(f"   [推荐] 汉字版 metadata : {META_OUT}")
    print(f"   [PathB] 粤拼版 train    : {TRAIN_JYUT}")
    print(f"   [PathB] 粤拼版 metadata : {META_JYUT}")
    print(f"   可读版   : {META_FULL}")
    print(f"   音节对照 : {SYLL_MAP}")


if __name__ == "__main__":
    main()
