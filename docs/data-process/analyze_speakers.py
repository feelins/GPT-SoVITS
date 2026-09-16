import csv, os, sys
from collections import defaultdict

base = os.path.dirname(os.path.abspath(__file__))
out = []

def analyze(tsv_name):
    tsv = os.path.join(base, tsv_name)
    if not os.path.exists(tsv):
        return {}
    cnt = defaultdict(int)
    total = 0
    with open(tsv, encoding='utf-8') as f:
        r = csv.DictReader(f, delimiter='\t')
        for row in r:
            cid = row.get('client_id', '').strip()
            if cid:
                cnt[cid] += 1
                total += 1
    return cnt, total

for name in ['validated.tsv', 'train.tsv', 'dev.tsv', 'test.tsv']:
    res = analyze(name)
    if not res:
        out.append(f'== {name}: MISSING')
        continue
    cnt, total = res
    # 排序取前若干
    top = sorted(cnt.items(), key=lambda x: -x[1])[:15]
    out.append(f'== {name}: 总条数={total}, 说话人数={len(cnt)}')
    out.append('   前15名说话人(client_id前12位..条数):')
    for cid, n in top:
        out.append(f'     {cid[:12]}..  {n}')

os.makedirs('E:/008-datasets/_tmp', exist_ok=True)
with open('E:/008-datasets/_tmp/speaker_analysis.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('\n'.join(out))
