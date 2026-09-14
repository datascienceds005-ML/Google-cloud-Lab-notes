import os
import json

class StateLedger:
    def __init__(self, project_name="default"):
        self.file_path = os.path.join(os.path.dirname(__file__), f"pipeline_state_{project_name}.json")
        self.state = {"project_name": project_name, "chunks": []}
        if os.path.exists(self.file_path):
            self.load()
        else:
            self.save()

    def init_chunks(self, boundaries):
        # Don't reinitialize if resuming an existing project
        if len(self.state["chunks"]) > 0:
            return
        self.state["chunks"] = []
        for i, (start_ms, end_ms) in enumerate(boundaries):
            self.state["chunks"].append({
                "id": i,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "status": "PENDING",
                "asr_path": None,
                "mixed_path": None
            })
        self.save()

    def get_next_pending_chunk(self):
        for chunk in self.state["chunks"]:
            if chunk["status"] != "COMMITTED":
                return chunk
        return None

    def update_chunk(self, chunk_id, **kwargs):
        for chunk in self.state["chunks"]:
            if chunk["id"] == chunk_id:
                chunk.update(kwargs)
                break
        self.save()

    def is_complete(self):
        return all(c["status"] == "COMMITTED" for c in self.state["chunks"])

    def get_final_audio_paths(self):
        return [c["mixed_path"] for c in self.state["chunks"] if c["mixed_path"]]

    def save(self):
        with open(self.file_path, 'w') as f:
            json.dump(self.state, f, indent=4)

    def load(self):
        with open(self.file_path, 'r') as f:
            self.state = json.load(f)