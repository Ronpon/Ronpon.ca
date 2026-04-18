"""Serialization helpers and image path resolution for the Werblers web UI.

Extracted from app.py to keep route handlers focused on request/response flow.
"""
from __future__ import annotations

from werblers_engine.types import TileType
from werblers_engine import content as C


# ---------------------------------------------------------------------------
# Hero image / animation constant maps
# ---------------------------------------------------------------------------

TOKEN_MAP: dict[str, str] = {
    "BILLFOLD":  "Assorted UI Images/Billfold Token.png",
    "GREGORY":   "Assorted UI Images/Gregory Token.png",
    "BRUNHILDE": "Assorted UI Images/Brunhilde Token.png",
    "RIZZT":     "Assorted UI Images/Rizzt Token.png",
}

CARD_IMG_MAP: dict[str, str] = {
    "BILLFOLD":  "Heroes/Billfold Baggains Card.png",
    "GREGORY":   "Heroes/Gregory Card.png",
    "BRUNHILDE": "Heroes/Brunhilde the Bodacious Card.png",
    "RIZZT":     "Heroes/Rizzt No'Cappin Card.png",
}

HERO_ANIM_MAP: dict[str, dict[str, str]] = {
    "BILLFOLD": {
        "general": "Hero Animations/Billfold General.mp4",
        "victory": "Hero Animations/Billfold Victory.mp4",
        "defeat":  "Hero Animations/Billfold Defeat.mp4",
    },
    "GREGORY": {
        "general": "Hero Animations/Gregory General.mp4",
        "victory": "Hero Animations/Gregory Victory.mp4",
        "defeat":  "Hero Animations/Gregory Defeat.mp4",
    },
    "BRUNHILDE": {
        "general": "Hero Animations/Brumhilde General.mp4",
        "victory": "Hero Animations/Brumhilde Victory.mp4",
        "defeat":  "Hero Animations/Brumhilde Defeat.mp4",
    },
    "RIZZT": {
        "general": "Hero Animations/Rizzt General.mp4",
        "victory": "Hero Animations/Rizzt Victory.mp4",
        "defeat":  "Hero Animations/Rizzt Defeat.mp4",
    },
}

# ---------------------------------------------------------------------------
# Item / card image path helpers
# ---------------------------------------------------------------------------

_SLOT_IMG_FOLDER = {
    "helmet": "Items/Head Armour/Head Armour Finished Cards",
    "chest":  "Items/Chest Armour/Chest Armour Finished Cards",
    "legs":   "Items/Leg Armour/Leg Armour Finished Cards",
    "weapon": "Items/Weapons/Weapon Finished Cards",
}

_ITEM_FILENAME_OVERRIDES: dict[str, str] = {
    "Swiss Guard Helmet": "Swiss Guard's Helmet",
    "Pumped Up Kicks": "Pumped up Kicks",
    "Chestplate Made of What the Black Box is Made of": "Black Box Chestplate",
    "Sweet bandana": "Sweet Bandana",
}


def normalize_item_filename(name: str) -> str:
    """Replace curly/smart apostrophes with straight ones so filenames match disk."""
    return name.replace('\u2019', "'").replace('\u2018', "'")


def item_card_image(item) -> str:
    if item.slot.value == "consumable":
        return consumable_card_image(item.name)
    folder = _SLOT_IMG_FOLDER.get(item.slot.value, "")
    display = _ITEM_FILENAME_OVERRIDES.get(item.name, normalize_item_filename(item.name))
    return f"{folder}/{display} Card.png" if folder else ""


def item_card_image_from_dict(item_dict: dict) -> str:
    slot = item_dict.get("slot", "")
    name = item_dict.get("name", "")
    if slot == "consumable":
        return consumable_card_image(name)
    folder = _SLOT_IMG_FOLDER.get(slot, "")
    display = _ITEM_FILENAME_OVERRIDES.get(name, normalize_item_filename(name))
    return f"{folder}/{display} Card.png" if folder else ""


def tile_level(pos: int) -> int:
    if pos <= 30: return 1
    if pos <= 60: return 2
    return 3


def consumable_card_image(name: str) -> str:
    safe_name = name.replace('\u2019', "'").replace('\u2018', "'")
    return f"Items/Consumables/Consumable Finished Cards/{safe_name} Card.png"


