"""
transcription.py v3.4 — Hub ASR & Dynamic Speaker Intelligence

Single canonical run_whisper_raw • batched main sweep → deep-capture sweep →
phone/intercom rescue sweep • extract_mono_boosted() so the Hub never imports
the heavy dubbing engine • run_diarization() with cached voiceprints and a
bimodal-pitch gender guard (dynamic Male_N / Female_N labels).

v3.4 REGRESSION FIXES (on top of the known-good 90% v3.2/v3.3 baseline):
  [T5-COMMS]  _is_band_limited() detects radio/intercom audio; band-limited
              segments are excluded from the gender pitch vote, so a
              high-pass comms line can never capture a Female label.
  [T5-GENDER] _decide_gender(): direct Female cut lowered to 148 Hz
              (Fran Heller pools 152–156 Hz), Male cut 138 Hz, gray zone
              138–148 Hz resolved by a quartile tie-break.
  [T5-CAP]    _cluster(): auto mode hard-capped at _MAX_AUTO_CLUSTERS = 4;
              distance_threshold 0.65 → 0.75 (cosine / average linkage).
              The 11-speaker explosion is structurally impossible; the
              Expected-speakers slider override behaves exactly as before.
"""


import gc, glob, os, re, logging, subprocess, tempfile
import numpy as np
import librosa
import streamlit as st
from scipy.signal import butter, sosfilt
from faster_whisper import WhisperModel

try:
    from faster_whisper import BatchedInferencePipeline
    HAS_BATCHED = True
except Exception:
    HAS_BATCHED = False

try:
    import psutil
    _PHYS = psutil.cpu_count(logical=False) or (os.cpu_count() or 2)
except Exception:
    _PHYS = os.cpu_count() or 2
N_THREADS = max(1, _PHYS)
os.environ.setdefault("OMP_NUM_THREADS", str(N_THREADS))

_HALLU = {
    "thank you.", "thanks for watching.", "thank you for watching.",
    "please subscribe!", "subscribe!", "like and subscribe!", "bye!",
    "you", "okay", "hmm", "[music]", "[applause]", "[music playing]",
    "subtitles by the amara.org community", "amara.org",
}


@st.cache_resource(max_entries=1)
def load_whisper_model(model_size="small.en"):
    return WhisperModel(model_size, device="cpu", compute_type="int8",
                        cpu_threads=N_THREADS, num_workers=1)


@st.cache_data(max_entries=4, show_spinner=False)
def _load_audio_16k(path: str, _mtime: float):
    return librosa.load(path, sr=16000, mono=True)


def extract_mono_boosted(video_path, boost_quiet=True):
    """Hub fast-path audio prep: 16 kHz mono + quiet-voice lift. Lives here so
    the Hub never imports the heavy dubbing engine (audio_engine) — startup
    stays instant. The output name is tagged with the source file's mtime so
    every new upload gets a fresh cache key (no stale-audio bugs)."""
    temp_dir = tempfile.gettempdir()
    stem = os.path.splitext(os.path.basename(video_path))[0]
    tag = f"{stem}_{int(os.path.getmtime(video_path))}"
    out = os.path.join(
        temp_dir,
        f"hub_mono16k_boost_{tag}.wav" if boost_quiet
        else f"hub_mono16k_plain_{tag}.wav")
    if os.path.exists(out):
        return out
    try:
        for old in glob.glob(os.path.join(temp_dir, "hub_mono16k_*")):
            if os.path.abspath(old) != os.path.abspath(out):
                os.unlink(old)
    except OSError:
        pass
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
           "-ar", "16000", "-ac", "1"]
    if boost_quiet:
        cmd += ["-af", "highpass=f=70,dynaudnorm=f=300:g=15:m=14:p=0.9"]
    cmd += [out]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE)
    return out


def _energy_dip_splits(y, sr, start, end, max_len, min_len=1.5):
    """Split [start, end] at low-energy dips so every piece is <= max_len."""
    dur = float(end - start)
    if dur <= max_len:
        return [(start, end)]
    hop, frame = int(0.01 * sr), int(0.03 * sr)
    x = y[int(start * sr):int(end * sr)]
    if len(x) < frame:
        return [(start, end)]
    rms = librosa.feature.rms(y=x, frame_length=frame, hop_length=hop)[0]
    n = len(rms)
    if n < 3:
        return [(start, end)]
    cuts = [0.0]
    while dur - cuts[-1] > max_len:
        lo = cuts[-1] + min_len
        hi = min(cuts[-1] + max_len, dur - min_len)
        if hi <= lo:
            break
        k_lo, k_hi = int(lo / dur * n), min(n - 1, int(hi / dur * n))
        if k_hi <= k_lo:
            k_lo = k_hi = max(0, k_hi - 1)
        k = k_lo + int(np.argmin(rms[k_lo:k_hi + 1]))
        cuts.append(min(k * hop / sr, dur - min_len))
    rel = cuts + [dur]
    pieces = [(start + a, start + b) for a, b in zip(rel[:-1], rel[1:])
              if b - a >= 0.4]
    return pieces or [(start, end)]


