"""Serialize / deserialize a Game object to/from JSON-compatible dicts.

This module handles converting the complex Game object (with Decks, Players,
typed dataclasses, etc.) into a plain dict that can be stored as JSON in the
database, and reconstructing a Game from that dict.
"""
from __future__ import annotations

import json
from typing import Optional

from .types import (
    Item, Consumable, Minion, Monster, Trait, Curse,
    Tile, TileType, EquipSlot, GameStatus,
)
from .deck import Deck
from .heroes import HEROES, HeroId
from .player import Player
from . import content as C


# ---------------------------------------------------------------------------
# Serializers  (object -> dict)
# ---------------------------------------------------------------------------

def _ser_item(item: Item) -> dict:
    return {
        "name": item.name,
        "slot": item.slot.value,
        "strength_bonus": item.strength_bonus,
        "effect_id": item.effect_id,
        "weapon_hand_bonus": item.weapon_hand_bonus,
        "hands": item.hands,
        "locked_by_curse_id": item.locked_by_curse_id,
        "tokens": item.tokens,
        "is_ranged": item.is_ranged,
        "is_gun": item.is_gun,
        "is_consumable": item.is_consumable,
    }


def _ser_consumable(c: Consumable) -> dict:
    return {
        "name": c.name,
        "effect_id": c.effect_id,
        "effect_value": c.effect_value,
        "effect_tier": c.effect_tier,
        "strength_bonus": c.strength_bonus,
    }


def _ser_minion(m: Minion) -> dict:
    return {"name": m.name, "strength_bonus": m.strength_bonus, "effect_id": m.effect_id}


def _ser_monster(m: Monster) -> dict:
    return {
        "name": m.name, "strength": m.strength, "level": m.level,
        "description": m.description, "trait_name": m.trait_name,
        "trait_text": m.trait_text, "curse_name": m.curse_name,
        "curse_text": m.curse_text, "bonus_text": m.bonus_text,
        "active": m.active, "effect_id": m.effect_id,
        "bonus_vs_male": m.bonus_vs_male,
    }


def _ser_trait(t: Trait) -> dict:
    return {
        "name": t.name, "effect_id": t.effect_id, "source_monster": t.source_monster,
        "strength_bonus": t.strength_bonus, "hand_size_bonus": t.hand_size_bonus,
        "move_bonus": t.move_bonus, "helmet_slot_bonus": t.helmet_slot_bonus,
        "chest_slot_bonus": t.chest_slot_bonus, "legs_slot_bonus": t.legs_slot_bonus,
        "weapon_hand_bonus": t.weapon_hand_bonus, "tokens": t.tokens,
    }


def _ser_curse(c: Curse) -> dict:
    return {
        "name": c.name, "effect_id": c.effect_id, "source_monster": c.source_monster,
        "linked_item_name": c.linked_item_name, "strength_bonus": c.strength_bonus,
        "hand_size_bonus": c.hand_size_bonus, "move_bonus": c.move_bonus,
        "helmet_slot_bonus": c.helmet_slot_bonus, "chest_slot_bonus": c.chest_slot_bonus,
        "legs_slot_bonus": c.legs_slot_bonus, "weapon_hand_bonus": c.weapon_hand_bonus,
        "tokens": c.tokens,
    }


def _ser_tile(t: Tile) -> dict:
    return {
        "index": t.index,
        "tile_type": t.tile_type.name,
        "revealed": t.revealed,
        "revealed_night": t.revealed_night,
    }


def _ser_deck(d: Deck) -> dict:
    """Serialize a Deck.  Cards can be ints, Items, Monsters, Traits, Curses, etc."""
    def _card(c):
        if isinstance(c, int):
            return c
        if isinstance(c, Item):
            return {"_type": "Item", **_ser_item(c)}
        if isinstance(c, Monster):
            return {"_type": "Monster", **_ser_monster(c)}
        if isinstance(c, Trait):
            return {"_type": "Trait", **_ser_trait(c)}
        if isinstance(c, Curse):
            return {"_type": "Curse", **_ser_curse(c)}
        if isinstance(c, Consumable):
            return {"_type": "Consumable", **_ser_consumable(c)}
        if isinstance(c, Minion):
            return {"_type": "Minion", **_ser_minion(c)}
        return c  # fallback (shouldn't happen)

    return {
        "cards": [_card(c) for c in d._cards],
        "discard": [_card(c) for c in d._discard],
        "auto_reshuffle": d._auto_reshuffle,
    }


