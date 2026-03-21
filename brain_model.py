"""
Optional PyTorch 'ETABS teacher' brain.

Weights (.pt):
  - env BALMORES_BRAIN_PT, or
  - models/strux_etabs_brain.pt, or
  - single *.pt under models/, or
  - single *.pt in project root

Config (optional): models/brain_config.json — copy from brain_config.example.json
  - input_dim, hidden_dim, output_dim, recommendation_labels[]

If nothing loads, the app uses FEM-only text. Cache refreshes when the .pt file changes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"

_DEFAULT_LABELS = [
    "Drift/stiffness looks acceptable for the chosen drift basis; verify load combinations in ETABS.",
    "Drift or deflection is relatively high; consider increasing member sizes or bracing.",
    "Internal forces show a few governing members; align ETABS design groups with the reported FEM groups.",
    "Reactions are non-trivial; confirm support modeling (fixity) matches construction.",
    "Run ETABS with the exported geometry and compare periods/base reactions to this linear snapshot.",
]


def load_brain_config() -> Dict[str, Any]:
    path = MODELS_DIR / "brain_config.json"
    cfg = {
        "input_dim": 24,
        "hidden_dim": 64,
        "output_dim": 5,
        "recommendation_labels": list(_DEFAULT_LABELS),
    }
    if not path.is_file():
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return cfg
    if isinstance(raw.get("input_dim"), int) and raw["input_dim"] > 0:
        cfg["input_dim"] = raw["input_dim"]
    if isinstance(raw.get("hidden_dim"), int) and raw["hidden_dim"] > 0:
        cfg["hidden_dim"] = raw["hidden_dim"]
    if isinstance(raw.get("output_dim"), int) and raw["output_dim"] > 0:
        cfg["output_dim"] = raw["output_dim"]
    labs = raw.get("recommendation_labels")
    if isinstance(labs, list) and all(isinstance(x, str) for x in labs) and labs:
        cfg["recommendation_labels"] = labs
    return cfg


def engineering_feature_list(result: Optional[Dict[str, Any]]) -> List[float]:
    """
    Ordered scalars for neural input (extend here when your 5000-sample model needs more).
    First 24 are stable defaults; extra slots are engineering-rich statistics for larger input_dim.
    """
    if not result or not result.get("ok"):
        return [0.0] * 64

    r = result["results"]
    mf = r.get("member_forces") or []
    moments = [float(x.get("moment_max_kNm") or 0) for x in mf]
    shears = [float(x.get("shear_max_kN") or 0) for x in mf]
    axials = [float(x.get("axial_max_kN") or 0) for x in mf]
    lengths = [float(x.get("length_m") or 0) for x in mf]

    roof = float(r.get("roof_disp_mm") or 0)
    lim = float(r.get("drift_limit_mm") or 1)
    ratio = roof / lim if lim > 0 else 0.0
    h = float(r.get("total_height_m") or 0)
    nb = len([x for x in mf if x.get("type") == "beam"])
    nc = len([x for x in mf if x.get("type") == "column"])
    nbr = len([x for x in mf if x.get("type") == "brace"])

    rx = r.get("support_reactions") or []
    fz = [float(x.get("Fz_kN") or 0) for x in rx]
    sum_abs_fz = float(sum(abs(v) for v in fz)) if fz else 0.0

    base = [
        roof,
        lim,
        ratio,
        h,
        float(len(mf)),
        float(nb),
        float(nc),
        float(nbr),
        float(max(moments) if moments else 0),
        float(sum(moments) / len(moments) if moments else 0),
        float(min(moments) if moments else 0),
        float(np.std(moments) if len(moments) > 1 else 0),
        float(max(shears) if shears else 0),
        float(max(axials) if axials else 0),
        float(min(axials) if axials else 0),
        float(max(lengths) if lengths else 0),
        float(r.get("drift_result") == "PASS"),
        float(len(r.get("beam_groups") or [])),
        float(len(r.get("column_groups") or [])),
        sum_abs_fz,
        float(len(rx)),
        float(r.get("roof_disp_mm") or 0) / float(h * 1000) if h > 0 else 0.0,
    ]
    while len(base) < 64:
        base.append(0.0)
    return base[:64]


def feature_vector(result: Optional[Dict[str, Any]], target_dim: int) -> np.ndarray:
    raw = engineering_feature_list(result)
    if target_dim <= 0:
        target_dim = 24
    n = min(len(raw), target_dim)
    out = np.zeros(target_dim, dtype=np.float32)
    out[:n] = np.array(raw[:n], dtype=np.float32)
    return out


def _labels_from_logits(y: np.ndarray, labels: List[str]) -> str:
    if y.size == 0:
        return ""
    k = int(np.argmax(y))
    if 0 <= k < len(labels):
        return labels[k]
    return labels[0] if labels else ""


def _make_mlp(state_dict: dict, cfg: Dict[str, Any]) -> Optional[Any]:
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        return None

    in_dim = int(cfg.get("input_dim") or 24)
    hidden = int(cfg.get("hidden_dim") or 64)
    out_dim = int(cfg.get("output_dim") or 5)

    class TinyMLP(nn.Module):
        def __init__(self, in_d, hid, out_d):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(in_d, hid),
                nn.Tanh(),
                nn.Linear(hid, out_d),
            )

        def forward(self, x):
            return self.net(x)

    candidates = [
        (in_dim, hidden, out_dim),
        (24, 64, 5),
        (16, 48, 5),
        (32, 64, 8),
        (48, 96, 8),
    ]
    for in_d, hid, out_d in candidates:
        m = TinyMLP(in_d, hid, out_d)
        try:
            m.load_state_dict(state_dict, strict=True)
            m.eval()
            cfg["input_dim"] = in_d
            cfg["hidden_dim"] = hid
            cfg["output_dim"] = out_d
            return m
        except Exception:
            continue
    m = TinyMLP(in_dim, hidden, out_dim)
    try:
        m.load_state_dict(state_dict, strict=False)
        m.eval()
        return m
    except Exception:
        return None


_cached_model = None
_cached_path: Optional[Path] = None
_cached_mtime: float = 0.0


def resolve_brain_path() -> Optional[Path]:
    env = os.getenv("BALMORES_BRAIN_PT", "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p
    default = MODELS_DIR / "strux_etabs_brain.pt"
    if default.is_file():
        return default
    if MODELS_DIR.is_dir():
        pts = sorted(MODELS_DIR.glob("*.pt"))
        if len(pts) == 1:
            return pts[0]
    root_pts = list(BASE_DIR.glob("*.pt"))
    if len(root_pts) == 1:
        return root_pts[0]
    return None


def load_brain() -> Tuple[Optional[Any], Optional[Path], Dict[str, Any]]:
    global _cached_model, _cached_path, _cached_mtime
    path = resolve_brain_path()
    cfg = load_brain_config()
    if path is None:
        _cached_model, _cached_path = None, None
        _cached_mtime = 0.0
        return None, None, cfg

    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0

    if _cached_model is not None and _cached_path == path and mtime == _cached_mtime:
        return _cached_model, path, cfg

    _cached_model = None
    _cached_path = path
    _cached_mtime = mtime

    try:
        import torch
    except ImportError:
        return None, path, cfg

    try:
        obj = torch.load(str(path), map_location="cpu", weights_only=False)
    except TypeError:
        obj = torch.load(str(path), map_location="cpu")
    except Exception:
        try:
            obj = torch.load(str(path), map_location="cpu")
        except Exception:
            return None, path, cfg

    model = None
    if isinstance(obj, dict) and "state_dict" in obj:
        inner_cfg = obj.get("config")
        if isinstance(inner_cfg, dict):
            for k in ("input_dim", "hidden_dim", "output_dim"):
                if isinstance(inner_cfg.get(k), int):
                    cfg[k] = inner_cfg[k]
        model = _make_mlp(obj["state_dict"], cfg)
    if model is None and hasattr(obj, "forward"):
        model = obj
        try:
            model.eval()
        except Exception:
            pass

    if model is None:
        try:
            model = __import__("torch").jit.load(str(path), map_location="cpu")
            model.eval()
        except Exception:
            model = None

    _cached_model = model
    return model, path, cfg


def brain_recommendation_text(result: Optional[Dict[str, Any]]) -> str:
    model, path, cfg = load_brain()
    if model is None or path is None:
        return ""

    x = feature_vector(result, int(cfg.get("input_dim") or 24))
    labels = cfg.get("recommendation_labels") or list(_DEFAULT_LABELS)

    try:
        import torch
    except ImportError:
        return ""

    t = torch.from_numpy(x).unsqueeze(0)
    try:
        with torch.no_grad():
            y = model(t)
        if hasattr(y, "cpu"):
            y = y.cpu().numpy().reshape(-1)
        else:
            y = np.array(y).reshape(-1)
        line = _labels_from_logits(y, list(labels))
        if not line:
            return ""
        return f"[Neural assist from {path.name}] {line}"
    except Exception:
        return ""


def brain_status_message() -> str:
    _, path, cfg = load_brain()
    if path is None:
        return "Brain: off — add models/strux_etabs_brain.pt or set BALMORES_BRAIN_PT."
    return (
        f"Brain: {path.name} | tensor in={cfg.get('input_dim')} "
        f"hidden={cfg.get('hidden_dim')} out={cfg.get('output_dim')}"
    )


def brain_config_public() -> Dict[str, Any]:
    """Safe snapshot for API / UI (no paths to secrets)."""
    _, path, cfg = load_brain()
    return {
        "weights_loaded": path is not None,
        "weights_name": path.name if path else None,
        "input_dim": cfg.get("input_dim"),
        "hidden_dim": cfg.get("hidden_dim"),
        "output_dim": cfg.get("output_dim"),
        "n_labels": len(cfg.get("recommendation_labels") or []),
    }
