import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.database import get_connection, init_db


class AuditLogger:
    def __init__(self) -> None:
        init_db()

    def log(
        self,
        event_type: str,
        entity_type: str,
        message: str,
        entity_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    event_type, entity_type, entity_id, message,
                    metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    entity_type,
                    entity_id,
                    message,
                    metadata_json,
                    created_at,
                ),
            )

    def latest(self, limit: int = 50):
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, event_type, entity_type, entity_id, message,
                       metadata_json, created_at
                FROM audit_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        logs = []
        for row in rows:
            item = dict(row)
            try:
                item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            except json.JSONDecodeError:
                item["metadata"] = {}
            logs.append(item)
        return logs

