from pydub import AudioSegment
from pydub.silence import detect_silence

def get_safe_chunks(audio_path, target_ms=120000, window_ms=10000, min_silence_ms=400, silence_thresh_db=-40):
    """
    Ingests a large WAV file and returns non-destructive chunk boundaries.
    Searches for the longest silence gap (>=400ms, -40dB) between 110s and 130s.
    """
    audio = AudioSegment.from_wav(audio_path)
    chunks = []
    current_start = 0
    
    while current_start < len(audio):
        target_end = current_start + target_ms
        if target_end >= len(audio):
            chunks.append((current_start, len(audio)))
            break
        
        start_search = max(0, target_end - window_ms)
        end_search = min(len(audio), target_end + window_ms)
        search_zone = audio[start_search:end_search]
        
        silences = detect_silence(search_zone, min_silence_len=min_silence_ms, silence_thresh=silence_thresh_db)
        
        if silences:
            # Pick the middle of the longest silence
            longest_silence = max(silences, key=lambda s: s[1] - s[0])
            cut_point = start_search + (longest_silence[0] + longest_silence[1]) // 2
            chunks.append((current_start, cut_point + 150)) # 150ms safety padding
            current_start = cut_point + 150
        else:
            # Fallback: Hard cut at 120s if no silence found
            chunks.append((current_start, target_end))
            current_start = target_end
            
    return chunks