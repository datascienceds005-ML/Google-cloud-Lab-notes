app.py


import streamlit as st
import os, time, tempfile, traceback

try:
    import torch
    torch.classes.__path__ = []
except Exception:
    pass

# ⚡ HUB-ONLY BUILD (Tabs 1–4 disabled):
# The heavy dubbing engine (audio_engine: Demucs, edge-tts, pedalboard,
# pydub, pyloudnorm) is intentionally NOT imported. Only the instant
# transcript pipeline runs. To re-enable the old tabs later, restore the
# previous app.py from your backup.

import transcription

st.set_page_config(page_title="⚡ Instant Transcript Hub", page_icon="⚡", layout="wide")

# --- Engine-version guard: fail loudly & clearly if transcription.py is stale
_REQUIRED_ENGINE = ("extract_mono_boosted", "_rescue_pass", "_split_bimodal_genders")
_missing = [fn for fn in _REQUIRED_ENGINE if not hasattr(transcription, fn)]
if _missing:
    st.error("transcription.py is outdated — missing function(s): "
             f"{', '.join(_missing)}. Replace transcription.py with the current "
             "v3.2 file (the one containing extract_mono_boosted), then restart "
             "this Space.")
    st.stop()


def load_futuristic_css():
    st.markdown("""
    <style>
        .stApp {
            background-color: #030508;
            background-image: linear-gradient(rgba(0, 243, 255, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 243, 255, 0.03) 1px, transparent 1px);
            background-size: 40px 40px; font-family: 'Segoe UI', 'Roboto', sans-serif; color: #e0e6ed;
        }
        #MainMenu {visibility: hidden;} footer {visibility: hidden;}
        header[data-testid="stHeader"] {background: transparent;}
        h1 { color: #00f3ff !important; letter-spacing: 3px; text-transform: uppercase; border-bottom: 2px solid rgba(0, 243, 255, 0.3); padding-bottom: 15px; font-weight: 700; }
        .stCaption { color: #8b9bb4 !important; letter-spacing: 1px; }
        section[data-testid="stSidebar"] { background-color: rgba(8, 12, 18, 0.9); border-right: 2px solid rgba(0, 243, 255, 0.3); }
        .stButton > button { background: linear-gradient(90deg, rgba(0,243,255,0.1), rgba(0,243,255,0.2)); border: 1px solid #00f3ff; color: #00f3ff; font-weight: bold; text-transform: uppercase; border-radius: 4px; padding: 12px 24px; }
        .stButton > button:hover { background: #00f3ff; color: #030508; }
        .stTextArea textarea { background-color: #0b1117 !important; color: #e0e6ed !important; border: 1px solid rgba(0, 243, 255, 0.3) !important; font-family: 'Menlo', monospace !important; }
    </style>
    """, unsafe_allow_html=True)

load_futuristic_css()

st.title("⚡ Automated Instant Transcript Hub")
st.caption("Single-module engine • Upload → auto-transcribe • 👨 Male / 👩 Female dual streams • "
           "dynamic Male_1… / Female_1… labels • precise [00:00:07 --> 00:01:31] timestamps • "
           "deep capture: whispers, background voices, phone/intercom audio")


