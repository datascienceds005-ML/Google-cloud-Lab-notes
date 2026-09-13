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