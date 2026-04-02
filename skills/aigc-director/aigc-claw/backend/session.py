# -*- coding: utf-8 -*-
import json
import os
import time

class SessionManager:
    """Manages chat sessions persistence"""
    def __init__(self, data_dir="code/data"):
        self.data_dir = data_dir
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def _get_file(self, session_id):
        return os.path.join(self.data_dir, f"{session_id}.json")

    def list_sessions(self):
        """List all sessions ordered by modification time"""
        sessions = []
        if not os.path.exists(self.data_dir):
            return sessions

        files = [f for f in os.listdir(self.data_dir) if f.endswith('.json')]
        for f in files:
            try:
                path = os.path.join(self.data_dir, f)
                with open(path, 'r', encoding='utf-8') as fs:
                    data = json.load(fs)
                    # title, id, last_updated
                    sessions.append({
                        "id": data.get("id"),
                        "title": data.get("title", "Untitled"),
                        "date": "7days", # Simplification. Real logic would calc date diff
                        "timestamp": os.path.getmtime(path)
                    })
            except Exception:
                continue
        
        # Sort by timestamp desc
        sessions.sort(key=lambda x: x['timestamp'], reverse=True)
        return sessions

    def get_session(self, session_id):
        """Get full history of a session"""
        path = self._get_file(session_id)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def save_session(self, session_id, title, messages, asset_library=None):
        """Save or update session"""
        data = {
            "id": session_id,
            "title": title,
            "last_updated": time.time(),
            "messages": messages,
            "asset_library": asset_library or {}
        }
        with open(self._get_file(session_id), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
