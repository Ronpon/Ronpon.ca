"""Game logic for Scenes From Your Phone."""
from __future__ import annotations

import base64
import json
import random
import re
import secrets
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from models.db import get_conn, ph
from models import party_games


GAME_KEY = "scenes-from-your-phone"
MODES = {"standard", "jumble", "draw"}
ANSWER_SECONDS = {30, 60, 120}
ROUND_COUNTS = {3, 5, 7}
VOTE_SECONDS = 30
REVEAL_SECONDS_PER_ANSWER = 2.0
MAX_TEXT_LENGTH = 180
MAX_DRAWING_DATA_URL_LENGTH = 320_000
LETTER_COUNT = 30
LETTER_POOL = "EEEEEEEEEEEEAAAAAAAAAIIIIIIIIOOOOOOOUUUUUNNNNNNRRRRRRTTTTTTLLLLSSSSDDGGBCMPFHVWYKJXQZ"

PROMPTS = [
    "Things you shouldn't whisper to a cashier",
    "Things you can say about your dinner but not your date",
    "Things that shouldn't be sticky",
    "Things you don't want your parents to walk in on",
    "Things you can yell during sports or sex",
    "Things you should never say to a pilot",
    "Bad times to make eye contact",
    "Things you don't want vibrating unexpectedly",
    "Things that sound dirty but aren't",
    "Things you regret putting on the internet",
    "Things you shouldn't lick",
    "Things you can say to your barber but not your surgeon",
    "Things you don't want to hear from the person behind you",
    "Weird things to say during a hug",
    "Things you shouldn't bring to a funeral",
    "Things you can say to a pet but not a child",
    "Things that are hard to explain to police",
    "Things that shouldn't smell like fish",
    "Things you shouldn't say while handcuffed",
    "Things you can say in a gym or a bedroom",
    "Things you don't want grandma finding",
    "Things you shouldn't moan loudly in public",
    "Things you shouldn't say while someone is eating a banana",
    "Things that should never be moist",
    "Things you shouldn't ask to borrow",
    "Things you don't want to hear from your doctor during surgery",
    "Things you can say to your phone but not your partner",
    "Things you shouldn't put between your legs",
    "Things you don't want to hear over a loudspeaker",
    "Things you shouldn't scream at church",
    "Things you shouldn't do with whipped cream",
    "Things you don't want your Uber driver to say",
    "Things you shouldn't say while zip ties are involved",
    "Things you shouldn't say while holding a cucumber",
    "Things that should never be unexpectedly warm",
    "Things you shouldn't try to do quietly",
    "Things you shouldn't say while covered in oil",
    "Things that are disappointing at under six inches",
    "Things you shouldn't pull out in class",
    "Things you shouldn't say while someone's filming",
    "Things you can say to a mechanic but not your spouse",
    "Things that shouldn't be leaking",
    "Things you shouldn't yell after midnight",
    "Things that are terrifying to hear from behind a closed door",
    "Things you shouldn't put in your mouth after midnight",
    "Things you shouldn't say while bouncing up and down",
    "Things you shouldn't accidentally send to your boss",
    "Things you don't want to hear from someone wearing gloves",
    "Things you shouldn't say while someone is bent over",
    "Things you shouldn't need batteries for",
]


class ScenesError(ValueError):
    """Raised when a Scenes action is invalid."""


def start_game(code: str, host_token: str, settings: dict[str, Any]) -> None:
    mode = str(settings.get("mode") or "standard").strip().lower()
    if mode not in MODES:
        mode = "standard"

    answer_seconds = _int_choice(settings.get("answer_seconds"), ANSWER_SECONDS, 60)
    rounds = _int_choice(settings.get("rounds"), ROUND_COUNTS, 3)

    with get_conn() as conn:
        cur = conn.cursor()
        room = _select_room(cur, code)
        if not _host_matches(room, host_token):
            raise ScenesError("Host access required.")

        now = _utcnow()
        state = _new_round_state(
            round_number=1,
            rounds=rounds,
            mode=mode,
            answer_seconds=answer_seconds,
            used_prompts=[],
            now=now,
        )
        cur.execute(f"DELETE FROM party_scene_votes WHERE room_id = {ph()}", (room["id"],))
        cur.execute(f"DELETE FROM party_scene_answers WHERE room_id = {ph()}", (room["id"],))
        cur.execute(
            f"UPDATE party_players SET score = {ph()}, is_ready = {ph()} WHERE room_id = {ph()}",
            (0, False, room["id"]),
        )
        _update_room(cur, room["id"], "playing", state, now)


