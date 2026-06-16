"""Videos section routes."""
from __future__ import annotations

import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from models.db import get_conn, ph

videos_bp = Blueprint("videos", __name__)
_MAX_VIDEO_TITLE_LENGTH = 120
_MAX_CATEGORY_LENGTH = 60
_VIDEO_SORTS = {
    "newest": "DESC",
    "oldest": "ASC",
}


def _extract_youtube_id(url_or_id: str) -> str | None:
    """Pull the 11-char video ID from a YouTube URL (or pass through a bare ID)."""
    url_or_id = url_or_id.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    m = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", url_or_id)
    return m.group(1) if m else None


def _is_admin() -> bool:
    return current_user.is_authenticated and current_user.is_admin


def _ensure_video_playlists(cur) -> list[str]:
    cur.execute("SELECT DISTINCT category FROM videos ORDER BY category")
    categories = [row[0] for row in cur.fetchall()]

    cur.execute("SELECT name FROM video_playlists")
    existing = {row[0] for row in cur.fetchall()}

    cur.execute("SELECT COALESCE(MAX(sort_order), -1) FROM video_playlists")
    max_order = cur.fetchone()[0]

    for category in categories:
        if category in existing:
            continue
        max_order += 1
        cur.execute(
            f"INSERT INTO video_playlists (name, sort_order) VALUES ({ph(2)})",
            (category, max_order),
        )
    return categories


def _ordered_video_categories(cur) -> list[str]:
    _ensure_video_playlists(cur)
    cur.execute(
        """
        SELECT name
        FROM video_playlists
        WHERE EXISTS (
            SELECT 1
            FROM videos
            WHERE videos.category = video_playlists.name
        )
        ORDER BY sort_order, LOWER(name)
        """
    )
    return [row[0] for row in cur.fetchall()]


@videos_bp.route("/")
def index():
    current_sort = request.args.get("sort", "newest")
    if current_sort not in _VIDEO_SORTS:
        current_sort = "newest"
    direction = _VIDEO_SORTS[current_sort]

    with get_conn() as conn:
        cur = conn.cursor()
        categories = _ordered_video_categories(cur)
        cur.execute(
            f"SELECT id, youtube_id, title, category, added_at "
            f"FROM videos ORDER BY added_at {direction}, id {direction}"
        )
        all_videos = cur.fetchall()

    grouped = {category: [] for category in categories}
    for video in all_videos:
        category = video[3] if not hasattr(video, "keys") else video["category"]
        grouped.setdefault(category, []).append(video)

    return render_template(
        "videos/index.html",
        grouped=grouped,
        categories=categories,
        current_sort=current_sort,
    )


@videos_bp.route("/add", methods=["GET", "POST"])
def add():
    if not _is_admin():
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
        if len(title) > _MAX_VIDEO_TITLE_LENGTH:
            flash("Title is too long.", "error")
            return redirect(url_for("videos.add"))
        if len(category) > _MAX_CATEGORY_LENGTH:
            flash("Category is too long.", "error")
            return redirect(url_for("videos.add"))

        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO videos (youtube_id, title, category) VALUES ({ph(3)})",
                (yt_id, title, category),
            )
            _ensure_video_playlists(cur)
        flash("Video added!", "success")
        return redirect(url_for("videos.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        categories = _ordered_video_categories(cur)

    return render_template("videos/add.html", categories=categories)


@videos_bp.route("/delete/<int:video_id>", methods=["POST"])
def delete(video_id):
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("videos.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM videos WHERE id = {ph()}", (video_id,))

    flash("Video removed.", "success")
    return redirect(url_for("videos.index"))


@videos_bp.route("/playlists/reorder", methods=["POST"])
def reorder_playlists():
    if not _is_admin():
        return jsonify({"ok": False, "error": "Admin access required."}), 403

    payload = request.get_json(silent=True) or {}
    incoming_categories = payload.get("categories")
    if not isinstance(incoming_categories, list):
        return jsonify({"ok": False, "error": "Expected a playlist order."}), 400

    categories = []
    seen = set()
    for value in incoming_categories:
        if not isinstance(value, str):
            return jsonify({"ok": False, "error": "Invalid playlist order."}), 400
        category = value.strip()
        if not category or len(category) > _MAX_CATEGORY_LENGTH or category in seen:
            return jsonify({"ok": False, "error": "Invalid playlist order."}), 400
        categories.append(category)
        seen.add(category)

    with get_conn() as conn:
        cur = conn.cursor()
        existing_categories = _ordered_video_categories(cur)
        if set(categories) != set(existing_categories):
            return jsonify({
                "ok": False,
                "error": "Playlist list changed. Reload and try again.",
            }), 400

        for position, category in enumerate(categories):
            cur.execute(
                f"UPDATE video_playlists SET sort_order = {ph()} WHERE name = {ph()}",
                (position, category),
            )

    return jsonify({"ok": True})
