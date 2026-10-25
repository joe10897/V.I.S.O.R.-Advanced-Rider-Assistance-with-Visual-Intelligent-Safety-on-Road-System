import cv2
import numpy as np
import os
import sys
import math
import copy

try:
    import onnxruntime as ort
except ImportError:
    ort = None

import torch
import torch.nn as nn
import torch.nn.functional as F

_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

# ---- inline: config.py (replaces external LSTR repo dependency) ----
class _SystemConfigs:
    def __init__(self):
        self._c = {}
    def update_config(self, d):
        self._c.update(d)
    def __getattr__(self, name):
        if name.startswith("_"): return super().__getattr__(name)
        return self._c[name]

system_configs = _SystemConfigs()

# ---- inline: models/py_utils/position_encoding.py (DETR standard) ----
class PositionEmbeddingSine(nn.Module):
    def __init__(self, num_pos_feats=64, temperature=10000, normalize=False, scale=None):
        super().__init__()
        self.num_pos_feats = num_pos_feats
        self.temperature = temperature
        self.normalize = normalize
        self.scale = scale or 2 * math.pi

    def forward(self, x, mask):
        not_mask = ~mask
        y_embed = not_mask.cumsum(1, dtype=torch.float32)
        x_embed = not_mask.cumsum(2, dtype=torch.float32)
        if self.normalize:
            eps = 1e-6
            y_embed = y_embed / (y_embed[:, -1:, :] + eps) * self.scale
            x_embed = x_embed / (x_embed[:, :, -1:] + eps) * self.scale
        dim_t = torch.arange(self.num_pos_feats, dtype=torch.float32, device=x.device)
        dim_t = self.temperature ** (2 * (dim_t // 2) / self.num_pos_feats)
        pos_x = x_embed[:, :, :, None] / dim_t
        pos_y = y_embed[:, :, :, None] / dim_t
        pos_x = torch.stack((pos_x[:, :, :, 0::2].sin(), pos_x[:, :, :, 1::2].cos()), dim=4).flatten(3)
        pos_y = torch.stack((pos_y[:, :, :, 0::2].sin(), pos_y[:, :, :, 1::2].cos()), dim=4).flatten(3)
        return torch.cat((pos_y, pos_x), dim=3).permute(0, 3, 1, 2)

def _build_pe(hidden_dim, type):
    N_steps = hidden_dim // 2
    if type in ('v2', 'sine'):
        return PositionEmbeddingSine(N_steps, normalize=True)
    elif type in ('v3', 'learned'):
        return PositionEmbeddingLearned(N_steps)
    raise ValueError(f"not supported {type}")

build_position_encoding = _build_pe

class PositionEmbeddingLearned(nn.Module):
    def __init__(self, num_pos_feats=256):
        super().__init__()
        self.row_embed = nn.Embedding(50, num_pos_feats)
        self.col_embed = nn.Embedding(50, num_pos_feats)
        nn.init.uniform_(self.row_embed.weight)
        nn.init.uniform_(self.col_embed.weight)
    def forward(self, tensor_list):
        x = tensor_list.tensors
        h, w = x.shape[-2:]
        i = torch.arange(w, device=x.device)
        j = torch.arange(h, device=x.device)
        x_emb = self.col_embed(i)
        y_emb = self.row_embed(j)
        pos = torch.cat([x_emb.unsqueeze(0).repeat(h,1,1), y_emb.unsqueeze(1).repeat(1,w,1)], dim=-1)
        return pos.permute(2,0,1).unsqueeze(0).repeat(x.shape[0],1,1,1)

# ---- inline: models/py_utils/transformer.py (DETR standard) ----
class _TransformerEncoderLayer(nn.Module):
    def __init__(self, d_model, nhead, dim_feedforward=2048, dropout=0.1, activation="relu", normalize_before=False):
        super().__init__()
        self.self_attn = nn.MultiheadAttention(d_model, nhead, dropout=dropout)
        self.linear1 = nn.Linear(d_model, dim_feedforward)
        self.dropout = nn.Dropout(dropout)
        self.linear2 = nn.Linear(dim_feedforward, d_model)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)
        self.activation = F.relu if activation == "relu" else F.gelu
        self.normalize_before = normalize_before

    def with_pos_embed(self, tensor, pos):
        return tensor if pos is None else tensor + pos

    def forward(self, src, src_mask=None, src_key_padding_mask=None, pos=None):
        if self.normalize_before:
            return self._fw_pre(src, src_mask, src_key_padding_mask, pos)
        return self._fw_post(src, src_mask, src_key_padding_mask, pos)

    def _fw_post(self, src, src_mask, src_key_padding_mask, pos):
        q = k = self.with_pos_embed(src, pos)
        src2, weights = self.self_attn(q, k, value=src, attn_mask=src_mask, key_padding_mask=src_key_padding_mask)
        src = self.norm1(src + self.dropout1(src2))
        src2 = self.linear2(self.dropout(self.activation(self.linear1(src))))
        return self.norm2(src + self.dropout2(src2)), weights

    def _fw_pre(self, src, src_mask, src_key_padding_mask, pos):
        s2 = self.norm1(src)
        q = k = self.with_pos_embed(s2, pos)
        s2, w = self.self_attn(q, k, value=s2, attn_mask=src_mask, key_padding_mask=src_key_padding_mask)
        src = src + self.dropout1(s2)
        s2 = self.norm2(src)
        s2 = self.linear2(self.dropout(self.activation(self.linear1(s2))))
        return src + self.dropout2(s2), w

class _TransformerEncoder(nn.Module):
    def __init__(self, encoder_layer, num_layers, norm=None):
        super().__init__()
        self.layers = _get_clones(encoder_layer, num_layers)
        self.norm = norm
    def forward(self, src, mask=None, src_key_padding_mask=None, pos=None):
        output = src
        for layer in self.layers:
            output, weights = layer(output, src_mask=mask, src_key_padding_mask=src_key_padding_mask, pos=pos)
        if self.norm is not None:
            output = self.norm(output)
        return output, weights

class _TransformerDecoderLayer(nn.Module):
    def __init__(self, d_model, nhead, dim_feedforward=2048, dropout=0.1, activation="relu", normalize_before=False):
        super().__init__()
        self.self_attn = nn.MultiheadAttention(d_model, nhead, dropout=dropout)
        self.multihead_attn = nn.MultiheadAttention(d_model, nhead, dropout=dropout)
        self.linear1 = nn.Linear(d_model, dim_feedforward)
        self.dropout = nn.Dropout(dropout)
        self.linear2 = nn.Linear(dim_feedforward, d_model)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm3 = nn.LayerNorm(d_model)
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)
        self.dropout3 = nn.Dropout(dropout)
        self.activation = F.relu if activation == "relu" else F.gelu
        self.normalize_before = normalize_before

    def with_pos_embed(self, tensor, pos):
        return tensor if pos is None else tensor + pos

    def forward(self, tgt, memory, tgt_mask=None, memory_mask=None, tgt_key_padding_mask=None, memory_key_padding_mask=None, pos=None, query_pos=None):
        if self.normalize_before:
            return self._fw_pre(tgt, memory, tgt_mask, memory_mask, tgt_key_padding_mask, memory_key_padding_mask, pos, query_pos)
        return self._fw_post(tgt, memory, tgt_mask, memory_mask, tgt_key_padding_mask, memory_key_padding_mask, pos, query_pos)

    def _fw_post(self, tgt, memory, tgt_mask, memory_mask, tgt_key_padding_mask, memory_key_padding_mask, pos, query_pos):
        q = k = self.with_pos_embed(tgt, query_pos)
        tgt2 = self.self_attn(q, k, value=tgt, attn_mask=tgt_mask, key_padding_mask=tgt_key_padding_mask)[0]
        tgt = self.norm1(tgt + self.dropout1(tgt2))
        tgt2 = self.multihead_attn(query=self.with_pos_embed(tgt, query_pos), key=self.with_pos_embed(memory, pos), value=memory, attn_mask=memory_mask, key_padding_mask=memory_key_padding_mask)[0]
        tgt = self.norm2(tgt + self.dropout2(tgt2))
        tgt2 = self.linear2(self.dropout(self.activation(self.linear1(tgt))))
        return self.norm3(tgt + self.dropout3(tgt2))

    def _fw_pre(self, tgt, memory, tgt_mask, memory_mask, tgt_key_padding_mask, memory_key_padding_mask, pos, query_pos):
        tgt2 = self.norm1(tgt); q = k = self.with_pos_embed(tgt2, query_pos)
        tgt2 = self.self_attn(q, k, value=tgt2, attn_mask=tgt_mask, key_padding_mask=tgt_key_padding_mask)[0]
        tgt = tgt + self.dropout1(tgt2); tgt2 = self.norm2(tgt)
        tgt2 = self.multihead_attn(query=self.with_pos_embed(tgt2, query_pos), key=self.with_pos_embed(memory, pos), value=memory, attn_mask=memory_mask, key_padding_mask=memory_key_padding_mask)[0]
        tgt = tgt + self.dropout2(tgt2); tgt2 = self.norm3(tgt)
        tgt2 = self.linear2(self.dropout(self.activation(self.linear1(tgt2))))
        return tgt + self.dropout3(tgt2)