def _ser_player(p: Player) -> dict:
    return {
        "player_id": p.player_id,
        "name": p.name,
        "position": p.position,
        "base_strength": p.base_strength,
        "helmets": [_ser_item(i) for i in p.helmets],
        "chest_armor": [_ser_item(i) for i in p.chest_armor],
        "leg_armor": [_ser_item(i) for i in p.leg_armor],
        "weapons": [_ser_item(i) for i in p.weapons],
        "consumables": [_ser_consumable(c) for c in p.consumables],
        "minions": [_ser_minion(m) for m in p.minions],
        "pack": [_ser_item(i) for i in p.pack],
        "captured_monsters": [_ser_monster(m) for m in p.captured_monsters],
        "auto_loses_next_battle": p.auto_loses_next_battle,
        "movement_discard": list(p.movement_discard),
        "last_card_played": p.last_card_played,
        "_base_helmet_slots": p._base_helmet_slots,
        "_base_chest_slots": p._base_chest_slots,
        "_base_legs_slots": p._base_legs_slots,
        "_base_weapon_hands": p._base_weapon_hands,
        "_base_pack_size": p._base_pack_size,
        "traits": [_ser_trait(t) for t in p.traits],
        "curses": [_ser_curse(c) for c in p.curses],
        "movement_hand": list(p.movement_hand),
        "max_hand_size": p.max_hand_size,
        "miniboss1_defeated": p.miniboss1_defeated,
        "miniboss2_defeated": p.miniboss2_defeated,
        "defeated_monsters": list(p.defeated_monsters),
        "_pending_movement_draws": p._pending_movement_draws,
        "hero_id": p.hero.id.name if p.hero else None,
        "mutagen_used": p.mutagen_used,
        "_beggar_gifts": p._beggar_gifts,
        "_beggar_completed": p._beggar_completed,
        "pending_trait_items": [_ser_item(i) for i in p.pending_trait_items],
        "pending_trait_minions": [_ser_minion(m) for m in p.pending_trait_minions],
    }


def _ser_pending(d: Optional[dict]) -> Optional[dict]:
    """Serialize _pending_offer or _pending_combat dict (contains Monster refs)."""
    if d is None:
        return None
    out = {}
    for k, v in d.items():
        if isinstance(v, Monster):
            out[k] = {"_type": "Monster", **_ser_monster(v)}
        elif isinstance(v, Item):
            out[k] = {"_type": "Item", **_ser_item(v)}
        elif isinstance(v, Trait):
            out[k] = {"_type": "Trait", **_ser_trait(v)}
        elif isinstance(v, Curse):
            out[k] = {"_type": "Curse", **_ser_curse(v)}
        elif isinstance(v, Consumable):
            out[k] = {"_type": "Consumable", **_ser_consumable(v)}
        elif isinstance(v, list):
            out[k] = [_ser_pending_value(x) for x in v]
        elif isinstance(v, dict):
            out[k] = _ser_pending(v)
        else:
            out[k] = v
    return out


def _ser_pending_value(v):
    if isinstance(v, Monster):
        return {"_type": "Monster", **_ser_monster(v)}
    if isinstance(v, Item):
        return {"_type": "Item", **_ser_item(v)}
    if isinstance(v, Trait):
        return {"_type": "Trait", **_ser_trait(v)}
    if isinstance(v, Curse):
        return {"_type": "Curse", **_ser_curse(v)}
    if isinstance(v, Consumable):
        return {"_type": "Consumable", **_ser_consumable(v)}
    if isinstance(v, Minion):
        return {"_type": "Minion", **_ser_minion(v)}
    if isinstance(v, dict):
        return _ser_pending(v)
    return v


# ---------------------------------------------------------------------------
# Top-level serialize
# ---------------------------------------------------------------------------

