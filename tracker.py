# tracker.py
import json
import os
from datetime import datetime

TRACKER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "job_history.json")

def load_history():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def is_processed(url):
    history = load_history()
    return url in history

def record_job(url, status, reason=""):
    history = load_history()
    history[url] = {
        "status": status,
        "reason": reason,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4, ensure_ascii=False)
    print(f"💾 Saved status [{status.upper()}] to history tracker.")