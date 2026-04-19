"""Videos section routes."""
from __future__ import annotations

import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from models.db import get_conn, ph

videos_bp = Blueprint("videos", __name__)


def _extract_youtube_id(url_or_id: str) -> str | None:
    """Pull the 11-char video ID from a YouTube URL (or pass through a bare ID)."""
    url_or_id = url_or_id.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    m = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", url_or_id)
    return m.group(1) if m else None


@videos_bp.route("/")
def index():
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute("SELECT DISTINCT category FROM videos ORDER BY category")
        categories = [row[0] for row in cur.fetchall()]

        cur.execute("SELECT id, youtube_id, title, category FROM videos ORDER BY category, added_at DESC")
        all_videos = cur.fetchall()

    # Group videos by category
    grouped = {}
    for v in all_videos:
        cat = v[3] if not hasattr(v, 'keys') else v['category']
        grouped.setdefault(cat, []).append(v)

    return render_template(
        "videos/index.html",
        grouped=grouped,
        categories=categories,
    )


@videos_bp.route("/add", methods=["GET", "POST"])
def add():
    if not (current_user.is_authenticated and current_user.is_admin):
        flash("Admin access required.", "error")
        return redirect(url_for("videos.index"))

    if request.method == "POST":
        raw_url = request.form.get("youtube_url", "")
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip() or "Uncategorized"

        yt_id = _extract_youtube_id(raw_url)
        if not yt_id:
            flash("Invalid YouTube URL or video ID.", "error")
            return redirect(url_for("videos.add"))
        if not title:
            flash("Title is required.", "error")
            return redirect(url_for("videos.add"))

        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO videos (youtube_id, title, category) VALUES ({ph(3)})",
                (yt_id, title, category),
            )
        flash("Video added!", "success")
        return redirect(url_for("videos.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM videos ORDER BY category")
        categories = [row[0] for row in cur.fetchall()]

    return render_template("videos/add.html", categories=categories)


@videos_bp.route("/delete/<int:video_id>", methods=["POST"])
def delete(video_id):
    if not (current_user.is_authenticated and current_user.is_admin):
        flash("Admin access required.", "error")
        return redirect(url_for("videos.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM videos WHERE id = {ph()}", (video_id,))

    flash("Video removed.", "success")
    return redirect(url_for("videos.index"))
