# -*- coding: utf-8 -*-
import os, re

ROOT = r"E:\003_ProgramLanguage\GPT-SoVITS\GPT_SoVITS"
hits_name = []
hits_content = []
kw_name = re.compile(r'(yue|jyut|cantonese|g2p|open|hkm|hak|jyp)', re.I)
kw_content = re.compile(r'jyutping|cantonese|jypinyin|港', re.I)

for dp, dn, fn in os.walk(ROOT):
    # 跳过大缓存/模型权重
    if any(s in dp for s in ('.git', '__pycache__', 'logs', 'SoVITS_weights', 'GPT_weights',
                              'pretrained_models', 'models', 'output')):
        continue
    for f in fn:
        if kw_name.search(f):
            hits_name.append(os.path.join(dp, f))
        if f.endswith(('.py', '.txt', '.json', '.md', '.yaml', '.yml', '.csv')):
            fp = os.path.join(dp, f)
            try:
                with open(fp, encoding='utf-8', errors='ignore') as fh:
                    head = fh.read(4000)
                if kw_content.search(head):
                    hits_content.append(fp)
            except Exception:
                pass

with open("E:/008-datasets/_tmp/gptsovits_probe.txt", "w", encoding="utf-8") as g:
    g.write("=== 文件名含 yue/jyut/cantonese/g2p 等 ===\n")
    g.write("\n".join(hits_name[:200]) + "\n\n")
    g.write("=== 内容含 jyutping/cantonese 的文件 ===\n")
    g.write("\n".join(hits_content[:200]) + "\n")
print("name_hits", len(hits_name), "content_hits", len(hits_content))
