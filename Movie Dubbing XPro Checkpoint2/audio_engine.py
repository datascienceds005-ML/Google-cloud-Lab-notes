"""
audio_engine.py v2.2 — Separation, TTS, Sync, Mix & QA (clean baseline)
"""
import os, sys, re, glob, time, asyncio, gc, shutil, logging, subprocess, tempfile
import numpy as np
import librosa
import soundfile as sf
import edge_tts
import psutil
from pydub import AudioSegment
from pedalboard import Pedalboard, HighpassFilter, Compressor, Limiter
import pyloudnorm as pyln

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

PFX = "dubpro_"
VOICE_MAP = {
    "Male_1": "hi-IN-MadhurNeural",   "Male_2": "mr-IN-ManoharNeural",
    "Male_3": "hi-IN-MadhurNeural",   "Male_4": "hi-IN-MadhurNeural",
    "Female_1": "hi-IN-SwaraNeural",  "Female_2": "mr-IN-AarohiNeural",
    "Female_3": "hi-IN-SwaraNeural",  "Female_4": "hi-IN-SwaraNeural",
    "Default": "hi-IN-MadhurNeural",
}

def fmt_ts(s):
    try:
        s = float(s)
    except (TypeError, ValueError):
        s = 0.0
    return f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{s % 60:06.3f}"

def _safe_unlink(p):
    try:
        if p and os.path.isfile(p):
            os.unlink(p)
    except OSError:
        pass

def cleanup_temp_artifacts(scope_dir=None):
    """Remove dubpro_* artifacts. scope_dir=None → legacy global sweep.
    scope_dir=<staging path> → ONLY that directory, so concurrent Space
    sessions, Tab 5 assets, and other tabs are never nuked (multi-user safe)."""
    if scope_dir:
        if not os.path.isdir(scope_dir):
            return
        for name in os.listdir(scope_dir):
            if name.startswith(PFX):
                _safe_unlink(os.path.join(scope_dir, name))
        gc.collect()
        return
    temp_dir = tempfile.gettempdir()
    shutil.rmtree(os.path.join(temp_dir, PFX + "separated"), ignore_errors=True)
    for name in os.listdir(temp_dir):
        if name.startswith(PFX):
            _safe_unlink(os.path.join(temp_dir, name))
    gc.collect()

def get_system_metrics():
    p = psutil.Process(os.getpid())
    vm = psutil.virtual_memory()
    return {"process_ram_mb": round(p.memory_info().rss / 1048576, 2),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "total_ram_gb": round(vm.total / 1073741824, 2),
            "available_ram_gb": round(vm.available / 1073741824, 2)}

def ts_to_seconds(t):
    if isinstance(t, (int, float)):
        return float(t)
    if ":" not in str(t):
        try: return float(t)
        except ValueError: return 0.0
    sec = 0.0
    try:
        for p in str(t).strip().split(":"):
            sec = sec * 60.0 + float(p)
    except ValueError:
        return 0.0
    return sec

def _ffprobe_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip())
    except Exception:
        return 0.0

def quick_extract_mono(video_path, boost_quiet=True):
    """Tab-5 fast path: 16 kHz mono extraction. boost_quiet adds highpass +
    dynaudnorm so low-volume / whispered dialogue is lifted before VAD/Whisper."""
    temp_dir = tempfile.gettempdir()
    out = os.path.join(
        temp_dir,
        (PFX + "quick_mono16k_boost.wav") if boost_quiet
        else (PFX + "quick_mono16k.wav"))
    if (os.path.exists(out) and os.path.exists(video_path)
            and os.path.getmtime(out) > os.path.getmtime(video_path)):
        return out
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
           "-ar", "16000", "-ac", "1"]
    if boost_quiet:
        cmd += ["-af", "highpass=f=70,dynaudnorm=f=300:g=15:m=14:p=0.9"]
    cmd += [out]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE)
    return out

