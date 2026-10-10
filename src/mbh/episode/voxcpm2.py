"""Load VoxCPM2 on CPU. Importing this module imports torch and voxcpm.

Kept separate so `mbh episode build` does not require the TTS stack.
The bf16 default dtype matches proto/render_vox.py and design_one.py: the model
otherwise constructs in fp32 and exhausts a 15 GB box.
"""

from __future__ import annotations

import os

import torch

torch.set_num_threads(int(os.environ.get("MBH_THREADS", os.cpu_count() or 4)))
torch.set_default_dtype(torch.bfloat16)
from voxcpm import VoxCPM  # noqa: E402  # optional heavy dependency, imported once at module load


def load_model(threads: int | None = None):
    if threads:
        torch.set_num_threads(threads)
    model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False)
    torch.set_default_dtype(torch.float32)
    sample_rate = int(model.tts_model.sample_rate)
    return (model, sample_rate)
