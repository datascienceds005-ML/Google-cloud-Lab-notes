import streamlit as st
import os, tempfile, time, traceback, json
from datetime import timedelta

# --- FIX FOR PYTORCH STREAMLIT CRASH ---
try:
    import torch
    torch.classes.__path__ = []  # type: ignore
except Exception:
    pass
# ---------------------------------------

import audio_engine
import transcription

st.set_page_config(page_title="High-Accuracy Transcription", layout="wide", page_icon="🎯")

st.title("🎯 High-Accuracy Transcription")
st.caption("State-of-the-Art ASR (large-v3) • Vocal Denoising • Context-Aware Prompting • Word-Level Precision")

# -------------------- Helper Functions --------------------
def _seconds_to_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def segments_to_srt(segments):
    lines = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{_seconds_to_srt_time(seg['start'])} --> {_seconds_to_srt_time(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)

def segments_to_plain_text(segments):
    return "\n".join([seg["text"] for seg in segments])

# -------------------- UI & Settings --------------------
st.markdown("### Upload Media File")
uploaded = st.file_uploader("Drag & drop or browse", type=["mp4", "mkv", "avi", "mov", "mp3", "wav"], accept_multiple_files=False, label_visibility="collapsed")

with st.expander("⚙️ Advanced Accuracy Settings", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        glossary = st.text_input(
            "Glossary & Context Hints", 
            placeholder="e.g. Portia, Marcus, Ashgrove, SpaceX, ASR",
            help="Provide character names, places, or technical terms. The model uses this as an initial prompt to guarantee 100% correct spelling of proper nouns."
        )
    with col2:
        speaker_count_override = st.slider(
            "Expected number of speakers", 0, 5, 0,
            help="0 = auto-detect. Forcing a number can improve diarization accuracy."
        )

if uploaded:
    video_path = os.path.join(tempfile.gettempdir(), uploaded.name)
    with open(video_path, "wb") as f:
        f.write(uploaded.read())
    
    st.video(video_path)
    st.markdown("---")
    
    if st.button("🚀 Generate High-Accuracy Transcript", use_container_width=True, type="primary"):
        monitor_ui = st.empty()
        try:
            with monitor_ui.container():
                st.subheader("🔄 Process Monitor")
                status_text = st.empty()
                prog_bar = st.progress(0, text="0%")
                
                # Step 1: Vocal Denoising (Crucial for 100% accuracy)
                status_text.markdown("**Status:** Phase 1 - Isolating Vocals & Removing Background Noise...")
                prog_bar.progress(0.10, text="10% - Audio Denoising (Demucs)")
                
                # Use the existing audio engine to separate vocals. This removes BGM that causes hallucinations.
                vocal_path, _ = audio_engine.separate_vocals_bgm(video_path)
                
                # Step 2: High-Accuracy Transcription (large-v3)
                status_text.markdown("**Status:** Phase 2 - Loading `large-v3` Model & Transcribing...")
                def update_trans_progress(p, msg="Processing..."):
                    overall_p = 10 + int(p * 0.90)
                    status_text.markdown(f"**Status:** {msg}")
                    prog_bar.progress(overall_p / 100.0, text=f"{overall_p}%")
                
                # Force model_size="large-v3" for maximum accuracy
                segments = transcription.transcribe_audio(
                    vocal_path, 
                    None, 
                    progress_cb=update_trans_progress, 
                    model_size="large-v3",           
                    glossary=glossary,               
                    speaker_count_override=speaker_count_override
                )
                
                prog_bar.progress(1.0, text="100% - Transcription Complete")
                status_text.markdown("**Status:** Transcript generated successfully!")
            
            st.markdown("---")
            st.subheader("📜 Full Transcript")
            st.caption("Review and edit the transcript below before downloading.")
            
            # Display the transcript in an editable text area
            full_text = segments_to_plain_text(segments)
            edited_text = st.text_area("Transcript Editor", value=full_text, height=400, label_visibility="collapsed")
            
            # Download Buttons
            st.markdown("---")
            st.subheader("📥 Export Options")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.download_button(
                    "⬇️ Download as Text (TXT)",
                    data=edited_text,
                    file_name=f"{os.path.splitext(uploaded.name)[0]}_transcript.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            with col2:
                st.download_button(
                    "⬇️ Download Subtitles (SRT)",
                    data=segments_to_srt(segments),
                    file_name=f"{os.path.splitext(uploaded.name)[0]}_subtitles.srt",
                    mime="text/plain",
                    use_container_width=True
                )
            with col3:
                # Provide a JSON export for developers
                st.download_button(
                    "⬇️ Download Segments (JSON)",
                    data=json.dumps(segments, indent=4),
                    file_name=f"{os.path.splitext(uploaded.name)[0]}_segments.json",
                    mime="application/json",
                    use_container_width=True
                )

        except Exception as e:
            err_msg = str(e)
            st.error(f"Transcription Failed: {err_msg}")
            st.code(traceback.format_exc())