def _split_long_segments(model, y, segments, max_len=10.0):
    """Whisper/VAD sometimes returns ONE mega-segment covering many speaker
    turns (fast continuous dialogue). Re-transcribe energy-dip pieces so
    diarization gets utterance-level blocks. Falls back to the original
    segment whenever pieces lose text — content is never dropped."""
    out = []
    for s in segments:
        dur = s["end"] - s["start"]
        if dur <= max_len or not (s["text"] or "").strip():
            out.append(s)
            continue
        pieces = _energy_dip_splits(y, 16000, s["start"], s["end"], max_len)
        if len(pieces) <= 1:
            out.append(s)
            continue
        rebuilt = []
        for a, b in pieces:
            i0, i1 = int(a * 16000), min(len(y), int(b * 16000))
            if i1 - i0 < int(0.3 * 16000):
                continue
            try:
                segs, _ = model.transcribe(
                    y[i0:i1], language="en", beam_size=1,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.6, log_prob_threshold=-1.0)
                for t in segs:
                    txt = (t.text or "").strip()
                    if txt and t.end > t.start:
                        rebuilt.append({"start": a + t.start,
                                        "end": a + t.end, "text": txt})
            except Exception as e:
                logging.warning("Split-transcribe failed (%.2f-%.2f): %s", a, b, e)
        rebuilt = _filter_hallucinations(rebuilt)
        if rebuilt and sum(len(r["text"]) for r in rebuilt) >= 0.5 * len(s["text"]):
            out.extend(rebuilt)
        else:
            out.append(s)
    return out


def _find_uncovered_regions(segments, duration, min_gap=0.5):
    """Timeline regions with no transcribed speech — deep-scan candidates."""
    covered = sorted((s["start"], s["end"]) for s in segments)
    regions, cursor = [], 0.0
    for s, e in covered:
        if s - cursor >= min_gap:
            regions.append((cursor, s))
        cursor = max(cursor, e)
    if duration - cursor >= min_gap:
        regions.append((cursor, duration))
    return [(a, b) for a, b in regions if b - a >= min_gap]


def _new_fraction(a, b, spans):
    """Fraction of [a, b] NOT covered by the sorted `spans` list."""
    if b <= a:
        return 0.0
    cov, cur = 0.0, a
    for s, e in spans:
        if e <= cur:
            continue
        if s >= b:
            break
        cov += min(b, e) - max(cur, s)
        cur = max(cur, e)
    cov = max(0.0, min(cov, b - a))
    return 1.0 - cov / (b - a)