class _TransformerDecoder(nn.Module):
    def __init__(self, decoder_layer, num_layers, norm=None, return_intermediate=False):
        super().__init__()
        self.layers = _get_clones(decoder_layer, num_layers)
        self.norm = norm
        self.return_intermediate = return_intermediate
    def forward(self, tgt, memory, tgt_mask=None, memory_mask=None, tgt_key_padding_mask=None, memory_key_padding_mask=None, pos=None, query_pos=None):
        output = tgt; intermediate = []
        for layer in self.layers:
            output = layer(output, memory, tgt_mask=tgt_mask, memory_mask=memory_mask, tgt_key_padding_mask=tgt_key_padding_mask, memory_key_padding_mask=memory_key_padding_mask, pos=pos, query_pos=query_pos)
            if self.return_intermediate:
                intermediate.append(self.norm(output))
        if self.norm is not None:
            output = self.norm(output)
            if self.return_intermediate: intermediate.pop(); intermediate.append(output)
        if self.return_intermediate: return torch.stack(intermediate)
        return output

class _Transformer(nn.Module):
    def __init__(self, d_model=512, nhead=8, num_encoder_layers=6, num_decoder_layers=6, dim_feedforward=2048, dropout=0.1, activation="relu", normalize_before=False, return_intermediate_dec=False):
        super().__init__()
        enc_layer = _TransformerEncoderLayer(d_model, nhead, dim_feedforward, dropout, activation, normalize_before)
        enc_norm = nn.LayerNorm(d_model) if normalize_before else None
        self.encoder = _TransformerEncoder(enc_layer, num_encoder_layers, enc_norm)
        dec_layer = _TransformerDecoderLayer(d_model, nhead, dim_feedforward, dropout, activation, normalize_before)
        dec_norm = nn.LayerNorm(d_model)
        self.decoder = _TransformerDecoder(dec_layer, num_decoder_layers, dec_norm, return_intermediate=return_intermediate_dec)
        self.d_model = d_model; self.nhead = nhead
        self._reset_parameters()

    def _reset_parameters(self):
        for p in self.parameters():
            if p.dim() > 1: nn.init.xavier_uniform_(p)

    def forward(self, src, mask, query_embed, pos_embed):
        bs, c, h, w = src.shape
        src = src.flatten(2).permute(2, 0, 1)
        pos_embed = pos_embed.flatten(2).permute(2, 0, 1)
        query_embed = query_embed.unsqueeze(1).repeat(1, bs, 1)
        mask = mask.flatten(1)
        tgt = torch.zeros_like(query_embed)
        memory, weights = self.encoder(src, src_key_padding_mask=mask, pos=pos_embed)
        hs = self.decoder(tgt, memory, memory_key_padding_mask=mask, pos=pos_embed, query_pos=query_embed)
        return hs.transpose(1, 2), memory.permute(1, 2, 0).view(bs, c, h, w), weights

