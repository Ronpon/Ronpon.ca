"""Effect hooks for monster-specific traits and curses.

Each monster's trait/curse carries an ``effect_id`` string.  Hook
functions keyed by that id are called at the appropriate moments:

* **Strength hooks** — called during combat strength calculation to
  add conditional bonuses (e.g. "+3 Str when wearing no helmet").
* **Movement hooks** — called when a movement card is played to
  modify its value (e.g. "treat all 6s as 1").
* **On-gain hooks** — called once when a trait/curse is first acquired
  (e.g. "discard all weapons", "receive a special item").

Effects that require systems not yet built (minion cards, pack/inventory,
token counters, PvP interactions) are assigned an ``effect_id`` but have
no hook implementation yet — they are logged as "deferred".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from .types import Curse, EquipSlot, Item, Minion, Trait

if TYPE_CHECKING:
    from .player import Player


# ===================================================================
# TRAIT — COMBAT STRENGTH HOOKS
# ===================================================================

def _calloused(player: Player) -> int:
    """Calloused (Nose Goblin): +3 Str when wearing no helmet."""
    return 3 if not player.helmets else 0


def _bde(player: Player) -> int:
    """BDE (Trouser Snake): +5 Str when wearing no leg armour."""
    return 5 if not player.leg_armor else 0


def _tough_skin(player: Player) -> int:
    """Tough Skin (Twisted Treant): +10 Str when you have no Chest armour."""
    return 10 if not player.chest_armor else 0


def _bark_worse_than_bite(player: Player) -> int:
    """Bark Worse Than its Bite (Wood Golem): +3 per empty equip slot."""
    empty = 0
    empty += max(0, player.helmet_slots - len(player.helmets))
    empty += max(0, player.chest_slots - len(player.chest_armor))
    empty += max(0, player.legs_slots - len(player.leg_armor))
    hands_used = sum(getattr(w, 'hands', 1) for w in player.weapons)
    empty += max(0, player.weapon_hands - hands_used)
    return 3 * empty


def _strengthened_by_taint(player: Player) -> int:
    """Strengthened by Taint (J. Dahmer Vampire): +2 per curse."""
    return 2 * len(player.curses)


_TRAIT_TOKEN_HOOKS: dict[str, Callable] = {
    "calloused": _calloused,
    "bde": _bde,
    "tough_skin": _tough_skin,
    "bark_worse_than_bite": _bark_worse_than_bite,
    "strengthened_by_taint": _strengthened_by_taint,
}


# ===================================================================
# CURSE — COMBAT STRENGTH HOOKS
# ===================================================================

def _nevernude(player: Player) -> int:
    """Nevernude (Demonic Analrapist): -5 Str per empty equip slot."""
    empty = 0
    empty += max(0, player.helmet_slots - len(player.helmets))
    empty += max(0, player.chest_slots - len(player.chest_armor))
    empty += max(0, player.legs_slots - len(player.leg_armor))
    hands_used = sum(getattr(w, 'hands', 1) for w in player.weapons)
    empty += max(0, player.weapon_hands - hands_used)
    return -5 * empty


def _facial_coverings(player: Player) -> int:
    """Facial Coverings Required (Coronavirus): -10 Str with no helmet."""
    return -10 if not player.helmets else 0


def _stabbed(player: Player) -> int:
    """Stabbed (Goblin Warrior): -1 Str for every curse afflicting you."""
    return -1 * len(player.curses)


_CURSE_TOKEN_HOOKS: dict[str, Callable] = {
    "nevernude": _nevernude,
    "facial_coverings": _facial_coverings,
    "stabbed": _stabbed,
}


# ===================================================================
# PUBLIC — strength bonus totals
# ===================================================================

def total_trait_effect_bonus(player: Player) -> int:
    """Sum of all conditional trait strength bonuses via event-driven token counts."""
    return sum(t.tokens for t in player.traits)


def total_curse_effect_bonus(player: Player) -> int:
    """Sum of all conditional curse strength bonuses via event-driven token counts."""
    return sum(c.tokens for c in player.curses)


# ===================================================================
# ITEM — COMBAT STRENGTH HOOKS (passive while equipped)
# ===================================================================

def _boots_of_streaking(player: Player) -> int:
    """Boots of Streaking: +13 extra Str (for +20 total) when no other equipment equipped.

    The item's base strength_bonus=7 is already counted in the item loop,
    so this hook adds the difference (+13) when the condition is met.
    """
    if not player.helmets and not player.chest_armor and not player.weapons:
        return 13
    return 0


def _crown_of_thorns(player: Player) -> int:
    """Crown of Thorns: +1 Str per Trait the player holds."""
    return len(player.traits)


def _wizards_robes(player: Player) -> int:
    """Wizard's Robes: +1 Str per Trait the player holds."""
    return len(player.traits)