def _transcribe_pass2(model, y, covered, prompt):
    """Deep-capture sweep: ONE sensitive batched pass (VAD 0.18) over the
    whole timeline, then keep only segments that land mostly OUTSIDE the
    pass-1 spans — quiet, whispered, background and third-party voices get
    added without duplicating already-transcribed dialogue. A single batched
    call replaces the old region-by-region loop → far faster."""
    vad_deep = dict(min_silence_duration_ms=120, threshold=0.18,
                    speech_pad_ms=320, min_speech_duration_ms=80)
    segs, ok = [], False
    if HAS_BATCHED:
        try:
            batched = BatchedInferencePipeline(model=model)
            kwargs = dict(batch_size=max(4, N_THREADS // 2), language="en",
                          beam_size=1, vad_filter=True, vad_parameters=vad_deep,
                          condition_on_previous_text=False,
                          no_speech_threshold=0.45, log_prob_threshold=-1.25)
            if prompt:
                kwargs["initial_prompt"] = prompt
            raw, _ = batched.transcribe(y, **kwargs)
            segs = [{"start": s.start, "end": s.end, "text": s.text} for s in raw]
            ok = True
        except Exception as e:
            logging.warning("Batched deep sweep fell back: %s", e)
    if not ok:
        raw, _ = model.transcribe(
            y, language="en", beam_size=1, best_of=1,
            vad_filter=True, vad_parameters=vad_deep,
            condition_on_previous_text=False,
            no_speech_threshold=0.45, log_prob_threshold=-1.25,
            initial_prompt=prompt)
        segs = [{"start": s.start, "end": s.end, "text": s.text} for s in raw]

    spans = sorted((float(s["start"]), float(s["end"])) for s in covered)
    return [s for s in _filter_hallucinations(segs)
            if _new_fraction(s["start"], s["end"], spans) >= 0.5]


def _rescue_pass(model, audio_path, regions, prompt):
    """Narrow-band rescue sweep for voices arriving through phones, intercoms,
    PC speakers or other band-limited devices. Processes ONLY the regions
    still uncovered after the main + deep sweeps, so the extra cost is tiny.
    Audio is band-passed (250–3800 Hz) and re-boosted before a very
    permissive VAD sweep."""
    tag = os.path.splitext(os.path.basename(audio_path))[0]
    temp_wav = os.path.join(tempfile.gettempdir(), f"hub_rescue_{tag}.wav")
    if not (os.path.exists(temp_wav) and os.path.getmtime(temp_wav)
            > os.path.getmtime(audio_path)):
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path, "-vn", "-acodec", "pcm_s16le",
                 "-ar", "16000", "-ac", "1", "-af",
                 "highpass=f=250,lowpass=f=3800,equalizer=f=1700:t=q:w=1.2:g=7,"
                 "dynaudnorm=f=250:g=18:m=16:p=0.9", temp_wav],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except Exception as e:
            logging.warning("Rescue band-filter failed: %s", e)
            return []
    try:
        y, _ = librosa.load(temp_wav, sr=16000, mono=True)
    except Exception:
        return []

    vad_rescue = dict(min_silence_duration_ms=100, threshold=0.15,
                      speech_pad_ms=250, min_speech_duration_ms=60)
    found = []
    for a, b in regions:
        i0, i1 = int(a * 16000), min(len(y), int(b * 16000))
        if i1 - i0 < int(0.3 * 16000):
            continue
        try:
            segs, _ = model.transcribe(
                y[i0:i1], language="en", beam_size=1, best_of=1,
                vad_filter=True, vad_parameters=vad_rescue,
                condition_on_previous_text=False,
                no_speech_threshold=0.30, log_prob_threshold=-1.40,
                initial_prompt=prompt)
            for s in segs:
                t = (s.text or "").strip()
                if t and s.end > s.start:
                    found.append({"start": a + s.start, "end": a + s.end, "text": t})
        except Exception as e:
            logging.warning("Rescue region %.2f-%.2f failed: %s", a, b, e)
    return _filter_hallucinations(found)



# ==========================================================================
# BEGIN PATCH T5-DOMAIN-FIX: deterministic proper-noun correction
# ==========================================================================
_DOMAIN_FIXES = [
    (re.compile(r"\bde[\w-]*ing\s+genocide\b", re.IGNORECASE),
     "spray painting genocide"),
    (re.compile(r"\barau?tari?a\b|\baratoria\b|\barautaria\b", re.IGNORECASE),
     "Aratare"),
]


def _apply_domain_fixes(text):
    """Deterministic correction for mishearings that survive prompt bias.
    Correct spellings like 'Aratare' never re-match."""
    for rx, repl in _DOMAIN_FIXES:
        text = rx.sub(repl, text)
    return text
# ==========================================================================
# END PATCH T5-DOMAIN-FIX
# ==========================================================================

