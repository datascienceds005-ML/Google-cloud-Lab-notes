import os, re, time
import streamlit as st
import audio_engine
import transcription
import staging

st.set_page_config(page_title="Master Dubbing Studio", page_icon="🎬", layout="wide")
st.title("🎬 Master Dubbing Studio — End-to-End Hindi Dub")
st.caption("ONE page, full flow: upload → Demucs → Whisper → Diarization (auto, once) → "
           "4-Box Translation Matrix → TTS → WSOLA → ducked mix → detached remux. "
           "Output audio = ducked BGM + Hindi TTS ONLY (source audio excluded by construction).")

# ---- engine guard: fail loudly on stale/incomplete audio_engine.py ----------
_REQUIRED_ENGINE = ("_sanitize_tts_text", "generate_tts_batch", "build_dub_track",
                    "mix_bgm_dub", "mux_video_audio_detached", "_track_mean_db",
                    "extract_and_isolate_bgm", "master_audio", "VOICE_MAP")
_missing = [fn for fn in _REQUIRED_ENGINE if not hasattr(audio_engine, fn)]
if _missing:
    st.error("audio_engine.py is stale/incomplete — missing: " + ", ".join(_missing)
             + ". Re-apply the v2.3 patch set, then restart the Space.")
    st.stop()

# ---------- helpers ----------
def fmt_ts_ms(t):
    t = max(0.0, float(t)); h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"

_TS_RX = re.compile(r"\[(\d{1,2}):(\d{2}):(\d{2}(?:\.\d{1,3})?)\s*-->\s*"
                    r"(\d{1,2}):(\d{2}):(\d{2}(?:\.\d{1,3})?)\]")

def _psec(h, m, s): return int(h) * 3600 + int(m) * 60 + float(s)

def parse_script(text):
    """'[00:01:24.550 --> 00:02:25.340]' blocks (+ following text lines) -> dicts."""
    blocks, cur = [], None
    for ln in (text or "").splitlines():
        m = _TS_RX.search(ln)
        if m:
            if cur: blocks.append(cur)
            cur = {"start": _psec(m.group(1), m.group(2), m.group(3)),
                   "end": _psec(m.group(4), m.group(5), m.group(6)), "text": ""}
        elif cur and ln.strip():
            cur["text"] = (cur["text"] + " " + ln.strip()).strip()
    if cur: blocks.append(cur)
    return [b for b in blocks if b["text"]]

def match_blocks(segs, blocks, tol=1.5):
    """Greedy nearest (start,end) one-to-one match -> {seg_index: hindi_text}."""
    res, used = {}, set()
    for i, s in enumerate(segs):
        best, bd = None, 1e18
        for j, b in enumerate(blocks):
            if j in used: continue
            d = abs(s["start"] - b["start"]) + abs(s["end"] - b["end"])
            if d < bd: bd, best = d, j
        if best is not None and bd <= tol:
            used.add(best); res[i] = blocks[best]["text"]
    return res

def run_separation(video_path, work_dir):
    try:
        return audio_engine.extract_and_isolate_bgm(video_path, work_dir=work_dir)
    except TypeError:                       # legacy v2.2 signature
        return audio_engine.extract_and_isolate_bgm(video_path)

# ---------- INPUT / STATE GATE ----------
uploaded = st.file_uploader("Upload source video", type=["mp4", "mkv", "avi", "mov"],
                            key="mst_upload")
if not uploaded:
    cached = [k for k in ("video", "bgm", "vocals_mono", "transcript", "dubbed_final")
              if staging.valid(k)]
    st.info("Upload करते ही पूरी analysis chain अपने आप चलेगी (Demucs → Whisper → "
            "Diarization) और 4-Box matrix भर जाएगा।")
    st.caption("Cached artifacts this session: "
               + (", ".join(cached) if cached else "none"))
    st.stop()

sig = f"{uploaded.name}|{uploaded.size}"
if st.session_state.get("mst_sig") != sig:                  # NEW file → full reset
    st.session_state.mst_sig = sig
    st.session_state.mst_auto_done = False
    for k in ("vocals_mono", "bgm", "vocals", "transcript", "dubbed_final",
              "dub_preview", "mix_preview"):
        st.session_state.pop("stage_" + k, None)

video_path = staging.save_upload(uploaded)
staging.put("video", video_path)
work_dir = os.path.dirname(video_path)
st.success(f"Source registered: {uploaded.name} ({uploaded.size/1e6:.1f} MB)")