def _barbarian_armour(player: Player) -> int:
    """Barbarian Armour: +4 extra Str (for +7 total) when a 2H weapon is equipped.

    The item's base strength_bonus=3 is already counted in the item loop,
    so this hook adds +4 when any equipped weapon has hands >= 2.
    """
    if any(item.hands >= 2 for item in player.weapons):
        return 4
    return 0


def _barbarian_sword(player: Player) -> int:
    """Barbarian Sword: +5 extra Str (for +10 total) when no chest or head armour."""
    if not player.chest_armor and not player.helmets:
        return 5
    return 0


def _nocappins_scimitar(player: Player) -> int:
    """No'Cappin's Scimitar: +2 extra Str (for +8 total) when 2 copies equipped."""
    count = sum(1 for w in player.weapons if w.name == "No'Cappin's Scimitar")
    if count >= 2:
        return 2
    return 0


def _mages_gauntlet(player: Player) -> int:
    """Mage's Gauntlet: tokens are accumulated via on-turn discard action.

    This hook simply returns the current token count, which is managed
    by game-level turn logic (discard trait → +1 token).
    """
    # Tokens are set externally; this hook preserves them across refresh.
    gauntlets = [w for w in player.weapons if w.effect_id == "mages_gauntlet"]
    return gauntlets[0].tokens if gauntlets else 0


_ITEM_TOKEN_HOOKS: dict[str, Callable] = {
    "boots_of_streaking": _boots_of_streaking,
    "crown_of_thorns": _crown_of_thorns,
    "wizards_robes": _wizards_robes,
    "barbarian_armour": _barbarian_armour,
    "barbarian_sword": _barbarian_sword,
    "nocappins_scimitar": _nocappins_scimitar,
    "mages_gauntlet": _mages_gauntlet,
}


def total_item_effect_bonus(player: Player) -> int:
    """Sum of all conditional strength bonuses from currently-equipped items via token counts."""
    return sum(
        i.tokens
        for i in player.helmets + player.chest_armor + player.leg_armor + player.weapons
    )


def refresh_tokens(player: Player) -> None:
    """Recompute and update `.tokens` on all traits, curses, and equipped items.

    Must be called whenever equipment, traits, or curses change so that
    token counts stay consistent with the current player state.

    Note: Items without a token hook (e.g. Face Mask) keep their existing
    token count unchanged — those tokens are accumulated via one-time events.
    Traits/curses with manually-managed tokens (e.g. strong_schlong,
    leather_daddy, residuals) also keep their tokens unchanged.
    """
    # Traits/curses whose tokens are managed by game events, not recomputed
    _MANUAL_TRAIT_TOKENS = {"strong_schlong", "leather_daddy", "residuals"}
    _MANUAL_CURSE_TOKENS: set[str] = set()

    for trait in player.traits:
        hook = _TRAIT_TOKEN_HOOKS.get(trait.effect_id)
        if hook is not None:
            trait.tokens = hook(player)
        elif trait.effect_id not in _MANUAL_TRAIT_TOKENS:
            trait.tokens = 0

    for curse in player.curses:
        hook = _CURSE_TOKEN_HOOKS.get(curse.effect_id)
        if hook is not None:
            curse.tokens = hook(player)
        elif curse.effect_id not in _MANUAL_CURSE_TOKENS:
            curse.tokens = 0

    for item in player.helmets + player.chest_armor + player.leg_armor + player.weapons:
        hook = _ITEM_TOKEN_HOOKS.get(item.effect_id)
        if hook is not None:
            item.tokens = hook(player)
        # Items with no hook (e.g. Face Mask) keep their tokens unchanged


