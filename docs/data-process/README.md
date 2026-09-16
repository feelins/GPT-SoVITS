# data-process：台语 GPT-SoVITS 数据处与训练方案文档

> 本目录汇总"nan-tw 台语数据 → GPT-SoVITS 训练"相关的方案分析、环境配置、数据探查文档。
> 原始数据：`E:\008-datasets\mcv-scripted-nan-tw-v23.0\cv-corpus-23.0-2025-09-05\nan-tw`
> 备注：源文件原位于 `Coqui.ai-TTS\scripts` 与 `E:\008-datasets\_tmp`，按"禁止删除"规则以**复制**方式归集于此，源文件保留。

## 主文档（决策用）
- `方案A-B-C分析_台语GPT-SoVITS文本表示决策.md` —— **核心决策文档**：第4字段"汉字/粤拼/台罗"三方案对比，为何台罗直喂不行（离散符号查表机制 + cantonese.py 代码证据），声调风险与单人微调自纠结论。**当前采用方案 A（汉字版 train.list，已生成）。**

## 背景与对比
- `台语数据_GPT-SoVITS训练方案与底座分析.md` —— 数据真实规模、音色≠发音、满语案例类比、三条路线（A 汉字 / B 粤拼 / C 台语原生）、是否需要台语底座。
- `GPT-SoVITS与Coqui-XTTS对比.md` —— 两框架原理对比、内容/音色解耦、四框架（GPT-SoVITS / XTTS / F5 / DiaMoE）横向对比、小语种与方言选型。
- `研究步骤.md` —— 本项目研究步骤记录。
- `配置推理环境虚拟环境.md` —— autoDL 上搭建 GPT-SoVITS（整合包路线）与 Coqui XTTS 的环境踩坑与配置。

## probes/ —— 数据探查脚本与原始输出（佐证）
- `gptsovits_probe.txt` —— 扫描 GPT-SoVITS 项目定位粤语 G2P 与音素字典文件的结果。
- `speaker_analysis.txt` —— nan-tw 各 TSV 说话人词条数统计（选定 7f33d4489734 的依据）。
- `unknown_syllables.txt` —— 台罗→粤拼手写映射时未覆盖的未知韵母音节及频次（方案 B 校对参考）。
- `check_train.txt` —— 汉字版 train.list 格式核验（无括号残留）。
- `probe_gptsovits.py` / `probe_dispatch.py` / `check_train.py` —— 上述探查脚本源码。