def reset_room(code: str, host_token: str) -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        room = _select_room(cur, code)
        if not _host_matches(room, host_token):
            raise ScenesError("Host access required.")
        cur.execute(f"DELETE FROM party_scene_votes WHERE room_id = {ph()}", (room["id"],))
        cur.execute(f"DELETE FROM party_scene_answers WHERE room_id = {ph()}", (room["id"],))
        cur.execute(
            f"UPDATE party_players SET score = {ph()}, is_ready = {ph()} WHERE room_id = {ph()}",
            (0, False, room["id"]),
        )
        _update_room(cur, room["id"], "lobby", {"round": 0}, _utcnow())


def submit_answer(code: str, player_token: str, payload: dict[str, Any]) -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        room = _select_room(cur, code)
        player = _select_player(cur, room, player_token)
        state = _maybe_advance(cur, room)
        if state.get("phase") != "answer":
            raise ScenesError("Answering is closed.")

        answer_kind, answer_text, answer_image = _answer_payload(state, payload)
        round_number = int(state.get("round") or 1)
        now = _stamp(_utcnow())
        existing = _select_answer(cur, room["id"], round_number, player["id"])
        if existing:
            cur.execute(
                f"""
                UPDATE party_scene_answers
                SET answer_kind = {ph()}, answer_text = {ph()}, answer_image = {ph()}, submitted_at = {ph()}
                WHERE id = {ph()}
                """,
                (answer_kind, answer_text, answer_image, now, existing["id"]),
            )
        else:
            cur.execute(
                f"""
                INSERT INTO party_scene_answers
                    (room_id, round_number, player_id, answer_kind, answer_text, answer_image, submitted_at)
                VALUES ({ph(7)})
                """,
                (room["id"], round_number, player["id"], answer_kind, answer_text, answer_image, now),
            )
        _touch_room(cur, room["id"])
        _maybe_advance(cur, room)


def submit_vote(code: str, player_token: str, answer_player_id: int) -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        room = _select_room(cur, code)
        player = _select_player(cur, room, player_token)
        state = _maybe_advance(cur, room)
        if state.get("phase") != "vote":
            raise ScenesError("Voting is closed.")

        round_number = int(state.get("round") or 1)
        answer = _select_answer(cur, room["id"], round_number, int(answer_player_id))
        if not answer:
            raise ScenesError("That answer is not available.")
        if int(answer["player_id"]) == int(player["id"]):
            raise ScenesError("You cannot vote for your own answer.")

        now = _stamp(_utcnow())
        existing = _select_vote(cur, room["id"], round_number, player["id"])
        if existing:
            cur.execute(
                f"UPDATE party_scene_votes SET answer_player_id = {ph()}, voted_at = {ph()} WHERE id = {ph()}",
                (answer["player_id"], now, existing["id"]),
            )
        else:
            cur.execute(
                f"""
                INSERT INTO party_scene_votes
                    (room_id, round_number, voter_player_id, answer_player_id, voted_at)
                VALUES ({ph(5)})
                """,
                (room["id"], round_number, player["id"], answer["player_id"], now),
            )
        _touch_room(cur, room["id"])
        _maybe_advance(cur, room)