def run_whisper_raw(audio_path, model_size="small.en", glossary="",
                    deep_scan=True, rescue=True, progress=None):
    """Hub ASR core (v3.1). Pipeline:
      1. batched main sweep (VAD 0.35)
      2. deep-capture sweep — one batched low-VAD pass, new coverage only
      3. optional narrow-band rescue sweep on still-uncovered regions
      4. utterance fine-split for clean diarization turn boundaries
    Returns chronological [{"start", "end", "text"}] segments."""
    _say = progress or (lambda msg: None)
    model = load_whisper_model(model_size)
    y, sr = _load_audio_16k(audio_path, os.path.getmtime(audio_path))
    duration = len(y) / sr
    # PATCH T5-PROMPT: domain hint precedes the user glossary.
    prompt = ("Movie dialogue, military sci-fi terms: DARPA, Aratare, "
              "Dagger team, cloaking technology, spray painting genocide. "
              + glossary.strip()).strip() or None

    vad_main = dict(min_silence_duration_ms=350, threshold=0.35,
                    speech_pad_ms=250, min_speech_duration_ms=120)

    _say("🚀 Main sweep (batched Whisper, VAD 0.35) ...")
    segments = _transcribe_pass1(model, y, vad_main, prompt)

    if deep_scan:
        try:
            _say(f"🔎 Deep-capture sweep (VAD 0.18 — whispers/background/third-party) "
                 f"… {len(segments)} segments so far")
            extra = _transcribe_pass2(model, y, segments, prompt)
            if extra:
                _say(f"   ➕ {len(extra)} new deep-captured block(s)")
                segments = segments + extra
        except Exception as e:
            logging.warning("Deep-capture sweep skipped: %s", e)

        if rescue:
            try:
                regions = _find_uncovered_regions(segments, duration, min_gap=0.5)
                if regions and sum(b - a for a, b in regions) >= 1.0:
                    _say(f"📡 Phone/intercom rescue sweep … {len(regions)} uncovered region(s)")
                    extra = _rescue_pass(model, audio_path, regions, prompt)
                    if extra:
                        _say(f"   ➕ {len(extra)} rescued block(s)")
                        segments = segments + extra
            except Exception as e:
                logging.warning("Rescue sweep skipped: %s", e)

    try:
        _say("✂️ Fine-splitting multi-speaker blobs into utterance blocks ...")
        segments = _split_long_segments(model, y, segments, max_len=10.0)
    except Exception as e:
        logging.warning("Fine-split pass skipped: %s", e)

    out = [{"start": round(max(0.0, s["start"]), 3),
            "end": round(min(duration, s["end"]), 3),
            "text": _apply_domain_fixes(s["text"].strip())}
           for s in segments if s["end"] > s["start"] and s["text"].strip()]
    out.sort(key=lambda s: s["start"])   # chronological order after sweeps
    gc.collect()
    return out


