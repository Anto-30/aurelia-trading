from pathlib import Path
import hashlib
def load_config_hash(root:Path):
 paths=[root/"config"/"LIVE_LOCK.yaml",root/"config"/"runtime.yaml"]
 payload=[]
 for p in paths: payload.append(p.read_text(encoding="utf-8") if p.exists() else f"MISSING:{p}")
 return hashlib.sha256("\n".join(payload).encode()).hexdigest()
