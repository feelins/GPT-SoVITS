# -*- coding: utf-8 -*-
"""
将 Common Voice nan-tw 完整数据集整理为 GPT-SoVITS「Phase 1 二级底座」的训练输入:

  1) 本地音频目录  prepared/wavs/   (从 clips_16k/ 复制/转换为单声道 16k 音频)
  2) 多说话人训练清单 prepared/train.list
       格式: {音频绝对路径}|{speaker_id(整数)}|{language}|{汉字文本}
  3) 说话人映射表     prepared/speaker_map.tsv
       格式: speaker_id | client_id | n_clips

与 build_metadata.py 的区别:
  - build_metadata.py 的 [A] 模式是按【单人 single_speaker】设计的
    (用 DEFAULT_CID 过滤单个人, SPEAKER 写死 nan_tw_01, 假定音频已在 wavs/*.wav);
  - 本脚本处理【完整 273 人】数据集, 给每人分配不同 speaker_id,
    并从 clips_16k/ 拉取/转换音频到本地 wavs/。

用法:
  # 默认: 仅复制 mp3 到 prepared/wavs (最快; 训练时 torchaudio 需 ffmpeg 后端, AutoDL 自带)
  python prepare_nan_tw_dataset.py

  # 转成 16k 单声道 wav (更标准, 需本机有 ffmpeg)
  python prepare_nan_tw_dataset.py --to-wav

  # 只保留 utterance 数 >= 50 的说话人, 最多取 50 人 (快速验证流程)
  python prepare_nan_tw_dataset.py --min-clips 50 --max-speakers 50

  # 仅预览: 不复制/转换音频, 只生成 train.list + speaker_map.tsv 看格式与数量
  python prepare_nan_tw_dataset.py --dry-run --max-speakers 5

  # 指定数据源与输出目录
  python prepare_nan_tw_dataset.py --src <nan-tw目录> --out <输出目录>
"""
import os
import re
import csv
import argparse
import collections
import subprocess
import shutil

PAREN_RE = re.compile(r'[（(][^）)]*[）)]')
CJK_RE = re.compile(r'[\u4e00-\u9fff]')

# 默认数据源 (本机路径); 也可用 --src 覆盖
DEFAULT_SRC = r"E:\008-datasets\mcv-scripted-nan-tw-v23.0\cv-corpus-23.0-2025-09-05\nan-tw"


def strip_roman(s):
    """去掉括号内的罗马字/台罗注音, 仅保留汉字正文。"""
    return PAREN_RE.sub("", s).strip()


def find_clip(src, name):
    """在 clips_16k/ 或 clips/ 中定位音频 (优先 16k)。"""
    for sub in ("clips_16k", "clips"):
        p = os.path.join(src, sub, name)
        if os.path.isfile(p):
            return p
    return None


def convert_to_wav(src_mp3, dst_wav):
    """mp3 -> 16k 单声道 wav; 优先 ffmpeg, 退化 torchaudio。返回是否成功。"""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src_mp3, "-ar", "16000", "-ac", "1", dst_wav],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        pass
    try:
        import torchaudio
        w, sr = torchaudio.load(src_mp3)
        if w.shape[0] > 1:
            w = w.mean(0, keepdim=True)
        if sr != 16000:
            w = torchaudio.functional.resample(w, sr, 16000)
        torchaudio.save(dst_wav, w, 16000)
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC, help="nan-tw 数据集根目录 (含 validated.tsv)")
    ap.add_argument("--out", default=None, help="输出目录, 默认 <src>/prepared")
    ap.add_argument("--lang", default="yue", help="底座语种字段 (Phase 1 用粤语 yue)")
    ap.add_argument("--to-wav", action="store_true", help="将 mp3 转为 16k 单声道 wav (需 ffmpeg)")
    ap.add_argument("--dry-run", action="store_true", help="仅生成 train.list/speaker_map.tsv, 不复制音频")
    ap.add_argument("--min-clips", type=int, default=1, help="每位说话人最少 utterance 数")
    ap.add_argument("--max-speakers", type=int, default=0, help="最多保留多少说话人 (0=全部)")
    args = ap.parse_args()

    src = args.src
    out = args.out or os.path.join(src, "prepared")
    wav_dir = os.path.join(out, "wavs")
    os.makedirs(wav_dir, exist_ok=True)

    val = os.path.join(src, "validated.tsv")
    if not os.path.isfile(val):
        raise SystemExit(f"[error] 未找到 validated.tsv: {val}")
    rows = list(csv.DictReader(open(val, encoding="utf-8"), delimiter="\t"))

    # 统计每位说话人的 clip 数, 过滤并排序
    cnt = collections.Counter(r["client_id"] for r in rows)
    cands = sorted([c for c, n in cnt.items() if n >= args.min_clips],
                   key=lambda c: -cnt[c])
    if args.max_speakers > 0:
        cands = cands[:args.max_speakers]
    spk_id = {cid: i for i, cid in enumerate(cands)}
    spk_meta = {i: (cid, cnt[cid]) for i, cid in enumerate(cands)}
    print(f"[info] 总说话人={len(cnt)}, 入选={len(cands)}, min_clips={args.min_clips}")

    train_lines = []
    missing = 0
    skipped_no_cjk = 0
    for r in rows:
        cid = r["client_id"]
        if cid not in spk_id:
            continue
        name = (r["path"] or "").strip()
        if not name:
            continue
        text = strip_roman(r["sentence"] or "")
        if not text or not CJK_RE.search(text):
            skipped_no_cjk += 1
            continue
        src_mp3 = find_clip(src, name)
        if src_mp3 is None:
            missing += 1
            continue

        if args.dry_run:
            # 预览模式: 不落音频, 用源路径占位 (仅验证清单与数量)
            dst = src_mp3
        elif args.to_wav:
            dst = os.path.join(wav_dir, os.path.splitext(name)[0] + ".wav")
            if not os.path.isfile(dst):
                if not convert_to_wav(src_mp3, dst):
                    # 转换失败 -> 退化复制 mp3
                    shutil.copy(src_mp3, os.path.join(wav_dir, name))
                    dst = os.path.join(wav_dir, name)
        else:
            dst = os.path.join(wav_dir, name)
            if not os.path.isfile(dst):
                shutil.copy(src_mp3, dst)

        train_lines.append(f"{dst}|{spk_id[cid]}|{args.lang}|{text}")

    with open(os.path.join(out, "train.list"), "w", encoding="utf-8") as f:
        f.write("\n".join(train_lines) + "\n")
    with open(os.path.join(out, "speaker_map.tsv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["speaker_id", "client_id", "n_clips"])
        for i in sorted(spk_meta):
            cid, n = spk_meta[i]
            w.writerow([i, cid, n])

    print(f"[done] 训练行数={len(train_lines)}, 缺失音频={missing}, 跳过(无汉字)={skipped_no_cjk}")
    print(f"   音频目录 : {wav_dir}")
    print(f"   train.list : {os.path.join(out, 'train.list')}")
    print(f"   speaker映射 : {os.path.join(out, 'speaker_map.tsv')}")
    print(f"[下一步] 把 train.list 拷到服务器, 训练时 n_speakers 设为 {len(cands)} (或默认 300)")


if __name__ == "__main__":
    main()
