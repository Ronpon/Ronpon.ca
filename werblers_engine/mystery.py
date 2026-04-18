"""Mystery Square event system.

Each Mystery Square triggers a randomly chosen event with weighted
probabilities.  Events vary by tier (determined by the player's current
board position).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .types import Item, Monster, Trait, Curse, Minion
from .player import Player
from .deck import Deck
from . import content as C
from . import effects as _fx


# ---------------------------------------------------------------------------
# Event definitions
# ---------------------------------------------------------------------------

# Rarity weights — relative probability of each rarity band.
# common=50, uncommon=25, rare=15, very_rare=10  (total 100)

@dataclass
class MysteryEvent:
    """Describes a mystery event to present to the player."""
    event_id: str          # e.g. "mystery_box", "the_wheel", "the_smith"
    name: str              # display name
    tier: int              # 1/2/3 derived from board position
    description: str = ""  # flavour text shown on the modal
    image_name: str = ""   # filename prefix for Events/ images (if different from name)


# Event catalogue with rarity bands
_EVENT_TABLE: list[tuple[str, str, str, str]] = [
    # (event_id, display_name, rarity, image_name)
    ("mystery_box",  "Mystery Box",  "common",   "Mystery Box"),
    ("the_wheel",    "The Wheel",    "common",   "Wheel"),
    ("the_smith",    "The Smith",    "uncommon", "Smith"),
    ("bandits",      "Bandits",      "very_rare", "Bandits"),
    ("thief",        "Thief",        "very_rare", "Thief"),
    ("beggar",       "Beggar",       "uncommon",  "Beggar"),
]

_RARITY_WEIGHTS = {
    "common":    50,
    "uncommon":  25,
    "rare":      15,
    "very_rare": 10,
}


def _get_tier(position: int) -> int:
    if position <= 30:
        return 1
    if position <= 60:
        return 2
    return 3


# ---------------------------------------------------------------------------
# Roll a random event
# ---------------------------------------------------------------------------

def roll_mystery_event(position: int, rng: random.Random | None = None, player=None) -> MysteryEvent:
    """Select a random mystery event weighted by rarity."""
    if rng is None:
        rng = random.Random()

    tier = _get_tier(position)

    # Build filtered event list — skip beggar if already completed
    # Also permanently exclude fairy_king — it is NEVER a standalone random event;
    # it only appears via the beggar's 3rd-gift transformation.
    _NEVER_RANDOM = {"fairy_king"}
    events = [e for e in _EVENT_TABLE if e[0] not in _NEVER_RANDOM]
    if player and getattr(player, "_beggar_completed", False):
        events = [e for e in events if e[0] != "beggar"]

    ids = [e[0] for e in events]
    names = [e[1] for e in events]
    rarities = [e[2] for e in events]
    image_names = [e[3] for e in events]
    weights = [_RARITY_WEIGHTS[r] for r in rarities]

    idx = rng.choices(range(len(ids)), weights=weights, k=1)[0]
    desc = _EVENT_DESCRIPTIONS.get(ids[idx], "")
    return MysteryEvent(
        event_id=ids[idx],
        name=names[idx],
        tier=tier,
        description=desc,
        image_name=image_names[idx],
    )


_EVENT_DESCRIPTIONS = {
    "mystery_box":  "A mysterious chest appears! Wager an item from your pack for a chance at a prize.",
    "the_wheel":    "A great wheel materialises before you! Give it a spin for a free prize!",
    "the_smith":    "A skilled blacksmith offers their services.",
    "bandits":      "Bandits leap from the shadows!",
    "thief":        "A thief slinks out of the darkness!",
    "beggar":       "A ragged beggar approaches you, hand outstretched.",
}


# ---------------------------------------------------------------------------
# Prize pool
# ---------------------------------------------------------------------------

# Prize types returned by _roll_prize:
#   "item"    → (tier_item, None)        — draw from item deck of given tier
#   "monster" → (None, monster_level)     — fight a monster (same or +1 tier)
#   "trait"   → (dead_monster_trait, None)— gain a dead monster's trait
#   "nothing" → (None, None)             — no prize

@dataclass
class Prize:
    prize_type: str       # "item", "monster", "monster_up", "trait", "nothing"
    tier: int = 1         # item tier for "item" prizes
    label: str = ""       # human-readable description


def _roll_prize(tier: int, rng: random.Random) -> Prize:
    """Roll a random prize from the mystery prize table.

    Rarity bands:
      common    (60%): same-tier item
      uncommon  (10%): tier+1 item
      rare      (21%): nothing (8%), curse (7%), trait (6%)
      very_rare ( 9%): tier-3 item
    """
    up_tier = min(tier + 1, 3)
    table = [
        # (prize_type,   tier_offset, label,                          weight)
        ("item",        0, f"Tier {tier} item",                      60),  # common
        ("item_up",     1, f"Tier {up_tier} item",                   10),  # uncommon
        ("nothing",     0, "Nothing!",                                 8),  # rare
        ("curse",       0, "A curse!",                                 7),  # rare
        ("trait",       0, "Dead monster's trait",                     6),  # rare
        ("item_t3",     0, "Tier 3 item",                              9),  # very rare
    ]
    types   = [t[0] for t in table]
    weights = [t[3] for t in table]
    labels  = [t[2] for t in table]

    idx = rng.choices(range(len(types)), weights=weights, k=1)[0]
    p_type = types[idx]
    # Normalise item_up and item_t3 into "item" with the correct tier
    if p_type == "item_up":
        return Prize(prize_type="item", tier=up_tier, label=labels[idx])
    if p_type == "item_t3":
        return Prize(prize_type="item", tier=3, label=labels[idx])
    prize_tier = tier + table[idx][1]
    if prize_tier > 3:
        prize_tier = 3
    return Prize(prize_type=p_type, tier=prize_tier, label=labels[idx])


# ---------------------------------------------------------------------------
# Event resolution helpers
# ---------------------------------------------------------------------------

def resolve_mystery_box(
    player: Player,
    tier: int,
    wager_pack_index: int,
    item_decks: dict[int, Deck],
    monster_decks: dict[int, Deck],
    trait_deck: Deck,
    log: list[str],
    rng: random.Random | None = None,
) -> dict:
    """Mystery Box: player wagers a pack item for a chance at a prize.

    Returns a result dict with keys:
      prize_type, item (if any), monster (if any), trait (if any), label
    """
    if rng is None:
        rng = random.Random()

    # Wager the item — unified index spans pack + consumables + monsters + equipped
    np = len(player.pack)
    nc = len(player.consumables)
    nm = len(player.captured_monsters)
    pack_total = np + nc + nm
    all_equipped = player.helmets + player.chest_armor + player.leg_armor + player.weapons
    total = pack_total + len(all_equipped)
    if wager_pack_index < 0 or wager_pack_index >= total:
        log.append("Mystery Box: invalid wager — no item selected.")
        return {"prize_type": "error"}

    if wager_pack_index < pack_total:
        name = player.evict_pack_slot(wager_pack_index)
        log.append(f"Mystery Box: wagered {name}.")
    else:
        equip_idx = wager_pack_index - pack_total
        item = all_equipped[equip_idx]
        player.unequip(item)
        log.append(f"Mystery Box: wagered {item.name} (equipped).")

    prize = _roll_prize(tier, rng)
    return _materialise_prize(prize, tier, player, item_decks, monster_decks, trait_deck, log, rng)


def resolve_the_wheel(
    player: Player,
    tier: int,
    item_decks: dict[int, Deck],
    monster_decks: dict[int, Deck],
    trait_deck: Deck,
    log: list[str],
    rng: random.Random | None = None,
) -> dict:
    """The Wheel: free spin — no wager required."""
    if rng is None:
        rng = random.Random()
    log.append("The Wheel: spinning!")
    prize = _roll_prize(tier, rng)
    return _materialise_prize(prize, tier, player, item_decks, monster_decks, trait_deck, log, rng)


def resolve_the_smith(
    player: Player,
    tier: int,
    item_decks: dict[int, Deck],
    wager_indices: list[int],
    chosen_equip_index: int,
    log: list[str],
) -> dict:
    """The Smith: trade 3 pack items for one item of the next tier.

    At Tier 3, instead choose an equipped item to receive +3 Str.
    ``wager_indices`` are unified pack indices (sorted descending for safe pop).
    ``chosen_equip_index`` is the index into the player's all-equipped list
    (only used at Tier 3).
    """
    if tier < 3:
        # Trade 3 items from pack (or equipped) for 1 item of tier+1
        if len(wager_indices) < 3:
            log.append("The Smith: need 3 items to trade.")
            return {"prize_type": "error"}
        np = len(player.pack)
        nc = len(player.consumables)
        nm = len(player.captured_monsters)
        pack_total = np + nc + nm
        all_equipped = player.helmets + player.chest_armor + player.leg_armor + player.weapons
        names = []
        # Process in descending order so pack indices stay valid
        for idx in sorted(wager_indices, reverse=True):
            if idx < pack_total:
                name = player.evict_pack_slot(idx)
                if name:
                    names.append(name)
            else:
                equip_idx = idx - pack_total
                if equip_idx < len(all_equipped):
                    item = all_equipped[equip_idx]
                    player.unequip(item)
                    names.append(item.name)
        log.append(f"The Smith: traded {', '.join(names)}.")
        next_tier = min(tier + 1, 3)
        # Smith only gives equip items, never consumables
        reward = None
        skipped: list = []
        for _ in range(50):  # safety limit
            candidate = item_decks[next_tier].draw()
            if candidate is None:
                break
            if candidate.is_consumable:
                skipped.append(candidate)
            else:
                reward = candidate
                break
        # Put skipped consumables back
        for s in skipped:
            item_decks[next_tier].put_bottom(s)
        if reward:
            log.append(f"The Smith: received {reward.name} (Tier {next_tier})!")
            return {"prize_type": "item", "item": reward, "label": f"Tier {next_tier} item"}
        else:
            log.append("The Smith: item deck empty — no reward.")
            return {"prize_type": "nothing", "label": "Deck empty"}
    else:
        # Tier 3: trade 3 pack items AND give +3 Str to a chosen equipped item
        if len(wager_indices) < 3:
            log.append("The Smith: need 3 items to trade.")
            return {"prize_type": "error"}
        np = len(player.pack)
        nc = len(player.consumables)
        nm = len(player.captured_monsters)
        pack_total = np + nc + nm
        names = []
        for idx in sorted(wager_indices, reverse=True):
            if idx < pack_total:
                name = player.evict_pack_slot(idx)
                if name:
                    names.append(name)
        if names:
            log.append(f"The Smith: traded {', '.join(names)}.")
        all_equipped = player.helmets + player.chest_armor + player.leg_armor + player.weapons
        if not all_equipped:
            log.append("The Smith: no equipped items to enhance.")
            return {"prize_type": "nothing", "label": "No items"}
        if chosen_equip_index < 0 or chosen_equip_index >= len(all_equipped):
            log.append("The Smith: invalid item selection.")
            return {"prize_type": "error"}
        item = all_equipped[chosen_equip_index]
        item.strength_bonus += 3
        log.append(f"The Smith: enhanced {item.name} by +3 Str (now +{item.strength_bonus})!")
        return {"prize_type": "smith_enhance", "item_name": item.name, "label": f"+3 Str to {item.name}"}


def resolve_bandits(
    player: Player,
    log: list[str],
) -> dict:
    """Bandits: forced discard of 1 random equipped item. Skip if nothing equipped."""
    all_equipped = player.helmets + player.chest_armor + player.leg_armor + player.weapons
    if not all_equipped:
        log.append("Bandits: you have nothing equipped — the bandits leave you alone!")
        return {"prize_type": "skip", "label": "Bandits leave you alone"}

    rng = random.Random()
    victim = rng.choice(all_equipped)
    player.unequip(victim)
    log.append(f"Bandits: stole your {victim.name}!")
    return {"prize_type": "stolen", "item": victim, "item_name": victim.name, "label": f"Lost {victim.name}"}


def resolve_thief(
    player: Player,
    log: list[str],
) -> dict:
    """Thief: lose all pack items. Skip if pack is empty."""
    pack_count = len(player.pack) + len(player.consumables) + len(player.captured_monsters)
    if pack_count == 0:
        log.append("Thief: your pack is empty — the thief slinks away!")
        return {"prize_type": "skip", "label": "Thief leaves you alone"}

    names = [i.name for i in player.pack] + [c.name for c in player.consumables] + [m.name for m in player.captured_monsters]
    player.pack.clear()
    player.consumables.clear()
    player.captured_monsters.clear()
    log.append(f"Thief: stole everything from your pack! Lost: {', '.join(names)}")
    return {"prize_type": "stolen", "items": names, "label": "Lost all pack items"}


def resolve_beggar(
    player: Player,
    tier: int,
    item_decks: dict[int, Deck],
    give_pack_index: int,
    log: list[str],
) -> dict:
    """Beggar: give an item. Track per-player counter. 3rd gift triggers Fairy King reveal.

    The counter is stored as ``_beggar_gifts`` and ``_beggar_completed`` on the player.
    After the 3rd gift, the beggar transforms into the Fairy King who offers 3 T3 items.
    """
    if getattr(player, "_beggar_completed", False):
        log.append("The beggar has moved on — there is nothing more here.")
        return {"prize_type": "skip", "label": "Beggar has moved on"}

    gifts_so_far = getattr(player, "_beggar_gifts", 0)
    np = len(player.pack)
    nc = len(player.consumables)
    nm = len(player.captured_monsters)
    total = np + nc + nm
    all_equipped = player.helmets + player.chest_armor + player.leg_armor + player.weapons
    total_all = total + len(all_equipped)
    if total_all == 0:
        log.append("Beggar: you have nothing to give — the beggar sighs and shuffles away.")
        return {"prize_type": "skip", "label": "Nothing to give"}

    if give_pack_index < 0 or give_pack_index >= total + len(all_equipped):
        log.append("Beggar: invalid item selection.")
        return {"prize_type": "error"}

    # Give from pack first, then equipped
    if give_pack_index < total:
        name = player.evict_pack_slot(give_pack_index)
        log.append(f"Beggar: you gave {name}.")
    else:
        equip_idx = give_pack_index - total
        item = all_equipped[equip_idx]
        player.unequip(item)
        log.append(f"Beggar: you gave {item.name} (equipped).")

    gifts_so_far += 1
    player._beggar_gifts = gifts_so_far

    if gifts_so_far >= 3:
        # 3rd gift: Fairy King reveal — draw 3 T3 items for player to choose from
        player._beggar_completed = True
        reward_items = []
        for _ in range(3):
            item = item_decks[3].draw()
            if item:
                reward_items.append(item)
        log.append("Beggar transforms into the Fairy King!")
        return {
            "prize_type": "fairy_king_reveal",
            "reward_items": reward_items,
            "label": "The Fairy King reveals himself!",
        }
    else:
        return {
            "prize_type": "beggar_thank",
            "label": "Thank you for your generosity.",
        }


# ---------------------------------------------------------------------------
# Prize materialisation
# ---------------------------------------------------------------------------

def _draw_item_balanced(deck: Deck, rng: random.Random):
    """Draw an item from *deck* with a 50/50 chance of equip vs consumable.

    Falls back to whichever type is still available if one pool is exhausted.
    Returns None only when the deck is completely empty.
    """
    from .types import EquipSlot
    want_consumable = rng.random() < 0.5
    primary = lambda i: i.slot == EquipSlot.CONSUMABLE if want_consumable else i.slot != EquipSlot.CONSUMABLE
    fallback = lambda i: i.slot != EquipSlot.CONSUMABLE if want_consumable else i.slot == EquipSlot.CONSUMABLE
    item = deck.draw_matching(primary, rng)
    if item is None:
        item = deck.draw_matching(fallback, rng)
    return item


def _materialise_prize(
    prize: Prize,
    tier: int,
    player: Player,
    item_decks: dict[int, Deck],
    monster_decks: dict[int, Deck],
    trait_deck: Deck,
    log: list[str],
    rng: random.Random,
) -> dict:
    """Turn an abstract Prize into a concrete result dict."""
    if prize.prize_type == "item":
        item = _draw_item_balanced(item_decks[prize.tier], rng)
        if item:
            log.append(f"  Prize: {item.name} (Tier {prize.tier} item)!")
            return {"prize_type": "item", "item": item, "label": prize.label}
        else:
            log.append("  Prize: item deck empty — nothing.")
            return {"prize_type": "nothing", "label": "Deck empty"}

    elif prize.prize_type == "curse":
        # Pick a monster from the tier-appropriate pool that has a curse
        tier_deck = monster_decks.get(tier)
        tier_pool = tier_deck.peek_all() if tier_deck else []
        monsters_with_curses = [m for m in tier_pool if m.curse_name]
        # Fallback: try all tiers if the tier pool has no cursed monsters
        if not monsters_with_curses:
            for t in (1, 2, 3):
                d = monster_decks.get(t)
                if d:
                    monsters_with_curses = [m for m in d.peek_all() if m.curse_name]
                if monsters_with_curses:
                    break
        if monsters_with_curses:
            import copy as _copy
            chosen_monster = rng.choice(monsters_with_curses)
            curse = C.curse_for_monster(chosen_monster)
            if curse is None:
                curse = _copy.copy(rng.choice(C.CURSE_POOL)) if C.CURSE_POOL else None
                chosen_monster = None
            if curse:
                from .encounters import _apply_curse
                blocked = not _apply_curse(player, curse, None, log)
                curse_label = curse.name if not blocked else f"{curse.name} (Immunized: blocked!)"
                return {
                    "prize_type": "curse",
                    "curse_name": curse.name,
                    "monster_name": chosen_monster.name if chosen_monster else None,
                    "label": f"Curse: {curse_label}",
                    "blocked": blocked,
                }
        import copy as _copy
        if C.CURSE_POOL:
            curse = _copy.copy(rng.choice(C.CURSE_POOL))
            from .encounters import _apply_curse
            blocked = not _apply_curse(player, curse, None, log)
            curse_label = curse.name if not blocked else f"{curse.name} (Immunized: blocked!)"
            return {"prize_type": "curse", "curse_name": curse.name, "label": f"Curse: {curse_label}", "blocked": blocked}
        log.append("  Prize: no curses available — nothing.")
        return {"prize_type": "nothing", "label": "Nothing"}

    elif prize.prize_type == "trait":
        # Draw a random dead monster and give its trait
        all_monsters = []
        for t in (1, 2, 3):
            deck = monster_decks.get(t)
            if deck:
                all_monsters.extend(deck.peek_all())
        monsters_with_traits = [m for m in all_monsters if m.trait_name and m.trait_name != "She's Melting!"]
        if monsters_with_traits:
            chosen = rng.choice(monsters_with_traits)
            trait = C.trait_for_monster(chosen)
            if trait:
                player.traits.append(trait)
                log.append(f"  Oops, it's already dead — take its curse!")
                log.append(f"  You got a dead {chosen.name}! Gained trait: {trait.name}")
                trait_items, trait_minions = _fx.on_trait_gained(player, trait, log)
                player.pending_trait_items.extend(trait_items)
                player.pending_trait_minions.extend(trait_minions)
                _fx.refresh_tokens(player)
                return {"prize_type": "trait", "trait": trait, "monster_name": chosen.name, "label": f"You got a dead {chosen.name}! You got {trait.name}!"}
        # Fallback: draw from trait deck
        trait = trait_deck.draw()
        if trait:
            player.traits.append(trait)
            log.append(f"  Prize: gained random trait '{trait.name}'!")
            trait_items, trait_minions = _fx.on_trait_gained(player, trait, log)
            player.pending_trait_items.extend(trait_items)
            player.pending_trait_minions.extend(trait_minions)
            _fx.refresh_tokens(player)
            return {"prize_type": "trait", "trait": trait, "label": f"Trait: {trait.name}"}
        log.append("  Prize: no traits available — nothing.")
        return {"prize_type": "nothing", "label": "No traits available"}

    else:  # "nothing"
        log.append("  Prize: nothing! Better luck next time.")
        return {"prize_type": "nothing", "label": "Nothing"}
