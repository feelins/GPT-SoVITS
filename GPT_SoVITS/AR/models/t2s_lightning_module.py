# modified from https://github.com/yangdongchao/SoundStorm/blob/master/soundstorm/s1/AR/models/t2s_lightning_module.py
# reference: https://github.com/lifeiteng/vall-e
import os
import sys

now_dir = os.getcwd()
sys.path.append(now_dir)
from typing import Dict

import torch
from pytorch_lightning import LightningModule

from AR.models.t2s_model import Text2SemanticDecoder
from AR.modules.lr_schedulers import WarmupCosineLRSchedule
from AR.modules.optim import ScaledAdam


class Text2SemanticLightningModule(LightningModule):
    def __init__(self, config, output_dir, is_train=True):
        super().__init__()
        self.config = config
        self.top_k = 3
        self.model = Text2SemanticDecoder(config=config, top_k=self.top_k)
        pretrained_s1 = config.get("pretrained_s1")
        if pretrained_s1 and is_train:
            # print(self.load_state_dict(torch.load(pretrained_s1,map_location="cpu")["state_dict"]))
            # teochew 分支往 symbols 追加了 104 个音素, 当前模型 ar_text_embedding
            # 维度(836) 与底模(不含 teochew) 不一致。底模没有新符号的 phoneme
            # embedding, 直接 load(strict=True) 会因 shape 不匹配报错。剔除该层后
            # 随机初始化, 其余权重正常加载。
            _s1 = torch.load(
                pretrained_s1,
                map_location="cpu",
                weights_only=False,
            )["weight"]
            # teochew 分支把 phoneme_vocab_size 从底模的 732 扩到 836(见 t2s_model.py)。
            # 底模 ar_text_embedding 只有 732 行, 直接 load 会因 shape 不匹配失败。
            # 这里把底模 embedding 前 732 行原样保留, 仅新增的 733~835 行(teochew
            # 新符号)做零初始化, 这样既继承原符号知识又避免越界。
            # 实际 checkpoint 中 phoneme embedding 的 key 为
            # "model.ar_text_embedding.word_embeddings.weight"（报错已确认），
            # 用子串匹配以兼容不同底模命名。
            _prefix = "model.ar_text_embedding"
            for _key in list(_s1.keys()):
                if _key.startswith(_prefix) and _s1[_key].shape.__len__() == 2 \
                        and _s1[_key].shape[0] < self.model.phoneme_vocab_size:
                    _old = _s1[_key]
                    _new = _old.new_zeros(self.model.phoneme_vocab_size, _old.shape[1])
                    _new[: _old.shape[0]] = _old
                    _s1[_key] = _new
            print(self.load_state_dict(_s1, strict=False))
        if is_train:
            self.automatic_optimization = False
            self.save_hyperparameters()
            self.eval_dir = output_dir / "eval"
            self.eval_dir.mkdir(parents=True, exist_ok=True)

    def training_step(self, batch: Dict, batch_idx: int):
        opt = self.optimizers()
        scheduler = self.lr_schedulers()
        forward = self.model.forward if self.config["train"].get("if_dpo", False) == True else self.model.forward_old
        loss, acc = forward(
            batch["phoneme_ids"],
            batch["phoneme_ids_len"],
            batch["semantic_ids"],
            batch["semantic_ids_len"],
            batch["bert_feature"],
        )
        self.manual_backward(loss)
        if batch_idx > 0 and batch_idx % 4 == 0:
            opt.step()
            opt.zero_grad()
            scheduler.step()

        self.log(
            "total_loss",
            loss,
            on_step=True,
            on_epoch=True,
            prog_bar=True,
            sync_dist=True,
        )
        self.log(
            "lr",
            scheduler.get_last_lr()[0],
            on_epoch=True,
            prog_bar=True,
            sync_dist=True,
        )
        self.log(
            f"top_{self.top_k}_acc",
            acc,
            on_step=True,
            on_epoch=True,
            prog_bar=True,
            sync_dist=True,
        )

    def validation_step(self, batch: Dict, batch_idx: int):
        return

    # # get loss
    # loss, acc = self.model.forward(
    #     batch['phoneme_ids'], batch['phoneme_ids_len'],
    #     batch['semantic_ids'], batch['semantic_ids_len'],
    #     batch['bert_feature']
    # )
    #
    # self.log(
    #     "val_total_loss",
    #     loss,
    #     on_step=True,
    #     on_epoch=True,
    #     prog_bar=True,
    #     sync_dist=True)
    # self.log(
    #     f"val_top_{self.top_k}_acc",
    #     acc,
    #     on_step=True,
    #     on_epoch=True,
    #     prog_bar=True,
    #     sync_dist=True)
    #
    # # get infer output
    # semantic_len = batch['semantic_ids'].size(1)
    # prompt_len = min(int(semantic_len * 0.5), 150)
    # prompt = batch['semantic_ids'][:, :prompt_len]
    # pred_semantic = self.model.infer(batch['phoneme_ids'],
    #                                  batch['phoneme_ids_len'], prompt,
    #                                  batch['bert_feature']
    #                                  )
    # save_name = f'semantic_toks_{batch_idx}.pt'
    # save_path = os.path.join(self.eval_dir, save_name)
    # torch.save(pred_semantic.detach().cpu(), save_path)

    def configure_optimizers(self):
        model_parameters = self.model.parameters()
        parameters_names = []
        parameters_names.append([name_param_pair[0] for name_param_pair in self.model.named_parameters()])
        lm_opt = ScaledAdam(
            model_parameters,
            lr=0.01,
            betas=(0.9, 0.95),
            clipping_scale=2.0,
            parameters_names=parameters_names,
            show_dominant_parameters=False,
            clipping_update_period=1000,
        )

        return {
            "optimizer": lm_opt,
            "lr_scheduler": {
                "scheduler": WarmupCosineLRSchedule(
                    lm_opt,
                    init_lr=self.config["optimizer"]["lr_init"],
                    peak_lr=self.config["optimizer"]["lr"],
                    end_lr=self.config["optimizer"]["lr_end"],
                    warmup_steps=self.config["optimizer"]["warmup_steps"],
                    total_steps=self.config["optimizer"]["decay_steps"],
                )
            },
        }
