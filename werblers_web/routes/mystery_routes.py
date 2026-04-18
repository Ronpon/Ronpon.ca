"""Mystery event API routes (mystery box, wheel, smith, fairy king, beggar)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from werblers_engine import content as C
from werblers_web.serializers import (
    item_card_image as _item_card_image,
    monster_card_image as _monster_card_image,
    item_to_dict_from_obj as _item_to_dict_from_obj,
)
from werblers_web.routes.helpers import _get_state, _build_state

mystery_bp = Blueprint("mystery", __name__)


@mystery_bp.route("/api/resolve_mystery", methods=["POST"])
def api_resolve_mystery():
    """Resolve a pending mystery event.

    JSON body:
        action: str —  "open" | "spin" | "smith" | "accept" | "give" | "skip"
        wager_index:   int  (pack slot for mystery_box / fairy_king give)
        smith_indices:  list[int]  (3 pack slot indices for the smith trade)
        smith_equip_index: int  (equipped item index for tier-3 smith enhancement)
    """
    import traceback as _tb
    try:
        return _api_resolve_mystery_inner()
    except Exception as exc:
        tb = _tb.format_exc()
        _tb.print_exc()
        return jsonify({"error": f"Server error in resolve_mystery: {exc}\n\nTraceback:\n{tb}"}), 500


def _api_resolve_mystery_inner():
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    po = _game._pending_offer
    if po is None or po.get("type") != "mystery":
        return jsonify({"error": "No pending mystery event"}), 400

    data: dict = request.get_json(force=True) or {}
    event = po["event"]
    player = _game.current_player
    level = po["level"]
    log: list[str] = po.get("log", _st["pending_log"] or [])

    from werblers_engine import mystery as _mys

    result: dict = {}
    event_id = event.event_id
    tier = event.tier

    # Handle skip/decline — finish the turn without resolving the event
    action = data.get("action", "")
    if action == "skip":
        log.append(f"Declined the {event.name} event.")
        _game._pending_offer = None
        _game._finish_post_encounter(player, log)
        _game._advance_turn()
        _st["pending_log"] = []
        _st["last_log"] = log
        return jsonify({
            "phase": "done",
            "prize_type": "skip",
            "mystery_result": "Declined",
            "state": _build_state(),
        })

    if event_id == "mystery_box":
        wager_idx = int(data.get("wager_index", -1))
        result = _mys.resolve_mystery_box(
            player, tier, wager_idx,
            _game.item_decks, _game.monster_decks, _game.trait_deck,
            log,
        )

    elif event_id == "the_wheel":
        result = _mys.resolve_the_wheel(
            player, tier,
            _game.item_decks, _game.monster_decks, _game.trait_deck,
            log,
        )

    elif event_id == "the_smith":
        smith_indices = data.get("smith_indices", [])
        smith_equip_idx = int(data.get("smith_equip_index", -1))
        result = _mys.resolve_the_smith(
            player, tier, _game.item_decks,
            smith_indices, smith_equip_idx, log,
        )

    elif event_id == "bandits":
        result = _mys.resolve_bandits(player, log)

    elif event_id == "thief":
        result = _mys.resolve_thief(player, log)

    elif event_id == "beggar":
        give_idx = int(data.get("wager_index", -1))
        result = _mys.resolve_beggar(
            player, tier, _game.item_decks, give_idx, log,
        )

    else:
        log.append(f"Unknown mystery event: {event_id}")
        result = {"prize_type": "nothing", "label": "Unknown event"}

    # If the prize is an item, set up a pending offer for placement
    if result.get("prize_type") == "item" and result.get("item"):
        item = result["item"]
        _game._pending_offer = {
            "type": "chest",
            "level": level,
            "items": [item],
            "moved_from": po["moved_from"], "moved_to": po["moved_to"],
            "card_played": po["card_played"], "tile_type": po["tile_type"],
            "from_mystery": True,
        }
        _st["last_log"] = log
        _st["pending_log"] = log
        return jsonify({
            "phase": "offer_chest",
            "event_id": event_id,
            "prize_type": result.get("prize_type", ""),
            "mystery_result": result.get("label", ""),
            "state": _build_state(),
            "offer": {"items": [_item_to_dict_from_obj(item)]},
        })

    # Fairy King reveal: keep pending offer alive so player can choose a T3 reward
    if result.get("prize_type") == "fairy_king_reveal":
        reward_items = result.get("reward_items", [])
        _game._pending_offer = {
            "type": "fairy_king_reward",
            "reward_items": reward_items,
            "moved_from": po["moved_from"], "moved_to": po["moved_to"],
            "card_played": po["card_played"], "tile_type": po["tile_type"],
            "log": log,
        }
        _st["last_log"] = log
        _st["pending_log"] = log
        return jsonify({
            "phase": "fairy_king_reveal",
            "mystery_result": result.get("label", ""),
            "state": _build_state(),
            "reward_items": [_item_to_dict_from_obj(i) for i in reward_items],
        })

    # Beggar accepted a gift (not the 3rd) — finish turn but signal UI
    if result.get("prize_type") == "beggar_thank":
        _game._pending_offer = None
        _game._finish_post_encounter(player, log)
        _game._advance_turn()
        _st["pending_log"] = []
        _st["last_log"] = log
        return jsonify({
            "phase": "beggar_thank",
            "event_id": event_id,
            "prize_type": "beggar_thank",
            "mystery_result": result.get("label", ""),
            "state": _build_state(),
        })

    # Error results — Don't finish the turn; let the player retry
    if result.get("prize_type") == "error":
        _st["last_log"] = log
        return jsonify({"error": "Invalid selection — please try again.", "state": _build_state()}), 400

    # Otherwise (nothing, skip, trait, smith_enhance, gift_accepted, stolen)
    # — finish the turn
    _game._pending_offer = None
    _game._finish_post_encounter(player, log)
    _game._advance_turn()
    _st["pending_log"] = []
    _st["last_log"] = log

    # Build rich outcome payload so the frontend can display a proper outcome screen
    outcome: dict = {
        "phase": "done",
        "mystery_result": result.get("label", ""),
        "prize_type": result.get("prize_type", "nothing"),
        "event_id": event_id,
        "state": _build_state(),
    }
    if result.get("item_name"):
        outcome["item_name"] = result["item_name"]
    if result.get("item"):
        outcome["card_image"] = _item_card_image(result["item"])
    if result.get("items"):
        outcome["stolen_items"] = result["items"]
    if result.get("trait") and hasattr(result["trait"], "name"):
        outcome["trait_name"] = result["trait"].name
        outcome["trait_description"] = C.TRAIT_DESCRIPTIONS.get(result["trait"].name, "")
    if result.get("curse_name"):
        outcome["curse_name"] = result["curse_name"]
        outcome["curse_description"] = C.CURSE_DESCRIPTIONS.get(result["curse_name"], "")
    if result.get("monster_name") and result.get("prize_type") == "curse":
        outcome["monster_name"] = result["monster_name"]
        outcome["card_image"] = _monster_card_image(result["monster_name"])
    return jsonify(outcome)


@mystery_bp.route("/api/resolve_fairy_king_reward", methods=["POST"])
def api_resolve_fairy_king_reward():
    """Player chooses one of the 3 T3 items offered by the Fairy King."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    po = _game._pending_offer
    if po is None or po.get("type") != "fairy_king_reward":
        return jsonify({"error": "No pending Fairy King reward"}), 400

    data: dict = request.get_json(force=True) or {}
    choice = int(data.get("choice_index", -1))
    reward_items = po["reward_items"]
    if choice < 0 or choice >= len(reward_items):
        return jsonify({"error": "Invalid choice"}), 400

    player = _game.current_player
    chosen = reward_items[choice]
    log: list[str] = po.get("log", _st["pending_log"] or [])

    _game._pending_offer = {
        "type": "chest",
        "level": 3,
        "items": [chosen],
        "moved_from": po["moved_from"], "moved_to": po["moved_to"],
        "card_played": po["card_played"], "tile_type": po["tile_type"],
    }
    log.append(f"The Fairy King bestows: {chosen.name}!")
    _st["last_log"] = log
    _st["pending_log"] = log
    return jsonify({
        "phase": "offer_chest",
        "mystery_result": f"Fairy King reward: {chosen.name}",
        "state": _build_state(),
        "offer": {"items": [_item_to_dict_from_obj(chosen)]},
    })