def total_minion_strength(player: Player) -> int:
    """Sum of all minion strength bonuses, including inter-minion effects.

    Minion Wrangler (effect_id='minion_wrangler'): each Minion Wrangler
    causes every OTHER minion to provide +2 additional Str.

    You're the Alpha! (effect_id='youre_the_alpha'): +1 Str per minion while trait held.
    The on-gain hook already applies +1 to existing minions; this function adds +1
    for any minion acquired AFTER the trait was gained.
    """
    if not player.minions:
        return 0
    base = sum(m.strength_bonus for m in player.minions)
    wrangler_count = sum(1 for m in player.minions if m.effect_id == "minion_wrangler")
    other_count = len(player.minions) - wrangler_count
    base += wrangler_count * other_count * 2
    return base


# ===================================================================
# MOVEMENT CARD MODIFICATION
# ===================================================================

def modify_movement_value(
    player: Player,
    card_value: int,
    is_night: bool = False,
) -> int:
    """Apply all curse-based movement card modifications.

    Processing order:
    1. Card-value overrides (e.g. 6→1, conditional 1→0)
    2. Additive adjustments (e.g. all cards -1)
    """
    value = card_value
    forced_zero = False

    # --- Phase 1: value overrides ---
    for curse in player.curses:
        eid = curse.effect_id
        if eid == "yer_a_hare" and card_value == 6:
            value = 1
        elif eid == "eughghghghgh":
            if len(player.curses) > len(player.traits) and card_value == 1:
                value = 0
                forced_zero = True

    # --- Phase 2: additive adjustments ---
    adjustment = 0
    for curse in player.curses:
        eid = curse.effect_id
        if eid == "botched_circumcision":
            adjustment -= 1
        elif eid == "scared_of_dark" and is_night:
            adjustment -= 1

    if adjustment and not forced_zero:
        value += adjustment
        # "Botched Circumcision" specifies minimum value of 1
        if any(c.effect_id == "botched_circumcision" for c in player.curses):
            value = max(1, value)
        else:
            value = max(0, value)

    return value


# ===================================================================
# HAND SIZE CAP (curse hooks checked in Player.effective_max_hand_size)
# ===================================================================

def hand_size_cap(player: Player) -> int | None:
    """Return the lowest hard cap on hand size from curses, or None."""
    cap = None
    for curse in player.curses:
        if curse.effect_id == "dude_wheres_my_card":
            limit = 3
            if cap is None or limit < cap:
                cap = limit
    return cap


# ===================================================================
# ON-GAIN: TRAIT
# ===================================================================

