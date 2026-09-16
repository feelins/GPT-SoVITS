"""
convert_v2pro_s2g_to_raw.py
=====================================================================
把 GPT-SoVITS v2Pro 训练日志里的 SoVITS-G 检查点
    logs/<exp>/logs_s2_v2Pro/G_*.pth
（utils.save_checkpoint 存成 {"model": state_dict, "optimizer": ...}）
转成 1A / 1B 能直接加载的「裸 weight」文件：
    SoVITS_weights_v2Pro/<name>_raw.pth
    （顶层键 "weight"，**无** v2Pro 的 05 版本头）

为什么需要这一步（实测坑，2026-07-31）
--------------------------------------------------------------------
- 训练时 WebUI "save small final model" 导出到 SoVITS_weights/ 的文件，
  v2Pro 会被 process_ckpt.savee 前插 2 字节 "05" 版本头。
- 推理加载器 load_sovits_new 能剥这个头，所以 1C 下拉能正常加载；
  但 1A(3-get-semantic.py)、1B(s2_train.py) 用裸 torch.load(...["weight"])，
  读带 05 头的文件会报 UnpicklingError: unpickling stack underflow。
- 同理，训练日志里的 G_*.pth 顶层是 "model" 键，裸 torch.load[...]["weight"]
  会 KeyError: 'weight'。
=> 1B 的 Pretrained SoVITS-G 必须是一份「裸 weight、无 05 头」的文件，
   本脚本即生成它。原始预训练 s2Gv2Pro.pth / s2Dv2Pro.pth 本身就是裸 zip，
   不用转换；logs 里的 D_*.pth 也是 "model" 键，但 D 不承载音色，
   1B 直接用 s2Dv2Pro.pth 即可。

用法（在 GPT-SoVITS 仓库根目录执行）
--------------------------------------------------------------------
    python docs/data-process/convert_v2pro_s2g_to_raw.py
按需修改下面 LOGS_G / OUT_PATH 两个变量。
"""
import torch
from GPT_SoVITS.process_ckpt import my_save

# ===================== 按需修改 =====================
LOGS_G = "logs/nan-tw-base-2nd/logs_s2_v2Pro/G_233333333333.pth"   # 训练日志里的 G 文件
OUT_PATH = "SoVITS_weights_v2Pro/nan-tw-base-2nd_e18_raw.pth"       # 输出的裸权重文件
# ===================================================

print("loading", LOGS_G)
ckpt = torch.load(LOGS_G, map_location="cpu", weights_only=False)

# 训练日志存的是 {"model": state_dict, "optimizer": ...}
sd = ckpt["model"] if "model" in ckpt else ckpt.get("weight")
if sd is None:
    raise KeyError("checkpoint 里既无 'model' 也无 'weight' 键，请检查文件")

# 转成 {"weight": {k: v.half()}} 的裸 zip（half 省显存，与导出格式一致）
my_save({"weight": {k: v.half() for k, v in sd.items()}}, OUT_PATH)
print("saved raw weight ->", OUT_PATH)
