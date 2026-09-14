# Teochew（潮汕话）GPT-SoVITS 文档索引

> 分支：`autodl-local` ｜ 当前实验：`teochew_04`（从官方底模重训，7646 句零 UNK）

## 文档导航
| 文件 | 内容 |
|------|------|
| [train_phase2_result.md](train_phase2_result.md) | **成果总结 + 后续扩展路线**（加更多数据 / 加发音人）—— 先看这个 |
| [train_plan_phase2.md](train_plan_phase2.md) | 第二阶段训练方案（含 WebUI 参数 §8、已验证状态） |
| [train_troubleshoot.md](train_troubleshoot.md) | 训练/推理排障记录（embedding resize、EOS 调优等错误 5–9） |
| [code.md](code.md) | 代码改动清单（s2_train / t2s_*/inference_webui 等修复） |
| [symbols_teochew.txt](symbols_teochew.txt) | 潮汕音素符号说明 |
| [test_teochew.py](test_teochew.py) | 音素/g2p 自测脚本 |
| [codes/](codes/) | 代码片段存档 |

## 关键产物（位于仓库外的大文件不入库）
- `data/new_chaoshan/train_full.list` —— 7646 行零 UNK 合并训练集（脚本再生）
- `data/04_ChaoShan/字_allpinyin_20180312.txt`（+229 字）、`allpinyin_with_shengyun.txt`（+34 音节）—— 已扩充词典，原文件 `.bak` 备份
- 脚本：`data/new_chaoshan/build_full_dataset.py`、`gen_mapping_candidates.py`

## 一句话结论
数据量（1309→7646 句）+ 词典覆盖（UNK 89.6%→0%）是决定合成稳定性与音质的主因；框架代码零改动。
