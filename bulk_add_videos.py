"""Bulk-import YouTube videos from a CSV file.

CSV format (with header row):
    url,title,category

Example rows:
    https://youtu.be/dQw4w9WgXcQ,My First Video,Vlogs
    https://www.youtube.com/watch?v=abc1234defg,Tutorial #1,Tutorials
    abc1234defg,Bare ID Example,Gaming

Usage:
    python bulk_add_videos.py videos.csv

    # Dry run (prints what would be inserted without touching the DB):
    python bulk_add_videos.py videos.csv --dry-run
"""
from __future__ import annotations

import argparse
import csv
import re
import sys


def _extract_youtube_id(raw: str) -> str | None:
    raw = raw.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", raw):
        return raw
    m = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", raw)
    return m.group(1) if m else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk-import YouTube videos from CSV.")
    parser.add_argument("csv_file", help="Path to the CSV file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print rows without inserting into the database")
    args = parser.parse_args()

    # Bootstrap the app config so get_conn() works
    from config import Config
    from models.db import init_db, get_conn, ph

    init_db(Config)

    rows = []
    errors = []

    with open(args.csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):   # line 1 is the header
            url   = row.get("url", "").strip()
            title = row.get("title", "").strip()
            cat   = row.get("category", "").strip() or "Uncategorized"

            yt_id = _extract_youtube_id(url)
            if not yt_id:
                errors.append(f"  Line {i}: invalid YouTube URL/ID — '{url}'")
                continue
            if not title:
                errors.append(f"  Line {i}: missing title for '{url}'")
                continue

            rows.append((yt_id, title, cat))

    if errors:
        print("Skipped rows with errors:")
        for e in errors:
            print(e)

    if not rows:
        print("No valid rows to import.")
        return

    if args.dry_run:
        print(f"Dry run — {len(rows)} row(s) would be inserted:")
        for yt_id, title, cat in rows:
            print(f"  [{cat}]  {title}  →  {yt_id}")
        return

    inserted = 0
    skipped  = 0

    with get_conn() as conn:
        cur = conn.cursor()
        # Fetch existing IDs to avoid duplicates
        cur.execute("SELECT youtube_id FROM videos")
        existing = {r[0] for r in cur.fetchall()}

        for yt_id, title, cat in rows:
            if yt_id in existing:
                print(f"  SKIP (already exists): {title}  ({yt_id})")
                skipped += 1
                continue
            cur.execute(
                f"INSERT INTO videos (youtube_id, title, category) VALUES ({ph(3)})",
                (yt_id, title, cat),
            )
            print(f"  ADD: [{cat}]  {title}  ({yt_id})")
            inserted += 1

    print(f"\nDone — {inserted} inserted, {skipped} skipped, {len(errors)} errored.")


if __name__ == "__main__":
    main()