def monster_card_image(name: str) -> str:
    return f"Monsters/Finished Cards/{name} Card.png"


def minion_card_image(name: str) -> str:
    return f"Minions/Finished Minion Cards/{name} Card.png"


def miniboss_card_image(name: str) -> str:
    return f"Mini Bosses/Finished Cards/{name} Card.png"


def werbler_card_image(name: str) -> str:
    return f"Werblers/Werbler Finished Cards/{name} Card.png"


# ---------------------------------------------------------------------------
# Tile image resolution
# ---------------------------------------------------------------------------

def tile_image(tile, is_night: bool, mb1_defeated: bool = False, mb2_defeated: bool = False) -> str:
    if tile.index == 1:
        return "Tiles/Blank Tile.png"
    if tile.tile_type == TileType.DAY_NIGHT:
        return "Tiles/Day and Night Tile.png"
    if tile.tile_type == TileType.WERBLER:
        return "Tiles/Werbler Tile.png"
    if tile.tile_type == TileType.MINIBOSS:
        if tile.index == 30:
            return "Tiles/Mini Boss 1 Defeated.png" if mb1_defeated else "Tiles/Mini Boss 1.png"
        else:
            return "Tiles/Mini Boss 2 Defeated.png" if mb2_defeated else "Tiles/Mini Boss 2 Tile.png"
    if is_night:
        return "Tiles/Night Tile.png"
    if not tile.revealed:
        return "Tiles/Hidden Tile.png"
    mapping = {
        TileType.BLANK:     "Tiles/Blank Tile.png",
        TileType.MONSTER:   "Tiles/Monster Tile.png",
        TileType.CHEST:     "Tiles/Chest Tile.png",
        TileType.SHOP:      "Tiles/Shop Tile.jpg",
        TileType.MYSTERY:   "Tiles/Mystery Tile.png",
    }
    return mapping.get(tile.tile_type, "Tiles/Hidden Tile.png")


# ---------------------------------------------------------------------------
# Object serializers (Item / Trait / Curse → dict)
# ---------------------------------------------------------------------------

def ser_item(item) -> dict:
    if item.slot.value == "consumable":
        card_img = consumable_card_image(item.name)
    else:
        card_img = item_card_image(item)
    return {
        "name":           item.name,
        "slot":           item.slot.value,
        "strength_bonus": item.strength_bonus,
        "effect_id":      item.effect_id,
        "hands":          item.hands,
        "tokens":         item.tokens,
        "card_image":     card_img,
        "is_consumable":  item.is_consumable,
    }


def ser_trait(t) -> dict:
    return {"name": t.name, "effect_id": t.effect_id, "tokens": t.tokens,
            "strength_bonus": t.strength_bonus,
            "description": C.TRAIT_DESCRIPTIONS.get(t.name, "")}


def ser_curse(c) -> dict:
    return {"name": c.name, "effect_id": c.effect_id, "tokens": c.tokens,
            "strength_bonus": c.strength_bonus,
            "description": C.CURSE_DESCRIPTIONS.get(c.name, "")}


def item_to_dict_from_obj(item) -> dict:
    """Serialize a types.Item object to dict for JSON (matching _item_to_dict pattern)."""
    return {
        "name": item.name,
        "slot": item.slot.value,
        "strength_bonus": item.strength_bonus,
        "effect_id": item.effect_id,
        "hands": item.hands,
        "is_consumable": item.is_consumable,
        "card_image": item_card_image(item),
    }


# ---------------------------------------------------------------------------
# Hero ability breakdown (human-readable passive bonus list)
# ---------------------------------------------------------------------------

def hero_ability_breakdown(player, is_night: bool) -> list:
    """Return a list of human-readable strings for hero passive ability bonuses."""
    lines = []
    hero = player.hero
    if not hero:
        return lines
    if hero.has_luscious_locks and not player.helmets:
        lines.append("Luscious Locks (no helmet): +5")
    if hero.has_skimpy_armour and player.chest_armor:
        for item in player.chest_armor:
            skimpy_bonus = max(0, 8 - item.strength_bonus)
            if skimpy_bonus > 0:
                lines.append(f"Skimpy Armour ({item.name}): +{skimpy_bonus} extra")
    if hero.has_night_stalker and is_night:
        lines.append(f"Night Stalker (night): +{hero.night_stalker_bonus}")
    return lines