def extract_and_isolate_bgm(video_path: str, work_dir: str | None = None):
    """v2.3: outputs land inside `work_dir` (the session staging dir from
    staging.py) when given, else legacy temp-root behaviour. No global
    cleanup here — the caller calls cleanup_temp_artifacts(work_dir) itself,
    so concurrent sessions and other tabs can never collide."""
    if not os.path.exists(video_path):
        raise RuntimeError(f"Video file not found: {video_path}")

    temp_dir = work_dir or tempfile.gettempdir()
    if work_dir:
        os.makedirs(temp_dir, exist_ok=True)
    stereo_wav = os.path.join(temp_dir, PFX + "stereo.wav")
    mono_wav = os.path.join(temp_dir, PFX + "vocals_mono16k.wav")
    sep_root = os.path.join(temp_dir, PFX + "separated")

    subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                    "-ar", "44100", "-ac", "2", stereo_wav],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        device = []
        try:
            import torch
            if torch.cuda.is_available():
                device = ["-d", "cuda"]
        except Exception:
            pass
        jobs = ["-j", str(max(1, psutil.cpu_count(logical=False) or 4))]
        res = subprocess.run(
            [sys.executable, "-m", "demucs", "--two-stems", "vocals", "-n", "htdemucs",
             "-o", sep_root] + device + jobs + [stereo_wav],
            capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Demucs failed: {res.stderr[-1200:]}")
        bgm_wav = max(glob.glob(os.path.join(sep_root, "htdemucs", "*", "no_vocals.wav")),
                      key=os.path.getmtime)
        voc_wav = max(glob.glob(os.path.join(sep_root, "htdemucs", "*", "vocals.wav")),
                      key=os.path.getmtime)
    except Exception as e:
        logging.warning("Demucs failed (%s) — degraded centre-cancel fallback.", e)
        bgm_wav = os.path.join(temp_dir, PFX + "bgm_karaoke.wav")
        voc_wav = stereo_wav
        subprocess.run(["ffmpeg", "-y", "-i", stereo_wav,
                        "-af", "pan=stereo|c0=0.5*c0-0.5*c1|c1=0.5*c1-0.5*c0", bgm_wav],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    subprocess.run(["ffmpeg", "-y", "-i", voc_wav, "-acodec", "pcm_s16le",
                    "-ar", "16000", "-ac", "1", mono_wav],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return mono_wav, bgm_wav, voc_wav



def _tts_sync(text, voice, out_path, retries=3):
    for attempt in range(retries):
        try:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(edge_tts.Communicate(text, voice).save(out_path))
            finally:
                loop.close()
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                return out_path
            _safe_unlink(out_path)
        except Exception as e:
            logging.warning("TTS retry %d failed: %s", attempt + 1, e)
        time.sleep(1.0 * (attempt + 1))
    return None

async def _fetch_tts(sem, text, voice, out_path, retries=2):
    async with sem:
        for attempt in range(retries + 1):
            try:
                await edge_tts.Communicate(text, voice).save(out_path)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                    return True
                _safe_unlink(out_path)
            except Exception as e:
                logging.warning("TTS attempt %d failed (%s): %s", attempt + 1, out_path, e)
            await asyncio.sleep(0.8 * (attempt + 1))
        return False
def _sanitize_tts_text(text: str) -> str:
    """Clean one transcript line for edge-tts: strip [tags]/timestamps,
    stray <ssml>/html, markdown punctuation artifacts and speaker labels;
    collapse whitespace; hard-cap length. Restored v2.3 (was lost in the
    hi-IN voice-map edit — engine line ~178 calls this)."""
    t = str(text or "")
    t = re.sub(r"\[[^\]]*\]", " ", t)                              # [music], [ts --> ts]
    t = re.sub(r"<[^>]+>", " ", t)                                 # <break/> etc.
    t = re.sub(r"[*_`#>|]", " ", t)                                # markdown artifacts
    t = re.sub(r"\b(?:Male|Female|Speaker)[-_ ]?\d*\b", " ", t)    # speaker labels
    t = re.sub(r"\s+", " ", t).strip()
    return t[:1800]


def generate_tts_batch(segments, temp_dir):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    sem = asyncio.Semaphore(4)
    paths, tasks, tidx = [], [], []
    try:
        for i, seg in enumerate(segments):
            text = _sanitize_tts_text(seg.get("text", ""))
            if not text or text == "(silence)":
                paths.append(None)
                continue
            out_path = os.path.join(temp_dir, f"{PFX}tts_{i}.mp3")
            paths.append(out_path)

            # डाइनैमिक स्पीकर (जैसे Male_1, Male_2, Female_1 आदि) के लिए सही वॉइस मैप चुनना
            speaker_key = seg.get("speaker", "Default")
            voice = VOICE_MAP.get(speaker_key, VOICE_MAP["Default"])

            tasks.append(_fetch_tts(sem, text, voice, out_path))
            tidx.append(i)
        results = loop.run_until_complete(
            asyncio.gather(*tasks, return_exceptions=True))
        for k, r in enumerate(results):
            if r is not True:
                paths[tidx[k]] = None
        return paths
    finally:
        loop.close()
        gc.collect()

def _merge_translations(trans_text, ref_segments):
    lines = [l.strip() for l in trans_text.splitlines() if l.strip()]
    matched, recovered, unfilled = 0, 0, []
    merged = []

    # टाइमस्टैम्प आधारित मैचिंग और आर्डर आधारित रिकवरी लॉजिक
    current_ts = None
    current_trans = []

    parsed_blocks = []
    block_ts = None
    block_lines = []

    for l in lines:
        if l.startswith("[") and "-->" in l:
            if block_ts:
                parsed_blocks.append((block_ts, " ".join(block_lines)))
            block_ts = l
            block_lines = []
        else:
            block_lines.append(l)
    if block_ts:
        parsed_blocks.append((block_ts, " ".join(block_lines)))

    for idx, ref in enumerate(ref_segments):
        start = ref["start"]
        end = ref["end"]
        speaker = ref["speaker"]

        # ट्रांसलेशन ढूंढना
        translated_text = ""
        if idx < len(lines) and not lines[idx].startswith("["):
            translated_text = lines[idx]
            recovered += 1
        else:
            translated_text = f"(silence)"
            unfilled.append(idx)

        merged.append({
            "start": start,
            "end": end,
            "speaker": speaker,
            "text": translated_text if translated_text else "(silence)"
        })
        matched += 1

    return merged, {"matched": matched, "recovered": recovered, "unfilled": unfilled}

def _fade_truncate(y, n, sr, fade_ms=25):
    y = y[:n].copy()
    f = min(len(y), int(sr * fade_ms / 1000))
    if f > 0:
        y[-f:] *= np.linspace(1, 0, f)
    return y

def _fade_edges(y, sr, ms=8):
    f = min(len(y) // 2, int(sr * ms / 1000))
    if f > 0:
        ramp = np.linspace(0, 1, f)
        y[:f] *= ramp
        y[-f:] *= ramp[::-1]
    return y

def fit_duration_wsola(wav_path, target_ms, max_stretch=1.45):
    y, sr = librosa.load(wav_path, sr=24000, mono=True)
    cur_ms = len(y) / sr * 1000.0
    if cur_ms < 1:
        return wav_path
    target_ms = max(100.0, float(target_ms))
    if abs(cur_ms - target_ms) / target_ms < 0.08:
        return wav_path
    rate = float(np.clip(cur_ms / target_ms, 1.0 / max_stretch, max_stretch))
    y2 = librosa.effects.time_stretch(y, rate=rate)
    n = int(target_ms / 1000.0 * sr)
    if len(y2) > n:
        y2 = _fade_truncate(y2, n, sr)
    elif len(y2) < n:
        y2 = np.pad(y2, (0, n - len(y2)))
    out = wav_path.replace(".wav", "_fit.wav")
    sf.write(out, y2, sr)
    return out

def _load_tts_clip(mp3_path, sr):
    try:
        seg = AudioSegment.from_mp3(mp3_path).set_frame_rate(sr).set_channels(1)
        if seg.dBFS is None:
            return None
        y = np.array(seg.get_array_of_samples()).astype(np.float32)
        y /= {1: 128.0, 2: 32768.0, 4: 2147483648.0}[seg.sample_width]
        return y
    except Exception:
        return None

def _normalize_clip(y, target_dbfs=-20.0):
    rms = float(np.sqrt(np.mean(y ** 2)) + 1e-9)
    gain = float(np.clip(10 ** (target_dbfs / 20.0) / rms, 0.25, 7.94))
    y = y * gain
    peak = np.abs(y).max()
    return y * (0.95 / peak) if peak > 0.95 else y

def master_audio(wav_path, target_lufs=-16.0):
    data, sr = sf.read(wav_path)
    if data.ndim == 1:
        data = np.column_stack([data, data])
    data = data.astype(np.float32)
    try:
        loud = pyln.Meter(sr).integrated_loudness(data)
        if np.isfinite(loud) and -70.0 < loud < 0:
            data = pyln.normalize.loudness(data, loud, target_lufs)
    except Exception:
        pass
    out = Pedalboard([HighpassFilter(75),
                      Compressor(threshold_db=-18.0, ratio=2.5),
                      Limiter(threshold_db=-1.0)])(data, sr)
    path = wav_path.replace(".wav", "_mastered.wav")
    sf.write(path, np.clip(out, -1.0, 1.0), sr)
    del data, out
    gc.collect()
    return path

def _track_mean_db(wav_path):
    """Mean level (dBFS) of a wav — the audible-gate: a 'silent' dub track
    fails loudly HERE instead of surfacing as a silent video later."""
    data, _ = sf.read(wav_path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    rms = float(np.sqrt(np.mean(np.square(data)))) if len(data) else 0.0
    return float(20 * np.log10(rms)) if rms > 0 else -120.0


def build_dub_track(segments, tts_paths, temp_dir, sr=24000):
    """v2.4 — anti-distortion rebuild:
      • numpy float accumulation (replaces pydub int32 wrapping of float32
        bytes — the source of the garbled 'gichbichana' artifacts)
      • per-clip PEAK normalisation to -3 dBFS working level, gain limited
        to ±12 dB (master limiter provides the final -1 dBFS ceiling)
      • WSOLA speed-up clamped to 1.18x max (natural conversational bound);
        short lines are centre-padded for lip-sync instead of slowed
      • 12 ms micro-fades on every clip edge, 25 ms fade on the rare trim —
        click-free without audible pumping
    Returns (wav_path, placed_count, missing_indices)."""
    order = sorted(range(len(segments)),
                   key=lambda i: ts_to_seconds(segments[i]["start"]))
    segs = [segments[i] for i in order]
    clips = [tts_paths[i] for i in order]
    if not segs:
        raise RuntimeError("No segments to dub")

    total_n = int((ts_to_seconds(segs[-1]["end"]) + 2.0) * sr)
    track = np.zeros(total_n, dtype=np.float32)
    fade = np.linspace(0.0, 1.0, max(2, int(0.012 * sr)), dtype=np.float32)
    placed, missing = 0, []

    for i, (seg, mp3) in enumerate(zip(segs, clips)):
        text = _sanitize_tts_text(seg.get("text", ""))
        if not text or text == "(silence)":
            continue
        p = mp3
        if not p or not os.path.exists(p) or os.path.getsize(p) < 1024:
            v = VOICE_MAP.get(seg.get("speaker", "Default"), VOICE_MAP["Default"])
            p = _tts_sync(text, v, os.path.join(temp_dir, f"{PFX}tts_fix_{i}.mp3"))
        if not p or not os.path.exists(p) or os.path.getsize(p) < 1024:
            missing.append(i)
            continue
        y = _load_tts_clip(p, sr)
        if y is None or len(y) < sr // 20:
            missing.append(i)
            continue
        y = np.asarray(y, dtype=np.float32)

        # peak-normalise to -3 dBFS, gain limited to ±12 dB
        peak = float(np.max(np.abs(y))) + 1e-9
        gain = float(np.clip((10.0 ** (-3.0 / 20.0)) / peak, 0.25, 4.0))
        y *= gain

        start_ms = int(ts_to_seconds(seg["start"]) * 1000)
        win_ms = max(350, int((ts_to_seconds(seg["end"])
                               - ts_to_seconds(seg["start"])) * 1000))
        next_ms = (int(ts_to_seconds(segs[i + 1]["start"]) * 1000)
                   if i + 1 < len(segs) else (total_n * 1000) // sr)
        gap_ms = max(0, next_ms - start_ms - 50)
        allowed_ms = win_ms + min(gap_ms, int(win_ms * 0.35) + 700)

        need_ms = len(y) * 1000.0 / sr
        if need_ms > win_ms:
            rate = min(1.18, need_ms / win_ms)          # speed up max 18 %
            y = librosa.effects.time_stretch(y, rate=rate)
        n_allowed = int(allowed_ms / 1000.0 * sr)
        if len(y) > n_allowed:                          # rare: gentle fade-trim
            f = min(n_allowed, int(0.025 * sr))
            y = y[:n_allowed].copy()
            y[-f:] *= np.linspace(1.0, 0.0, f, dtype=np.float32)

        # micro-fades at clip edges (kills clicks, inaudible at 12 ms)
        f = min(len(y) // 2, fade.size)
        y[:f] *= fade[:f]
        y[-f:] *= fade[::-1][:f]

        # centre inside the natural window (lip-sync) — never slow speech
        n_win = int(win_ms / 1000.0 * sr)
        pad = max(0, (n_win - len(y)) // 2) if len(y) < n_win else 0
        i0 = min(total_n - 1, int(start_ms / 1000.0 * sr) + pad)
        i1 = min(total_n, i0 + len(y))
        if i1 > i0:
            track[i0:i1] += y[:i1 - i0]
            placed += 1

    np.clip(track, -0.84, 0.84, out=track)              # hard ceiling -1.5 dBFS
    out = os.path.join(temp_dir, PFX + "dub_continuous.wav")
    sf.write(out, track, sr, subtype="PCM_16")
    return out, placed, missing


def mix_bgm_dub(bgm_wav, dub_wav, duck_db=-12.0, temp_dir=None,
                voice_gain_db=3.0):
    """v2.4 — dialogue-safe ducking mix:
      • the dub bus is asplit into sidechain-TRIGGER + MIX-BUS — the previous
        graph re-consumed the [dub] output label, which misroutes/loses the
        dialogue on many ffmpeg builds (root cause of voice dropping)
      • dialogue pre-gained +voice_gain_db → explicit volume leveling that
        guarantees speech prominence (equivalent of amix weights=1 1.2,
        without version-dependent weights parsing)
      • amix normalize=0 (no default -6 dB bus halving), duration=longest,
        dropout_transition=0 (no level jumps), rates matched via aformat
      • hard-fails with stderr; no silent fallbacks"""
    mix_out = os.path.join(temp_dir or tempfile.gettempdir(),
                           PFX + "mix_pre_master.wav")
    ratio = float(np.clip(abs(duck_db) / 3.0, 2.0, 6.0))
    filt = (
        "[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[bg];"
        "[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[dub0];"
        f"[dub0]volume={voice_gain_db:.1f}dB[dub1];"
        "[dub1]asplit=2[trig][mix];"
        f"[bg][trig]sidechaincompress=threshold=0.03:ratio={ratio:.1f}:"
        "attack=8:release=280[bgd];"
        "[bgd][mix]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[a]"
    )
    res = subprocess.run(["ffmpeg", "-y", "-i", bgm_wav, "-i", dub_wav,
                          "-filter_complex", filt, "-map", "[a]",
                          "-ac", "2", mix_out],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"BGM+dub mix failed: {res.stderr[-800:]}")
    return mix_out

def mux_video_audio_detached(video_path, audio_wav, temp_dir=None):
    """Simple 2-input mux: audio comes ONLY from input 1 — source audio
    streams are structurally unmappable. Output path is ALWAYS the last
    positional argument (previous slicing bug made ffmpeg treat '192k'
    as the output file and never wrote `out`)."""
    out = os.path.join(temp_dir or tempfile.gettempdir(), PFX + "dubbed_final.mp4")
    for vargs in (["-c:v", "copy"],
                  ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]):
        cmd = (["ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_wav,
                "-map", "0:v:0",
                "-map", "1:a"]
               + vargs +
               ["-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", "-shortest",
                out])
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return out
    raise RuntimeError(f"Mux failed: {res.stderr[-800:]}")

    
def mix_and_remux(video_path, bgm_wav, segments, tts_paths, duck_db, temp_dir,
                  vocals_wav=None, target_lufs=-16.0, apply_residual_mask=False):
    sr = 24000
    # Optional deep-clean: spectrally subtract residual vocal bleed from BGM
    # (Tab 4 "Deep-clean BGM" checkbox; uses the demucs vocals stem as reference).
    if apply_residual_mask and vocals_wav and os.path.exists(vocals_wav):
        try:
            bgm_wav = spectral_residual_mask(bgm_wav, vocals_wav)
        except Exception as e:
            logging.warning("Residual-mask deep clean failed (%s) — using raw BGM.", e)
    segments = sorted(segments, key=lambda s: ts_to_seconds(s["start"]))
    last_end = max([ts_to_seconds(s["end"]) for s in segments], default=0.0)
    video_dur = _ffprobe_duration(video_path) or (last_end + 2.0)
    total_n = int((max(video_dur, last_end) + 2.0) * sr)
    dub = np.zeros((total_n, 2), dtype=np.float32)

    missing = 0
    for i, seg in enumerate(segments):
        text = _sanitize_tts_text(seg.get("text", ""))
        mp3 = tts_paths[i] if i < len(tts_paths) else None

        if (not mp3 or not os.path.exists(mp3)) and text and text != "(silence)":
            speaker_key = seg.get("speaker", "Default")
            voice = VOICE_MAP.get(speaker_key, VOICE_MAP["Default"])
            retry_path = mp3 or os.path.join(temp_dir, f"{PFX}tts_retry_{i}.mp3")
            mp3 = _tts_sync(text, voice, retry_path)
            if i < len(tts_paths): tts_paths[i] = mp3

        if not mp3 or not os.path.exists(mp3):
            if text and text != "(silence)":
                missing += 1
            continue
        try:
            clip = _load_tts_clip(mp3, sr)
            if clip is None or len(clip) < sr // 20:
                missing += 1
                continue
            clip = _normalize_clip(clip)
            start_s = ts_to_seconds(seg["start"])
            end_s = ts_to_seconds(seg["end"])
            next_start = ts_to_seconds(segments[i + 1]["start"]) if i + 1 < len(segments) else video_dur
            window = max(0.35, end_s - start_s)
            gap = max(0.0, next_start - start_s - 0.05)
            max_window = max(window, min(gap, window * 1.75, window + 1.5))
            need_ms = len(clip) / sr * 1000.0
            target_ms = max(window * 1000.0, min(max_window * 1000.0, need_ms))
            tmp_wav = mp3.replace(".mp3", ".wav")
            sf.write(tmp_wav, clip, sr)
            fitted = fit_duration_wsola(tmp_wav, target_ms)
            y, _ = librosa.load(fitted, sr=sr, mono=True)
            _safe_unlink(mp3); _safe_unlink(tmp_wav)
            if fitted != tmp_wav: _safe_unlink(fitted)
            y = _fade_edges(y, sr, 8)
            i0 = int((start_s + 0.04) * sr)
            if i0 >= total_n:
                i0 = max(0, total_n - len(y))
            i1 = min(total_n, i0 + len(y))
            if i1 > i0:
                dub[i0:i1, 0] += y[:i1 - i0]
                dub[i0:i1, 1] += y[:i1 - i0]
        except Exception:
            missing += 1

    dub_wav = os.path.join(temp_dir, PFX + "dub_track.wav")
    sf.write(dub_wav, dub, sr)
    mastered = master_audio(dub_wav, target_lufs)

    output_video = os.path.join(temp_dir, PFX + "dubbed_final.mp4")
    ratio = float(np.clip(abs(duck_db) / 2.0, 2.0, 12.0))

    # PATCH T5-DETACH (zero original-audio guarantee): the ONLY audio in the
    # output is [a], built strictly from input 1 (Demucs BGM stem, ducked)
    # + input 2 (Hindi TTS master). Input 0 contributes video ONLY; the
    # negative map '-0:a?' actively strips every source audio stream.
    filt = (
        "[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[bg];"
        "[2:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[dub];"
        f"[bg][dub]sidechaincompress=threshold=0.03:ratio={ratio:.1f}:"
        "attack=8:release=280[bgd];"
        "[bgd][dub]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
    )

    def run_encode(vargs, f):
        cmd = (["ffmpeg", "-y", "-i", video_path, "-i", bgm_wav, "-i", mastered,
                "-filter_complex", f,
                "-map", "0:v:0",
                "-map", "[a]",
                "-map", "-0:a?",
                "-sn", "-dn"] + vargs +
               ["-c:a", "aac", "-b:a", "192k", "-shortest",
                "-movflags", "+faststart", output_video])
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE)
        if res.returncode != 0:
            logging.warning("encode attempt failed: %s",
                            res.stderr.decode("utf-8", "ignore")[-400:])
            raise subprocess.CalledProcessError(res.returncode, cmd,
                                                stderr=res.stderr)


    attempts = [(["-c:v", "copy"], filt),
                (["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"], filt)]

    last = None
    for vargs, f in attempts:
        try:
            run_encode(vargs, f); last = None; break
        except subprocess.CalledProcessError as e:
            last = e
    if last is not None:
        err = last.stderr.decode("utf-8", "ignore") if last.stderr else "unknown"
        raise RuntimeError(f"FFmpeg mixing failed: {err[-1200:]}")

    qa = verify_output(output_video, mastered, segments, missing, vocals_wav, video_dur)
    gc.collect()
    return output_video, mastered, qa

def find_uncovered_dialogue(vocals_wav, covered_windows, total_dur,
                            thresh_db=-38.0, min_len=0.5, pad=0.3):
    y, sr = librosa.load(vocals_wav, sr=16000, mono=True)
    hop = int(0.05 * sr)
    db = 20 * np.log10(librosa.feature.rms(y=y, frame_length=int(0.2 * sr),
                                           hop_length=hop)[0] + 1e-9)
    active = db > thresh_db
    for k in range(1, len(active)):
        if active[k - 1] and db[k] > thresh_db - 6:
            active[k] = True
    uncovered, t0 = [], None
    for k, a in enumerate(active):
        t = k * hop / sr
        in_cover = any(s - pad <= t <= e + pad for s, e in covered_windows)
        if a and not in_cover and t < total_dur:
            if t0 is None:
                t0 = t
        else:
            if t0 is not None and t - t0 >= min_len:
                uncovered.append((round(t0, 2), round(t, 2)))
            t0 = None
    if t0 is not None and total_dur - t0 >= min_len:
        uncovered.append((round(t0, 2), round(total_dur, 2)))
    return uncovered[:20]

def verify_output(output_video, dub_master, segments, tts_missing,
                  vocals_wav, video_dur):
    report = {"tts_missing": tts_missing, "audio_streams": None,
              "duration_ok": None, "silent_dub_windows": [],
              "uncovered_dialogue": [], "status": "ok"}
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", output_video],
            capture_output=True, text=True)
        report["audio_streams"] = len([l for l in probe.stdout.splitlines() if l.strip()])
        if report["audio_streams"] != 1:
            report["status"] = "warn"
        report["duration_ok"] = abs(_ffprobe_duration(output_video) - video_dur) <= 2.0
        if not report["duration_ok"]:
            report["status"] = "warn"
    except Exception:
        report["status"] = "warn"

    try:
        qa_wav = os.path.join(os.path.dirname(output_video), PFX + "qa.wav")
        subprocess.run(["ffmpeg", "-y", "-i", output_video, "-vn", "-ac", "1",
                        "-ar", "16000", qa_wav], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        y, sr = librosa.load(qa_wav, sr=16000, mono=True)
        _safe_unlink(qa_wav)
        for s in segments:
            a, b = int(ts_to_seconds(s["start"]) * sr), int(ts_to_seconds(s["end"]) * sr)
            if b <= a or b > len(y):
                continue
            if float(np.sqrt(np.mean(y[a:b] ** 2))) < 0.004:
                report["silent_dub_windows"].append(s["start"])
        if report["silent_dub_windows"]:
            report["status"] = "warn"
    except Exception:
        pass

    if vocals_wav and os.path.exists(vocals_wav):
        try:
            covered = [(ts_to_seconds(s["start"]), ts_to_seconds(s["end"]))
                       for s in segments]
            report["uncovered_dialogue"] = find_uncovered_dialogue(
                vocals_wav, covered, video_dur)
            if report["uncovered_dialogue"]:
                report["status"] = "warn"
        except Exception:
            pass
    return report

def spectral_residual_mask(bgm_wav, vocals_wav, out_wav=None, strength=0.55,
                           chunk_sec=20.0):
    out_wav = out_wav or bgm_wav.replace(".wav", "_masked.wav")
    yb, sr = librosa.load(bgm_wav, sr=44100, mono=False)
    yv, _ = librosa.load(vocals_wav, sr=44100, mono=False)
    if yb.ndim == 1: yb = np.stack([yb, yb])
    if yv.ndim == 1: yv = np.stack([yv, yv])
    n = min(yb.shape[1], yv.shape[1]); yb, yv = yb[:, :n], yv[:, :n]
    n_fft, hop, fade = 2048, 512, int(0.25 * sr)
    ch = int(chunk_sec * sr)
    out, wsum = np.zeros((2, n)), np.zeros(n)
    pos = 0
    while pos < n:
        a1 = min(n, pos + ch); L = a1 - pos
        f = min(fade, L)
        w = np.ones(L)
        if pos > 0: w[:f] = np.linspace(0, 1, f)
        if a1 < n:  w[-f:] = np.linspace(1, 0, f)
        for c in range(2):
            B = librosa.stft(yb[c, pos:a1], n_fft=n_fft, hop_length=hop)
            V = librosa.stft(yv[c, pos:a1], n_fft=n_fft, hop_length=hop)
            vm, bm = np.abs(V), np.abs(B)
            mask = vm * vm / (vm * vm + bm * bm + 1e-9)
            out[c, pos:a1] += librosa.istft(B * (1.0 - strength * mask),
                                            hop_length=hop, length=L) * w
        wsum[pos:a1] += w
        if a1 >= n:
            break
        pos += max(1, ch - fade)
    out /= np.maximum(wsum, 1e-9)[None, :]
    sf.write(out_wav, out.T, sr)
    return out_wav
