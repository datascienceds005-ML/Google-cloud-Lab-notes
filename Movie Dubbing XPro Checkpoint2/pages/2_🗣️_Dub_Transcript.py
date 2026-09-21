import streamlit as st
import audio_engine
import transcription
import staging

try:
    import torch
    torch.classes.__path__ = []
except Exception:
    pass

st.set_page_config(page_title="Step 2 · Dub Transcript", page_icon="🗣️", layout="wide")
st.title("🗣️ Step 2 — ASR + Diarization on the CLEAN vocal stem")
st.caption("Reuses the LOCKED Tab 5 engine unchanged. Deep-capture/rescue OFF — "
           "the Demucs stem replaces them. Expect much faster ASR than the Hub.")

if not staging.valid("vocals_mono"):
    st.warning("Run Step 1 (Audio Separation) first."); st.stop()

c1, c2 = st.columns(2)
model_size = c1.selectbox("Whisper model", ["small.en", "base.en", "medium.en"], index=0, key="p2_model")
spk_override = c2.slider("Expected speakers (0 = auto)", 0, 6, 0, key="p2_spk")

if st.button("🚀 Transcribe vocal stem", type="primary", key="p2_run"):
    with st.status("Multi-pass ASR (single sweep) → diarization…", expanded=True) as status:
        try:
            raw = transcription.run_whisper_raw(
                staging.get("vocals_mono"), model_size=model_size,
                deep_scan=False, rescue=False,
                progress=lambda m: st.write(m))
            final, stats = transcription.run_diarization(
                staging.get("vocals_mono"), raw, speaker_count_override=spk_override)
        except Exception as e:
            status.update(label="❌ ASR/diarization failed", state="error")
            st.exception(e); st.stop()
        payload = {"segments": final, "speaker_stats": stats,
                   "meta": {"source": "demucs_vocal_stem", "model": model_size,
                            "spk_override": spk_override, "n_segments": len(final)}}
        staging.save_json("transcript", payload)
        status.update(label=f"✅ {len(final)} labelled segments", state="complete")

tp = staging.load_json("transcript")
if tp:
    st.dataframe(tp["speaker_stats"], use_container_width=True)
    male = [s for s in tp["segments"] if s["speaker"].startswith("Male")]
    female = [s for s in tp["segments"] if s["speaker"].startswith("Female")]
    st.metric("Male segments", len(male)); st.metric("Female segments", len(female))
    with st.expander("Chronological preview (first 30 lines)"):
        for s in tp["segments"][:30]:
            st.write(f"`[{s['start']:7.2f} → {s['end']:7.2f}]` **{s['speaker']}**: {s['text']}")
    st.download_button("⬇️ Download transcript JSON (LLM export)",
                       __import__("json").dumps(tp, ensure_ascii=False, indent=2),
                       file_name="dub_transcript.json", key="p2_dl")
    if st.button("🔒 Lock transcript for TTS", type="primary", key="p2_lock"):
        staging.put("transcript_locked", staging.get("transcript"))
        st.success("Locked — proceed to Step 3 (Hindi TTS).")