# ---------- Transcript helpers ----------
def fmt_ts_hub(seconds):
    """Seconds -> HH:MM:SS (e.g. 00:01:31) for [start --> end] stamps."""
    try:
        seconds = max(0.0, float(seconds))
    except (TypeError, ValueError):
        seconds = 0.0
    h, m, s = int(seconds // 3600), int(seconds % 3600 // 60), int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _hub_speaker_sort(sid):
    """Sort Male_1, Male_2 ... Male_10 numerically."""
    try:
        return int(str(sid).split("_")[-1])
    except (ValueError, IndexError):
        return 999


def hub_stream_lines(segments):
    """Split diarized segments into male / female / full-timeline lines,
    every line carrying an explicit [start --> end] timestamp."""
    male, female, timeline = [], [], []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        spk = (seg.get("speaker") or "").strip()
        ts = f"[{fmt_ts_hub(seg.get('start', 0))} --> {fmt_ts_hub(seg.get('end', 0))}]"
        line = f"{ts} {spk}: {text}" if spk else f"{ts} {text}"
        timeline.append(line)
        if spk.startswith("Female"):
            female.append(line)
        elif spk:
            male.append(line)
    return male, female, timeline


# ---------- Session state ----------
if "standalone_hub_done" not in st.session_state: st.session_state.standalone_hub_done = False
if "standalone_male_text" not in st.session_state: st.session_state.standalone_male_text = ""
if "standalone_female_text" not in st.session_state: st.session_state.standalone_female_text = ""
if "standalone_timeline_text" not in st.session_state: st.session_state.standalone_timeline_text = ""
if "standalone_speaker_stats" not in st.session_state: st.session_state.standalone_speaker_stats = []
if "standalone_male_ids" not in st.session_state: st.session_state.standalone_male_ids = []
if "standalone_female_ids" not in st.session_state: st.session_state.standalone_female_ids = []
if "last_standalone_file" not in st.session_state: st.session_state.last_standalone_file = ""
if "hub_model_used" not in st.session_state: st.session_state.hub_model_used = ""
if "hub_override_used" not in st.session_state: st.session_state.hub_override_used = 0
if "hub_deep_used" not in st.session_state: st.session_state.hub_deep_used = True
if "hub_rescue_used" not in st.session_state: st.session_state.hub_rescue_used = True
if "hub_total_s" not in st.session_state: st.session_state.hub_total_s = 0.0
if "hub_asr_s" not in st.session_state: st.session_state.hub_asr_s = 0.0
if "hub_diar_s" not in st.session_state: st.session_state.hub_diar_s = 0.0


# ---------- Sidebar controls ----------
with st.sidebar:
    st.subheader("⚡ Hub Controls")
    whisper_model_size = st.selectbox(
        "Whisper model", ["small.en", "base.en", "medium.en", "large-v3"], index=0,
        help="base.en = turbo • small.en = best speed/accuracy default • medium/large = noisier audio")
    speaker_count_override = st.slider("Expected speakers (0 = auto-detect)", 0, 6, 0)
    glossary = st.text_input("Glossary / context hints", placeholder="names, jargon…")

    st.divider()
    st.subheader("📡 Deep Voice Capture")
    quiet_boost = st.checkbox("Quiet-voice lift (whispers / low audio)", value=True)
    deep_capture = st.checkbox("Deep-capture sweep (background / third-party voices)", value=True)
    phone_rescue = st.checkbox("Phone / intercom rescue (narrow-band voices)", value=True)

    st.divider()
    st.subheader("📊 Live Resources")
    try:
        import psutil
        p = psutil.Process(os.getpid())
        vm = psutil.virtual_memory()
        st.metric("Process RAM", f"{p.memory_info().rss / 1048576:.0f} MB")
        st.metric("Available RAM", f"{vm.available / 1073741824:.1f} GB")
    except Exception:
        st.metric("Process RAM", "Active")


# ---------- Main flow ----------
uploaded = st.file_uploader(
    "Upload video for instant transcription (MP4, MKV, AVI, MOV)",
    type=["mp4", "mkv", "avi", "mov"],
    key="standalone_video_upload"
)

if uploaded:
    st.video(uploaded)

    # ---- Reset whenever a NEW file (name+size) is uploaded ----
    file_sig = f"{uploaded.name}|{uploaded.size}"
    if st.session_state.get("last_standalone_file") != file_sig:
        st.session_state.last_standalone_file = file_sig
        st.session_state.standalone_hub_done = False
        st.session_state.standalone_male_text = ""
        st.session_state.standalone_female_text = ""
        st.session_state.standalone_timeline_text = ""
        st.session_state.standalone_speaker_stats = []
        st.session_state.standalone_male_ids = []
        st.session_state.standalone_female_ids = []
        for k in ("hub_male_box", "hub_female_box"):
            st.session_state.pop(k, None)

    # ---- Manual re-run with the CURRENT sidebar settings ----
    if st.button("🔄 Re-run Transcript (applies current sidebar settings)", key="hub_rerun"):
        st.session_state.standalone_hub_done = False
        for k in ("hub_male_box", "hub_female_box"):
            st.session_state.pop(k, None)
        st.rerun()

    if not st.session_state.get("standalone_hub_done"):
        with st.status("🚀 Instant Transcription: multi-pass ASR → gender split ...", expanded=True) as status:
            try:
                t_global = time.time()

                st.write("📂 Step 1/4: Saving upload ...")
                video_path = os.path.join(tempfile.gettempdir(), f"hub_{uploaded.name}")
                # write only when new/changed → stable mtime → all downstream caches hit
                if not os.path.exists(video_path) or os.path.getsize(video_path) != uploaded.size:
                    with open(video_path, "wb") as f:
                        f.write(uploaded.getbuffer())

                st.write("🎵 Step 2/4: 16 kHz mono extraction" + (" + quiet-voice lift ..." if quiet_boost else " ..."))
                t_s = time.time()
                audio_path = transcription.extract_mono_boosted(video_path, boost_quiet=quiet_boost)
                st.write(f"   ⏱ audio ready in {time.time() - t_s:.1f}s")

                st.write("🧠 Step 3/4: Multi-pass Whisper ASR (main sweep → deep capture → rescue) ...")
                t_s = time.time()
                raw_segments = transcription.run_whisper_raw(
                    audio_path, model_size=whisper_model_size, glossary=glossary,
                    deep_scan=deep_capture, rescue=phone_rescue,
                    progress=lambda msg: st.write(msg))
                asr_s = time.time() - t_s
                st.write(f"   ⏱ {len(raw_segments)} segments in {asr_s:.1f}s")

                st.write("🗣️ Step 4/4: Voice fingerprinting → clustering → gender split → Male_N / Female_N ...")
                t_s = time.time()
                final_segments, speaker_stats = [], []
                try:
                    final_segments, speaker_stats = transcription.run_diarization(
                        audio_path, raw_segments,
                        speaker_count_override=speaker_count_override)
                except Exception as dia_err:
                    st.warning(f"⚠️ Speaker separation failed ({dia_err}) — timestamps-only transcript दिखाया जा रहा है।")
                diar_s = time.time() - t_s
                st.write(f"   ⏱ done in {diar_s:.1f}s — {len(final_segments)} labelled blocks")

                male_lines, female_lines, timeline_lines = hub_stream_lines(final_segments)
                if not final_segments and raw_segments:
                    timeline_lines = [
                        f"[{fmt_ts_hub(s['start'])} --> {fmt_ts_hub(s['end'])}] {s['text'].strip()}"
                        for s in raw_segments if s.get("text", "").strip()
                    ]

                st.session_state.standalone_male_text = "\n".join(male_lines)
                st.session_state.standalone_female_text = "\n".join(female_lines)
                st.session_state.standalone_timeline_text = "\n".join(timeline_lines)
                st.session_state.standalone_speaker_stats = speaker_stats or []
                st.session_state.standalone_male_ids = sorted(
                    {s["speaker"] for s in final_segments if s["speaker"].startswith("Male")},
                    key=_hub_speaker_sort)
                st.session_state.standalone_female_ids = sorted(
                    {s["speaker"] for s in final_segments if s["speaker"].startswith("Female")},
                    key=_hub_speaker_sort)
                st.session_state.hub_model_used = whisper_model_size
                st.session_state.hub_override_used = speaker_count_override
                st.session_state.hub_deep_used = deep_capture
                st.session_state.hub_rescue_used = phone_rescue
                st.session_state.hub_total_s = time.time() - t_global
                st.session_state.hub_asr_s = asr_s
                st.session_state.hub_diar_s = diar_s
                st.session_state.standalone_hub_done = True

                n_voices = (len(st.session_state.standalone_male_ids)
                            + len(st.session_state.standalone_female_ids))
                status.update(
                    label=(f"✅ Dual-Stream Transcript Ready in {st.session_state.hub_total_s:.1f}s — "
                           f"{len(timeline_lines)} dialogue blocks • {n_voices} distinct voices"),
                    state="complete")
            except Exception as e:
                status.update(label="❌ Transcription failed", state="error")
                st.error(f"प्रक्रिया में त्रुटि आई: {str(e)}")
                st.code(traceback.format_exc())

    # ================= RESULTS =================
    if st.session_state.get("standalone_hub_done"):

        m_used = st.session_state.get("hub_model_used", "?")
        o_used = st.session_state.get("hub_override_used", 0)
        d_used = st.session_state.get("hub_deep_used", True)
        r_used = st.session_state.get("hub_rescue_used", True)
        st.caption(f"🧪 Settings used: Whisper `{m_used}` • speakers: "
                   f"{'auto' if not o_used else o_used} • deep capture "
                   f"{'ON' if d_used else 'OFF'} • rescue "
                   f"{'ON' if r_used else 'OFF'} • ⏱ total "
                   f"{st.session_state.get('hub_total_s', 0):.1f}s "
                   f"(ASR {st.session_state.get('hub_asr_s', 0):.1f}s / "
                   f"split {st.session_state.get('hub_diar_s', 0):.1f}s)")

        if not (st.session_state.get("standalone_timeline_text") or "").strip():
            st.warning("⚠️ कोई speech detect नहीं हुई — sidebar से बड़ा model (medium.en) चुनकर "
                       "'Re-run' दबाएँ, और Deep Voice Capture के तीनों toggles ON रखें।")

        stats = st.session_state.get("standalone_speaker_stats") or []
        if stats:
            st.markdown("#### 🧬 Detected Voices (clustering + pitch)")
            st.dataframe(stats, use_container_width=True)
        # v3.4 caption sync (thresholds updated; logic itself lives in transcription.py)
        st.caption("Median F0 ≥ 148 Hz → Female, ≤ 138 Hz → Male; the 138–148 Hz gray zone falls back to a "
                   "quartile heuristic. Bimodal clusters are auto-split so mixed genders never share one label. "
                   "Auto mode is hard-capped at 4 speakers.")

        st.divider()
        st.markdown("### 📝 Dual Speaker Transcript Streams")

        male_txt = st.session_state.get("standalone_male_text", "")
        female_txt = st.session_state.get("standalone_female_text", "")
        m_ids = st.session_state.get("standalone_male_ids", [])
        f_ids = st.session_state.get("standalone_female_ids", [])

        col_m, col_f = st.columns(2)

        with col_m:
            m_label = ", ".join(m_ids) if m_ids else "—"
            st.markdown(f"##### 👨 Male Voice Box — {len(m_ids)} speaker(s): {m_label}")
            if male_txt:
                st.text_area("Male transcript (timestamps + dynamic speaker labels)",
                             value=male_txt, height=420, key="hub_male_box")
                with st.expander("📋 One-click copy — Male stream"):
                    st.code(male_txt, language=None)
                st.download_button("📥 Download Male Stream (.txt)", male_txt,
                                   file_name="male_speaker_stream.txt", mime="text/plain",
                                   use_container_width=True, key="hub_dl_male")
            else:
                st.info("इस audio में कोई male आवाज़ detect नहीं हुई।")

        with col_f:
            f_label = ", ".join(f_ids) if f_ids else "—"
            st.markdown(f"##### 👩 Female Voice Box — {len(f_ids)} speaker(s): {f_label}")
            if female_txt:
                st.text_area("Female transcript (timestamps + dynamic speaker labels)",
                             value=female_txt, height=420, key="hub_female_box")
                with st.expander("📋 One-click copy — Female stream"):
                    st.code(female_txt, language=None)
                st.download_button("📥 Download Female Stream (.txt)", female_txt,
                                   file_name="female_speaker_stream.txt", mime="text/plain",
                                   use_container_width=True, key="hub_dl_female")
            else:
                st.info("इस audio में कोई female आवाज़ detect नहीं हुई।")

        st.divider()
        with st.expander("🔀 Full Chronological Timeline — All Voices (one-click copy)", expanded=False):
            timeline_txt = st.session_state.get("standalone_timeline_text", "")
            if timeline_txt:
                st.code(timeline_txt, language=None)
                st.download_button("📥 Download Full Timed Transcript (.txt)", timeline_txt,
                                   file_name="full_timed_transcript.txt", mime="text/plain",
                                   use_container_width=True, key="hub_dl_full")
            else:
                st.warning("⚠️ कोई speech detect नहीं हुई — 'Re-run' दबाएँ।")
else:
    st.info("💡 video upload करते ही dual-box (👨 Male / 👩 Female) transcript — dynamic speaker "
            "labels और precise timestamps के साथ — तुरंत तैयार हो जाएगा।")


audioengine.py


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

def cleanup_temp_artifacts():
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

def extract_and_isolate_bgm(video_path: str):
    cleanup_temp_artifacts()
    if not os.path.exists(video_path):
        raise RuntimeError(f"Video file not found: {video_path}")

    temp_dir = tempfile.gettempdir()
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

def _sanitize_tts_text(t):
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = re.sub(r"\b(?:Male|Female|Speaker)[-_ ]?\w*\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()[:1800]

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
    filt = (
        "[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[bg];"
        "[2:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[dub];"
        f"[bg][dub]sidechaincompress=threshold=0.03:ratio={ratio:.1f}:"
        f"attack=8:release=280[bgd];"
        "[bgd][dub]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
    )

    def run_encode(vargs, f):
        cmd = ["ffmpeg", "-y", "-i", video_path, "-i", bgm_wav, "-i", mastered,
               "-filter_complex", f, "-map", "0:v:0", "-map", "[a]"] + vargs + \
              ["-c:a", "aac", "-b:a", "192k", "-shortest",
               "-movflags", "+faststart", output_video]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE)

    attempts = [ (["-c:v", "copy"], filt),
                 (["-c:v", "copy"], filt.replace(":normalize=0", "")),
                 (["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"],
                  filt.replace(":normalize=0", "")) ]
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
        qa_wav = os.path.join(tempfile.gettempdir(), PFX + "qa.wav")
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

transcption.py