rc1, rc2, _ = st.columns([1, 1, 2])
if rc1.button("🔄 Re-run Separation"):
    for k in ("bgm", "vocals", "vocals_mono", "transcript", "dubbed_final",
              "dub_preview", "mix_preview"):
        st.session_state.pop("stage_" + k, None)
    st.session_state.mst_auto_done = False
    st.rerun()
if rc2.button("🔄 Re-run Diarization"):
    for k in ("transcript", "dubbed_final", "dub_preview", "mix_preview"):
        st.session_state.pop("stage_" + k, None)
    st.session_state.mst_auto_done = False
    st.rerun()

need_sep = not (staging.valid("vocals_mono") and staging.valid("bgm"))
need_asr = not staging.valid("transcript")
if (need_sep or need_asr) and not st.session_state.get("mst_auto_done"):
    with st.status("🚀 Auto-pipeline: Demucs → Whisper → Diarization …",
                   expanded=True) as status:
        if need_sep:
            st.write("🎵 Demucs separation (CPU subprocess, 2–4 min) …")
            t0 = time.time()
            mono_wav, bgm_wav, voc_wav = run_separation(video_path, work_dir)
            staging.put("vocals_mono", mono_wav)
            staging.put("bgm", bgm_wav)
            staging.put("vocals", voc_wav)
            st.write(f"   ⏱ separation done in {time.time()-t0:.0f}s")
        if need_asr:
            st.write("🧠 Whisper + diarization on the CLEAN vocal stem …")
            t0 = time.time()
            raw = transcription.run_whisper_raw(
                staging.get("vocals_mono"), deep_scan=False, rescue=False,
                progress=lambda m: st.write(m))
            final, stats = transcription.run_diarization(
                staging.get("vocals_mono"), raw)
            staging.save_json("transcript",
                              {"segments": final, "speaker_stats": stats})
            st.write(f"   ⏱ ASR+diarization done in {time.time()-t0:.0f}s — "
                     f"{len(final)} segments")
        st.session_state.mst_auto_done = True
        status.update(label="✅ Auto-pipeline complete", state="complete")

if not staging.valid("transcript"):
    st.warning("Transcript missing — press a Re-run button above."); st.stop()

# ---------- 4-BOX TRANSLATION MATRIX ----------
segs = staging.load_json("transcript")["segments"]
male_segs = [s for s in segs if s["speaker"].startswith("Male")]
female_segs = [s for s in segs if s["speaker"].startswith("Female")]

def render_script(sset):
    return "\n".join(f"[{fmt_ts_ms(s['start'])} --> {fmt_ts_ms(s['end'])}]\n"
                     f"{s['speaker']}\n{s['text']}" for s in sset)

male_en, female_en = render_script(male_segs), render_script(female_segs)

st.markdown("### 🤹 Translation Matrix")
top1, top2 = st.columns(2)
with top1:
    st.markdown(f"#### 👨 Male Speaker ({len(male_segs)} lines)")
    st.text_area("Male Script (English, timed)", value=male_en, height=240,
                 disabled=True, key="mst_m_en")
    with st.expander("📋 COPY MALE TIMESTAMPS"):
        st.code(male_en, language=None)
        st.download_button("⬇️ Male script (.txt)", male_en,
                           file_name="male_script.txt", key="mst_dl_m")
with top2:
    st.markdown(f"#### 👩 Female Speaker ({len(female_segs)} lines)")
    st.text_area("Female Script (English, timed)", value=female_en, height=240,
                 disabled=True, key="mst_f_en")
    with st.expander("📋 COPY FEMALE TIMESTAMPS"):
        st.code(female_en, language=None)
        st.download_button("⬇️ Female script (.txt)", female_en,
                           file_name="female_script.txt", key="mst_dl_f")

bot1, bot2 = st.columns(2)
hi_male = bot1.text_area("Male Hindi Translation (Paste here — same timestamps)",
                         height=240, key="mst_hi_m",
                         placeholder="पूरा Male box यहाँ paste करें (same [timestamps])")
hi_female = bot2.text_area("Female Hindi Translation (Paste here — same timestamps)",
                           height=240, key="mst_hi_f",
                           placeholder="पूरा Female box यहाँ paste करें (same [timestamps])")