def serialize_game(game) -> str:
    """Convert a Game instance to a JSON string for storage."""
    from .game import Game  # avoid circular
    g: Game = game

    data = {
        "version": 1,
        "board": [_ser_tile(t) for t in g.board],
        "is_night": g.is_night,
        "turn_number": g.turn_number,
        "status": g.status.name,
        "winner": g.winner,
        "players": [_ser_player(p) for p in g.players],
        "_current_player_idx": g._current_player_idx,
        # Decks
        "monster_decks": {str(k): _ser_deck(v) for k, v in g.monster_decks.items()},
        "item_decks": {str(k): _ser_deck(v) for k, v in g.item_decks.items()},
        "trait_deck": _ser_deck(g.trait_deck),
        "curse_deck": _ser_deck(g.curse_deck),
        "movement_decks": {str(k): _ser_deck(v) for k, v in g.movement_decks.items()},
        "miniboss_deck_t1": _ser_deck(g.miniboss_deck_t1),
        "miniboss_deck_t2": _ser_deck(g.miniboss_deck_t2),
        "active_miniboss_t1": _ser_monster(g.active_miniboss_t1) if g.active_miniboss_t1 else None,
        "active_miniboss_t2": _ser_monster(g.active_miniboss_t2) if g.active_miniboss_t2 else None,
        "player_werblers": {str(k): _ser_monster(v) for k, v in g.player_werblers.items()},
        "_decision_counter": g._decision_counter,
        "_pending_offer": _ser_pending(g._pending_offer),
        "_last_combat_info": g._last_combat_info,
        "_pending_combat": _ser_pending(g._pending_combat),
        "_prefight_str_bonus": g._prefight_str_bonus,
        "_prefight_monster_str_bonus": g._prefight_monster_str_bonus,
        "_rakeitin_pending_placement": g._rakeitin_pending_placement,
    }
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Deserializers (dict -> object)
# ---------------------------------------------------------------------------

def _de_item(d: dict) -> Item:
    dd = {k: v for k, v in d.items() if k != "_type"}
    dd["slot"] = EquipSlot(dd["slot"])
    return Item(**dd)


def _de_consumable(d: dict) -> Consumable:
    dd = {k: v for k, v in d.items() if k != "_type"}
    return Consumable(**dd)


def _de_minion(d: dict) -> Minion:
    dd = {k: v for k, v in d.items() if k != "_type"}
    return Minion(**dd)


def _de_monster(d: dict) -> Monster:
    dd = {k: v for k, v in d.items() if k != "_type"}
    return Monster(**dd)


def _de_trait(d: dict) -> Trait:
    dd = {k: v for k, v in d.items() if k != "_type"}
    return Trait(**dd)


def _de_curse(d: dict) -> Curse:
    dd = {k: v for k, v in d.items() if k != "_type"}
    return Curse(**dd)


def _de_tile(d: dict) -> Tile:
    return Tile(
        index=d["index"],
        tile_type=TileType[d["tile_type"]],
        revealed=d["revealed"],
        revealed_night=d.get("revealed_night", False),
    )


def _de_card(c):
    """Deserialize a card from a deck.  Could be an int or a typed dict."""
    if isinstance(c, int):
        return c
    if isinstance(c, dict):
        t = c.get("_type")
        if t == "Item":
            return _de_item(c)
        if t == "Monster":
            return _de_monster(c)
        if t == "Trait":
            return _de_trait(c)
        if t == "Curse":
            return _de_curse(c)
        if t == "Consumable":
            return _de_consumable(c)
        if t == "Minion":
            return _de_minion(c)
    return c


def _de_deck(d: dict) -> Deck:
    """Reconstruct a Deck from serialized data without reshuffling."""
    deck = object.__new__(Deck)
    import random
    deck._cards = [_de_card(c) for c in d["cards"]]
    deck._discard = [_de_card(c) for c in d["discard"]]
    deck._rng = random.Random()
    deck._auto_reshuffle = d.get("auto_reshuffle", False)
    return deck


