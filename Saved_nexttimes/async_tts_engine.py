import asyncio
import edge_tts
import os

VOICE_MAP = {
    "Male_1": "hi-IN-MadhurNeural", "Male_2": "mr-IN-ManoharNeural",
    "Female_1": "hi-IN-SwaraNeural", "Female_2": "mr-IN-AarohiNeural",
    "Default": "hi-IN-MadhurNeural"
}

async def _fetch_tts(semaphore, text, voice, out_path):
    async with semaphore:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(out_path)

async def generate_tts_batch(segments, temp_dir):
    """
    Generates TTS for all segments in a chunk concurrently.
    Limits to 4 concurrent requests to avoid Microsoft Edge rate-limiting.
    """
    semaphore = asyncio.Semaphore(4)
    tasks = []
    paths = []
    
    for i, seg in enumerate(segments):
        if not seg["text"].strip() or seg["text"] == "(silence)":
            paths.append(None)
            continue
            
        voice = VOICE_MAP.get(seg["speaker"], VOICE_MAP["Default"])
        out_path = os.path.join(temp_dir, f"tts_{i}.mp3")
        paths.append(out_path)
        tasks.append(_fetch_tts(semaphore, seg["text"], voice, out_path))
        
    await asyncio.gather(*tasks)
    return paths

def run_tts_batch(segments, temp_dir):
    # Safely run async loop inside Streamlit
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    return loop.run_until_complete(generate_tts_batch(segments, temp_dir))