# ---------- EXECUTE ----------
st.markdown("### ⚡ Execute Dubbing Pipeline")
cD, cL, cS = st.columns(3)
duck_db = cD.slider("BGM duck (dB)", -24, -6, -12, key="mst_duck")
lufs = cL.slider("Target loudness (LUFS)", -20, -12, -16, key="mst_lufs")
keep_unmapped = cS.checkbox("Unmatched lines → English fallback", value=False,
                            key="mst_fb",
                            help="OFF (recommended): unmatched lines stay silent. "
                                 "ON: they keep the original English text for TTS.")

out_path = None                                   # always bound before the block
if st.button("🚀 Generate Hindi Dubbed Video Now", type="primary", key="mst_go"):
    # 1) parse + map --------------------------------------------------------
    hi_m = match_blocks(male_segs, parse_script(hi_male))
    hi_f = match_blocks(female_segs, parse_script(hi_female))
    if not hi_m and not hi_f:
        st.error("No Hindi lines matched — Boxes 3/4 are empty or carry no "
                 "[hh:mm:ss --> hh:mm:ss] timestamps. Copy the top boxes into your "
                 "LLM and paste the results back."); st.stop()
    unified, unmapped = [], []
    for i, s in enumerate(segs):
        pool = hi_f if s["speaker"].startswith("Female") else hi_m
        txt = pool.get(i)
        if not txt:
            unmapped.append(i)
            txt = s["text"] if keep_unmapped else "(silence)"
        unified.append({"start": s["start"], "end": s["end"],
                        "speaker": s["speaker"], "text": txt})
    st.write(f"Hindi mapped: {len(segs)-len(unmapped)}/{len(segs)} "
             f"(male {len(hi_m)} · female {len(hi_f)})"
             + (f" · unmatched: {len(unmapped)}" if unmapped else ""))

    # 2) TTS → continuous track → validation --------------------------------
    with st.status("Synthesizing Hindi TTS → building continuous dub track → "
                   "mixing → remuxing …", expanded=True) as status:
        tts_paths = audio_engine.generate_tts_batch(unified, work_dir)
        dub_wav, placed, miss = audio_engine.build_dub_track(
            unified, tts_paths, work_dir)
        if miss:
            status.update(label="❌ TTS failure — mix halted", state="error")
            st.error(f"HARD HALT: {len(miss)} line(s) failed synthesis/decode — "
                     "refusing to render a BGM-only video. Failed lines:")
            for i in miss[:10]:
                st.write(f"`#{i}` {unified[i]['speaker']} @ "
                         f"{fmt_ts_ms(unified[i]['start'])} — "
                         f"{unified[i]['text'][:80]}")
            st.stop()
        db = audio_engine._track_mean_db(dub_wav)
        st.write(f"✅ Continuous Hindi track: {placed} lines · level {db:.1f} dBFS")
        if db < -50:
            status.update(label="❌ Dub track is silent", state="error")
            st.error("HARD HALT: dub track has no audible content — TTS clips "
                     "decode empty. Check edge-tts network / Hindi text.")
            st.stop()
        staging.put("dub_preview", dub_wav)

        # 3) ducked BGM + Hindi mix → master ---------------------------------
        mix_wav = audio_engine.mix_bgm_dub(staging.get("bgm"), dub_wav,
                                           duck_db, work_dir)
        mastered = audio_engine.master_audio(mix_wav, lufs)
        staging.put("mix_preview", mastered)
        st.write("✅ Ducked BGM + Hindi mixed & mastered")

        # 4) detached remux (source audio structurally excluded) -------------
        out_path = audio_engine.mux_video_audio_detached(video_path, mastered,
                                                         work_dir)
        staging.put("dubbed_final", out_path)
        st.write("✅ Remuxed — original audio excluded by construction")
        status.update(label="✅ Dub complete — audition the previews below",
                      state="complete")

# ---------- DELIVERY: audible previews + video ----------
if staging.valid("dub_preview"):
    st.markdown("#### 🎧 Hindi Voice Preview (continuous dub track only)")
    st.audio(staging.get("dub_preview"))
if staging.valid("mix_preview"):
    st.markdown("#### 🎧 Final Mix Preview (ducked BGM + Hindi)")
    st.audio(staging.get("mix_preview"))
if staging.valid("dubbed_final"):
    st.video(staging.get("dubbed_final"))
    st.download_button("⬇️ Download dubbed video",
                       data=open(staging.get("dubbed_final"), "rb"),
                       file_name="hindi_dubbed.mp4", key="mst_dl_v")
    st.caption("Verify: zero English anywhere (including gaps between lines), "
               "Hindi on every mapped line, BGM continuous under dialogue.")
