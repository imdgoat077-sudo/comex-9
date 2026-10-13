"""
Durable chat conversations (SQLite): the source of truth for what was said, in which tab group.

Identity model (kept apart on purpose; nothing here depends on how the orchestrator works):
    group_id         a set of browser tabs that share one chat. An independent tab is a group of one
                     ("grp-<tabId>"); tabs opened by agents for a conversation join that conversation's group.
    conversation_id  one chat thread. A group points at its current conversation; "new chat" starts another one
                     and closes the old (kept, marked for compaction into long-term memory later).
    run_id / taskId  one execution (single-agent task or multi-agent run). Messages carry it for provenance.
    tab_id           a browser tab (the React/Electron tab id). A tab is in at most one group at a time.
    worker_id        an agent's own identity for authorization; recorded on the tab it was given.

Kùzu stays the store for long-term knowledge; this file only holds conversations, their messages, which tabs are in
which group, and verified outcomes (actions that happened, so they are not repeated).
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

DEFAULT_PATH = os.path.join(os.path.expanduser("~"), ".comex", "chats.db")
HISTORY_TURNS = 10          # messages the parent agent sees
HISTORY_CHARS = 2000        # per message
TITLE_CHARS = 80

_SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    group_id TEXT,
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',            -- open | closed
    compaction_status TEXT NOT NULL DEFAULT 'none', -- none | pending | done
    summary TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    closed_at REAL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL,                             -- user | assistant
    content TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'chat',              -- chat | run
    meta TEXT,
    run_id TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_by_conversation ON messages(conversation_id, seq);
CREATE TABLE IF NOT EXISTS group_tabs (
    group_id TEXT NOT NULL,
    tab_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'main',               -- main | agent | link
    run_id TEXT,
    worker_id TEXT,
    added_at REAL NOT NULL,
    removed_at REAL,
    PRIMARY KEY (group_id, tab_id)
);
CREATE INDEX IF NOT EXISTS group_tabs_by_tab ON group_tabs(tab_id);
CREATE TABLE IF NOT EXISTS outcomes (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    run_id TEXT,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    url TEXT,
    details TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS outcomes_by_conversation ON outcomes(conversation_id, created_at);
"""


def _new_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{secrets.token_hex(3)}"


