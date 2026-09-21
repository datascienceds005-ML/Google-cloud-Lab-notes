import time, subprocess
import streamlit as st
import audio_engine
import staging

try:
    import torch
    torch.classes.__path__ = []
except Exception:
    pass

st.set_page_config(page_title="Step 1 · Separation", page_icon="🎵", layout="wide")
st.title("🎵 Step 1 — Audio Stripping & BGM Isolation (Demucs)")
st.caption("Heavy op #1 (runs as a subprocess — RAM peak dies with the child). "
           "Verify clean vocal stem + BGM before any ASR/TTS work.")

# ---- call helper: tolerant to both engine signatures -----------------------
def run_separation(video_path, work_dir):
    try:
        return audio_engine.extract_and_isolate_bgm(video_path, work_dir=work_dir)
    except TypeError:                       # legacy v2.2 signature
        return audio_engine.extract_and_isolate_bgm(video_path)


def _dur(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                              "format=duration", "-of",
                              "default=noprint_wrappers=1:nokey=1", path],
                             capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip())
    except Exception:
        return 0.0


uploaded = st.file_uploader("Upload source video", type=["mp4", "mkv", "avi", "mov"],
                            key="dub_upload_p1")
if uploaded:
    video_path = staging.save_upload(uploaded)
    staging.put("video", video_path)
    st.success(f"Source registered: {uploaded.name} ({uploaded.size/1e6:.1f} MB)")

    ram0 = staging.ram_mb()
    t0 = time.time()
    if st.button("🚀 Run Demucs separation", type="primary", key="p1_run"):
        with st.status("Running Demucs (htdemucs, CPU — expect a few minutes)…",
                       expanded=True) as status:
            st.write(f"RAM before: {ram0:.0f} MB")
            try:
                mono_wav, bgm_wav, voc_wav = run_separation(
                    video_path, staging.session_dir(uploaded))
            except Exception as e:
                status.update(label="❌ Demucs failed", state="error")
                st.exception(e)
                st.stop()
            elapsed = time.time() - t0
            staging.put("vocals_mono", mono_wav)
            staging.put("bgm", bgm_wav)
            staging.put("vocals", voc_wav)
            status.update(label=f"✅ Separation done in {elapsed:.0f}s", state="complete")

    if staging.valid("bgm"):
        ram1 = staging.ram_mb()
        c1, c2, c3 = st.columns(3)
        c1.metric("⏱ Elapsed", f"{time.time() - t0 if 't0' in dir() else 0:.0f}s" if False else "—")
        c2.metric("🧠 Process RAM", f"{ram1:.0f} MB")
        c3.metric("Δ RAM", f"{(ram1 - ram0):+.0f} MB" if ram0 else "—")

        st.markdown("#### ✅ Verification")
        rows = {"BGM stem": staging.get("bgm"), "Vocals stem (stereo)": staging.get("vocals"),
                "Vocals mono 16k (ASR input)": staging.get("vocals_mono")}
        ok = True
        for name, p in rows.items():
            sz = __import__("os").path.getsize(p) / 1e6
            d = _dur(p)
            good = sz > 0.05 and d > 1.0
            ok &= good
            st.write(f"{'✅' if good else '❌'} **{name}** — {sz:.1f} MB · {d:.1f}s")
        st.markdown("#### 👂 Listen-check the isolation")
        st.audio(staging.get("bgm"), format="audio/wav")
        st.caption("BGM above — should contain music/FX, NO clear dialogue.")
        st.audio(staging.get("vocals"), format="audio/wav")
        st.caption("Vocals above — should contain dialogue, minimal music bleed.")
        if ok:
            st.success("Step 1 PASSED — proceed to Step 2 (Dub Transcript).")
        else:
            st.error("An output looks empty/corrupt — re-run before continuing.")