def on_trait_gained(player: Player, trait: Trait, log: list[str]) -> tuple[list[Item], list[Minion]]:
    """Apply one-time effects when a trait is first acquired.

    Returns a tuple of (pending_items, pending_minions) — items and minions
    that need manual placement by the player.
    """
    eid = trait.effect_id
    pending_items: list[Item] = []
    pending_minions: list[Minion] = []

    if eid == "ball_and_chain":
        item = Item("Ball and Chain", EquipSlot.WEAPON, strength_bonus=7)
        used_hands = sum(w.hands for w in player.weapons)
        if player.weapon_hands - used_hands >= item.hands:
            player.weapons.append(item)
            log.append("  Ball and Chain: received Ball and Chain (+5 weapon)!")
        else:
            pending_items.append(item)
            log.append("  Ball and Chain: received Ball and Chain (+5 weapon) — no slot available!")

    elif eid == "birdie":
        item = Item("Power Driver", EquipSlot.WEAPON, strength_bonus=10, hands=2)
        used_hands = sum(w.hands for w in player.weapons)
        if player.weapon_hands - used_hands >= item.hands:
            player.weapons.append(item)
            log.append("  You Got a Birdie!: received Power Driver (+10, 2H weapon)!")
        else:
            pending_items.append(item)
            log.append("  You Got a Birdie!: received Power Driver (+10, 2H weapon) — no slot available!")

    elif eid == "kapwing":
        item = Item("Bulletproof Vest", EquipSlot.CHEST, strength_bonus=8)
        if len(player.chest_armor) < player.chest_slots:
            player.chest_armor.append(item)
            log.append("  Kapwing!: received Bulletproof Vest (+6 chest)!")
        else:
            pending_items.append(item)
            log.append("  Kapwing!: received Bulletproof Vest (+6 chest) — no slot available!")

    elif eid == "grown_up":
        m = Minion("Ted Bearson", strength_bonus=3)
        if player.add_minion(m):
            on_minion_gained(player, m, log)
            log.append("  I'm a Grown-up Now!: Ted Bearson (+3 minion) joins your party!")
        else:
            pending_minions.append(m)
            log.append("  I'm a Grown-up Now!: Ted Bearson (+3 minion) — minion slots full, choose one to replace!")

    elif eid == "misunderstood":
        m = Minion("Swamp Friend", strength_bonus=7)
        if player.add_minion(m):
            on_minion_gained(player, m, log)
            log.append("  Misunderstood: Swamp Friend (+7 minion) joins your party!")
        else:
            pending_minions.append(m)
            log.append("  Misunderstood: Swamp Friend (+7 minion) — minion slots full, choose one to replace!")

    elif eid == "alpha":
        m = Minion("Pet Velociraptor", strength_bonus=5)
        if player.add_minion(m):
            on_minion_gained(player, m, log)
            log.append("  Alpha: Pet Velociraptor (+5 minion) joins your party!")
        else:
            pending_minions.append(m)
            log.append("  Alpha: Pet Velociraptor (+5 minion) — minion slots full, choose one to replace!")

    elif eid == "youre_the_alpha":
        # +1 Str to every currently equipped minion (future ones handled in total_minion_strength)
        if player.minions:
            for m in player.minions:
                m.strength_bonus += 1
            log.append(f"  You're the Alpha!: each of your {len(player.minions)} minion(s) gains +1 Str.")
        else:
            log.append("  You're the Alpha!: no minions yet — buff applies when you gain them.")

    elif eid == "new_lord":
        m = Minion("Demon Spawn", strength_bonus=6)
        if player.add_minion(m):
            on_minion_gained(player, m, log)
            log.append("  New Lord: Demon Spawn (+6 minion) joins your party!")
        else:
            pending_minions.append(m)
            log.append("  New Lord: Demon Spawn (+6 minion) — minion slots full, choose one to replace!")

    elif eid == "overlord":
        m = Minion("Minion Wrangler", strength_bonus=3, effect_id="minion_wrangler")
        if player.add_minion(m):
            on_minion_gained(player, m, log)
            log.append("  Overlord: Minion Wrangler (+3, buffs all other minions +2) joins your party!")
        else:
            pending_minions.append(m)
            log.append("  Overlord: Minion Wrangler (+3) — minion slots full, choose one to replace!")

    elif eid == "adorable":
        m = Minion("Cute Gremlin", strength_bonus=2)
        if player.add_minion(m):
            on_minion_gained(player, m, log)
            log.append("  Adorable: Cute Gremlin (+2 minion) joins your party!")
        else:
            pending_minions.append(m)
            log.append("  Adorable: Cute Gremlin (+2 minion) — minion slots full, choose one to replace!")

    elif eid == "shes_melting":
        from .types import Consumable
        vial = Consumable("Vial of Liquid Witch", strength_bonus=10)
        if player.add_consumable_to_pack(vial):
            log.append("  She's Melting!: received Vial of Liquid Witch (consumable, +10 Str in one battle).")
        else:
            log.append("  She's Melting!: received Vial of Liquid Witch — pack full, discarded.")

    elif eid == "strong_schlong":
        trait.tokens = 5
        log.append("  Strong Schlong: 5 Str tokens added to this card.")

    elif eid == "my_hands_awesome":
        # Draw immediately to the new hand size (now 5 = 3 base + 2 bonus)
        new_max = player.effective_max_hand_size
        shortfall = max(0, new_max - len(player.movement_hand))
        if shortfall:
            player._pending_movement_draws += shortfall
            log.append(
                f"  My Hands are Awesome\u2026: drawing {shortfall} card(s) now "
                f"to reach hand size {new_max}!"
            )

    elif eid == "immunized":
        log.append("  Immunized: the next curse you receive will be negated!")

    refresh_tokens(player)
    return pending_items, pending_minions


# ===================================================================
# ON-LOSE: TRAIT / ON-GAIN: MINION
# ===================================================================

def on_trait_lost(player: Player, trait: Trait, log: list[str]) -> None:
    """Undo effects that were applied when a trait was gained."""
    eid = trait.effect_id
    if eid == "youre_the_alpha":
        if player.minions:
            for m in player.minions:
                m.strength_bonus = max(0, m.strength_bonus - 1)
            log.append(
                f"  You're the Alpha! lost: each of your {len(player.minions)} "
                f"minion(s) loses -1 Str."
            )


