# -*- coding: utf-8 -*-
"""
从 Common Voice (nan-tw) 中提取单一说话人的数据，单独保存：
  - 音频 -> single_speaker/wavs/  (优先转 24k 单声道 wav；无 ffmpeg 则保留 mp3)
  - single_speaker/metadata.csv    (干净元数据)
  - single_speaker/filelist.txt    (GPT-SoVITS 格式: 相对路径|说话人|文本)

用法:
  python extract_single_speaker.py            # 用默认说话人
  python extract_single_speaker.py --cid 7f33d4489734...   # 指定 client_id(可只给前若干位)
"""
import os, sys, csv, shutil, subprocess, argparse

BASE = os.path.dirname(os.path.abspath(__file__))
CLIPS = os.path.join(BASE, "clips")
CLIPS16 = os.path.join(BASE, "clips_16k")
VALIDATED = os.path.join(BASE, "validated.tsv")
OUT_DIR = os.path.join(BASE, "single_speaker")
WAV_DIR = os.path.join(OUT_DIR, "wavs")

# 默认说话人：validated 中 1317 条，男/三十多岁/台南腔，数据足且干净
DEFAULT_CID = "7f33d4489734"

SPEAKER_NAME = "nan_tw_spk1"   # GPT-SoVITS 中的说话人标签


def have_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=15)
        return True
    except Exception:
        return False


def find_clip(path):
    p = os.path.join(CLIPS, path)
    if os.path.exists(p):
        return p
    p16 = os.path.join(CLIPS16, path)
    if os.path.exists(p16):
        return p16
    return None


def to_wav(src, dst):
    """转 24k 单声道 wav；失败返回 False"""
    try:
        subprocess.run(["ffmpeg", "-y", "-i", src, "-ar", "24000", "-ac", "1", dst],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        return os.path.exists(dst) and os.path.getsize(dst) > 0
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cid", default=DEFAULT_CID, help="client_id 前缀或完整值")
    args = ap.parse_args()

    use_ffmpeg = have_ffmpeg()
    ext_out = ".wav" if use_ffmpeg else ".mp3"
    print(f"[info] ffmpeg={'有' if use_ffmpeg else '无'} -> 输出音频扩展名 {ext_out}")

    if not os.path.exists(VALIDATED):
        print("ERROR: 找不到 validated.tsv", file=sys.stderr)
        sys.exit(1)

    # 1) 收集该说话人的行
    rows = []
    with open(VALIDATED, encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            cid = (row.get("client_id") or "").strip()
            if cid.startswith(args.cid):
                rows.append(row)
    if not rows:
        print(f"ERROR: 未找到 client_id 以 {args.cid} 开头的条目", file=sys.stderr)
        sys.exit(1)
    real_cid = rows[0]["client_id"]
    print(f"[info] 说话人 client_id={real_cid[:16]}.. 共 {len(rows)} 条")

    os.makedirs(WAV_DIR, exist_ok=True)

    meta = []          # (audio_file, sentence, domain, age, gender, accent, variant)
    copied = 0
    skipped = 0
    for row in rows:
        path = (row.get("path") or "").strip()
        if not path:
            skipped += 1
            continue
        src = find_clip(path)
        if src is None:
            skipped += 1
            continue
        base_name = os.path.splitext(os.path.basename(path))[0]
        dst = os.path.join(WAV_DIR, base_name + ext_out)
        ok = False
        if use_ffmpeg:
            ok = to_wav(src, dst)
        if not ok:
            # 回退：直接复制原文件(保留原扩展名)
            dst = os.path.join(WAV_DIR, os.path.basename(path))
            try:
                shutil.copy2(src, dst)
                ok = True
            except Exception:
                ok = False
        if ok:
            copied += 1
            meta.append((
                os.path.basename(dst),
                (row.get("sentence") or "").strip(),
                (row.get("sentence_domain") or "").strip(),
                (row.get("age") or "").strip(),
                (row.get("gender") or "").strip(),
                (row.get("accents") or "").strip(),
                (row.get("variant") or "").strip(),
            ))
        else:
            skipped += 1

    # 2) 写 metadata.csv
    csv_path = os.path.join(OUT_DIR, "metadata.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["audio_file", "speaker", "text",
                    "sentence_domain", "age", "gender", "accent", "variant"])
        for m in meta:
            w.writerow([m[0], SPEAKER_NAME, m[1], m[2], m[3], m[4], m[5], m[6]])

    # 3) 写 GPT-SoVITS filelist (相对路径|说话人|文本)
    lst_path = os.path.join(OUT_DIR, "filelist.txt")
    rel_wav = "wavs"
    with open(lst_path, "w", encoding="utf-8") as f:
        for m in meta:
            f.write(f"{rel_wav}/{m[0]}|{SPEAKER_NAME}|{m[1]}\n")

    print(f"[done] 复制音频 {copied} 条, 跳过 {skipped} 条")
    print(f"       音频目录: {WAV_DIR}")
    print(f"       元数据  : {csv_path}")
    print(f"       GPT-SoVITS 清单: {lst_path}")


if __name__ == "__main__":
    main()
