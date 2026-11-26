"""
Session, Recent Comparisons & Workspace Profile Persistence Manager.
Stores open comparison tabs, recent comparisons, and named comparison profiles.
"""

import os
import json
import time
from typing import List, Dict, Any, Optional


class SessionManager:
    """Manages workspace session restoration, recent history, and comparison profiles."""

    @classmethod
    def get_storage_dir(cls) -> str:
        app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
        storage = os.path.join(app_data, "diff_and_compare")
        os.makedirs(storage, exist_ok=True)
        return storage

    @classmethod
    def get_session_file(cls) -> str:
        return os.path.join(cls.get_storage_dir(), "active_session.json")

    @classmethod
    def get_profiles_file(cls) -> str:
        return os.path.join(cls.get_storage_dir(), "profiles.json")

    @classmethod
    def get_recent_file(cls) -> str:
        return os.path.join(cls.get_storage_dir(), "recent_comparisons.json")

    @classmethod
    def save_session(cls, tabs_data: List[Dict[str, Any]], active_tab_index: int = 0) -> bool:
        """Saves current open tabs to disk for automatic session restoration."""
        try:
            payload = {
                "active_index": active_tab_index,
                "tabs": tabs_data
            }
            with open(cls.get_session_file(), "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            return True
        except Exception:
            return False

    @classmethod
    def load_session(cls) -> Optional[Dict[str, Any]]:
        """Loads last active session if exists."""
        filepath = cls.get_session_file()
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @classmethod
    def save_profile(cls, name: str, tabs_data: List[Dict[str, Any]]) -> bool:
        """Saves a named comparison workspace profile."""
        try:
            profiles = cls.load_all_profiles()
            profiles[name] = tabs_data
            with open(cls.get_profiles_file(), "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2)
            return True
        except Exception:
            return False

    @classmethod
    def delete_profile(cls, name: str) -> bool:
        """Deletes a named comparison workspace profile."""
        try:
            profiles = cls.load_all_profiles()
            if name in profiles:
                del profiles[name]
                with open(cls.get_profiles_file(), "w", encoding="utf-8") as f:
                    json.dump(profiles, f, indent=2)
                return True
            return False
        except Exception:
            return False

    @classmethod
    def load_all_profiles(cls) -> Dict[str, Any]:
        filepath = cls.get_profiles_file()
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def add_recent_comparison(cls, left_path: str, right_path: str, mode: str = "auto", max_items: int = 12) -> bool:
        """Records a recent file/folder comparison pair (deduplicated, newest first)."""
        if not left_path or not right_path:
            return False
        try:
            items = cls.get_recent_comparisons(limit=max_items)
            norm_l = os.path.normpath(left_path)
            norm_r = os.path.normpath(right_path)
            items = [
                it for it in items
                if not (os.path.normpath(it.get("left_path", "")) == norm_l and os.path.normpath(it.get("right_path", "")) == norm_r)
            ]
            items.insert(0, {
                "left_path": left_path,
                "right_path": right_path,
                "mode": mode,
                "timestamp": time.time(),
            })
            items = items[:max_items]
            with open(cls.get_recent_file(), "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)
            return True
        except Exception:
            return False

    @classmethod
    def get_recent_comparisons(cls, limit: int = 10) -> List[Dict[str, Any]]:
        filepath = cls.get_recent_file()
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data[:limit]
            return []
        except Exception:
            return []

    @classmethod
    def clear_recent_comparisons(cls) -> bool:
        filepath = cls.get_recent_file()
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        except Exception:
            return False