def enrich_snapshot(code: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot["room"].get("game_key") != GAME_KEY:
        return snapshot

    with get_conn() as conn:
        cur = conn.cursor()
        room = _select_room(cur, code)
        if not room:
            return snapshot
        state = _maybe_advance(cur, room)
        room = _select_room(cur, code) or room
        players = _select_players(cur, room["id"])
        current_player_id = (snapshot.get("current_player") or {}).get("id")
        snapshot["players"] = [
            _public_player(player, room["host_token"])
            for player in players
        ]
        snapshot["current_player"] = next(
            (player for player in snapshot["players"] if player["id"] == current_player_id),
            snapshot.get("current_player"),
        )
        snapshot["room"]["state"] = state
        snapshot["game"] = _game_payload(cur, room, state, players, current_player_id)
        return snapshot


def _game_payload(cur, room: dict[str, Any], state: dict[str, Any], players: list[dict[str, Any]], current_player_id: int | None) -> dict[str, Any]:
    phase = state.get("phase") or "lobby"
    round_number = int(state.get("round") or 0)
    answers = _select_answers(cur, room["id"], round_number) if round_number else []
    votes = _select_votes(cur, room["id"], round_number) if round_number else []
    answer_owner_ids = {int(answer["player_id"]) for answer in answers}
    vote_counts = Counter(int(vote["answer_player_id"]) for vote in votes)
    voter_ids = {int(vote["voter_player_id"]) for vote in votes}
    current_answer = current_player_id in answer_owner_ids if current_player_id else False
    current_vote = current_player_id in voter_ids if current_player_id else False
    reveal_step = _reveal_step(state, len(answers))

    return {
        "key": GAME_KEY,
        "phase": phase,
        "round": round_number,
        "rounds": int(state.get("rounds") or 3),
        "mode": state.get("mode") or "standard",
        "answer_seconds": int(state.get("answer_seconds") or 60),
        "vote_seconds": VOTE_SECONDS,
        "prompt": state.get("prompt") or "",
        "letters": state.get("letters") or [],
        "seconds_left": _seconds_left(state),
        "submitted_current": current_answer,
        "voted_current": current_vote,
        "answer_count": len(answers),
        "required_answer_count": len(players),
        "vote_count": len(votes),
        "required_vote_count": _required_vote_count(players, answers),
        "answers": _public_answers(
            answers,
            players,
            vote_counts,
            current_player_id,
            phase,
            reveal_step,
            state.get("reveal_order") or [],
        ),
        "scoreboard": _scoreboard(players),
        "reveal_step": reveal_step,
        "reveal_total": len(answers),
    }


def _maybe_advance(cur, room: dict[str, Any]) -> dict[str, Any]:
    state = _state_from_room(room)
    if room["status"] != "playing" or state.get("phase") not in {"answer", "vote", "reveal"}:
        return state

    now = _utcnow()
    phase = state.get("phase")
    round_number = int(state.get("round") or 1)
    players = _select_players(cur, room["id"])
    answers = _select_answers(cur, room["id"], round_number)

    if phase == "answer":
        time_up = _parse_time(state.get("phase_ends_at")) <= now
        all_done = bool(players) and len(answers) >= len(players)
        if time_up or all_done:
            state = _advance_to_vote(cur, room, state, now)
    elif phase == "vote":
        votes = _select_votes(cur, room["id"], round_number)
        required_votes = _required_vote_count(players, answers)
        time_up = _parse_time(state.get("phase_ends_at")) <= now
        all_done = required_votes == 0 or len(votes) >= required_votes
        if time_up or all_done:
            state = _advance_to_reveal(cur, room, state, answers, votes, now)
    elif phase == "reveal":
        reveal_total = len(answers)
        reveal_seconds = max(3.0, (reveal_total + 1) * REVEAL_SECONDS_PER_ANSWER)
        started = _parse_time(state.get("phase_started_at"))
        if now >= started + timedelta(seconds=reveal_seconds):
            if int(state.get("round") or 1) >= int(state.get("rounds") or 3):
                state = _advance_to_results(cur, room, state, now)
            else:
                state = _advance_to_next_round(cur, room, state, now)

    return state


def _advance_to_vote(cur, room: dict[str, Any], state: dict[str, Any], now: datetime) -> dict[str, Any]:
    state = dict(state)
    state["phase"] = "vote"
    state["phase_started_at"] = _stamp(now)
    state["phase_ends_at"] = _stamp(now + timedelta(seconds=VOTE_SECONDS))
    _update_room(cur, room["id"], "playing", state, now)
    room["state"] = state
    return state


def _advance_to_reveal(
    cur,
    room: dict[str, Any],
    state: dict[str, Any],
    answers: list[dict[str, Any]],
    votes: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    vote_counts = Counter(int(vote["answer_player_id"]) for vote in votes)
    for player_id, score in vote_counts.items():
        cur.execute(
            f"UPDATE party_players SET score = score + {ph()} WHERE room_id = {ph()} AND id = {ph()}",
            (int(score), room["id"], player_id),
        )

    reveal_order = [int(answer["player_id"]) for answer in answers]
    random.shuffle(reveal_order)
    state = dict(state)
    state["phase"] = "reveal"
    state["phase_started_at"] = _stamp(now)
    state["phase_ends_at"] = ""
    state["reveal_order"] = reveal_order
    _update_room(cur, room["id"], "playing", state, now)
    room["state"] = state
    return state


def _advance_to_next_round(cur, room: dict[str, Any], state: dict[str, Any], now: datetime) -> dict[str, Any]:
    state = _new_round_state(
        round_number=int(state.get("round") or 1) + 1,
        rounds=int(state.get("rounds") or 3),
        mode=str(state.get("mode") or "standard"),
        answer_seconds=int(state.get("answer_seconds") or 60),
        used_prompts=list(state.get("used_prompts") or []),
        now=now,
    )
    _update_room(cur, room["id"], "playing", state, now)
    room["state"] = state
    return state


def _advance_to_results(cur, room: dict[str, Any], state: dict[str, Any], now: datetime) -> dict[str, Any]:
    state = dict(state)
    state["phase"] = "results"
    state["phase_started_at"] = _stamp(now)
    state["phase_ends_at"] = ""
    _update_room(cur, room["id"], "playing", state, now)
    room["state"] = state
    return state


def _new_round_state(
    *,
    round_number: int,
    rounds: int,
    mode: str,
    answer_seconds: int,
    used_prompts: list[str],
    now: datetime,
) -> dict[str, Any]:
    prompt = _choose_prompt(used_prompts)
    next_used = [*used_prompts, prompt]
    if len(next_used) >= len(PROMPTS):
        next_used = [prompt]
    return {
        "phase": "answer",
        "round": round_number,
        "rounds": rounds,
        "mode": mode,
        "answer_seconds": answer_seconds,
        "vote_seconds": VOTE_SECONDS,
        "prompt": prompt,
        "used_prompts": next_used,
        "letters": _letters() if mode == "jumble" else [],
        "phase_started_at": _stamp(now),
        "phase_ends_at": _stamp(now + timedelta(seconds=answer_seconds)),
        "reveal_order": [],
    }


def _answer_payload(state: dict[str, Any], payload: dict[str, Any]) -> tuple[str, str, str]:
    mode = state.get("mode") or "standard"
    if mode == "draw":
        image = str(payload.get("answer_image") or "")
        if not _valid_png_data_url(image):
            raise ScenesError("Send a drawing before clicking done.")
        return "draw", "", image

    answer_text = _clean_answer_text(str(payload.get("answer_text") or ""))
    if not answer_text:
        raise ScenesError("Write an answer before clicking done.")
    if mode == "jumble":
        _validate_jumble_answer(answer_text, state.get("letters") or [])
    return "text", answer_text, ""


def _validate_jumble_answer(answer_text: str, letters: list[str]) -> None:
    allowed = Counter(str(letter).upper() for letter in letters)
    used = Counter(char.upper() for char in answer_text if char.isalpha())
    for char, count in used.items():
        if count > allowed.get(char, 0):
            raise ScenesError("That answer uses letters outside the jumble.")


def _clean_answer_text(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned[:MAX_TEXT_LENGTH]


def _valid_png_data_url(value: str) -> bool:
    prefix = "data:image/png;base64,"
    if not value.startswith(prefix) or len(value) > MAX_DRAWING_DATA_URL_LENGTH:
        return False
    try:
        base64.b64decode(value[len(prefix):], validate=True)
    except (ValueError, TypeError):
        return False
    return True


def _public_answers(
    answers: list[dict[str, Any]],
    players: list[dict[str, Any]],
    vote_counts: Counter,
    current_player_id: int | None,
    phase: str,
    reveal_step: int,
    reveal_order: list[int],
) -> list[dict[str, Any]]:
    player_by_id = {int(player["id"]): player for player in players}
    revealed_ids: set[int] = set()
    if phase in {"reveal", "results"}:
        order = [int(player_id) for player_id in reveal_order] or [int(answer["player_id"]) for answer in answers]
        revealed_ids = set(order[:reveal_step]) if phase == "reveal" else set(order)

    visible = []
    for answer in answers:
        player_id = int(answer["player_id"])
        revealed = player_id in revealed_ids
        owner = player_by_id.get(player_id)
        visible.append({
            "answer_id": player_id,
            "kind": answer["answer_kind"],
            "text": answer["answer_text"],
            "image": answer["answer_image"],
            "is_own": current_player_id == player_id,
            "is_revealed": revealed,
            "owner_name": owner["name"] if revealed and owner else "",
            "vote_count": int(vote_counts.get(player_id, 0)) if phase in {"reveal", "results"} else None,
        })
    return visible


def _scoreboard(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(players, key=lambda player: (-int(player["score"]), str(player["joined_at"]), int(player["id"])))
    return [
        {
            "id": int(player["id"]),
            "name": player["name"],
            "score": int(player["score"] or 0),
            "rank": index + 1,
        }
        for index, player in enumerate(ranked)
    ]


def _reveal_step(state: dict[str, Any], total: int) -> int:
    if state.get("phase") == "results":
        return total
    if state.get("phase") != "reveal":
        return 0
    started = _parse_time(state.get("phase_started_at"))
    elapsed = max(0.0, (_utcnow() - started).total_seconds())
    return min(total, int(elapsed // REVEAL_SECONDS_PER_ANSWER) + 1)


def _seconds_left(state: dict[str, Any]) -> int:
    if state.get("phase") not in {"answer", "vote"}:
        return 0
    return max(0, int((_parse_time(state.get("phase_ends_at")) - _utcnow()).total_seconds()))


def _required_vote_count(players: list[dict[str, Any]], answers: list[dict[str, Any]]) -> int:
    answer_owner_ids = {int(answer["player_id"]) for answer in answers}
    return sum(1 for player in players if any(owner_id != int(player["id"]) for owner_id in answer_owner_ids))


def _choose_prompt(used_prompts: list[str]) -> str:
    available = [prompt for prompt in PROMPTS if prompt not in set(used_prompts)]
    return secrets.choice(available or PROMPTS)


def _letters() -> list[str]:
    letters = [secrets.choice(LETTER_POOL) for _ in range(LETTER_COUNT)]
    random.shuffle(letters)
    return letters


def _int_choice(value: Any, choices: set[int], default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed in choices else default


def _select_room(cur, code: str) -> dict[str, Any] | None:
    normalized = party_games.normalize_code(code)
    cur.execute(
        f"""
        SELECT id, code, game_key, status, host_token, state_json, created_at, updated_at
        FROM party_rooms
        WHERE code = {ph()}
        """,
        (normalized,),
    )
    row = cur.fetchone()
    if not row:
        raise ScenesError("Room not found.")
    return {
        "id": _field(row, "id", 0),
        "code": _field(row, "code", 1),
        "game_key": _field(row, "game_key", 2),
        "status": _field(row, "status", 3),
        "host_token": _field(row, "host_token", 4),
        "state": _state_from_raw(_field(row, "state_json", 5)),
    }


def _select_player(cur, room: dict[str, Any], token: str) -> dict[str, Any]:
    cur.execute(
        f"""
        SELECT id, room_id, name, token, is_ready, score, joined_at, last_seen_at
        FROM party_players
        WHERE room_id = {ph()} AND token = {ph()}
        """,
        (room["id"], token),
    )
    row = cur.fetchone()
    if not row:
        raise ScenesError("Player access required.")
    return _player_from_row(row)


def _select_players(cur, room_id: int) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        SELECT id, room_id, name, token, is_ready, score, joined_at, last_seen_at
        FROM party_players
        WHERE room_id = {ph()}
        ORDER BY joined_at, id
        """,
        (room_id,),
    )
    return [_player_from_row(row) for row in cur.fetchall()]


def _select_answer(cur, room_id: int, round_number: int, player_id: int) -> dict[str, Any] | None:
    cur.execute(
        f"""
        SELECT id, room_id, round_number, player_id, answer_kind, answer_text, answer_image, submitted_at
        FROM party_scene_answers
        WHERE room_id = {ph()} AND round_number = {ph()} AND player_id = {ph()}
        """,
        (room_id, round_number, player_id),
    )
    row = cur.fetchone()
    return _answer_from_row(row) if row else None


def _select_answers(cur, room_id: int, round_number: int) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        SELECT id, room_id, round_number, player_id, answer_kind, answer_text, answer_image, submitted_at
        FROM party_scene_answers
        WHERE room_id = {ph()} AND round_number = {ph()}
        ORDER BY submitted_at, id
        """,
        (room_id, round_number),
    )
    return [_answer_from_row(row) for row in cur.fetchall()]


def _select_vote(cur, room_id: int, round_number: int, voter_player_id: int) -> dict[str, Any] | None:
    cur.execute(
        f"""
        SELECT id, room_id, round_number, voter_player_id, answer_player_id, voted_at
        FROM party_scene_votes
        WHERE room_id = {ph()} AND round_number = {ph()} AND voter_player_id = {ph()}
        """,
        (room_id, round_number, voter_player_id),
    )
    row = cur.fetchone()
    return _vote_from_row(row) if row else None


def _select_votes(cur, room_id: int, round_number: int) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        SELECT id, room_id, round_number, voter_player_id, answer_player_id, voted_at
        FROM party_scene_votes
        WHERE room_id = {ph()} AND round_number = {ph()}
        ORDER BY voted_at, id
        """,
        (room_id, round_number),
    )
    return [_vote_from_row(row) for row in cur.fetchall()]


def _update_room(cur, room_id: int, status: str, state: dict[str, Any], now: datetime) -> None:
    cur.execute(
        f"""
        UPDATE party_rooms
        SET status = {ph()}, state_json = {ph()}, updated_at = {ph()}
        WHERE id = {ph()}
        """,
        (status, json.dumps(state), _stamp(now), room_id),
    )


def _touch_room(cur, room_id: int) -> None:
    cur.execute(
        f"UPDATE party_rooms SET updated_at = {ph()} WHERE id = {ph()}",
        (_stamp(_utcnow()), room_id),
    )


def _host_matches(room: dict[str, Any] | None, host_token: str | None) -> bool:
    return bool(room and host_token and secrets.compare_digest(host_token, room["host_token"]))


def _state_from_room(room: dict[str, Any]) -> dict[str, Any]:
    return dict(room.get("state") or {})


def _state_from_raw(raw_state: Any) -> dict[str, Any]:
    try:
        state = json.loads(raw_state or "{}")
    except (TypeError, json.JSONDecodeError):
        state = {}
    return state if isinstance(state, dict) else {}


def _player_from_row(row) -> dict[str, Any]:
    return {
        "id": int(_field(row, "id", 0)),
        "room_id": int(_field(row, "room_id", 1)),
        "name": _field(row, "name", 2),
        "token": _field(row, "token", 3),
        "is_ready": bool(_field(row, "is_ready", 4)),
        "score": int(_field(row, "score", 5) or 0),
        "joined_at": _field(row, "joined_at", 6),
        "last_seen_at": _field(row, "last_seen_at", 7),
    }


def _answer_from_row(row) -> dict[str, Any]:
    return {
        "id": int(_field(row, "id", 0)),
        "room_id": int(_field(row, "room_id", 1)),
        "round_number": int(_field(row, "round_number", 2)),
        "player_id": int(_field(row, "player_id", 3)),
        "answer_kind": _field(row, "answer_kind", 4),
        "answer_text": _field(row, "answer_text", 5),
        "answer_image": _field(row, "answer_image", 6),
        "submitted_at": _field(row, "submitted_at", 7),
    }


def _vote_from_row(row) -> dict[str, Any]:
    return {
        "id": int(_field(row, "id", 0)),
        "room_id": int(_field(row, "room_id", 1)),
        "round_number": int(_field(row, "round_number", 2)),
        "voter_player_id": int(_field(row, "voter_player_id", 3)),
        "answer_player_id": int(_field(row, "answer_player_id", 4)),
        "voted_at": _field(row, "voted_at", 5),
    }


def _public_player(player: dict[str, Any], host_token: str) -> dict[str, Any]:
    return {
        "id": player["id"],
        "name": player["name"],
        "is_ready": player["is_ready"],
        "score": player["score"],
        "is_connected": _is_recent(player["last_seen_at"]),
        "is_host_player": secrets.compare_digest(player["token"], host_token),
    }


def _is_recent(value: Any) -> bool:
    seen_at = _parse_time(value)
    return _utcnow() - seen_at <= timedelta(seconds=45)


def _parse_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            dt = _utcnow()
    else:
        dt = _utcnow()
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _field(row, key: str, index: int):
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return row[index]
