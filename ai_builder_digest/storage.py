from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

from .models import DigestItem, SourceAudit


SCHEMA = """
CREATE TABLE IF NOT EXISTS digest_items (
  target_date TEXT NOT NULL,
  link TEXT NOT NULL,
  title TEXT NOT NULL,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  stream TEXT NOT NULL,
  published TEXT,
  score INTEGER NOT NULL,
  brief TEXT,
  importance TEXT,
  credibility TEXT,
  claim_check TEXT,
  judge TEXT,
  judge_reason TEXT,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (target_date, link)
);

CREATE TABLE IF NOT EXISTS source_audits (
  target_date TEXT NOT NULL,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  region TEXT NOT NULL,
  status TEXT NOT NULL,
  total_fetched INTEGER NOT NULL,
  today_count INTEGER NOT NULL,
  selected_count INTEGER NOT NULL,
  error TEXT,
  notes_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (target_date, name)
);
"""


def save_run(db_path: str | Path, target_date: date, items: list[DigestItem], audits: list[SourceAudit]) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        for item in items:
            conn.execute(
                """
                INSERT OR REPLACE INTO digest_items (
                  target_date, link, title, source, category, stream, published, score,
                  brief, importance, credibility, claim_check, judge, judge_reason,
                  payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_date.isoformat(),
                    item.link,
                    item.title,
                    item.source,
                    item.category,
                    item.stream,
                    item.published,
                    item.score,
                    item.brief,
                    item.importance,
                    item.credibility,
                    item.claim_check,
                    item.judge,
                    item.judge_reason,
                    json.dumps(item.as_dict(), ensure_ascii=False),
                    now,
                ),
            )
        for audit in audits:
            conn.execute(
                """
                INSERT OR REPLACE INTO source_audits (
                  target_date, name, url, region, status, total_fetched, today_count,
                  selected_count, error, notes_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_date.isoformat(),
                    audit.name,
                    audit.url,
                    audit.region,
                    audit.status,
                    audit.total_fetched,
                    audit.today_count,
                    audit.selected_count,
                    audit.error,
                    json.dumps(audit.notes, ensure_ascii=False),
                    now,
                ),
            )
