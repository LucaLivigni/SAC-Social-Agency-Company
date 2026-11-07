from __future__ import annotations
import json, os, platform, subprocess
from pathlib import Path

SERVICE = "sac-marketing-studio"
FALLBACK = Path.home() / ".sac-marketing-studio" / "secrets.json"

def _mac_get(name: str) -> str:
    try:
        p = subprocess.run(["security","find-generic-password","-s",SERVICE,"-a",name,"-w"], capture_output=True, text=True, check=False)
        return p.stdout.strip() if p.returncode == 0 else ""
    except Exception:
        return ""

def _mac_set(name: str, value: str):
    subprocess.run(["security","add-generic-password","-U","-s",SERVICE,"-a",name,"-w",value], capture_output=True, text=True, check=True)

def _mac_delete(name: str):
    subprocess.run(["security","delete-generic-password","-s",SERVICE,"-a",name], capture_output=True, text=True, check=False)

def _load() -> dict:
    if not FALLBACK.exists(): return {}
    try: return json.loads(FALLBACK.read_text(encoding="utf-8"))
    except Exception: return {}

def _save(data: dict):
    FALLBACK.parent.mkdir(parents=True, exist_ok=True)
    FALLBACK.write_text(json.dumps(data), encoding="utf-8")
    try: os.chmod(FALLBACK, 0o600)
    except Exception: pass

def get_secret(name: str, env_name: str = "") -> str:
    if env_name and os.getenv(env_name): return os.getenv(env_name, "")
    if platform.system() == "Darwin":
        v = _mac_get(name)
        if v: return v
    return _load().get(name, "")

def set_secret(name: str, value: str):
    if platform.system() == "Darwin":
        try:
            _mac_set(name, value); return
        except Exception: pass
    d = _load(); d[name] = value; _save(d)

def delete_secret(name: str):
    if platform.system() == "Darwin": _mac_delete(name)
    d = _load(); d.pop(name, None); _save(d)