def _de_player(d: dict) -> Player:
    hero_id_str = d.get("hero_id")
    hero = HEROES[HeroId[hero_id_str]] if hero_id_str else None

    p = Player(player_id=d["player_id"], name=d["name"])
    p.position = d["position"]
    p.base_strength = d["base_strength"]
    p.helmets = [_de_item(i) for i in d["helmets"]]
    p.chest_armor = [_de_item(i) for i in d["chest_armor"]]
    p.leg_armor = [_de_item(i) for i in d["leg_armor"]]
    p.weapons = [_de_item(i) for i in d["weapons"]]
    p.consumables = [_de_consumable(c) for c in d["consumables"]]
    p.minions = [_de_minion(m) for m in d["minions"]]
    p.pack = [_de_item(i) for i in d["pack"]]
    p.captured_monsters = [_de_monster(m) for m in d["captured_monsters"]]
    p.auto_loses_next_battle = d["auto_loses_next_battle"]
    p.movement_discard = d["movement_discard"]
    p.last_card_played = d["last_card_played"]
    p._base_helmet_slots = d["_base_helmet_slots"]
    p._base_chest_slots = d["_base_chest_slots"]
    p._base_legs_slots = d["_base_legs_slots"]
    p._base_weapon_hands = d["_base_weapon_hands"]
    p._base_pack_size = d.get("_base_pack_size", 3)
    p.traits = [_de_trait(t) for t in d["traits"]]
    p.curses = [_de_curse(c) for c in d["curses"]]
    p.movement_hand = d["movement_hand"]
    p.max_hand_size = d["max_hand_size"]
    p.miniboss1_defeated = d["miniboss1_defeated"]
    p.miniboss2_defeated = d["miniboss2_defeated"]
    p.defeated_monsters = set(d["defeated_monsters"])
    p._pending_movement_draws = d["_pending_movement_draws"]
    p.mutagen_used = d.get("mutagen_used", False)
    p._beggar_gifts = d.get("_beggar_gifts", 0)
    p._beggar_completed = d.get("_beggar_completed", False)
    p.pending_trait_items = [_de_item(i) for i in d.get("pending_trait_items", [])]
    p.pending_trait_minions = [_de_minion(m) for m in d.get("pending_trait_minions", [])]
    if hero:
        p._hero = hero
    return p


def _de_pending(d: Optional[dict]) -> Optional[dict]:
    """Deserialize _pending_offer / _pending_combat dict."""
    if d is None:
        return None
    out = {}
    for k, v in d.items():
        if isinstance(v, dict) and "_type" in v:
            out[k] = _de_card(v)
        elif isinstance(v, list):
            out[k] = [_de_pending_value(x) for x in v]
        elif isinstance(v, dict):
            out[k] = _de_pending(v)
        else:
            out[k] = v
    return out


def _de_pending_value(v):
    if isinstance(v, dict) and "_type" in v:
        return _de_card(v)
    if isinstance(v, dict):
        return _de_pending(v)
    return v


# ---------------------------------------------------------------------------
# Top-level deserialize
# ---------------------------------------------------------------------------

def deserialize_game(json_str: str):
    """Reconstruct a Game instance from a JSON string."""
    from .game import Game

    data = json.loads(json_str)

    # Create an empty Game shell without running __init__
    g = object.__new__(Game)

    g.board = [_de_tile(t) for t in data["board"]]
    g.is_night = data["is_night"]
    g.turn_number = data["turn_number"]
    g.status = GameStatus[data["status"]]
    g.winner = data["winner"]
    g.players = [_de_player(p) for p in data["players"]]
    g._current_player_idx = data["_current_player_idx"]

    # Decks
    g.monster_decks = {int(k): _de_deck(v) for k, v in data["monster_decks"].items()}
    g.item_decks = {int(k): _de_deck(v) for k, v in data["item_decks"].items()}
    g.trait_deck = _de_deck(data["trait_deck"])
    g.curse_deck = _de_deck(data["curse_deck"])
    g.movement_decks = {int(k): _de_deck(v) for k, v in data["movement_decks"].items()}
    g.miniboss_deck_t1 = _de_deck(data["miniboss_deck_t1"])
    g.miniboss_deck_t2 = _de_deck(data["miniboss_deck_t2"])
    g.active_miniboss_t1 = _de_monster(data["active_miniboss_t1"]) if data["active_miniboss_t1"] else None
    g.active_miniboss_t2 = _de_monster(data["active_miniboss_t2"]) if data["active_miniboss_t2"] else None
    g.player_werblers = {int(k): _de_monster(v) for k, v in data["player_werblers"].items()}
    g._decision_counter = data["_decision_counter"]
    g._pending_offer = _de_pending(data["_pending_offer"])
    g._last_combat_info = data["_last_combat_info"]
    g._pending_combat = _de_pending(data["_pending_combat"])
    g._prefight_str_bonus = data["_prefight_str_bonus"]
    g._prefight_monster_str_bonus = data["_prefight_monster_str_bonus"]
    g._rakeitin_pending_placement = data.get("_rakeitin_pending_placement", False)

    return g
