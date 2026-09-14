import os
import json
import numpy as np

class GlobalSpeakerRegistry:
    def __init__(self, state_path="global_speakers.json"):
        self.state_path = state_path
        self.speakers = []
        if os.path.exists(state_path):
            self.load()

    def register_or_match(self, embedding, f0):
        if not self.speakers:
            # First speaker ever detected
            gender = "Female" if f0 > 165 else "Male"
            spk_id = f"{gender}_1"
            self.speakers.append({"id": spk_id, "gender": gender, "centroid": embedding.tolist(), "count": 1})
            self.save()
            return spk_id
        
        # Calculate Cosine Similarity against all known speakers
        best_match = None
        best_score = -1.0
        
        for spk in self.speakers:
            centroid = np.array(spk["centroid"])
            # Cosine Similarity = (A . B) / (||A|| ||B||)
            score = np.dot(embedding, centroid) / (np.linalg.norm(embedding) * np.linalg.norm(centroid) + 1e-8)
            if score > best_score:
                best_score = score
                best_match = spk
        
        if best_score >= 0.85:
            # Match found: Update centroid to track voice drift safely
            best_match["count"] += 1
            new_centroid = (np.array(best_match["centroid"]) * (best_match["count"]-1) + embedding) / best_match["count"]
            best_match["centroid"] = new_centroid.tolist()
            self.save()
            return best_match["id"]
        else:
            # No match found: Register new speaker
            gender = "Female" if f0 > 165 else "Male"
            num = len([s for s in self.speakers if s["gender"] == gender]) + 1
            spk_id = f"{gender}_{num}"
            self.speakers.append({"id": spk_id, "gender": gender, "centroid": embedding.tolist(), "count": 1})
            self.save()
            return spk_id

    def save(self):
        with open(self.state_path, 'w') as f:
            json.dump(self.speakers, f, indent=4)

    def load(self):
        with open(self.state_path, 'r') as f:
            self.speakers = json.load(f)