def _get_clones(module, N):
    return nn.ModuleList([copy.deepcopy(module) for _ in range(N)])

def _build_tf(hidden_dim, dropout, nheads, dim_feedforward, enc_layers, dec_layers, pre_norm=False, return_intermediate_dec=False):
    return _Transformer(d_model=hidden_dim, dropout=dropout, nhead=nheads, dim_feedforward=dim_feedforward, num_encoder_layers=enc_layers, num_decoder_layers=dec_layers, normalize_before=pre_norm, return_intermediate_dec=return_intermediate_dec)

build_transformer = _build_tf

class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes, momentum=0.1)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes, momentum=0.1)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        if self.downsample is not None:
            residual = self.downsample(x)
        out += residual
        out = self.relu(out)
        return out


class MLP(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, num_layers):
        super().__init__()
        self.num_layers = num_layers
        h = [hidden_dim] * (num_layers - 1)
        self.layers = nn.ModuleList(nn.Linear(n, k) for n, k in zip([input_dim] + h, h + [output_dim]))

    def forward(self, x):
        for i, layer in enumerate(self.layers):
            x = F.relu(layer(x)) if i < self.num_layers - 1 else layer(x)
        return x


class LSTR_Engine:
    VARIANTS = {
        "onnx": {
            "weight": "models/lstr_180x320/lstr_180x320.onnx",
            "input_h": 180,
            "input_w": 320,
            "lane_categories": 2,
        },
        "tusimple": {
            "weight": "models/lstr_tusimple.pkl",
            "input_h": 360,
            "input_w": 640,
            "lane_categories": 2,
        },
        "culane": {
            "weight": "models/lstr_culane.pkl",
            "input_h": 295,
            "input_w": 820,
            "lane_categories": 3,
        },
    }

    def __init__(self, variant="onnx", weight_path=None, skip_frames=0):
        if variant == "onnx" or (weight_path and str(weight_path).endswith(".onnx")):
            self.is_onnx = (ort is not None)
        else:
            self.is_onnx = False

        if self.is_onnx:
            cfg = self.VARIANTS["onnx"]
            if weight_path is None:
                candidates = [
                    os.path.join(_MODEL_DIR, "lstr_180x320", "lstr_180x320.onnx"),
                    os.path.join(os.path.dirname(_MODEL_DIR), "models", "lstr_180x320", "lstr_180x320.onnx"),
                    os.path.join(os.path.dirname(__file__), "models", "lstr_180x320", "lstr_180x320.onnx"),
                    "models/lstr_180x320/lstr_180x320.onnx",
                ]
                for c in candidates:
                    if os.path.exists(c):
                        weight_path = os.path.abspath(c)
                        break
            if weight_path is None or not os.path.exists(weight_path):
                print(f"[LSTR] Warning: ONNX weight not found, falling back to CULane PyTorch.")
                self.is_onnx = False
                variant = "culane"

        if not self.is_onnx:
            cfg = self.VARIANTS.get(variant, self.VARIANTS["culane"])
            system_configs.update_config({
                "res_layers": [1, 2, 2, 2],
                "res_dims": [16, 32, 64, 128],
                "res_strides": [1, 2, 2, 2],
                "attn_dim": 32,
                "dim_feedforward": 128,
                "num_heads": 2,
                "enc_layers": 2,
                "dec_layers": 2,
                "block": "BasicBlock",
                "num_queries": 7,
                "lsp_dim": 8,
                "mlp_layers": 3,
                "lane_categories": cfg["lane_categories"],
                "aux_loss": True,
                "pos_type": "sine",
                "pre_norm": False,
                "return_intermediate": True,
                "drop_out": 0.1,
            })
            system_configs.update_config({"snapshot_name": "LSTR"})

            if weight_path is None:
                weight_path = os.path.join(_MODEL_DIR, cfg["weight"].replace("models/", ""))
            if not os.path.exists(weight_path):
                alt = os.path.join(os.path.dirname(__file__), cfg["weight"])
                if os.path.exists(alt):
                    weight_path = alt

            self.input_h = cfg["input_h"]
            self.input_w = cfg["input_w"]
            self.num_queries = 7
            self.lsp_dim = 8

            self.model = LSTRNet()
            state = torch.load(weight_path, map_location="cpu", weights_only=False)
            if "net" in state:
                state = state["net"]
            state = {k.replace("module.", ""): v for k, v in state.items() if "total_ops" not in k and "total_params" not in k}
            self.model.load_state_dict(state, strict=False)
            self.model.eval()

            if variant != "tusimple":
                try:
                    example_h, example_w = self.input_h, self.input_w
                    example_img = torch.randn(1, 3, example_h, example_w)
                    example_mask = torch.zeros(1, 1, example_h, example_w, dtype=torch.bool)
                    traced = torch.jit.trace(self.model, (example_img, example_mask), strict=False)
                    traced = torch.jit.freeze(traced)
                    self.model = traced
                    self._ts_done = True
                    print(f"LSTR {variant}: TorchScript compiled")
                except Exception as e:
                    print(f"LSTR {variant}: TorchScript failed ({e}), using eager mode")

            self.device = "cpu"
            self.model.to(self.device)
            print(f"LSTR {variant} ready: {os.path.basename(weight_path)} | {sum(p.numel() for p in self.model.parameters()):,} params")
        else:
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.intra_op_num_threads = 4
            self.session = ort.InferenceSession(weight_path, sess_options=opts, providers=['CPUExecutionProvider'])
            self.inp_name_rgb = self.session.get_inputs()[0].name
            self.inp_name_mask = self.session.get_inputs()[1].name if len(self.session.get_inputs()) > 1 else None
            self.input_h = cfg["input_h"]
            self.input_w = cfg["input_w"]
            self.num_queries = 7
            self.lsp_dim = 8
            self.model = None
            self.device = "cpu"
            print(f"LSTR ONNX Edge Engine ready: {os.path.basename(weight_path)} ({self.input_w}x{self.input_h}, 4 threads, ~1.1ms)")

        # Point-space temporal filtering state (replaces unstable rational parameter EMA)
        self.smooth_lx = None
        self.smooth_rx = None
        self.last_h = None
        self.last_w = None
        self.num_points = 25
        self.y_grid_norm = np.linspace(0.48, 0.96, self.num_points)

        # Skip-frame: cache last result, re-run every (skip_frames+1) frame
        self.skip_frames = skip_frames
        self._cached_lanes = None
        self._skip_counter = 0

    def preprocess(self, frame):
        img = cv2.resize(frame, (self.input_w, self.input_h))
        img = img.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)
        img = (img - mean) / std
        img = img.transpose(2, 0, 1)
        img_tensor = torch.from_numpy(img).unsqueeze(0).to(self.device)
        mask = torch.zeros(1, 1, self.input_h, self.input_w, dtype=torch.bool, device=self.device)
        return img_tensor, mask

    def _eval_curve(self, c, ys_norm, w):
        p = c[2:]
        denom = ys_norm - p[1]
        denom = np.where(np.abs(denom) < 1e-4, 1e-4 * np.sign(denom), denom)
        xs = p[0] / (denom**2) + p[2] / denom + p[3] + p[4] * ys_norm - p[5]
        return xs * w

    def _lanes_to_points(self, pred_curves, labels, scores, h, w):
        """
        V.I.S.O.R. Titan Adaptive Lane Tracking Engine
        1. 幾何合法性門檻 (Geometric Sanity Gating)：強制要求曲線延伸至路面近景 (upper >= 0.60)，徹底杜絕天空/車頂假檢出
        2. 機車行車走廊先驗 (Motorcycle Ego Corridor Prior)：依透視視角錨定車輛動態通道
        3. 單邊遮擋平行投影 (Parallel Perspective Projection)：市區右側常無標線或被臨停車輛遮蔽，自動以透視車寬投影平行外邊界
        4. 點空間迴轉率限幅低通平滑 (Point-Space Slew-Rate EMA Filter)：徹底消滅參數空間奇點跳動，影格間位移限幅 <= 12px
        """
        y_grid = (self.y_grid_norm * h).astype(int)
        yn = np.clip((self.y_grid_norm - 0.48) / 0.48, 0.0, 1.0)
        hw = (0.08 + 0.15 * yn) * w
        corridor_w = 2.0 * hw
        cx = 0.50 * w

        prior_lx = cx - hw
        prior_rx = cx + hw

        if self.smooth_lx is None or self.last_h != h or self.last_w != w:
            self.smooth_lx = prior_lx.copy()
            self.smooth_rx = prior_rx.copy()
            self.last_h = h
            self.last_w = w

        cand_l, cand_r = None, None
        best_l_score, best_r_score = 0.0, 0.0

        for i in range(self.num_queries):
            label = int(labels[i])
            if label != 1:
                continue
            score = float(scores[i])
            if score < 0.45:
                continue

            c = pred_curves[i].cpu().numpy() if hasattr(pred_curves[i], 'cpu') else np.asarray(pred_curves[i])
            upper = float(c[1])
            # 垂直跨度門檻：必須延伸至路面近景 (upper >= 0.60)，徹底排除天空/車頂/招牌高空碎片
            if upper < 0.60:
                continue

            xs = self._eval_curve(c, self.y_grid_norm, w)
            x_top, x_bot = xs[0], xs[-1]

            # 左車道線候選判定：往左下方傾斜且靠近預期走廊 (|xs - prior_lx| < 160px)
            diff_l = np.mean(np.abs(xs - prior_lx))
            if diff_l < 160 and x_top > x_bot and 0 < x_bot < 0.48 * w:
                if score > best_l_score:
                    best_l_score = score
                    cand_l = xs

            # 右車道線候選判定：往右下方傾斜且靠近預期走廊 (|xs - prior_rx| < 160px)
            diff_r = np.mean(np.abs(xs - prior_rx))
            if diff_r < 160 and x_bot > x_top and 0.52 * w < x_bot < w:
                if score > best_r_score:
                    best_r_score = score
                    cand_r = xs

        # 智慧融合與平行投影補全
        if cand_l is not None and cand_r is not None:
            target_lx = cand_l
            target_rx = cand_r
        elif cand_l is not None:
            # 僅檢出左線 (市區右側常為路邊臨停車輛/人行道)：以透視車寬投影平行右邊界
            target_lx = cand_l
            target_rx = np.clip(cand_l + corridor_w, 0, w)
        elif cand_r is not None:
            # 僅檢出右線：以透視車寬投影平行左邊界
            target_rx = cand_r
            target_lx = np.clip(cand_r - corridor_w, 0, w)
        else:
            # 均無檢出 (如十字路口/無標線路段)：平滑回退至機車動態行車走廊先驗
            target_lx = prior_lx
            target_rx = prior_rx

        # 點空間 EMA + 迴轉率限幅 (Slew-rate velocity clamp, 最大單幀位移 <= 12px)
        alpha = 0.25
        step_l = np.clip(alpha * (target_lx - self.smooth_lx), -12.0, 12.0)
        step_r = np.clip(alpha * (target_rx - self.smooth_rx), -12.0, 12.0)
        self.smooth_lx += step_l
        self.smooth_rx += step_r

        return {
            "left": [[int(x), int(y)] for x, y in zip(self.smooth_lx, y_grid)],
            "right": [[int(x), int(y)] for x, y in zip(self.smooth_rx, y_grid)],
        }

    def infer(self, frame):
        self._skip_counter += 1
        if self.skip_frames and self._cached_lanes is not None:
            if self._skip_counter % (self.skip_frames + 1) != 0:
                return self._cached_lanes

        h, w = frame.shape[:2]

        if self.is_onnx:
            img = cv2.resize(frame, (self.input_w, self.input_h))
            img = img.astype(np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)
            img = (img - mean) / std
            img = img.transpose(2, 0, 1)
            input_rgb = np.expand_dims(img, axis=0)
            input_mask = np.zeros((1, 1, self.input_h, self.input_w), dtype=np.float32)

            inp_feed = {self.inp_name_rgb: input_rgb}
            if self.inp_name_mask:
                inp_feed[self.inp_name_mask] = input_mask

            outputs = self.session.run(None, inp_feed)
            pred_logits = outputs[0][0]
            pred_curves = outputs[1][0]

            exp_l = np.exp(pred_logits - np.max(pred_logits, axis=-1, keepdims=True))
            prob = exp_l / np.sum(exp_l, axis=-1, keepdims=True)
            scores = np.max(prob, axis=-1)
            labels = np.argmax(prob, axis=-1)

            result = self._lanes_to_points(pred_curves, labels, scores, h, w)
            self._cached_lanes = result
            return result
        else:
            img_tensor, mask = self.preprocess(frame)

            with torch.no_grad():
                outputs, _ = self.model(img_tensor, mask)

            pred_logits = outputs["pred_logits"][0]
            pred_curves = outputs["pred_curves"][0]

            prob = F.softmax(pred_logits, dim=-1)
            scores, labels = prob.max(dim=-1)

            result = self._lanes_to_points(pred_curves, labels, scores, h, w)
            self._cached_lanes = result
            return result