# ---------------------------------------------------------------------------
# Combat info enrichment
# ---------------------------------------------------------------------------

def enrich_combat_info(info: dict, game, get_state_fn) -> dict:
    """Add card image path and player gear to combat info for the frontend battle scene.

    Parameters
    ----------
    info : dict
        Raw combat_info dict from the engine.
    game : Game
        The current Game instance.
    get_state_fn : callable
        Returns the mutable session state dict (for pending_log access, etc.).
    """
    category = info.get("category", "monster")
    name = info.get("monster_name", "")
    if category == "miniboss":
        info["card_image"] = miniboss_card_image(name)
    elif category == "werbler":
        info["card_image"] = werbler_card_image(name)
    else:
        info["card_image"] = monster_card_image(name)
    bg_map = {1: "Backgrounds/Forest Background.png", 2: "Backgrounds/Cave Background.png", 3: "Backgrounds/Dungeon Background.png"}
    info["background"] = bg_map.get(info.get("level", 1), bg_map[1])
    hero_id = info.get("hero_id")
    if hero_id:
        info["hero_card_image"] = CARD_IMG_MAP.get(hero_id, "")
        info["hero_animations"] = HERO_ANIM_MAP.get(hero_id, {})
    if game is not None:
        _pfp = game.current_player
        info["has_swiftness"] = any(t.effect_id == "swiftness" for t in _pfp.traits)
    trait_name = info.get("trait_gained")
    if trait_name:
        info["trait_gained_desc"] = C.TRAIT_DESCRIPTIONS.get(trait_name, "")
    curse_name = info.get("curse_gained")
    if curse_name:
        info["curse_gained_desc"] = C.CURSE_DESCRIPTIONS.get(curse_name, "")
    if game is not None:
        player_id = info.get("player_id")
        player = next((p for p in game.players if p.player_id == player_id), None)
        if player is None:
            player = game.current_player
        info["player_gear"] = (
            [ser_item(i) for i in player.helmets]
            + [ser_item(i) for i in player.chest_armor]
            + [ser_item(i) for i in player.leg_armor]
            + [ser_item(i) for i in player.weapons]
        )
        info["player_traits"] = [ser_trait(t) for t in player.traits]
        info["player_curses"] = [ser_curse(c) for c in player.curses]
        if "nearby_queue" not in info and game._pending_combat is not None:
            _PROXIMITY = 5
            other_players = game._pending_combat.get("other_players", [])
            queue = []
            for bp in other_players:
                if abs(bp.position - player.position) > _PROXIMITY:
                    continue
                usable = [c for c in bp.consumables if c.effect_id == "monster_str_mod"]
                if not usable:
                    continue
                queue.append({
                    "player_id":   bp.player_id,
                    "name":        bp.name,
                    "token_image": TOKEN_MAP.get(bp.hero.id.name if bp.hero else "", ""),
                    "consumables": [{"name": c.name, "card_image": consumable_card_image(c.name),
                                     "effect_id": c.effect_id, "effect_value": c.effect_value,
                                     "effect_tier": c.effect_tier, "strength_bonus": c.strength_bonus}
                                    for c in usable],
                })
            info["nearby_queue"] = queue
            if game._pending_combat is not None:
                game._pending_combat["nearby_queue"] = [q["player_id"] for q in queue]
        info["player_minions"] = [{"name": m.name, "strength_bonus": m.strength_bonus, "card_image": minion_card_image(m.name)} for m in player.minions]
        info["player_base_strength"] = player.base_strength
        info["player_helmet_slots"] = player.helmet_slots
        info["player_chest_slots"] = player.chest_slots
        info["player_legs_slots"] = player.legs_slots
        info["player_weapon_hands"] = player.weapon_hands
        info.setdefault("prefight_str_bonus", game._prefight_str_bonus)
        _hero_breakdown = list(info.get("ability_breakdown") or []) + hero_ability_breakdown(player, game.is_night)
        if _hero_breakdown:
            info["ability_breakdown"] = _hero_breakdown
    return info


# ---------------------------------------------------------------------------
# Full game state builder
# ---------------------------------------------------------------------------

