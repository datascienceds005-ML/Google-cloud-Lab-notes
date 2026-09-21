"""
staging.py — dubbing pipeline state layer (Phase B).

Rule: audio files live ONLY on disk under /tmp/dubpro_stage/<session>/.
st.session_state holds paths + size stamps (survives Streamlit page hops
and reruns). Every page gates on staging.valid() before running.
"""
import os
import time
import json
import hashlib
import tempfile
import streamlit as st

STAGE_ROOT = os.path.join(tempfile.gettempdir(), "dubpro_stage")


def session_dir(uploaded) -> str:
    """Stable per-upload staging dir (same name|size convention as app.py)."""
    sig = f"{uploaded.name}|{uploaded.size}"
    d = os.path.join(STAGE_ROOT, hashlib.md5(sig.encode()).hexdigest()[:12])
    os.makedirs(d, exist_ok=True)
    return d


def save_upload(uploaded) -> str:
    """Persist upload into the session dir (idempotent)."""
    d = session_dir(uploaded)
    path = os.path.join(d, f"source_{uploaded.name}")
    if not os.path.exists(path) or os.path.getsize(path) != uploaded.size:
        with open(path, "wb") as f:
            f.write(uploaded.getbuffer())
    return path


def put(key: str, path: str) -> None:
    """Register an artifact with a size stamp (integrity check on read)."""
    st.session_state["stage_" + key] = {
        "path": path,
        "size": os.path.getsize(path) if os.path.exists(path) else -1,
        "ts": time.time(),
    }


def valid(key: str) -> bool:
    v = st.session_state.get("stage_" + key)
    return bool(v and v["size"] >= 0 and os.path.exists(v["path"])
                and os.path.getsize(v["path"]) == v["size"])


def get(key: str):
    v = st.session_state.get("stage_" + key)
    return v["path"] if v else None


def save_json(key: str, payload) -> str:
    d = os.path.dirname(get("video") or STAGE_ROOT) or STAGE_ROOT
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{key}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    put(key, path)
    return path


def load_json(key: str):
    p = get(key)
    if p and os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def clear_all() -> None:
    for k in [k for k in list(st.session_state) if k.startswith("stage_")]:
        del st.session_state[k]


def ram_mb():
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1048576
    except Exception:
        return None
