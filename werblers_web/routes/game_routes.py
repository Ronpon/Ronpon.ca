"""Game setup and turn-flow API routes (new game, state, movement, offers)."""
from __future__ import annotations

import uuid
from typing import Optional

from flask import Blueprint, jsonify, request, session

from werblers_engine.game import Game
from werblers_engine.heroes import HEROES, HeroId
from werblers_engine import effects as _fx
from werblers_web.serializers import (
    CARD_IMG_MAP as _CARD_IMG_MAP,
    HERO_ANIM_MAP as _HERO_ANIM_MAP,
    tile_level as _tile_level,
    item_card_image_from_dict as _item_card_image_from_dict,
    consumable_card_image as _consumable_card_image,
    item_to_dict_from_obj as _item_to_dict_from_obj,
)
from werblers_web.routes.helpers import _sessions, _get_state, _enrich_combat_info, _build_state

game_bp = Blueprint("game", __name__)


@game_bp.route("/api/heroes")
def api_heroes():
    result = []
    for hero_id, hero in HEROES.items():
        result.append({
            "id":          hero_id.name,
            "name":        hero.name,
            "title":       hero.title,
            "description": hero.description,
            "card_image":  _CARD_IMG_MAP.get(hero_id.name, ""),
            "animations":  _HERO_ANIM_MAP.get(hero_id.name, {}),
        })
    return jsonify(result)


@game_bp.route("/api/new_game", methods=["POST"])
def api_new_game():
    data: dict = request.get_json(force=True) or {}
    hero_id_strs: list[str] = data.get("hero_ids", [])
    num_players: int = len(hero_id_strs) if hero_id_strs else data.get("num_players", 1)
    seed: Optional[int] = data.get("seed", None)
    hero_ids = [HeroId[h] for h in hero_id_strs] if hero_id_strs else None
    game = Game(num_players=num_players, hero_ids=hero_ids, seed=seed)
    for p in game.players:
        game.draw_movement_cards(p)
    sid = str(uuid.uuid4())
    session["game_id"] = sid
    _sessions[sid] = {"game": game, "last_log": ["New game started!"], "pending_log": []}
    return jsonify({"ok": True, "state": _build_state()})


@game_bp.route("/api/state")
def api_state():
    if _get_state()["game"] is None:
        return jsonify({"error": "No game in progress"}), 400
    return jsonify(_build_state())


