# run_demucs.py
import sys
import contextlib
import torchaudio
import soundfile as sf
import torch
import numpy as np

# 1. Patched torchaudio.save using soundfile
def _patched_save(filepath, src, sample_rate, **kwargs):
    if isinstance(src, torch.Tensor):
        src = src.cpu().numpy()

    # soundfile expects (samples, channels), torchaudio uses (channels, samples)
    if src.ndim == 1:
        src = np.column_stack([src])
    else:
        src = src.T

    sf.write(filepath, src, sample_rate)

# 2. Context manager for safe temporary patching
@contextlib.contextmanager
def patched_torchaudio_save():
    """Temporarily patch torchaudio.save to use soundfile backend.

    This avoids the fragile global monkey-patch and ensures the original
    is restored even if exceptions occur.
    """
    original_save = torchaudio.save
    torchaudio.save = _patched_save
    try:
        yield
    finally:
        torchaudio.save = original_save

# 3. Now run the Demucs CLI with the patch applied
if __name__ == "__main__":
    from demucs.separate import main
    with patched_torchaudio_save():
        main(sys.argv[1:])