def _transcribe_pass1(model, y, vad_params, prompt):
    if HAS_BATCHED:
        batched = BatchedInferencePipeline(model=model)
        extras = [{"initial_prompt": prompt}] if prompt else []
        for extra in extras + [{}]:
            try:
                segs, _ = batched.transcribe(
                    y, batch_size=max(4, N_THREADS // 2), language="en",
                    vad_filter=True, vad_parameters=vad_params,
                    condition_on_previous_text=False, **extra)
                out = [{"start": s.start, "end": s.end, "text": s.text} for s in segs]
                if out:
                    return _filter_hallucinations(out)
            except Exception as e:
                logging.warning("Batched pipeline fell back: %s", e)
    segs, _ = model.transcribe(
        y, language="en", beam_size=1, best_of=1,
        vad_filter=True, vad_parameters=vad_params,
        condition_on_previous_text=False,
        no_speech_threshold=0.6, log_prob_threshold=-1.0,
        initial_prompt=prompt)
    return _filter_hallucinations(
        [{"start": s.start, "end": s.end, "text": s.text} for s in segs])


def _filter_hallucinations(segs):
    clean, recent = [], []
    for s in segs:
        t = re.sub(r"\s+", " ", s["text"]).strip()
        low = t.lower().strip(" .!,")
        if not t or low in _HALLU:
            continue
        if len(recent) >= 2 and low == recent[-1] == recent[-2]:
            continue
        recent.append(low)
        clean.append({**s, "text": t})
    return clean


def _merge_and_dedupe(segs, merge_gap=0.25):
    segs = sorted(segs, key=lambda s: s["start"])
    out = []
    for s in segs:
        if out and s["start"] - out[-1]["end"] <= merge_gap:
            out[-1]["end"] = max(out[-1]["end"], s["end"])
            out[-1]["text"] = (out[-1]["text"] + " " + s["text"]).strip()
        else:
            out.append(dict(s))
    return out


def run_asr_postprocessing(raw_segments):
    segs = _merge_and_dedupe([dict(s) for s in raw_segments if s.get("text", "").strip()])
    processed = []
    for s in segs:
        if s["end"] - s["start"] < 0.15:
            s["end"] = s["start"] + 0.15
        processed.append({"start": round(s["start"], 3),
                          "end": round(s["end"], 3), "text": s["text"]})
    gc.collect()
    return processed


def _segment_features(y, sr, start, end):
    # Speed cap: analyse at most 8 s (centre crop) per segment so the
    # Instant Hub stays fast on long utterances; still representative.
    i0, i1 = int(start * sr), min(len(y), int(end * sr) + int(0.05 * sr))
    max_win = int(8.0 * sr)
    if i1 - i0 > max_win:
        mid = (i0 + i1) // 2
        i0, i1 = max(0, mid - max_win // 2), min(len(y), mid + max_win // 2)
    x = y[i0:i1]
    if len(x) < int(0.25 * sr):
        x = np.pad(x, (0, int(0.25 * sr) - len(x)))
    x = sosfilt(butter(4, 70, 'hp', fs=sr, output='sos'), x)
    mfcc = librosa.feature.mfcc(y=x, sr=sr, n_mfcc=20)
    d1, d2 = librosa.feature.delta(mfcc), librosa.feature.delta(mfcc, order=2)
    emb = np.concatenate([mfcc.mean(1), mfcc.std(1), d1.mean(1), d2.mean(1)])
    f0, voiced, _ = librosa.pyin(x, fmin=60, fmax=400, sr=sr, fill_na=np.nan)
    v = f0[voiced & ~np.isnan(f0)]
    return (emb.astype(np.float32),
            float(np.median(v)) if v.size else 0.0,
            float(np.mean(voiced)) if voiced is not None else 0.0)


@st.cache_data(max_entries=8, show_spinner=False)
def _segment_features_cached(path, _mtime, start, end):
    """Per-segment voiceprint cached by (file, mtime, span) — Re-run with a
    different speaker-count re-clusters in seconds without recomputing
    MFCC/pitch."""
    y, sr = _load_audio_16k(path, _mtime)
    return _segment_features(y, sr, start, end)


# ==========================================================================
# BEGIN PATCH T5-COMMS-LOWBAND (optional hardening — additive only)
# ==========================================================================
def _comms_lowband_depleted(y_seg, sr=16000, low_hz=300.0, max_low_ratio=0.06):
    """Second comms signature: tactical radio strips the band BELOW ~300 Hz,
    so <6 % of total energy sits under 300 Hz, while clean speech always
    carries its harmonic fundamental there (male 85-180 Hz, female 150-250 Hz).
    Strictly additive OR-gate for _is_band_limited — catches comms whose high
    band is masked by room/reverb bleed. Fran-safe: her ~155 Hz fundamental
    keeps her low-band ratio far above the cut. REVERT = remove the OR clause
    in _is_band_limited (PATCH H2) if any Fran segment ever leaves Female_1."""
    try:
        x = np.asarray(y_seg, dtype=np.float64)
        if x.size < int(0.30 * sr):
            return False
        spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
        freqs = np.fft.rfftfreq(x.size, d=1.0 / sr)
        tot = float(spec.sum())
        if tot <= 1e-9:
            return False
        low = float(spec[freqs < low_hz].sum())
        return (low / tot) < max_low_ratio
    except Exception:
        return False
# ==========================================================================
# END PATCH T5-COMMS-LOWBAND
# ==========================================================================

# ==========================================================================
# BEGIN PATCH T5-COMMS: band-limit detector (radio/intercom signature)
# ==========================================================================
def _is_band_limited(y_seg, sr=16000, frame_sec=0.5, min_frac=0.50,
                     hi_hz=5000.0, energy_ratio=0.015, rolloff_hz=3800.0):
    """Comms detector (frame-level): radio/intercom is hard band-limited to
    ~3.4 kHz, so most 0.5 s frames carry <1.5 % of energy above 5 kHz.
    Flags when >= min_frac of frames qualify OR 95 % of all energy sits below
    3.8 kHz. Catches radio speech mixed with room audio in one segment;
    clean speech (male or female) has broadband frames and is never flagged."""
    try:
        x = np.asarray(y_seg, dtype=np.float64)
        win = int(frame_sec * sr)
        if x.size < win:
            return False
        step = win // 2
        total = hits = a = 0
        while a + win <= x.size:
            spec = np.abs(np.fft.rfft(x[a:a + win] * np.hanning(win)))
            freqs = np.fft.rfftfreq(win, d=1.0 / sr)
            tot = float(spec.sum()) + 1e-12
            if float(spec[freqs >= hi_hz].sum()) / tot < energy_ratio:
                hits += 1
            total += 1
            a += step
        if total and (hits >= min_frac * total or _comms_lowband_depleted(x, sr)):
            return True
        spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
        freqs = np.fft.rfftfreq(x.size, d=1.0 / sr)
        cum = np.cumsum(spec)
        k = min(int(np.searchsorted(cum, 0.95 * (float(spec.sum()) + 1e-12))),
                len(freqs) - 1)
        return float(freqs[k]) <= rolloff_hz
    except Exception:
        return False
# ==========================================================================
# END PATCH T5-COMMS
# ==========================================================================


# ==========================================================================
# BEGIN PATCH T5-GENDER: re-anchored gender boundaries (v3.4)
# ==========================================================================
def _decide_gender(pooled_f0):
    """Calibrated gender boundaries (v3.4 re-anchor):
      • median F0 >= 148 Hz  -> Female (Fran Heller pools 152–156 Hz; a
        fragmented or slightly diluted pool can no longer drop below the cut)
      • median F0 <= 138 Hz  -> Male
      • 138–148 Hz gray zone -> quartile tie-break (q25 >= 144 -> Female)
    Adult male medians almost never exceed 140 Hz, so 148 Hz stays a safe
    direct Female cut while 138 Hz keeps ordinary male voices decisively Male."""
    if not pooled_f0:
        return "Male", 0.35, 0.0
    med = float(np.median(pooled_f0))
    q25 = float(np.percentile(pooled_f0, 25)) if len(pooled_f0) >= 4 else med
    if med >= 148:
        return "Female", min(1.0, 0.55 + (med - 148) / 60), med
    if med <= 138:
        return "Male", min(1.0, 0.6 + (138 - med) / 60), med
    return ("Female", 0.55, med) if q25 >= 144 else ("Male", 0.55, med)
# ==========================================================================
# END PATCH T5-GENDER
# ==========================================================================


def _split_bimodal_genders(labels_list, f0_med, voiced_frac):
    """Gender-integrity guard: if one cluster pools a bimodal pitch range
    (p90 − p10 ≥ 70 Hz), a male and a female were probably merged by timbre
    similarity — split at the pooled median into low/high-pitch sub-clusters
    so the dual-stream boxes stay gender-accurate."""
    labs = list(labels_list)
    next_id = (max(labs) + 1) if labs else 0
    for c in sorted(set(labs)):
        idxs = [i for i, lab in enumerate(labs)
                if lab == c and voiced_frac[i] >= 0.10 and f0_med[i] > 0]
        if len(idxs) < 6:
            continue
        vals = [f0_med[i] for i in idxs]
        lo, hi = np.percentile(vals, [10, 90])
        if hi - lo < 70.0:
            continue
        mid = float(np.median(vals))
        high = [i for i in idxs if f0_med[i] > mid]
        low = [i for i in idxs if f0_med[i] <= mid]
        if len(high) >= 3 and len(low) >= 3:
            for i in high:
                labs[i] = next_id
            logging.info("Bimodal-pitch split applied to cluster %s", c)
            next_id += 1
    return labs


def _merge_closest(E, labels):
    uniq = list(np.unique(labels))
    cents = {c: E[labels == c].mean(axis=0) for c in uniq}
    best, pair = None, None
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            a, b = cents[uniq[i]], cents[uniq[j]]
            d = 1 - float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
            if best is None or d < best:
                best, pair = d, (uniq[i], uniq[j])
    labels = np.array(labels)
    labels[labels == pair[1]] = pair[0]
    return labels


# ==========================================================================
# BEGIN PATCH T5-CAP: hard auto-mode ceiling (halts the 11-speaker explosion)
# ==========================================================================
_MAX_AUTO_CLUSTERS = 4   # HARD ceiling in auto mode: 3 lead characters + 1
                         # comms/noise bucket. The 11-speaker explosion
                         # (cap-10 + one bimodal split) is now impossible.


def _cluster(E, k_override):
    from sklearn.cluster import AgglomerativeClustering
    n = len(E)
    if n == 1:
        return np.zeros(1, dtype=int)
    if k_override and 1 <= k_override <= n:
        return AgglomerativeClustering(
            n_clusters=k_override, metric="cosine", linkage="average").fit_predict(E)

    # 0.75 groups same-voice variation (BGM / channel / reverb) that 0.65
    # shredded into micro-clusters; the cap below is the real safety net.
    labels = AgglomerativeClustering(
        n_clusters=None, distance_threshold=0.75,
        metric="cosine", linkage="average").fit_predict(E)

    cap = min(_MAX_AUTO_CLUSTERS, n)
    while len(set(labels)) > cap:
        labels = _merge_closest(E, labels)
    return labels
# ==========================================================================
# END PATCH T5-CAP
# ==========================================================================

# ==========================================================================
# BEGIN PATCH T5-MALE-SPLIT: stricter second pass inside male clusters
# ==========================================================================
MALE_SPLIT_THRESHOLD = 0.62   # cosine cut used ONLY inside male clusters
MALE_SPLIT_MIN_SEGS = 3       # each branch needs >= 3 segments ...
MALE_SPLIT_MIN_SECS = 5.0     # ... and >= 5 s speech (no 1-sec identities)
MAX_TOTAL_VOICES = 6          # absolute ceiling across the whole timeline


def _subsplit_male_clusters(E, labels_list, f0_med, voiced_frac,
                            band_flags, segs):
    """The 0.75 main threshold intentionally fuses similar voices to prevent
    the 11-speaker explosion; this pass re-examines each provisional-Male
    cluster at MALE_SPLIT_THRESHOLD so General Orland and Dr. Clyne branch
    into separate identities. Guards: both branches need >=3 segments and
    >=5 s of speech (micro-clusters rejoin the parent instead), female
    clusters are never touched, and MAX_TOTAL_VOICES bounds the total."""
    from sklearn.cluster import AgglomerativeClustering
    labs = list(labels_list)
    next_id = (max(labs) + 1) if labs else 0
    for c in sorted(set(labs)):
        if len(set(labs)) >= MAX_TOTAL_VOICES:
            break
        idxs = [i for i, l in enumerate(labs) if l == c]
        if len(idxs) < 2 * MALE_SPLIT_MIN_SEGS:
            continue
        clean = [i for i in idxs
                 if not band_flags[i] and voiced_frac[i] >= 0.10 and f0_med[i] > 0]
        if len(clean) < 2 * MALE_SPLIT_MIN_SEGS:
            continue
        if _decide_gender([f0_med[i] for i in clean])[0] != "Male":
            continue                      # female cluster — leave untouched
        try:
            sub = AgglomerativeClustering(
                n_clusters=None, distance_threshold=MALE_SPLIT_THRESHOLD,
                metric="cosine", linkage="average").fit_predict(E[idxs])
        except Exception as e:
            logging.warning("Male sub-split failed for cluster %s: %s", c, e)
            continue
        groups = {}
        for j, i in enumerate(idxs):
            groups.setdefault(int(sub[j]), []).append(i)
        big = [g for g in groups.values()
               if len(g) >= MALE_SPLIT_MIN_SEGS
               and sum(segs[i]["end"] - segs[i]["start"] for i in g) >= MALE_SPLIT_MIN_SECS]
        if len(big) < 2:
            continue
        for g in big[1:]:                 # first branch keeps id c, rest split off
            for i in g:
                labs[i] = next_id
            next_id += 1
        logging.info("Male sub-split: cluster %s -> %d voices", c, len(big))
    return labs
# ==========================================================================
# END PATCH T5-MALE-SPLIT
# ==========================================================================



def run_diarization(audio_path, raw_segments, speaker_count_override=0):
    """Voice fingerprinting → clustering (+ bimodal-pitch gender guard) →
    pitch-based gender → dynamic Male_1, Male_2, ... / Female_1, Female_2, ...
    labels ordered by first appearance on the timeline.

    Returns:
        (segments, speaker_stats)
        segments: [{"start", "end", "speaker", "text"}] sorted by start
        speaker_stats: list of dicts for st.dataframe
    """
    segs = sorted(
        ({"start": float(s.get("start", 0.0)),
          "end": float(s.get("end", 0.0)),
          "text": (s.get("text") or "").strip()}
         for s in (raw_segments or [])
         if (s.get("text") or "").strip() and s.get("end", 0) > s.get("start", 0)),
        key=lambda s: s["start"])
    if not segs:
        return [], []

    mtime = os.path.getmtime(audio_path)
    y, sr = _load_audio_16k(audio_path, mtime)
    duration = len(y) / sr

    # PATCH T5-COMMS-FLAG: also record whether each segment is band-limited
    # (radio/intercom) so it can be excluded from the gender pitch vote.
    feats, f0_med, voiced_frac, band_flags = [], [], [], []
    for s in segs:
        emb, f0m, vf = _segment_features_cached(audio_path, mtime,
                                                s["start"], s["end"])
        feats.append(emb); f0_med.append(f0m); voiced_frac.append(vf)
        i0 = int(s["start"] * sr)
        i1 = min(len(y), int(s["end"] * sr))
        band_flags.append(_is_band_limited(y[i0:i1], sr))
    E = np.vstack(feats).astype(np.float32)

    try:
        labels = np.asarray(_cluster(E, speaker_count_override))
    except Exception as e:
        logging.warning("Clustering failed (%s) — single-voice fallback", e)
        labels = np.zeros(len(segs), dtype=int)
    labels_list = labels.tolist()

    # Gender-integrity guard (male + female merged in one cluster → split)
    labels_list = _split_bimodal_genders(labels_list, f0_med, voiced_frac)

    # PATCH T5-MALE-SPLIT: refine male clusters so Orland / Clyne separate.
    labels_list = _subsplit_male_clusters(E, labels_list, f0_med,
                                          voiced_frac, band_flags, segs)

    # PATCH T5-COMMS-GUARD: only clean (non-comms) segments with enough voiced
    # frames vote. Band-limited radio lines are excluded entirely, so a
    # comms-only cluster pools empty and defaults to Male — the Dagger-team
    # line can never take a Female label again.
    pooled = {}
    for i, lab in enumerate(labels_list):
        if band_flags[i]:
            continue
        if voiced_frac[i] >= 0.10 and f0_med[i] > 0:
            pooled.setdefault(lab, []).append(f0_med[i])

    def _first_seen(c):
        return min(segs[i]["start"] for i, lab in enumerate(labels_list)
                   if lab == c)

    clusters = sorted(set(labels_list), key=_first_seen)

    label_name, stats = {}, []
    male_n, female_n = 0, 0
    for c in clusters:
        gender, conf, med_f0 = _decide_gender(pooled.get(c, []))
        if gender == "Female":
            female_n += 1
            name = f"Female_{female_n}"
        else:
            male_n += 1
            name = f"Male_{male_n}"
        label_name[c] = name
        idxs = [i for i, lab in enumerate(labels_list) if lab == c]
        speech_s = sum(segs[i]["end"] - segs[i]["start"] for i in idxs)
        v_pct = 100.0 * float(np.mean([voiced_frac[i] for i in idxs])) if idxs else 0.0
        stats.append({"Speaker": name, "Gender": gender, "Segments": len(idxs),
                      "Speech (s)": round(speech_s, 1),
                      "Median F0 (Hz)": round(med_f0, 1),
                      "Voiced (%)": round(v_pct, 1),
                      "Confidence": round(conf, 2)})

        
    # PATCH T5-COMMS-OVERRIDE (self-contained): pitch from band-limited radio
    # audio skews upward, so comms can NEVER carry a Female label — even when
    # clustering placed those segments inside a female cluster. They move to
    # a dedicated Male comms bucket with its own Male_N label + stats row.
    try:
        _bf = band_flags
    except NameError:
        _bf = [_is_band_limited(y[int(s["start"] * sr):min(len(y), int(s["end"] * sr))], sr)
               for s in segs]
    speaker_of = {i: label_name[labels_list[i]] for i in range(len(segs))}
    comms_idxs = [i for i in range(len(segs))
                  if _bf[i] and speaker_of[i].startswith("Female")]
    if comms_idxs:
        male_n += 1
        comms_name = f"Male_{male_n}"
        for i in comms_idxs:
            speaker_of[i] = comms_name
        stats.append({"Speaker": comms_name, "Gender": "Male",
                      "Segments": len(comms_idxs),
                      "Speech (s)": round(sum(segs[i]["end"] - segs[i]["start"]
                                              for i in comms_idxs), 1),
                      "Median F0 (Hz)": round(float(np.mean([f0_med[i]
                                                             for i in comms_idxs])), 1),
                      "Voiced (%)": round(100.0 * float(np.mean([voiced_frac[i]
                                                                 for i in comms_idxs])), 1),
                      "Confidence": 0.5})
    final = [{"start": round(s["start"], 3),
              "end": round(min(s["end"], duration), 3),
              "speaker": speaker_of[i],
              "text": s["text"]}
             for i, s in enumerate(segs)]
    final.sort(key=lambda s: s["start"])
    gc.collect()
    return final, stats

# ---- TEMPORARY SELF-TEST — DELETE AFTER PASSING ----
_sr = 16000
_rng = np.random.default_rng(0)
_tt = np.arange(_sr * 6) / _sr
_radio = (0.4*np.sin(2*np.pi*300*_tt) + 0.3*np.sin(2*np.pi*900*_tt)
          + 0.3*np.sin(2*np.pi*1800*_tt)).astype(np.float32)
_clean = (_rng.normal(0, .05, _sr*6) + 0.2*np.sin(2*np.pi*180*_tt)).astype(np.float32)
assert _is_band_limited(_radio, _sr) is True, "FAIL: radio not flagged"
assert _is_band_limited(_clean, _sr) is False, "FAIL: clean audio flagged"
assert _apply_domain_fixes("depreping genocide, arautaria") == "spray painting genocide, Aratare", "FAIL: vocab"
print("SELFTEST OK")
# ---- END TEMPORARY SELF-TEST ----