@game_bp.route("/api/get_abilities")
def api_get_abilities():
    """Return available 'you may' abilities for the current player."""
    _game = _get_state()["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    abilities = _game.get_available_abilities()
    return jsonify({"abilities": abilities})


@game_bp.route("/api/begin_move", methods=["POST"])
def api_begin_move():
    """Phase 1: play a movement card, reveal tile, pause if chest/shop."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    # Guard: reject if there's already an unresolved pending state
    if _game._pending_offer is not None:
        return jsonify({"error": "Resolve the current offer first"}), 409
    if _game._pending_combat is not None:
        return jsonify({"error": "Resolve the current combat first"}), 409
    data: dict = request.get_json(force=True) or {}
    card_index: int = int(data.get("card_index", 0))
    flee: bool = bool(data.get("flee", False))
    activated: dict = data.get("activated", {})
    direction: str = data.get("direction", "forward")
    result = _game.begin_move(card_index=card_index, flee=flee, activated=activated, direction=direction)
    log = result.get("log", [])
    moved_to = result.get("moved_to")
    tile_type = result.get("tile_type", "")
    bg_map = {1: "Backgrounds/Forest Background.png", 2: "Backgrounds/Cave Background.png", 3: "Backgrounds/Dungeon Background.png"}
    background = bg_map.get(_tile_level(moved_to) if moved_to else 1, bg_map[1])
    tile_scene = {"tile_type": tile_type, "background": background, "moved_to": moved_to}
    if result["phase"] in ("done", "combat"):
        _st["pending_log"] = []
        _st["last_log"] = log
        combat_info = result.get("combat_info")
        if combat_info:
            combat_info = _enrich_combat_info(combat_info)
        return jsonify({"phase": result["phase"], "state": _build_state(), "combat_info": combat_info, "tile_scene": tile_scene})
    elif result["phase"] == "charlie_work":
        _st["pending_log"] = log
        _st["last_log"] = log
        return jsonify({
            "phase":      "charlie_work",
            "level":      result.get("level", 1),
            "state":      _build_state(),
            "tile_scene": tile_scene,
            "log":        log,
        })
    elif result["phase"] == "mystery":
        _st["pending_log"] = log
        _st["last_log"] = log
        me = result.get("mystery_event", {})
        img_name = me.get('image_name') or me['name']
        me["image"] = f"Events/{img_name} Tier {me['tier']}.png"
        return jsonify({
            "phase":         "mystery",
            "mystery_event": me,
            "state":         _build_state(),
            "tile_scene":    tile_scene,
        })
    else:
        _st["pending_log"] = log
        _st["last_log"] = log
        raw_offer = result["offer"]
        enriched_items = [
            {**item, "card_image": _item_card_image_from_dict(item)}
            for item in raw_offer.get("items", [])
        ]
        offer = {**raw_offer, "items": enriched_items}
        # Check if scavenger trait allows swapping the chest item
        has_scavenger = result["phase"] == "offer_chest" and any(
            t.effect_id == "scavenger" for t in _game.current_player.traits
        )
        offer["has_scavenger"] = has_scavenger
        return jsonify({
            "phase":      result["phase"],
            "offer":      offer,
            "state":      _build_state(),
            "tile_scene": tile_scene,
        })


@game_bp.route("/api/resolve_charlie_work", methods=["POST"])
def api_resolve_charlie_work():
    """Resolve the No More Charlie Work decision (phase == 'charlie_work')."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    use_it: bool = bool(data.get("use_it", False))
    result = _game.resolve_charlie_work(use_it=use_it)
    log = _st["pending_log"] + result.get("log", [])
    _st["pending_log"] = []
    _st["last_log"] = log
    combat_info = result.get("combat_info")
    if combat_info:
        combat_info = _enrich_combat_info(combat_info)
    return jsonify({"phase": result["phase"], "state": _build_state(), "combat_info": combat_info})


@game_bp.route("/api/resolve_offer", methods=["POST"])
def api_resolve_offer():
    """Phase 2: apply player item choices, complete the turn."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    choices: dict = request.get_json(force=True) or {}
    result = _game.resolve_offer(choices=choices)
    combined_log = _st["pending_log"] + result.get("log", [])
    _st["pending_log"] = combined_log
    _st["last_log"] = combined_log
    if result.get("phase") == "rake_it_in":
        equips = [
            {**e, "card_image": _item_card_image_from_dict(e)}
            for e in result.get("equips", [])
        ]
        pack_items = [
            {**i, "card_image": _item_card_image_from_dict(i)}
            for i in result.get("pack_items", [])
        ]
        consumable_items = [
            {**i, "card_image": _consumable_card_image(i.get("name", ""))}
            for i in result.get("consumable_items", [])
        ]
        shop_remaining = [
            {**i, "card_image": _item_card_image_from_dict(i)}
            for i in result.get("shop_remaining", [])
        ]
        return jsonify({
            "phase": "rake_it_in",
            "sub_type": result.get("sub_type", "chest"),
            "equips": equips,
            "pack_items": pack_items,
            "consumable_items": consumable_items,
            "shop_remaining": shop_remaining,
            "state": _build_state(),
            "log": combined_log,
        })
    _st["pending_log"] = []
    return jsonify({"phase": "done", "state": _build_state()})


@game_bp.route("/api/resolve_rake_it_in", methods=["POST"])
def api_resolve_rake_it_in():
    """Resolve the Rake It In decision (phase == 'rake_it_in')."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    use_it = bool(data.get("use_it", False))
    discard_slot = str(data.get("discard_slot", ""))
    discard_idx  = int(data.get("discard_idx", 0))
    second_item_choice = int(data.get("second_item_choice", -1))
    placement_choices = {k: data[k] for k in ("placement", "equip_action", "equip_item_index") if k in data}
    result = _game.resolve_rake_it_in(
        use_it=use_it,
        discard_slot=discard_slot,
        discard_idx=discard_idx,
        second_item_choice=second_item_choice,
        placement_choices=placement_choices,
    )
    combined_log = _st["pending_log"] + result.get("log", [])
    _st["pending_log"] = []
    _st["last_log"] = combined_log
    bonus = result.get("bonus_item")
    if bonus:
        bonus["card_image"] = _item_card_image_from_dict(bonus)
    return jsonify({"phase": "done", "state": _build_state(), "bonus_item": bonus})


@game_bp.route("/api/place_trait_item", methods=["POST"])
def api_place_trait_item():
    """Place a pending trait item (received from a trait like Ball and Chain)."""
    _game = _get_state()["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    target_pid = data.get("player_id")
    if target_pid is not None:
        player = next((p for p in _game.players if p.player_id == target_pid), None)
        if player is None:
            return jsonify({"error": "Unknown player_id"}), 400
    else:
        player = _game.current_player
    if not player.pending_trait_items:
        return jsonify({"error": "No pending trait items"}), 400
    item = player.pending_trait_items.pop(0)
    choices = data.get("placement_choices", {})
    log: list[str] = []
    if choices.get("discard"):
        log.append(f"  {item.name} discarded.")
    else:
        _game._apply_item_to_player(player, item, choices, log)
    _fx.refresh_tokens(player)
    if _game._rakeitin_pending_placement and not player.pending_trait_items:
        _game._rakeitin_pending_placement = False
        _game._advance_turn()
    return jsonify({"ok": True, "state": _build_state(), "log": log})


@game_bp.route("/api/resolve_minion", methods=["POST"])
def api_resolve_minion():
    """Replace an existing minion with a pending one, or discard the pending minion."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    player_id: int = int(data.get("player_id", _game.current_player.player_id))
    replace_index: int = int(data.get("replace_index", -1))
    discard: bool = bool(data.get("discard", False))

    player = next((p for p in _game.players if p.player_id == player_id), None)
    if player is None:
        return jsonify({"error": "Player not found"}), 400
    if not player.pending_trait_minions:
        return jsonify({"error": "No pending minions"}), 400

    minion = player.pending_trait_minions.pop(0)
    log: list[str] = []
    if discard:
        log.append(f"  {minion.name} discarded (minion slots full).")
    elif 0 <= replace_index < len(player.minions):
        old = player.minions[replace_index]
        player.minions[replace_index] = minion
        from werblers_engine import effects as _fx_mod
        _fx_mod.on_minion_gained(player, minion, log)
        log.append(f"  {old.name} replaced by {minion.name}.")
    else:
        if not player.add_minion(minion):
            player.pending_trait_minions.insert(0, minion)
            return jsonify({"error": "Invalid replace_index and at minion cap"}), 400
        from werblers_engine import effects as _fx_mod
        _fx_mod.on_minion_gained(player, minion, log)
        log.append(f"  {minion.name} added to minions.")

    _st["last_log"] = log
    return jsonify({"ok": True, "state": _build_state()})


@game_bp.route("/api/play_turn", methods=["POST"])
def api_play_turn():
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    card_index: int = int(data.get("card_index", 0))
    flee: bool = bool(data.get("flee", False))
    shop_choice: int = int(data.get("shop_choice", 0))
    result = _game.play_turn(card_index=card_index, flee=flee, shop_choice=shop_choice)
    _st["last_log"] = result.encounter_log
    return jsonify({"ok": True, "state": _build_state()})
