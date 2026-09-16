# -*- coding: utf-8 -*-
"""
台罗(Tailo) -> 粤拼(Jyutping) 近似音位映射。
用途: 把 Taiwanese(Hokkien) 的台罗罗马字, 映射到 GPT-SoVITS 的 yue 底座所能接受的
      Jyutping 音素空间(声母+韵母+声调数值 1-6), 以便借 yue 底座做台语 TTS。

注意: 这是"音位近似"映射, 并非标准转换(台语≠粤语)。尤其声调是最弱的环节,
      映射表 TONE_TL2JYU 与 TONE_DIACRITIC 都可被你直接修改微调。
"""
import unicodedata, re, os, csv, argparse

# ---------- 1. 声调: 台罗调号 -> 台罗调类(1-8) ----------
# 预组合字符(常用)
PRE = {
    'á': ('a', 2), 'à': ('a', 3), 'â': ('a', 4), 'ā': ('a', 1), 'ä': ('a', 5), 'ã': ('a', 1),
    'é': ('e', 2), 'è': ('e', 3), 'ê': ('e', 4), 'ē': ('e', 1), 'ë': ('e', 5), 'ẽ': ('e', 1),
    'í': ('i', 2), 'ì': ('i', 3), 'î': ('i', 4), 'ī': ('i', 1), 'ï': ('i', 5), 'ĩ': ('i', 1),
    'ó': ('o', 2), 'ò': ('o', 3), 'ô': ('o', 4), 'ō': ('o', 1), 'ö': ('o', 5), 'õ': ('o', 1),
    'ú': ('u', 2), 'ù': ('u', 3), 'û': ('u', 4), 'ū': ('u', 1), 'ü': ('u', 5), 'ũ': ('u', 1),
}

# 台罗调类 -> 粤拼声调数值(1-6)。按调型近似:
#   1 阴平(高平) -> 1(高平)
#   2 上声(升)   -> 2(高升)
#   3 阴去(降)   -> 3(中平)
#   4 阳去(低)   -> 4(低降)
#   5 阴入(高促) -> 1(高促, 配 -p/-t/-k)
#   7 阳入(中促) -> 3
#   8 阳入(低促) -> 6(低促)
TONE_TL2JYU = {1: 1, 2: 2, 3: 3, 4: 4, 5: 1, 6: 4, 7: 3, 8: 6}


def detect_tone(syl):
    for ch in syl:
        if ch in PRE:
            return PRE[ch][1]
    d = unicodedata.normalize('NFD', syl)
    if '\u0323' in d:          # 点下 = 阳入(8)
        return 8
    if '\u0301' in d:
        return 2
    if '\u0300' in d:
        return 3
    if '\u0302' in d:
        return 4
    if '\u0304' in d:
        return 1
    if '\u0308' in d:
        return 5
    return 1


def strip_marks(syl):
    d = unicodedata.normalize('NFD', syl)
    out = []
    for ch in d:
        if ch in ('\u0300', '\u0301', '\u0302', '\u0304', '\u0308', '\u0323', '\u0303'):
            continue
        out.append(ch)
    s = ''.join(out)
    s = s.replace('\u207f', '').replace('ⁿ', '')   # 去掉鼻化符 ⁿ
    return s


def is_nasal(syl):
    d = unicodedata.normalize('NFD', syl)
    return ('\u0303' in d) or ('\u207f' in syl) or ('ⁿ' in syl)


# ---------- 2. 声母映射 (Tailo -> Jyutping) ----------
ONSET = {
    'p': 'b', 'ph': 'p', 'b': 'b',
    't': 'd', 'th': 't', 'l': 'l', 'n': 'n',
    'k': 'g', 'kh': 'k', 'g': 'g',
    'ts': 'z', 'tsh': 'c', 's': 's', 'j': 'j',
    'h': 'h', 'm': 'm', 'ng': 'ng',
    '': '',
}
ONSET_ORDER = ['tsh', 'ts', 'kh', 'th', 'ph', 'chh', 'ch', 'ng', 'b', 'p',
               't', 'k', 'g', 's', 'h', 'm', 'n', 'l', 'j', '']

