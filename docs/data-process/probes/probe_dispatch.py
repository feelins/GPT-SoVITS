# -*- coding: utf-8 -*-
import os, re, importlib.util

ROOT = r"E:\003_ProgramLanguage\GPT-SoVITS\GPT_SoVITS"

# 1) 找 "yue" 在代码里如何路由到 g2p
dispatch = []
for dp, dn, fn in os.walk(os.path.join(ROOT, "text")):
    for f in fn:
        if f.endswith(".py"):
            fp = os.path.join(dp, f)
            try:
                t = open(fp, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if re.search(r'"yue"|\'yue\'|yue', t) and ("g2p" in t or "cantonese" in t or "import" in t):
                for i, line in enumerate(t.splitlines(), 1):
                    if "yue" in line and ("g2p" in line or "cantonese" in line or "import" in line):
                        dispatch.append(f"{fp}:{i}: {line.strip()}")

# 2) 找 text/__init__.py 的 language -> g2p 映射
initp = os.path.join(ROOT, "text", "__init__.py")
init_txt = ""
if os.path.exists(initp):
    init_txt = open(initp, encoding="utf-8", errors="ignore").read()

with open("E:/008-datasets/_tmp/dispatch_probe.txt", "w", encoding="utf-8") as g:
    g.write("=== yue 路由相关行 ===\n")
    g.write("\n".join(dispatch[:60]) + "\n\n")
    g.write("=== text/__init__.py 内容 ===\n")
    g.write(init_txt[:3000])

# 3) 测试 ToJyutping 是否可导入
try:
    import ToJyutping
    g2 = True
except Exception as e:
    g2 = False
    err = repr(e)
with open("E:/008-datasets/_tmp/tojyutping_check.txt", "w", encoding="utf-8") as g:
    g.write("ToJyutping import: " + ("OK" if g2 else "FAIL " + err) + "\n")
print("dispatch_hits", len(dispatch), "ToJyutping", g2)
