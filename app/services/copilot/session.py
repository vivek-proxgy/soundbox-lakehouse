"""Configurable session history tracking (Local files / GCS) for Copilot."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config.settings import get_settings

try:
    from google.cloud import storage
    HAS_GCS_SDK = True
except ImportError:
    storage = None
    HAS_GCS_SDK = False


def get_or_create_session(session_id: Optional[str]) -> str:
    """Resolve the session ID or generate a new UUID-based ID."""
    return session_id or str(uuid.uuid4())


def _get_local_filepath(session_id: str) -> str:
    """Resolve local path to store session json."""
    settings = get_settings()
    root = os.getenv("SESSION_LOCAL_DIR")
    if not root:
        try:
            root = os.path.join(settings.lakehouse_local_root, "sessions")
        except Exception:
            root = os.path.join(os.getcwd(), ".sessions")
            
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, f"{session_id}.json")


def _get_gcs_blob(session_id: str) -> Any:
    """Resolve GCS blob for session storage."""
    if not HAS_GCS_SDK or storage is None:
        raise RuntimeError("google-cloud-storage SDK is not installed in the environment.")
    
    settings = get_settings()
    bucket_name = os.getenv("SESSION_GCS_BUCKET") or settings.gcs_bucket
    prefix = os.getenv("SESSION_GCS_PREFIX") or "sessions/"
    
    client = storage.Client(project=settings.google_cloud_project)
    bucket = client.bucket(bucket_name)
    blob_name = f"{prefix.rstrip('/')}/{session_id}.json"
    return bucket.blob(blob_name)


def get_history(session_id: str) -> List[Dict[str, Any]]:
    """Retrieve chat history list from the configured storage engine (Local / GCS)."""
    storage_type = os.getenv("SESSION_STORAGE_TYPE", "local").lower()
    
    if storage_type == "gcs":
        try:
            blob = _get_gcs_blob(session_id)
            if not blob.exists():
                return []
            content = blob.download_as_text()
            return json.loads(content)
        except Exception as e:
            print(f"[copilot-session] Failed to read history from GCS: {e}")
            return []
            
    # Local file storage
    filepath = _get_local_filepath(session_id)
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[copilot-session] Failed to read local session file: {e}")
        return []


def append_history(session_id: str, user_content: str, bot_content: str) -> None:
    """Append a message turn to chat history, with a hard limit of the last 20 messages."""
    history = get_history(session_id)
    
    # Enforce memory safety / request payload sizes by keeping the last 20 messages
    history = history[-20:]
    
    history.append({
        "role": "user",
        "content": user_content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    history.append({
        "role": "assistant",
        "content": bot_content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    
    storage_type = os.getenv("SESSION_STORAGE_TYPE", "local").lower()
    
    if storage_type == "gcs":
        try:
            blob = _get_gcs_blob(session_id)
            blob.upload_from_string(json.dumps(history, indent=2), content_type="application/json")
            return
        except Exception as e:
            print(f"[copilot-session] Failed to write session to GCS: {e}")
            return
            
    # Local file storage
    filepath = _get_local_filepath(session_id)
    try:
        with open(filepath, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"[copilot-session] Failed to write local session file: {e}")


def delete_session(session_id: str) -> None:
    """Terminate the session and delete its conversation history from storage."""
    storage_type = os.getenv("SESSION_STORAGE_TYPE", "local").lower()
    
    if storage_type == "gcs":
        try:
            blob = _get_gcs_blob(session_id)
            if blob.exists():
                blob.delete()
                print(f"[copilot-session] Session {session_id} deleted from GCS.")
            return
        except Exception as e:
            print(f"[copilot-session] Failed to delete session from GCS: {e}")
            return
            
    # Local file storage
    filepath = _get_local_filepath(session_id)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"[copilot-session] Session {session_id} deleted from local file.")
        except Exception as e:
            print(f"[copilot-session] Failed to delete local session file: {e}")
