"""Inventory management API routes (equip, manage, discard items)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from werblers_engine import effects as _fx
from werblers_web.serializers import (
    item_card_image as _item_card_image,
    item_to_dict_from_obj as _item_to_dict_from_obj,
    ser_item as _ser_item,
)
from werblers_web.routes.helpers import _get_state, _build_state

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/api/equip_from_pack", methods=["POST"])
def api_equip_from_pack():
    """Move an item from pack to an equipment slot.

    Optional flags:
      ``force``   -- discard the displaced item when no free slot available.
      ``to_pack`` -- move the displaced item to the pack instead of discarding.
      ``displaced_actions`` -- list of dicts with {action: 'discard'|'to_pack', discard_pack_index: int} for each displaced item.
    """
    _game = _get_state()["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    pack_index = int(data.get("pack_index", 0))
    force   = bool(data.get("force",   False))
    to_pack = bool(data.get("to_pack", False))
    discard_pack_index = int(data.get("discard_pack_index", -1))
    to_pack_index = int(data.get("to_pack_index", -1))
    equip_displaced = bool(data.get("equip_displaced", False))
    displaced_actions = data.get("displaced_actions", None)
    player = _game.current_player
    if pack_index < 0 or pack_index >= len(player.pack):
        return jsonify({"error": "Invalid pack index"}), 400
    item = player.pack[pack_index]
    if not player.can_equip(item):
        # --- Weapon slot: compute how many weapons must be displaced ---
        if item.slot.value == "weapon":
            hands_used = sum(w.hands for w in player.weapons)
            hands_free = player.weapon_hands - hands_used
            hands_to_free = item.hands - hands_free

            items_to_displace = []
            freed = 0
            for w in list(player.weapons):
                if freed >= hands_to_free:
                    break
                items_to_displace.append(w)
                freed += w.hands

            if len(items_to_displace) > 1:
                if displaced_actions is None:
                    displaced_data = [{
                        "name": w.name,
                        "card_image": _item_card_image(w),
                        "hands": w.hands,
                        "strength_bonus": w.strength_bonus,
                    } for w in items_to_displace]
                    return jsonify({
                        "error": "multi_displace",
                        "displaced_items": displaced_data,
                        "pack_slots_free": player.pack_slots_free + 1,
                    })
                else:
                    try:
                        pi = player.pack.index(item)
                    except ValueError:
                        pi = pack_index
                    player.pack.pop(pi)

                    for i, w in enumerate(items_to_displace):
                        da = displaced_actions[i] if i < len(displaced_actions) else {"action": "discard"}
                        if da.get("action") == "to_pack":
                            dpi = int(da.get("discard_pack_index", -1))
                            if player.pack_slots_free <= 0:
                                if dpi >= 0:
                                    player.evict_pack_slot(dpi)
                                else:
                                    player.unequip(w)
                                    continue
                            player.unequip(w)
                            player.pack.append(w)
                        else:  # discard
                            player.unequip(w)
                    player.equip(item)
                    _fx.refresh_tokens(player)
                    return jsonify({"ok": True, "state": _build_state()})

        # --- Single-displacement path (non-weapon slots, or single-weapon swap) ---
        if force or to_pack:
            slot_map = {
                "helmet": player.helmets,
                "chest":  player.chest_armor,
                "legs":   player.leg_armor,
                "weapon": player.weapons,
            }
            existing_list = slot_map.get(item.slot.value, [])
            if existing_list:
                displaced = existing_list[0]
                if to_pack:
                    if player.pack_slots_used - 1 >= player.pack_size:
                        if discard_pack_index >= 0:
                            evicted_pack_item = player.pack[discard_pack_index] if equip_displaced else None
                            player.evict_pack_slot(discard_pack_index)
                        else:
                            pack_data = [{"name": p.name, "card_image": _item_card_image(p),
                                          "is_consumable": p.slot.value == "consumable"} for p in player.pack]
                            return jsonify({"error": "pack_full", "pack": pack_data,
                                            "displaced_name": displaced.name})
                    else:
                        evicted_pack_item = None
                    player.unequip(displaced)
                    try:
                        pi = player.pack.index(item)
                    except ValueError:
                        pi = pack_index
                    player.pack.pop(pi)
                    insert_pos = to_pack_index if (to_pack_index >= 0 and to_pack_index <= len(player.pack)) else min(pi, len(player.pack))
                    player.pack.insert(insert_pos, displaced)
                    player.equip(item)
                    if equip_displaced and evicted_pack_item is not None:
                        if player.can_equip(evicted_pack_item):
                            player.equip(evicted_pack_item)
                        else:
                            player.pack.append(evicted_pack_item)
                    _fx.refresh_tokens(player)
                    return jsonify({"ok": True, "state": _build_state()})
                else:
                    player.unequip(displaced)
        if not player.can_equip(item):
            return jsonify({"error": f"Cannot equip {item.name} \u2014 no free slot"}), 400
    player.pack.pop(pack_index)
    player.equip(item)
    return jsonify({"ok": True, "state": _build_state()})


@inventory_bp.route("/api/manage_item", methods=["POST"])
def api_manage_item():
    """Discard or move-to-pack an equipped or packed item from the player sheet.

    JSON body:
        action  : "discard" | "to_pack" | "to_equip"
        source  : "equip_helmet" | "equip_chest" | "equip_leg" | "equip_weapon" | "pack"
        index   : integer index within that slot list
    """
    _game = _get_state()["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    action = data.get("action", "")
    source = data.get("source", "")
    idx    = int(data.get("index", 0))
    player = _game.current_player

    slot_map = {
        "equip_helmet": player.helmets,
        "equip_chest":  player.chest_armor,
        "equip_leg":    player.leg_armor,
        "equip_weapon": player.weapons,
        "pack":         player.pack,
    }
    item_list = slot_map.get(source)
    if item_list is None:
        return jsonify({"error": f"Unknown source: {source}"}), 400
    if idx < 0 or idx >= len(item_list):
        return jsonify({"error": "Index out of range"}), 400

    item = item_list[idx]

    if action == "discard":
        if source == "pack":
            player.pack.pop(idx)
        else:
            player.unequip(item)
        _fx.refresh_tokens(player)
        return jsonify({"ok": True, "state": _build_state()})

    if action == "to_pack":
        if source == "pack":
            return jsonify({"error": "Already in pack"}), 400
        discard_pack_idx = data.get("discard_pack_index")
        swap_to_equip = bool(data.get("swap_to_equip", False))
        if discard_pack_idx is not None:
            dpi = int(discard_pack_idx)
            if 0 <= dpi < len(player.pack):
                displaced_item = player.pack.pop(dpi)
            else:
                return jsonify({"error": "Invalid pack discard index"}), 400
        elif player.pack_slots_free <= 0:
            return jsonify({"error": "pack_full", "pack": [_ser_item(i) for i in player.pack]}), 409
        else:
            displaced_item = None
        player.unequip(item)
        player.pack.append(item)
        if swap_to_equip and displaced_item is not None:
            player.equip(displaced_item)
        _fx.refresh_tokens(player)
        return jsonify({"ok": True, "state": _build_state()})

    if action == "to_equip":
        if source != "pack":
            return jsonify({"error": "Item must come from pack to equip"}), 400
        if not player.can_equip(item):
            return jsonify({"error": f"Cannot equip {item.name} — no free slot"}), 400
        player.pack.pop(idx)
        player.equip(item)
        return jsonify({"ok": True, "state": _build_state()})

    return jsonify({"error": f"Unknown action: {action}"}), 400


@inventory_bp.route("/api/discard_consumable", methods=["POST"])
def api_discard_consumable():
    """Discard a consumable from the player's consumables list."""
    _game = _get_state()["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    idx = int(data.get("consumable_index", 0))
    player = _game.current_player
    if idx < 0 or idx >= len(player.consumables):
        return jsonify({"error": "Invalid consumable index"}), 400
    player.consumables.pop(idx)
    return jsonify({"ok": True, "state": _build_state()})


@inventory_bp.route("/api/release_monster", methods=["POST"])
def api_release_monster():
    """Release a captured monster from the player's pack."""
    _game = _get_state()["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    idx = int(data.get("index", 0))
    player = _game.current_player
    if idx < 0 or idx >= len(player.captured_monsters):
        return jsonify({"error": "Invalid monster index"}), 400
    player.captured_monsters.pop(idx)
    return jsonify({"ok": True, "state": _build_state()})


@inventory_bp.route("/api/scavenger_swap", methods=["POST"])
def api_scavenger_swap():
    """Scavenger trait: put chest item back on bottom and draw a new one."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    po = _game._pending_offer
    if po is None or po.get("type") != "chest":
        return jsonify({"error": "No pending chest offer"}), 400
    player = _game.current_player
    if not any(t.effect_id == "scavenger" for t in player.traits):
        return jsonify({"error": "Player does not have Scavenger trait"}), 400
    level = po["level"]
    old_item = po["items"][0]
    _game.item_decks[level].put_bottom(old_item)
    new_item = _game.item_decks[level].draw()
    if new_item is None:
        new_item = _game.item_decks[level].draw()
    if new_item is None:
        return jsonify({"error": "Item deck is empty"}), 400
    po["items"] = [new_item]
    log_line = f"  Scavenger: put {old_item.name} back, drew {new_item.name}."
    _st["pending_log"].append(log_line)
    _st["last_log"].append(log_line)
    enriched = _item_to_dict_from_obj(new_item)
    return jsonify({
        "ok": True,
        "offer": {"items": [enriched], "has_scavenger": False},
        "state": _build_state(),
    })