class ChatStore:
    """Thread-safe SQLite store. Every write commits before returning, so a crash loses at most the call in flight."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or os.getenv("COMEX_CHAT_DB_PATH") or DEFAULT_PATH
        if self.path != ":memory:":
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        if self.path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ── groups and conversations ─────────────────────────────────────────────────────────────────

    def _create_conversation_locked(self, group_id: str) -> str:
        now = time.time()
        cid = _new_id("conv")
        self._db.execute("INSERT INTO conversations (id, group_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                         (cid, group_id, now, now))
        self._db.execute("UPDATE groups SET conversation_id = ?, updated_at = ? WHERE id = ?", (cid, now, group_id))
        return cid

    def ensure_group(self, group_id: str, tab_id: Optional[str] = None, role: str = "main") -> Dict[str, Any]:
        """The group (created if new) with its current conversation (created if it has none); joins tab_id to it."""
        if not group_id:
            raise ValueError("group_id is required")
        with self._lock:
            now = time.time()
            self._db.execute("INSERT OR IGNORE INTO groups (id, created_at, updated_at) VALUES (?, ?, ?)",
                             (group_id, now, now))
            row = self._db.execute("SELECT conversation_id FROM groups WHERE id = ?", (group_id,)).fetchone()
            cid = row["conversation_id"]
            conv = self._db.execute("SELECT status FROM conversations WHERE id = ?", (cid,)).fetchone() if cid else None
            if conv is None:
                cid = self._create_conversation_locked(group_id)
            elif conv["status"] != "open":
                # The group came back (its closing was undone, or it was restored): its chat continues. It is compacted
                # again when it closes next time; the summary has a fixed id, so that replaces the earlier one.
                self._db.execute("UPDATE conversations SET status = 'open', closed_at = NULL, compaction_status = 'none', "
                                 "updated_at = ? WHERE id = ?", (now, cid))
            if tab_id:
                self._join_locked(group_id, tab_id, role, None, None)
        return {"group_id": group_id, "conversation_id": cid}

    def new_conversation(self, group_id: str) -> str:
        """Start a fresh conversation for the group. The old one is kept and marked for compaction."""
        with self._lock:
            row = self._db.execute("SELECT conversation_id FROM groups WHERE id = ?", (group_id,)).fetchone()
            if row is None:
                now = time.time()
                self._db.execute("INSERT INTO groups (id, created_at, updated_at) VALUES (?, ?, ?)", (group_id, now, now))
            elif row["conversation_id"]:
                self._close_conversation_locked(row["conversation_id"])
            return self._create_conversation_locked(group_id)

    def attach_conversation(self, group_id: str, conversation_id: str) -> None:
        """Reopen an earlier conversation in this group (from the history list)."""
        with self._lock:
            if not self._db.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone():
                raise KeyError(conversation_id)
            now = time.time()
            self._db.execute("INSERT OR IGNORE INTO groups (id, created_at, updated_at) VALUES (?, ?, ?)", (group_id, now, now))
            self._db.execute("UPDATE groups SET conversation_id = ?, updated_at = ? WHERE id = ?", (conversation_id, now, group_id))
            self._db.execute("UPDATE conversations SET status = 'open', group_id = ?, updated_at = ? WHERE id = ?",
                             (group_id, now, conversation_id))

    def _close_conversation_locked(self, conversation_id: str) -> None:
        has_messages = self._db.execute("SELECT 1 FROM messages WHERE conversation_id = ? LIMIT 1", (conversation_id,)).fetchone()
        self._db.execute(
            "UPDATE conversations SET status = 'closed', closed_at = ?, "
            "compaction_status = CASE WHEN compaction_status = 'done' THEN 'done' WHEN ? THEN 'pending' ELSE 'none' END "
            "WHERE id = ? AND status = 'open'",
            (time.time(), 1 if has_messages else 0, conversation_id))

    def conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._db.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return dict(row) if row else None

    def list_conversations(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT c.id, c.group_id, c.title, c.status, c.updated_at, COUNT(m.id) AS message_count "
                "FROM conversations c JOIN messages m ON m.conversation_id = c.id "
                "GROUP BY c.id ORDER BY c.updated_at DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def pending_compaction(self) -> List[str]:
        """Closed conversations whose compaction has not finished (also those interrupted by a crash)."""
        with self._lock:
            rows = self._db.execute("SELECT id FROM conversations WHERE compaction_status = 'pending' ORDER BY closed_at").fetchall()
        return [r["id"] for r in rows]

    def set_compaction(self, conversation_id: str, status: str, summary: Optional[str] = None) -> None:
        if status not in ("none", "pending", "done"):
            raise ValueError("bad compaction status")
        with self._lock:
            self._db.execute("UPDATE conversations SET compaction_status = ?, summary = COALESCE(?, summary) WHERE id = ?",
                             (status, summary, conversation_id))

    # ── tabs in groups ───────────────────────────────────────────────────────────────────────────

    def _join_locked(self, group_id: str, tab_id: str, role: str, run_id: Optional[str], worker_id: Optional[str]) -> None:
        now = time.time()
        # a tab is in one group at a time: leaving any other group first
        self._db.execute("UPDATE group_tabs SET removed_at = ? WHERE tab_id = ? AND group_id != ? AND removed_at IS NULL",
                         (now, tab_id, group_id))
        self._db.execute(
            "INSERT INTO group_tabs (group_id, tab_id, role, run_id, worker_id, added_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(group_id, tab_id) DO UPDATE SET removed_at = NULL, role = excluded.role, "
            "run_id = COALESCE(excluded.run_id, group_tabs.run_id), worker_id = COALESCE(excluded.worker_id, group_tabs.worker_id)",
            (group_id, tab_id, role, run_id, worker_id, now))

    def join_group(self, group_id: str, tab_id: str, role: str = "agent", run_id: Optional[str] = None,
                   worker_id: Optional[str] = None) -> None:
        with self._lock:
            now = time.time()
            self._db.execute("INSERT OR IGNORE INTO groups (id, created_at, updated_at) VALUES (?, ?, ?)", (group_id, now, now))
            self._join_locked(group_id, tab_id, role, run_id, worker_id)

    def group_tabs(self, group_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT tab_id, role, run_id, worker_id FROM group_tabs "
                                    "WHERE group_id = ? AND removed_at IS NULL ORDER BY added_at", (group_id,)).fetchall()
        return [dict(r) for r in rows]

    def group_of_tab(self, tab_id: str) -> Optional[str]:
        with self._lock:
            row = self._db.execute("SELECT group_id FROM group_tabs WHERE tab_id = ? AND removed_at IS NULL", (tab_id,)).fetchone()
        return row["group_id"] if row else None

    def is_tab_in_group(self, group_id: str, tab_id: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM group_tabs WHERE group_id = ? AND tab_id = ? AND removed_at IS NULL",
                                    (group_id, tab_id)).fetchone() is not None

    def remove_tab(self, tab_id: str) -> Optional[str]:
        """
        A tab was closed. It leaves its group; the group's conversation is kept. When the group's last tab closes the
        conversation is closed and marked for compaction. Returns the conversation id that was closed, if any.
        """
        with self._lock:
            row = self._db.execute("SELECT group_id FROM group_tabs WHERE tab_id = ? AND removed_at IS NULL", (tab_id,)).fetchone()
            if row is None:
                return None
            group_id = row["group_id"]
            self._db.execute("UPDATE group_tabs SET removed_at = ? WHERE tab_id = ? AND removed_at IS NULL", (time.time(), tab_id))
            left = self._db.execute("SELECT 1 FROM group_tabs WHERE group_id = ? AND removed_at IS NULL LIMIT 1", (group_id,)).fetchone()
            if left:
                return None
            g = self._db.execute("SELECT conversation_id FROM groups WHERE id = ?", (group_id,)).fetchone()
            if g and g["conversation_id"]:
                self._close_conversation_locked(g["conversation_id"])
                return g["conversation_id"]
        return None

    def close_group(self, group_id: str) -> Optional[str]:
        """
        The whole group was closed: all its tabs leave it and its conversation is closed (kept, shown in History and
        compacted). Returns the closed conversation id, if the group had an open one.
        """
        with self._lock:
            now = time.time()
            self._db.execute("UPDATE group_tabs SET removed_at = ? WHERE group_id = ? AND removed_at IS NULL", (now, group_id))
            g = self._db.execute("SELECT conversation_id FROM groups WHERE id = ?", (group_id,)).fetchone()
            if not g or not g["conversation_id"]:
                return None
            open_ = self._db.execute("SELECT 1 FROM conversations WHERE id = ? AND status = 'open'", (g["conversation_id"],)).fetchone()
            self._close_conversation_locked(g["conversation_id"])
            return g["conversation_id"] if open_ else None

    # ── messages ────────────────────────────────────────────────────────────────────────────────

    def append_message(self, conversation_id: str, role: str, content: str, kind: str = "chat",
                       meta: Optional[Dict[str, Any]] = None, run_id: Optional[str] = None,
                       message_id: Optional[str] = None) -> str:
        """Store one message. A repeated message_id is ignored, so a retried write never duplicates a turn."""
        if role not in ("user", "assistant"):
            raise ValueError("role must be user or assistant")
        mid = message_id or _new_id("msg")
        with self._lock:
            if not self._db.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone():
                raise KeyError(conversation_id)
            now = time.time()
            seq = self._db.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM messages WHERE conversation_id = ?",
                                   (conversation_id,)).fetchone()[0]
            cur = self._db.execute(
                "INSERT OR IGNORE INTO messages (id, conversation_id, seq, role, content, kind, meta, run_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (mid, conversation_id, seq, role, content or "", kind, json.dumps(meta, default=str) if meta else None, run_id, now))
            if cur.rowcount:
                # A reply that lands after its conversation closed (a run stopped by closing its group) is kept, but it
                # does not reopen the conversation; a summary made before it is redone so it includes the reply.
                self._db.execute("UPDATE conversations SET updated_at = ?, compaction_status = CASE WHEN status = 'closed' "
                                 "AND compaction_status = 'done' THEN 'pending' ELSE compaction_status END WHERE id = ?",
                                 (now, conversation_id))
                if role == "user":
                    self._db.execute("UPDATE conversations SET title = ? WHERE id = ? AND title = ''",
                                     (" ".join((content or "").split())[:TITLE_CHARS], conversation_id))
        return mid

    def messages(self, conversation_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if limit:
                rows = self._db.execute("SELECT * FROM (SELECT * FROM messages WHERE conversation_id = ? ORDER BY seq DESC LIMIT ?) "
                                        "ORDER BY seq", (conversation_id, int(limit))).fetchall()
            else:
                rows = self._db.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY seq", (conversation_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["meta"] = json.loads(d["meta"]) if d.get("meta") else {}
            out.append(d)
        return out

    def history_for_model(self, conversation_id: str, limit: int = HISTORY_TURNS, max_chars: int = HISTORY_CHARS) -> List[Dict[str, Any]]:
        """The bounded recent history a parent agent sees: role, content, and the verified outcome when there was one."""
        return [{"role": m["role"], "content": m["content"][:max_chars], "task_outcome": (m["meta"] or {}).get("task_outcome")}
                for m in self.messages(conversation_id, limit=limit) if m["content"]]

    # ── verified outcomes ───────────────────────────────────────────────────────────────────────

    def record_outcome(self, conversation_id: str, action: str, status: str, run_id: Optional[str] = None,
                       url: Optional[str] = None, details: Optional[str] = None) -> str:
        oid = _new_id("out")
        with self._lock:
            self._db.execute("INSERT INTO outcomes (id, conversation_id, run_id, action, status, url, details, created_at) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                             (oid, conversation_id, run_id, action[:300], status, url, (details or "")[:600], time.time()))
        return oid

    def outcomes(self, conversation_id: str, limit: int = 6) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT action, status, url, details, run_id, created_at FROM outcomes "
                                    "WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?", (conversation_id, int(limit))).fetchall()
        return [dict(r) for r in reversed(rows)]


_STORE: Optional[ChatStore] = None
_STORE_LOCK = threading.Lock()


def get_chat_store() -> ChatStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = ChatStore()
        return _STORE


def set_chat_store(store: Optional[ChatStore]) -> None:
    """For tests: swap in an isolated store."""
    global _STORE
    with _STORE_LOCK:
        _STORE = store