def build_state(get_state_fn) -> dict:
    """Build the full game state dict for JSON responses.

    Parameters
    ----------
    get_state_fn : callable
        Returns the mutable session state dict with keys "game", "last_log", etc.
    """
    _st = get_state_fn()
    g = _st["game"]
    current = g.current_player
    board_data = [
        {
            "index":     t.index,
            "tile_type": t.tile_type.name,
            "revealed":  t.revealed,
            "image":     tile_image(t, g.is_night, mb1_defeated=False, mb2_defeated=False),
            "image_defeated": tile_image(t, g.is_night, mb1_defeated=True, mb2_defeated=True) if t.tile_type == TileType.MINIBOSS else None,
        }
        for t in g.board[1:]
    ]
    players_data = []
    for p in g.players:
        hid = p.hero.id.name if p.hero else None
        players_data.append({
            "player_id":          p.player_id,
            "name":               p.name,
            "hero_name":          p.name,
            "position":           p.position,
            "strength":           p.combat_strength(is_night=g.is_night),
            "hero_id":            hid,
            "token_image":        TOKEN_MAP.get(hid) if hid else None,
            "hero_card_image":    CARD_IMG_MAP.get(hid) if hid else None,
            "hero_animations":    HERO_ANIM_MAP.get(hid, {}) if hid else {},
            "movement_hand":      list(p.movement_hand),
            "is_current":         p is current,
            "helmets":            [ser_item(i) for i in p.helmets],
            "chest_armor":        [ser_item(i) for i in p.chest_armor],
            "leg_armor":          [ser_item(i) for i in p.leg_armor],
            "weapons":            [ser_item(i) for i in p.weapons],
            "pack":               [ser_item(i) for i in p.pack],
            "consumables":        [{"name": c.name, "card_image": consumable_card_image(c.name), "strength_bonus": c.strength_bonus, "effect_id": c.effect_id, "effect_tier": c.effect_tier, "effect_value": c.effect_value} for c in p.consumables],
            "captured_monsters":  [{"name": m.name, "card_image": monster_card_image(m.name), "level": m.level} for m in p.captured_monsters],
            "traits":             [ser_trait(t) for t in p.traits],
            "curses":             [ser_curse(c) for c in p.curses],
            "minions":            [{"name": m.name, "strength_bonus": m.strength_bonus, "effect_id": m.effect_id, "card_image": minion_card_image(m.name)} for m in p.minions],
            "helmet_slots":       p.helmet_slots,
            "chest_slots":        p.chest_slots,
            "legs_slots":         p.legs_slots,
            "pack_slots_free":    p.pack_slots_free,
            "pack_size":          p.pack_size,
            "miniboss1_defeated": p.miniboss1_defeated,
            "miniboss2_defeated": p.miniboss2_defeated,
            "base_strength":       p.base_strength,
            "weapon_hands":          p.weapon_hands,
            "movement_discard_top":   p.movement_discard[-1] if p.movement_discard else None,
            "movement_discard_count": len(p.movement_discard),
            "movement_discard_list":  list(p.movement_discard),
            "movement_deck_cards":    g.movement_decks[p.player_id].peek_all(),
            "movement_card_bonus":    p.hero.movement_card_bonus if p.hero else 0,
            "pending_trait_items":    [ser_item(i) for i in p.pending_trait_items],
            "pending_trait_minions": [{"name": m.name, "strength_bonus": m.strength_bonus, "effect_id": m.effect_id, "card_image": minion_card_image(m.name)} for m in p.pending_trait_minions],
            "max_minions":           p.MAX_MINIONS,
            "beggar_gifts":          getattr(p, "_beggar_gifts", 0),
            "beggar_completed":      getattr(p, "_beggar_completed", False),
            "ability_breakdown":     hero_ability_breakdown(p, g.is_night),
        })
    return {
        "turn_number":       g.turn_number,
        "is_night":          g.is_night,
        "current_player_id": current.player_id,
        "game_status":       g.status.name,
        "winner":            g.winner,
        "board":             board_data,
        "players":           players_data,
        "log":               _st["last_log"],
        "has_pending_offer": g._pending_offer is not None,
        "has_pending_combat": g._pending_combat is not None and g._pending_combat.get("type") != "awaiting_charlie_work",
        "has_pending_charlie_work": g._pending_combat is not None and g._pending_combat.get("type") == "awaiting_charlie_work",
        "prefight_str_bonus": g._prefight_str_bonus,
        "prefight_monster_str_bonus": g._prefight_monster_str_bonus,
    }