def on_minion_gained(player: Player, minion: "Minion", log: list[str]) -> None:  # type: ignore[name-defined]
    """Apply per-minion effects when a new minion joins the player's party."""
    if any(t.effect_id == "youre_the_alpha" for t in player.traits):
        minion.strength_bonus += 1
        log.append(f"  You're the Alpha!: {minion.name} gains +1 Str.")


# ===================================================================
# ON-GAIN: CURSE
# ===================================================================

def on_curse_gained(
    player: Player,
    curse: Curse,
    log: list[str],
    decide_fn: Callable[[str, list[str]], bool] | None = None,
    other_players: list[Player] | None = None,
    select_fn: Callable[[str, list[str], list[str]], int] | None = None,
) -> None:
    """Apply one-time effects when a curse is first acquired."""
    eid = curse.effect_id

    # --- Equipment destruction ---
    if eid == "it_got_in":
        if player.leg_armor:
            names = [i.name for i in player.leg_armor]
            player.leg_armor.clear()
            log.append(f"  It Got In!: discarded all footgear: {names}")
        pack_footgear = [i for i in player.pack if i.slot == EquipSlot.LEGS]
        if pack_footgear:
            pack_names = [i.name for i in pack_footgear]
            player.pack = [i for i in player.pack if i.slot != EquipSlot.LEGS]
            log.append(f"  It Got In!: also discarded footgear from pack: {pack_names}")

    elif eid == "botched_circumcision":
        log.append("  Botched Circumcision: all movement cards −1 permanently (min 1).")

    elif eid == "rust_spreading":
        if player.weapons:
            protected = [w for w in player.weapons if w.effect_id == "bloody_stump"]
            removed = [w for w in player.weapons if w.effect_id != "bloody_stump"]
            if removed:
                names = [i.name for i in removed]
                player.weapons[:] = protected
                log.append(f"  The Rust is Spreading!: discarded all weapons: {names}")

    elif eid == "dont_look_up":
        if player.helmets:
            names = [i.name for i in player.helmets]
            player.helmets.clear()
            log.append(f"  Don't look up!: discarded helmet(s): {names}")

    elif eid == "need_a_place":
        if player.leg_armor:
            names = [i.name for i in player.leg_armor]
            player.leg_armor.clear()
            log.append(f"  I Need a Place to Go!: discarded boots: {names}")

    elif eid == "laundry_day":
        packed: list[str] = []
        removed: list[str] = []
        for slot_list in [player.helmets, player.chest_armor, player.leg_armor]:
            for item in list(slot_list):
                if player.pack_slots_free > 0:
                    player.pack.append(item)
                    packed.append(item.name)
                else:
                    removed.append(item.name)
            slot_list.clear()
        if packed:
            log.append(f"  Laundry Day!: armor moved to pack: {packed}")
        if removed:
            log.append(f"  Laundry Day!: armor discarded (no pack room): {removed}")

    elif eid == "smell_wont_come_out":
        discarded = _player_choice_discard_n_equips(player, 2, log, decide_fn, select_fn)
        if discarded:
            log.append(f"  The Smell Won't Come Out!: discarded {len(discarded)} equip(s): {discarded}")

    elif eid == "drink_tastes_funny":
        discarded = _player_choice_discard_n_equips(player, 2, log, decide_fn, select_fn)
        if discarded:
            log.append(f"  My Drink Tastes Funny…: discarded {len(discarded)} equipped card(s): {discarded}")

    elif eid == "shot_through_heart":
        if player.chest_armor:
            names = [i.name for i in player.chest_armor]
            player.chest_armor.clear()
            log.append(f"  Shot Through the Heart!: discarded chest armor: {names}")
        wound = Item("Gunshot Wound", EquipSlot.CHEST, strength_bonus=-3,
                     locked_by_curse_id="shot_through_heart")
        player.chest_armor.append(wound)
        curse.strength_bonus = 0  # penalty comes from the Gunshot Wound item
        log.append("  Shot Through the Heart!: Gunshot Wound (-3 Str, locked) placed in chest slot.")

    elif eid == "the_rack":
        # Discard 1 trait or equip per curse afflicting you
        count = len(player.curses)
        removed_names: list[str] = []
        for _ in range(count):
            if player.traits:
                t = player.traits.pop(0)
                removed_names.append(f"trait:{t.name}")
            else:
                names = _discard_n_equips(player, 1)
                removed_names.extend(names)
        if removed_names:
            log.append(f"  Now, Cardinal, the Rack!: discarded {len(removed_names)}: {removed_names}")

    # --- Move backward ---
    elif eid == "roughing_kicker":
        if player.is_rooting_immune:
            log.append("  Roughing the Kicker!: Boots of Rooting protect you! No movement.")
        else:
            old = player.position
            player.position = max(1, player.position - 15)
            log.append(f"  Roughing the Kicker!: moved back to tile {player.position} (was {old}).")

    elif eid == "blacklisted":
        if player.is_rooting_immune:
            log.append("  Blacklisted!: Boots of Rooting protect you! No movement.")
        else:
            old = player.position
            player.position = 1
            log.append(f"  Blacklisted!: sent back to Start (was tile {old}).")

    elif eid == "quite_setback":
        if player.is_rooting_immune:
            log.append("  Quite the Setback!: Boots of Rooting protect you from moving back!")
        else:
            old = player.position
            player.position = max(1, player.position - 10)
            log.append(f"  Quite the Setback!: moved back to tile {player.position} (was {old}).")
        discarded_count = sum(1 for c in player.movement_hand if c in (3, 4))
        player.movement_hand = [c for c in player.movement_hand if c not in (3, 4)]
        if discarded_count:
            log.append(f"  Quite the Setback!: discarded {discarded_count} movement card(s).")
            player._pending_movement_draws = discarded_count

    # --- Hand size on-gain ---
    elif eid == "dude_wheres_my_card":
        if len(player.movement_hand) > 3:
            excess = len(player.movement_hand) - 3
            player.movement_hand = player.movement_hand[:3]
            log.append(f"  Dude, Where's My Card?: discarded {excess} excess movement card(s).")

    elif eid == "together_forever":
        teddy = Minion("Lonely Teddy", strength_bonus=-2)
        if not player.add_minion(teddy):
            # Forced curse minion — discard weakest positive minion to make room
            weakest_idx = min(range(len(player.minions)), key=lambda i: player.minions[i].strength_bonus)
            old = player.minions[weakest_idx]
            player.minions[weakest_idx] = teddy
            log.append(f"  Together Forever!: {old.name} replaced by Lonely Teddy (-2 Str) — minion slots full!")
        else:
            log.append("  Together Forever!: Lonely Teddy (-2 Str minion) joins your party…")
        on_minion_gained(player, teddy, log)

    elif eid == "dont_get_it_wet_gremlin":
        gremlin = Minion("Crazed Gremlin", strength_bonus=-2)
        if not player.add_minion(gremlin):
            weakest_idx = min(range(len(player.minions)), key=lambda i: player.minions[i].strength_bonus)
            old = player.minions[weakest_idx]
            player.minions[weakest_idx] = gremlin
            log.append(f"  Don't Get it Wet: {old.name} replaced by Crazed Gremlin (-2) — minion slots full!")
        else:
            log.append("  Don't Get it Wet: Crazed Gremlin (-2 minion) joins your party. Oh no.")
        on_minion_gained(player, gremlin, log)

    # --- Pack effects ---
    elif eid in ("flooded_base", "clever_girl"):
        discarded = [item.name for item in player.pack]
        player.pack.clear()
        if discarded:
            log.append(f"  [{curse.name}]: pack cleared — discarded {', '.join(discarded)}.")
        else:
            log.append(f"  [{curse.name}]: pack was already empty.")

    elif eid == "out_of_phase":
        while len(player.pack) > 1:
            evicted = player.pack.pop()
            log.append(f"  [Out of Phase]: {evicted.name} discarded from pack (limit now 1).")
        log.append("  [Out of Phase]: pack limit reduced to 1 for the rest of the game.")

    # --- Auto-lose next battle ---
    elif eid == "cursed_auto_lose":
        player.auto_loses_next_battle = True
        log.append(f"  [{curse.name}]: you will automatically lose your next battle!")

    # (It's Wriggling is now handled as a persistent trigger in encounters.py)

    # --- Its Taking Over: discard all leg and chest armor ---
    elif eid == "its_taking_over":
        discarded: list[str] = []
        if player.leg_armor:
            discarded.extend(i.name for i in player.leg_armor)
            player.leg_armor.clear()
        if player.chest_armor:
            discarded.extend(i.name for i in player.chest_armor)
            player.chest_armor.clear()
        if discarded:
            log.append(f"  It's Taking Over!: discarded legs and chest armour: {discarded}")
        else:
            log.append("  It's Taking Over!: no leg or chest armour equipped \u2014 nothing discarded.")

    # --- Get Rekt: discard highest-Str equipped item immediately ---
    elif eid == "get_rekt":
        all_equipped = player.helmets + player.chest_armor + player.leg_armor + player.weapons
        eligible = [
            i for i in all_equipped
            if not i.locked_by_curse_id
            or not any(c.effect_id == i.locked_by_curse_id for c in player.curses)
        ]
        if eligible:
            best = max(eligible, key=lambda i: i.strength_bonus)
            player.unequip(best)
            log.append(f"  Get Rekt!: {best.name} Discarded.")
        else:
            log.append("  Get Rekt!: no eligible equipped items to discard.")

    # --- Can't Stop the Music: force locked Dancing Shoes to feet ---
    elif eid == "cant_stop_music":
        if player.leg_armor:
            discarded = [item.name for item in player.leg_armor]
            player.leg_armor.clear()
            log.append(f"  Can't Stop the Music!: existing footgear discarded: {discarded}")
        shoes = Item(
            "Dancing Shoes", EquipSlot.LEGS, strength_bonus=1,
            effect_id="dancing_shoes", locked_by_curse_id="cant_stop_music",
        )
        player.leg_armor.append(shoes)
        log.append("  Can't Stop the Music!: Dancing Shoes (+1 Str, locked) materialized on your feet.")

    # --- Drank Blood: force locked Bloody Stump into chosen weapon slot ---
    elif eid == "drank_blood":
        stump = Item(
            "Bloody Stump", EquipSlot.WEAPON, strength_bonus=-3,
            effect_id="bloody_stump", locked_by_curse_id="drank_blood",
        )
        two_handers = [w for w in player.weapons if w.hands >= 2]
        one_handers = [w for w in player.weapons if w.hands == 1]
        if two_handers:
            victim = two_handers[0]
            player.weapons.remove(victim)
            log.append(f"  He Drank Your Blood…: {victim.name} (2H weapon) discarded.")
        elif one_handers:
            if decide_fn and len(one_handers) > 1:
                replace_first = decide_fn(
                    "He Drank Your Blood: Replace first weapon? (No = replace last)", log
                )
                victim = one_handers[0] if replace_first else one_handers[-1]
            else:
                victim = one_handers[-1]
            player.weapons.remove(victim)
            log.append(f"  He Drank Your Blood…: {victim.name} discarded.")
        player.weapons.append(stump)
        log.append("  He Drank Your Blood…: Bloody Stump (-3 Str, locked) forced into weapon slot.")

    # --- Kneel: passive — Werbler gets +10 Str during final fight ---
    elif eid == "kneel":
        log.append("  KNEEL!: The Werbler grows stronger. Your next fight against it will be harder.")

    # --- Walk of Shame: curse adds to the counter but has no effect ---
    elif eid == "walk_of_shame":
        log.append("  [Wait, You Lost to THIS?]: ...nothing happens. Absolutely mortifying.")

    # --- So Lethargic: token drain triggered by game.py when 3/4 is played ---
    # (no on-gain effect; the curse.strength_bonus is decremented in game.py)

    # --- Bad Trip: random card selection enforced by game.py ---
    # (no on-gain effect; game.py checks for this curse during card selection)

    # --- Enslaved: give two items to an opponent ---
    elif eid == "enslaved":
        if not other_players:
            log.append("  Enslaved!: no opponents — skipped.")
        else:
            recipient = other_players[0]
            for _i in range(2):
                giveable = [
                    item for item in (
                        player.helmets + player.chest_armor + player.leg_armor + player.weapons
                    )
                    if not item.locked_by_curse_id
                    or not any(c.effect_id == item.locked_by_curse_id for c in player.curses)
                ] + list(player.pack)
                if not giveable:
                    log.append("  Enslaved!: no more items to give.")
                    break
                chosen = giveable[0]
                if chosen in player.pack:
                    player.pack.remove(chosen)
                else:
                    player.unequip(chosen)
                if recipient.equip(chosen):
                    log.append(f"  Enslaved!: {chosen.name} equipped by {recipient.name}.")
                elif recipient.pack_slots_free > 0:
                    recipient.pack.append(chosen)
                    log.append(f"  Enslaved!: {chosen.name} added to {recipient.name}'s pack.")
                else:
                    log.append(f"  Enslaved!: {chosen.name} discarded (no room for {recipient.name}).")

    # --- You're On the Menu: force Bloody Stump onto arm or boot slot ---
    elif eid == "youre_on_menu":
        if decide_fn:
            use_arm = decide_fn(
                "You're On the Menu: Place Bloody Stump on arm slot? (No = boot slot)", log
            )
        else:
            use_arm = True
        stump = Item(
            "Bloody Stump", EquipSlot.WEAPON, strength_bonus=-2,
            locked_by_curse_id="youre_on_menu",
        )
        if use_arm:
            if player.weapons:
                unlocked = [w for w in player.weapons
                            if not w.locked_by_curse_id
                            or not any(c.effect_id == w.locked_by_curse_id for c in player.curses)]
                if unlocked:
                    victim = unlocked[-1]
                    player.weapons.remove(victim)
                    log.append(f"  You're On the Menu: {victim.name} discarded from weapon slot.")
            player.weapons.append(stump)
            log.append("  You're On the Menu: Bloody Stump (-2 Str, locked) placed in weapon slot.")
        else:
            stump.slot = EquipSlot.LEGS
            if player.leg_armor:
                victim = player.leg_armor[-1]
                player.leg_armor.remove(victim)
                log.append(f"  You're On the Menu: {victim.name} discarded from boot slot.")
            player.leg_armor.append(stump)
            log.append("  You're On the Menu: Bloody Stump (-2 Str, locked) placed in boot slot.")

    refresh_tokens(player)