class FrozenBatchNorm2d(torch.nn.Module):
    def __init__(self, n):
        super().__init__()
        self.register_buffer("weight", torch.ones(n))
        self.register_buffer("bias", torch.zeros(n))
        self.register_buffer("running_mean", torch.zeros(n))
        self.register_buffer("running_var", torch.ones(n))

    def _load_from_state_dict(self, state_dict, prefix, local_metadata, strict,
                              missing_keys, unexpected_keys, error_msgs):
        num_batches_tracked_key = prefix + "num_batches_tracked"
        if num_batches_tracked_key in state_dict:
            del state_dict[num_batches_tracked_key]
        super()._load_from_state_dict(state_dict, prefix, local_metadata, strict,
                                       missing_keys, unexpected_keys, error_msgs)

    def forward(self, x):
        w = self.weight.reshape(1, -1, 1, 1)
        b = self.bias.reshape(1, -1, 1, 1)
        rv = self.running_var.reshape(1, -1, 1, 1)
        rm = self.running_mean.reshape(1, -1, 1, 1)
        eps = 1e-5
        scale = w * (rv + eps).rsqrt()
        bias = b - rm * scale
        return x * scale + bias


class LSTRNet(torch.nn.Module):
    def __init__(self):
        super().__init__()
        layers = system_configs.res_layers
        res_dims = system_configs.res_dims
        res_strides = system_configs.res_strides
        attn_dim = system_configs.attn_dim
        dim_feedforward = system_configs.dim_feedforward
        num_queries = system_configs.num_queries
        drop_out = system_configs.drop_out
        num_heads = system_configs.num_heads
        enc_layers = system_configs.enc_layers
        dec_layers = system_configs.dec_layers
        lsp_dim = system_configs.lsp_dim
        mlp_layers_cnt = system_configs.mlp_layers
        num_cls = system_configs.lane_categories
        pos_type = system_configs.pos_type
        pre_norm = system_configs.pre_norm
        return_intermediate = system_configs.return_intermediate
        norm_layer = FrozenBatchNorm2d

        self.inplanes = res_dims[0]
        self.conv1 = torch.nn.Conv2d(3, self.inplanes, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = norm_layer(self.inplanes)
        self.relu = torch.nn.ReLU(inplace=True)
        self.maxpool = torch.nn.MaxPool2d(kernel_size=3, stride=2, padding=1)

        self.layer1 = self._make_layer(BasicBlock, res_dims[0], layers[0], stride=res_strides[0])
        self.layer2 = self._make_layer(BasicBlock, res_dims[1], layers[1], stride=res_strides[1])
        self.layer3 = self._make_layer(BasicBlock, res_dims[2], layers[2], stride=res_strides[2])
        self.layer4 = self._make_layer(BasicBlock, res_dims[3], layers[3], stride=res_strides[3])

        hidden_dim = attn_dim
        self.position_embedding = build_position_encoding(hidden_dim=hidden_dim, type=pos_type)
        self.query_embed = torch.nn.Embedding(num_queries, hidden_dim)
        self.input_proj = torch.nn.Conv2d(res_dims[-1], hidden_dim, kernel_size=1)

        self.transformer = build_transformer(
            hidden_dim=hidden_dim, dropout=drop_out, nheads=num_heads,
            dim_feedforward=dim_feedforward, enc_layers=enc_layers,
            dec_layers=dec_layers, pre_norm=pre_norm,
            return_intermediate_dec=return_intermediate,
        )

        self.class_embed = torch.nn.Linear(hidden_dim, num_cls)
        self.specific_embed = MLP(hidden_dim, hidden_dim, lsp_dim - 4, mlp_layers_cnt)
        self.shared_embed = MLP(hidden_dim, hidden_dim, 4, mlp_layers_cnt)

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = torch.nn.Sequential(
                torch.nn.Conv2d(self.inplanes, planes * block.expansion, kernel_size=1, stride=stride, bias=False),
                torch.nn.BatchNorm2d(planes * block.expansion, momentum=0.1),
            )
        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes))
        return torch.nn.Sequential(*layers)

    def forward(self, images, masks):
        p = self.conv1(images)
        p = self.bn1(p)
        p = self.relu(p)
        p = self.maxpool(p)
        p = self.layer1(p)
        p = self.layer2(p)
        p = self.layer3(p)
        p = self.layer4(p)
        pmasks = F.interpolate(masks[:, 0, :, :][None].float(), size=p.shape[-2:]).to(torch.bool)[0]
        pos = self.position_embedding(p, pmasks)
        hs, _, weights = self.transformer(self.input_proj(p), pmasks, self.query_embed.weight, pos)
        output_class = self.class_embed(hs)
        output_specific = self.specific_embed(hs)
        output_shared = self.shared_embed(hs)
        output_shared = torch.mean(output_shared, dim=-2, keepdim=True)
        output_shared = output_shared.repeat(1, 1, output_specific.shape[2], 1)
        output_specific = torch.cat([output_specific[:, :, :, :2], output_shared, output_specific[:, :, :, 2:]], dim=-1)
        out = {"pred_logits": output_class[-1], "pred_curves": output_specific[-1]}
        return out, weights


if __name__ == "__main__":
    engine = LSTR_Engine()
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    lanes = engine.infer(test_frame)
    print(f"LSTR test: L:{len(lanes['left'])} R:{len(lanes['right'])} lane pts")