# ---------- 3. 韵母映射 (Tailo -> Jyutping) ----------
RHYME = {
    'a': 'aa', 'ah': 'aat', 'ai': 'aai', 'au': 'aau',
    'am': 'am', 'ap': 'ap', 'an': 'an', 'at': 'at', 'ang': 'ang', 'ak': 'ak',
    'e': 'e', 'eh': 'et', 'eng': 'ang', 'ek': 'ak', 'ei': 'ai',
    'i': 'i', 'ih': 'it', 'ia': 'e', 'iam': 'im', 'iap': 'ip', 'ian': 'in',
    'iat': 'it', 'iang': 'oeng', 'iak': 'ek', 'iau': 'iu', 'im': 'im',
    'ip': 'ip', 'in': 'in', 'it': 'it', 'ing': 'ing', 'ik': 'ik',
    'io': 'oe', 'ion': 'un', 'iong': 'ung', 'iok': 'uk', 'iu': 'iu', 'iuh': 'ut',
    'o': 'o', 'oh': 'ot', 'oi': 'oi', 'ong': 'ong', 'ok': 'ok', 'orh': 'ot',
    'u': 'u', 'uh': 'ut', 'ua': 'aa', 'uai': 'aai', 'uan': 'un', 'uat': 'ut',
    'uang': 'ong', 'ue': 'o', 'ueh': 'ot', 'ui': 'eoi', 'un': 'un', 'ut': 'ut',
    'ng': 'ng', 'nk': 'ng', 'nn': 'an',
}
# 鼻化韵母 (aⁿ -> an, iⁿ -> in ...)
RHYME_NASAL = {
    'a': 'an', 'e': 'en', 'i': 'in', 'o': 'on', 'u': 'un',
    'ai': 'ain', 'au': 'aun', 'ia': 'in', 'io': 'ion', 'iu': 'iun',
    'ua': 'uan', 'ue': 'oen', 'ui': 'eon', 'ng': 'ng',
}


def parse_syllable(syl):
    """返回 (onset_j, rhyme_j, tl_tone) 或 None(无法解析原样返回)"""
    syl = syl.strip()
    if not syl:
        return None
    tone = detect_tone(syl)
    nasal = is_nasal(syl)
    base = strip_marks(syl).lower()
    # 拆声母
    onset = ''
    for o in ONSET_ORDER:
        if o and base.startswith(o):
            onset = o
            base = base[len(o):]
            break
    rhyme = base
    if nasal and rhyme in RHYME_NASAL:
        rhyme = RHYME_NASAL[rhyme]
    rj = RHYME.get(rhyme, rhyme)     # 未知韵母保留原样(标 unknown 由调用方统计)
    oj = ONSET.get(onset, onset)
    return oj, rj, tone


def to_jyutping(text):
    """把一句台罗罗马字转成粤拼字符串(音节空格分隔, 带声调数值)。"""
    # 按空格/连字符切分音节
    toks = re.split(r'[\s\-]+', text)
    out = []
    for tk in toks:
        if not tk:
            continue
        # 去掉可能的标点
        tk = re.sub(r'[，。、,.;:!?（）()"]', '', tk)
        if not tk:
            continue
        res = parse_syllable(tk)
        if res is None:
            out.append(tk)
            continue
        oj, rj, tl = res
        jt = TONE_TL2JYU.get(tl, 1)
        out.append(f"{oj}{rj}{jt}")
    return ' '.join(out)


# ---------- 4. 从真实数据生成对照报告 ----------
def build_report(meta_csv, out_tsv):
    import collections
    cnt = collections.Counter()
    with open(meta_csv, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            pin = row.get('pinyin', '') or row.get('text', '')
            # 取括号里的台罗
            m = re.search(r'[（(]([^）)]*)[）)]', pin)
            rom = m.group(1) if m else pin
            for syl in re.split(r'[\s\-]+', rom):
                syl = re.sub(r'[，。、,.;:!?（）()"]', '', syl)
                if syl:
                    cnt[syl] += 1
    rows = []
    unknown = 0
    for syl, n in sorted(cnt.items(), key=lambda x: -x[1]):
        res = parse_syllable(syl)
        if res is None:
            jy = syl
        else:
            oj, rj, tl = res
            jt = TONE_TL2JYU.get(tl, 1)
            jy = f"{oj}{rj}{jt}"
            if rj not in RHYME.values() and rj == strip_marks(syl).lower().lstrip('ptk...'):
                pass
        # 标记未知韵母
        if res and res[1] not in RHYME.values() and res[1] not in RHYME_NASAL.values():
            unknown += 1
            tag = 'UNKNOWN_RHYME'
        else:
            tag = ''
        rows.append((syl, jy, n, tag))
    with open(out_tsv, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['tailo_syllable', 'jyutping', 'count', 'flag'])
        w.writerows(rows)
    print(f"[report] 不同音节数={len(rows)}, 未知韵母={unknown}")
    print(f"         输出: {out_tsv}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', action='store_true', help='从 metadata.csv 生成音节对照表')
    ap.add_argument('--meta', default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                   'single_speaker', 'metadata.csv'))
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  'single_speaker', 'syllable_map.tsv'))
    ap.add_argument('--text', default=None, help='直接转换一句台罗, 例如 "kau-kóo"')
    args = ap.parse_args()
    if args.text:
        print(to_jyutping(args.text))
    elif args.report:
        build_report(args.meta, args.out)
    else:
        print("用法: python tailo2jyutping.py --report | --text \"kau-kóo\"")