# ------------------------------------------------------------------
# Hero combat-loss effect
# ------------------------------------------------------------------

def apply_brunhilde_combat_loss(player, log: list[str]) -> None:
    """Brunhilde: Skimpy Armour --- destroy chest armour on combat loss."""
    if player.hero and player.hero.has_skimpy_armour and player.chest_armor:
        destroyed = player.chest_armor.pop(0)
        refresh_tokens(player)
        log.append(
            f"  Skimpy Armour: {destroyed.name} was shredded in defeat and discarded!"
        )


def _player_choice_discard_n_equips(
    player: Player,
    n: int,
    log: list[str],
    decide_fn: Callable[[str, list[str]], bool] | None = None,
    select_fn: Callable[[str, list[str], list[str]], int] | None = None,
) -> list[str]:
    """Discard up to *n* equipped items with player choice.

    When a *select_fn* is provided the full list of discardable items is
    presented at once and the player picks one item per discard (UI-style).
    Falls back to auto-discard (first item) when neither callback is given.
    Items locked by an active curse are always skipped.
    """
    discarded: list[str] = []
    for _ in range(n):
        # Build flat list of all currently-removable equipped items
        candidates: list[Item] = []
        for slot_list in [player.weapons, player.helmets, player.chest_armor, player.leg_armor]:
            for item in list(slot_list):
                locked = (
                    item.locked_by_curse_id
                    and any(c.effect_id == item.locked_by_curse_id for c in player.curses)
                )
                if not locked:
                    candidates.append(item)
        if not candidates:
            break
        if select_fn is not None:
            labels = [f"{item.name} ({item.slot.value})" for item in candidates]
            idx = select_fn(
                f"Select an item to discard ({len(discarded) + 1}/{n}):",
                labels,
                log,
            )
            idx = max(0, min(idx, len(candidates) - 1))
            chosen = candidates[idx]
        else:
            chosen = candidates[0]
        player.unequip(chosen)
        discarded.append(chosen.name)
    return discarded


def _discard_n_equips(player: Player, n: int) -> list[str]:
    """Auto-discard up to *n* equipped items. Returns discarded names.

    Items locked by an active curse are skipped.
    """
    discarded: list[str] = []
    for slot_list in [player.weapons, player.leg_armor, player.chest_armor, player.helmets]:
        removable = [
            item for item in slot_list
            if not item.locked_by_curse_id
            or not any(c.effect_id == item.locked_by_curse_id for c in player.curses)
        ]
        while removable and len(discarded) < n:
            item = removable.pop()
            slot_list.remove(item)
            discarded.append(item.name)
    return discarded
