"""Combat API routes (fight, flee, consumable use, bystander interactions)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from werblers_engine import content as C
from werblers_engine import effects as _fx
from werblers_web.serializers import (
    TOKEN_MAP as _TOKEN_MAP,
    item_card_image as _item_card_image,
    consumable_card_image as _consumable_card_image,
    monster_card_image as _monster_card_image,
)
from werblers_web.routes.helpers import _get_state, _enrich_combat_info, _build_state

combat_bp = Blueprint("combat", __name__)


@combat_bp.route("/api/fight", methods=["POST"])
def api_fight():
    """Resolve the pending monster combat."""
    _st = _get_state()
    _game = _st["game"]
    try:
        if _game is None:
            return jsonify({"error": "No game in progress"}), 400
        if _game._pending_combat is None:
            return jsonify({"error": "No pending combat"}), 400
        from_mystery = _game._pending_combat.get("from_mystery", False)
        result = _game.fight()
        _st["last_log"] = result.get("log", [])
        combat_info = result.get("combat_info")
        if combat_info:
            combat_info = _enrich_combat_info(combat_info)
        phase = "summoned_done" if result.get("summoned_monster") else "done"
        return jsonify({"phase": phase, "state": _build_state(), "combat_info": combat_info})
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        traceback.print_exc()
        return jsonify({"error": f"Server error during fight: {exc}\n\nTraceback:\n{tb}"}), 500


@combat_bp.route("/api/flee", methods=["POST"])
def api_flee():
    """Billfold: Fly, you dummy! — flee the pending monster or miniboss combat."""
    _st = _get_state()
    _game = _st["game"]
    try:
        if _game is None:
            return jsonify({"error": "No game in progress"}), 400
        result = _game.flee_monster()
        if "error" in result:
            return jsonify(result), 400
        _st["last_log"] = result.get("log", [])
        return jsonify({"phase": "done", "state": _build_state()})
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        traceback.print_exc()
        return jsonify({"error": f"Server error during flee: {exc}\n\nTraceback:\n{tb}"}), 500


@combat_bp.route("/api/swiftness_flee", methods=["POST"])
def api_swiftness_flee():
    """Swiftness trait: flee from pending monster/miniboss at no cost (no position change)."""
    _st = _get_state()
    _game = _st["game"]
    try:
        if _game is None:
            return jsonify({"error": "No game in progress"}), 400
        if _game._pending_combat is None:
            return jsonify({"error": "No pending combat"}), 400
        player = _game.current_player
        if not any(t.effect_id == "swiftness" for t in player.traits):
            return jsonify({"error": "Player does not have Swiftness"}), 400
        pc = _game._pending_combat
        if pc.get("type", "monster") == "werbler":
            return jsonify({"error": "Cannot flee from the Werbler!"}), 400
        _game._pending_combat = None
        log = pc["log"]
        monster = pc.get("monster")
        if monster:
            log.append(f"  Swiftness: {player.name} flees from {monster.name}! No combat.")
        _game._prefight_str_bonus = 0
        _game._prefight_monster_str_bonus = 0
        _game._finish_post_encounter(player, log)
        _game._advance_turn()
        _st["last_log"] = log
        return jsonify({"phase": "done", "state": _build_state()})
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Server error: {exc}"}), 500


@combat_bp.route("/api/use_ill_come_in_again", methods=["POST"])
def api_use_ill_come_in_again():
    """Use I'll Come In Again / I See Everything: return current monster and draw a new one."""
    _game = _get_state()["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    result = _game.use_ill_come_in_again()
    if "error" in result:
        return jsonify(result), 400
    combat_info = _enrich_combat_info(result["combat_info"])
    return jsonify({"phase": "combat", "state": _build_state(), "combat_info": combat_info})


@combat_bp.route("/api/use_eight_lives", methods=["POST"])
def api_use_eight_lives():
    """Immediately use Eight Lives to remove a curse."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    curse_index = int(data.get("curse_index", 0))
    result = _game.use_eight_lives(curse_index)
    if result.get("log"):
        _st["last_log"] = _st["last_log"] + result["log"]
    return jsonify({"ok": result["ok"], "state": _build_state()})


@combat_bp.route("/api/summon_monster", methods=["POST"])
def api_summon_monster():
    """Summon a captured monster as an ENEMY, triggering a fight."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    idx = int(data.get("index", 0))
    player = _game.current_player
    if idx < 0 or idx >= len(player.captured_monsters):
        return jsonify({"error": "Invalid monster index"}), 400
    monster = player.captured_monsters.pop(idx)
    tier = monster.level
    log = [f"{player.name} summons {monster.name} to fight!"]
    other_players = [p for p in _game.players if p is not player]
    has_reroll = any(t.effect_id in ("ill_come_in_again", "i_see_everything") for t in player.traits)
    _game._prefight_str_bonus = 0
    _game._prefight_monster_str_bonus = 0
    _game._pending_combat = {
        "monster": monster,
        "effective_deck": _game.monster_decks.get(tier),
        "other_players": other_players,
        "level": tier,
        "log": log,
        "old_pos": player.position,
        "new_pos": player.position,
        "card_value": 0,
        "tile_type": "MONSTER",
        "ill_come_in_again_available": has_reroll,
        "summoned_monster": True,
    }
    _male_bonus = monster.bonus_vs_male if (monster.bonus_vs_male and player.hero and player.hero.is_male) else 0
    combat_info = {
        "monster_name": monster.name,
        "monster_strength": monster.strength + _male_bonus,
        "monster_bonus_vs_male": _male_bonus,
        "player_strength": player.combat_strength(),
        "player_id": player.player_id,
        "player_name": player.name,
        "hero_id": player.hero.id.name if player.hero else None,
        "category": "monster",
        "level": tier,
        "result": None,
        "ill_come_in_again_available": has_reroll,
    }
    _game._last_combat_info = combat_info
    _st["last_log"] = log
    return jsonify({"ok": True, "phase": "combat", "state": _build_state(),
                    "combat_info": _enrich_combat_info(combat_info)})


@combat_bp.route("/api/crossroads_discard", methods=["POST"])
def api_crossroads_discard():
    """Pre-fight Fair Exchange: discard selected equipped items before fighting Crossroads Demon."""
    _game = _get_state()["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    if _game._pending_combat is None:
        return jsonify({"error": "No pending combat"}), 400
    miniboss = _game._pending_combat.get("monster")
    if not miniboss or getattr(miniboss, "effect_id", "") != "crossroads_demon":
        return jsonify({"error": "Not a Crossroads Demon encounter"}), 400
    data: dict = request.get_json(force=True) or {}
    equip_sources: list[dict] = data.get("equip_sources", [])
    player = _game.current_player
    slot_map = {
        "equip_helmet": player.helmets,
        "equip_chest":  player.chest_armor,
        "equip_leg":    player.leg_armor,
        "equip_weapon": player.weapons,
    }
    sorted_sources = sorted(equip_sources, key=lambda x: x.get("index", 0), reverse=True)
    discarded: list = []
    for src_info in sorted_sources:
        source = src_info.get("source", "")
        idx = int(src_info.get("index", -1))
        item_list = slot_map.get(source)
        if item_list is not None and 0 <= idx < len(item_list):
            item = item_list.pop(idx)
            discarded.append(item)
    if discarded:
        _fx.refresh_tokens(player)
        _game._pending_combat.setdefault("crossroads_discards", []).extend(discarded)
        from werblers_engine import encounters as _enc
        _ab_log: list[str] = []
        _ab_player_mod, _ab_monster_mod, _ = _enc._apply_miniboss_modifiers(
            player, miniboss, _ab_log, _game.is_night)
        _game._pending_combat["ability_player_mod"] = _ab_player_mod
        _game._pending_combat["ability_monster_mod"] = _ab_monster_mod
        _game._pending_combat["ability_breakdown"] = _ab_log
    pc = _game._pending_combat
    combat_info = {
        "monster_name": miniboss.name,
        "monster_strength": miniboss.strength + pc.get("ability_monster_mod", 0),
        "player_strength": max(0, player.combat_strength() + pc.get("ability_player_mod", 0)),
        "ability_player_mod": pc.get("ability_player_mod", 0),
        "ability_monster_mod": pc.get("ability_monster_mod", 0),
        "ability_breakdown": pc.get("ability_breakdown", []),
        "description": getattr(miniboss, "description", ""),
        "effect_id": miniboss.effect_id,
        "player_id": player.player_id,
        "player_name": player.name,
        "hero_id": player.hero.id.name if player.hero else None,
        "category": "miniboss",
        "level": pc.get("level", 2),
        "result": None,
        "crossroads_discards_count": len(pc.get("crossroads_discards", [])),
    }
    combat_info = _enrich_combat_info(combat_info)
    return jsonify({"ok": True, "state": _build_state(), "combat_info": combat_info})


@combat_bp.route("/api/use_consumable", methods=["POST"])
def api_use_consumable():
    """Use a consumable (combat-only or overworld effects)."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    idx = int(data.get("consumable_index", 0))
    player = _game.current_player
    if idx < 0 or idx >= len(player.consumables):
        return jsonify({"error": "Invalid consumable index"}), 400
    consumable = player.consumables.pop(idx)

    # ------------------------------------------------------------------ COMBAT-ONLY
    if consumable.effect_id == "capture_monster":
        if _game._pending_combat is None:
            tier = consumable.effect_tier
            deck = _game.monster_decks.get(tier)
            if deck is None:
                player.consumables.insert(idx, consumable)
                return jsonify({"error": f"Invalid tier {tier}"}), 400
            monster = deck.draw()
            if monster is None:
                player.consumables.insert(idx, consumable)
                return jsonify({"error": f"Tier-{tier} monster deck is empty \u2014 no monster to summon."}), 400
            log = [f"{player.name} activates {consumable.name}: a {monster.name} appears!"]
            other_players = [p for p in _game.players if p is not player]
            has_reroll = any(t.effect_id in ("ill_come_in_again", "i_see_everything") for t in player.traits)
            _game._prefight_str_bonus = 0
            _game._prefight_monster_str_bonus = 0
            _game._pending_combat = {
                "monster": monster,
                "effective_deck": deck,
                "other_players": other_players,
                "level": tier,
                "log": log,
                "old_pos": player.position,
                "new_pos": player.position,
                "card_value": 0,
                "tile_type": "MONSTER",
                "ill_come_in_again_available": has_reroll,
                "capture_device_triggered": True,
            }
            combat_info = {
                "monster_name": monster.name,
                "monster_strength": monster.strength,
                "player_strength": player.combat_strength(),
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "monster",
                "level": tier,
                "result": None,
                "ill_come_in_again_available": has_reroll,
            }
            _game._last_combat_info = combat_info
            _st["last_log"] = log
            return jsonify({"ok": True, "phase": "combat", "state": _build_state(),
                            "combat_info": _enrich_combat_info(combat_info)})
        pc = _game._pending_combat
        if pc.get("type") in ("miniboss", "werbler"):
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "Monster Capture Devices cannot be used on mini-bosses or Werblers!"}), 400
        monster = pc.get("monster") if pc else None
        if monster is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "No monster to capture"}), 400
        if consumable.effect_tier < monster.level:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": f"Capture device Tier {consumable.effect_tier} is too weak for a Level {monster.level} monster"}), 400
        if not player.add_captured_monster(monster):
            player.captured_monsters.append(monster)
        log = pc["log"]
        log.append(f"  {consumable.name}: {monster.name} captured!")
        _game._pending_combat = None
        _game._finish_post_encounter(player, log)
        _game._advance_turn()
        _st["last_log"] = log
        return jsonify({"ok": True, "phase": "captured", "monster_name": monster.name, "state": _build_state()})

    if consumable.effect_id == "" and consumable.strength_bonus > 0:
        if _game._pending_combat is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "Strength potions can only be used before a fight."}), 400
        _game._prefight_str_bonus += consumable.strength_bonus

    elif consumable.effect_id == "monster_str_mod":
        if _game._pending_combat is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "Monster-weakening vials can only be used before a fight."}), 400
        _game._prefight_monster_str_bonus += consumable.effect_value

    # ------------------------------------------------------------------ OVERWORLD: gain_trait
    elif consumable.effect_id == "gain_trait":
        tier = consumable.effect_tier
        deck = _game.monster_decks.get(tier)
        if deck is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": f"Invalid tier {tier}"}), 400
        drawn = deck.draw()
        if drawn is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": f"Tier-{tier} monster deck is empty — no effect."}), 400
        trait = (
            C.trait_for_monster(drawn) if drawn.trait_name
            else _game.trait_deck.draw()
        )
        if trait is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "No traits available."}), 400
        trait_log: list[str] = []
        player.traits.append(trait)
        trait_log.append(f"{player.name} used {consumable.name}: drew {drawn.name}.")
        trait_log.append(f"{player.name} gained trait '{trait.name}'!")
        trait_items, trait_minions = _fx.on_trait_gained(player, trait, trait_log)
        player.pending_trait_items.extend(trait_items)
        player.pending_trait_minions.extend(trait_minions)
        _fx.refresh_tokens(player)
        _st["last_log"] = trait_log
        return jsonify({"ok": True, "phase": "trait_gained", "trait_name": trait.name,
                        "monster_name": drawn.name,
                        "monster_card_image": _monster_card_image(drawn.name),
                        "trait_desc": C.TRAIT_DESCRIPTIONS.get(trait.name, ""),
                        "state": _build_state()})

    # ------------------------------------------------------------------ OVERWORLD: give_curse
    elif consumable.effect_id == "give_curse":
        tier = consumable.effect_tier
        deck = _game.monster_decks.get(tier)
        if deck is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": f"Invalid tier {tier}"}), 400
        drawn = deck.draw()
        if drawn is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": f"Tier-{tier} monster deck is empty — no effect."}), 400
        curse = (
            C.curse_for_monster(drawn) if drawn.curse_name
            else _game.curse_deck.draw()
        )
        if curse is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "No curses available."}), 400
        target_id = data.get("target_player_id", None)
        all_players = _game.players
        if target_id is not None:
            chosen_target = next((p for p in all_players if p.player_id == int(target_id)), None)
            target = chosen_target if chosen_target else (all_players[0] if all_players else player)
        else:
            others = [p for p in all_players if p is not player]
            target = others[0] if others else player
        curse_log: list[str] = []
        curse_log.append(f"{player.name} used {consumable.name}: drew {drawn.name}.")
        target.curses.append(curse)
        curse_log.append(f"{target.name} received curse '{curse.name}'!")
        _fx.on_curse_gained(target, curse, curse_log, None, [p for p in _game.players if p is not target], None)
        _fx.refresh_tokens(target)
        _st["last_log"] = curse_log
        return jsonify({"ok": True, "phase": "curse_given", "curse_name": curse.name,
                        "target_name": target.name,
                        "target_player_id": target.player_id,
                        "monster_name": drawn.name,
                        "monster_card_image": _monster_card_image(drawn.name),
                        "curse_desc": C.CURSE_DESCRIPTIONS.get(curse.name, ""),
                        "state": _build_state()})

    # ------------------------------------------------------------------ Combat info update
    ability_mod = _game._last_combat_info.get("ability_player_mod", 0) if _game._last_combat_info else 0
    if _game._last_combat_info:
        _game._last_combat_info["player_strength"] = max(0, player.combat_strength() + _game._prefight_str_bonus + ability_mod)
        _game._last_combat_info["monster_strength"] = (
            _game._last_combat_info.get("monster_strength", 0)
            + (consumable.effect_value if consumable.effect_id == "monster_str_mod" else 0)
        )
        _game._last_combat_info["prefight_str_bonus"] = _game._prefight_str_bonus
    return jsonify({"ok": True, "state": _build_state(), "combat_info": _enrich_combat_info(dict(_game._last_combat_info)) if _game._last_combat_info else None})


@combat_bp.route("/api/use_pack_consumable", methods=["POST"])
def api_use_pack_consumable():
    """Use a consumable item that is still in the player's pack (is_consumable=True)."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    import copy as _copy
    data: dict = request.get_json(force=True) or {}
    pack_idx = int(data.get("pack_index", 0))
    player = _game.current_player
    if pack_idx < 0 or pack_idx >= len(player.pack):
        return jsonify({"error": "Invalid pack index"}), 400
    item = player.pack[pack_idx]
    if not item.is_consumable:
        return jsonify({"error": "That item is not a consumable"}), 400
    consumable = next((c for c in C.CONSUMABLE_POOL if c.name == item.name), None)
    if consumable is None:
        return jsonify({"error": f"Unknown consumable type: {item.name}"}), 400
    consumable = _copy.copy(consumable)
    player.pack.pop(pack_idx)

    if consumable.effect_id == "gain_trait":
        tier = consumable.effect_tier
        deck = _game.monster_decks.get(tier)
        if deck is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": f"Invalid tier {tier}"}), 400
        drawn = deck.draw()
        if drawn is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": f"Tier-{tier} monster deck is empty."}), 400
        trait = (C.trait_for_monster(drawn) if drawn.trait_name else _game.trait_deck.draw())
        if trait is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": "No traits available."}), 400
        trait_log: list[str] = [f"{player.name} used {consumable.name}: drew {drawn.name}.",
                                 f"{player.name} gained trait '{trait.name}'!"]
        player.traits.append(trait)
        trait_items, trait_minions = _fx.on_trait_gained(player, trait, trait_log)
        player.pending_trait_items.extend(trait_items)
        player.pending_trait_minions.extend(trait_minions)
        _fx.refresh_tokens(player)
        _st["last_log"] = trait_log
        return jsonify({"ok": True, "phase": "trait_gained", "trait_name": trait.name,
                        "monster_name": drawn.name,
                        "monster_card_image": _monster_card_image(drawn.name),
                        "trait_desc": C.TRAIT_DESCRIPTIONS.get(trait.name, ""),
                        "state": _build_state()})

    elif consumable.effect_id == "give_curse":
        tier = consumable.effect_tier
        deck = _game.monster_decks.get(tier)
        if deck is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": f"Invalid tier {tier}"}), 400
        drawn = deck.draw()
        if drawn is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": f"Tier-{tier} monster deck is empty."}), 400
        curse = (C.curse_for_monster(drawn) if drawn.curse_name else _game.curse_deck.draw())
        if curse is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": "No curses available."}), 400
        target_id = data.get("target_player_id", None)
        all_players = _game.players
        if target_id is not None:
            chosen_target = next((p for p in all_players if p.player_id == int(target_id)), None)
            target = chosen_target if chosen_target else (all_players[0] if all_players else player)
        else:
            others = [p for p in all_players if p is not player]
            target = others[0] if others else player
        curse_log = [f"{player.name} used {consumable.name}: drew {drawn.name}.",
                     f"{target.name} received curse '{curse.name}'!"]
        target.curses.append(curse)
        _fx.on_curse_gained(target, curse, curse_log, None, [p for p in _game.players if p is not target], None)
        _fx.refresh_tokens(target)
        _st["last_log"] = curse_log
        return jsonify({"ok": True, "phase": "curse_given", "curse_name": curse.name,
                        "target_name": target.name, "target_player_id": target.player_id,
                        "monster_name": drawn.name,
                        "monster_card_image": _monster_card_image(drawn.name),
                        "curse_desc": C.CURSE_DESCRIPTIONS.get(curse.name, ""),
                        "state": _build_state()})

    player.pack.insert(pack_idx, item)
    return jsonify({"error": f"Unsupported consumable effect: {consumable.effect_id}"}), 400


@combat_bp.route("/api/bystander_consumable", methods=["POST"])
def api_bystander_consumable():
    """Non-fighting nearby player uses (or skips) a consumable at combat start."""
    _st = _get_state()
    _game = _st["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    if _game._pending_combat is None:
        return jsonify({"error": "No pending combat"}), 400
    data: dict = request.get_json(force=True) or {}
    bystander_id = int(data.get("player_id", -1))
    skip: bool = bool(data.get("skip", False))
    consumable_index = data.get("consumable_index", None)

    bystander = next((p for p in _game.players if p.player_id == bystander_id), None)
    if bystander is None:
        return jsonify({"error": f"Unknown player_id {bystander_id}"}), 400

    pc = _game._pending_combat
    nearby_queue: list = pc.get("nearby_queue", [])
    if bystander_id not in nearby_queue:
        return jsonify({"error": "Player is not in the nearby queue"}), 400

    nearby_queue.remove(bystander_id)
    pc["nearby_queue"] = nearby_queue

    log = pc.get("log", [])

    if not skip and consumable_index is not None:
        cidx = int(consumable_index)
        usable = [c for c in bystander.consumables if c.effect_id == "monster_str_mod"]
        if 0 <= cidx < len(usable):
            chosen = usable[cidx]
            bystander.consumables.remove(chosen)
            monster = pc.get("monster")
            if monster:
                delta = chosen.effect_value
                old_str = monster.strength
                monster.strength = max(0, monster.strength + delta)
                sign = "+" if delta >= 0 else ""
                log.append(
                    f"  {bystander.name} used {chosen.name} on {monster.name}: "
                    f"monster strength {sign}{delta} ({old_str} \u2192 {monster.strength})."
                )
                if _game._last_combat_info:
                    _game._last_combat_info["monster_strength"] = monster.strength

    _st["last_log"] = log

    combat_info = _enrich_combat_info(dict(_game._last_combat_info)) if _game._last_combat_info else None
    if combat_info is not None:
        remaining_players = [p for p in _game.players
                             if p.player_id in nearby_queue]
        combat_info["nearby_queue"] = [
            {
                "player_id":   bp.player_id,
                "name":        bp.name,
                "token_image": _TOKEN_MAP.get(bp.hero.id.name if bp.hero else "", ""),
                "consumables": [{"name": c.name, "card_image": _consumable_card_image(c.name),
                                 "effect_id": c.effect_id, "effect_value": c.effect_value,
                                 "effect_tier": c.effect_tier, "strength_bonus": c.strength_bonus}
                                for c in bp.consumables if c.effect_id == "monster_str_mod"],
            }
            for bp in remaining_players
        ]
    return jsonify({"ok": True, "combat_info": combat_info, "state": _build_state()})
