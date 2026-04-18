"""Encounter resolution for each tile type --- RULES.md §7."""

from __future__ import annotations

from typing import Callable, Optional

from .types import (
    CombatResult,
    Consumable,
    GameContext,
    GameStatus,
    TileType,
    Trait,
    Curse,
    Item,
    Monster,
)
from .player import Player
from .combat import resolve_combat
from .deck import Deck
from . import content as C
from . import effects as _fx

# Re-export boss/werbler encounter functions so existing callers
# (game.py, tests) can continue using ``enc.encounter_miniboss`` etc.
from .miniboss import (                        # noqa: F401
    encounter_miniboss,
    _apply_miniboss_modifiers,
    _ogre_pre_combat,
    _count_empty_equip_slots,
)
from .werbler import (                         # noqa: F401
    encounter_werbler,
    _apply_werbler_modifiers,
    _apply_werbler_loss,
)


def _pick_random_trait(trait_deck: Deck[Trait]) -> Optional[Trait]:
    return trait_deck.draw()


def _pick_random_curse(curse_deck: Deck[Curse]) -> Optional[Curse]:
    return curse_deck.draw()


def _apply_brunhilde_combat_loss(player: Player, log: list[str]) -> None:
    """Brunhilde: Skimpy Armour --- destroy chest armour on combat loss."""
    _fx.apply_brunhilde_combat_loss(player, log)


# ------------------------------------------------------------------
# Central curse-application guard
# ------------------------------------------------------------------

_FOOTGEAR_CURSE_IDS = {"it_got_in", "need_a_place", "cant_stop_music"}
_WEAPON_DISCARD_CURSE_IDS = {"rust_spreading"}


def _apply_curse(
    player: Player,
    curse: Curse,
    monster: Optional[Monster],
    log: list[str],
    decide_fn: Optional[Callable] = None,
    other_players: Optional[list] = None,
    select_fn: Optional[Callable] = None,
) -> bool:
    """Apply a curse to the player, checking immunity guards first.

    Returns True if the curse was actually applied, False if it was blocked.
    """
    # Phallic Dexterity: block footgear curses
    if curse.effect_id in _FOOTGEAR_CURSE_IDS:
        if any(t.effect_id == "phallic_dexterity" for t in player.traits):
            log.append(f"  Phallic Dexterity: {curse.name} blocked! (footgear immunity)")
            return False

    # Rust Immunity: block weapon-discard curses
    if curse.effect_id in _WEAPON_DISCARD_CURSE_IDS:
        if any(t.effect_id == "rust_immunity" for t in player.traits):
            log.append(f"  Rust Immunity: {curse.name} blocked! (weapon immunity)")
            return False

    # Vaxxed: block Tier 2 curses
    if monster and monster.level == 2:
        if any(t.effect_id == "vaxxed" for t in player.traits):
            log.append(f"  Vaxxed!: {curse.name} blocked! (Tier 2 immunity)")
            return False

    # Immunized: negate next curse (one-shot, consumes trait)
    immunized_idx = next(
        (i for i, t in enumerate(player.traits) if t.effect_id == "immunized"), None
    )
    if immunized_idx is not None:
        consumed = player.traits.pop(immunized_idx)
        _fx.refresh_tokens(player)
        log.append(f"  Immunized: {curse.name} negated! (Immunized trait consumed)")
        return False

    # It's Wriggling: persistent — lose a trait whenever a new curse arrives
    if any(c.effect_id == "its_wriggling" for c in player.curses):
        if player.traits:
            lost = player.traits.pop()
            _fx.refresh_tokens(player)
            log.append(f"  It's Wriggling!: lost trait '{lost.name}' due to new curse.")

    # Apply the curse
    player.curses.append(curse)
    log.append(f"  Gained curse: {curse.name}")
    _fx.on_curse_gained(player, curse, log, decide_fn=decide_fn, other_players=other_players, select_fn=select_fn)
    return True


# ------------------------------------------------------------------
# Item draw hooks (Rake It In, Scavenger)
# ------------------------------------------------------------------

def _check_scavenger(
    player: Player,
    item: Item,
    item_deck: Deck[Item],
    log: list[str],
    decide_fn: Optional[Callable],
) -> Item:
    """Scavenger: may put drawn equip on bottom and draw another."""
    if not decide_fn:
        return item
    if any(t.effect_id == "scavenger" for t in player.traits):
        if decide_fn(f"Scavenger: Put {item.name} back and draw another?", log):
            item_deck.put_bottom(item)
            replacement = item_deck.draw()
            if replacement is not None:
                log.append(f"  Scavenger: {item.name} put back, drew {replacement.name}.")
                return replacement
            log.append("  Scavenger: deck empty after put-back.")
    return item


def _check_rake_it_in(
    player: Player,
    item_deck: Deck[Item],
    log: list[str],
    decide_fn: Optional[Callable],
) -> None:
    """Rake It In: may discard an equipped card to draw a second item."""
    if not decide_fn:
        return
    if not any(t.effect_id == "rake_it_in" for t in player.traits):
        return
    all_equips = player.helmets + player.chest_armor + player.leg_armor + player.weapons
    unlocked = [
        e for e in all_equips
        if not e.locked_by_curse_id
        or not any(c.effect_id == e.locked_by_curse_id for c in player.curses)
    ]
    if not unlocked:
        return
    if decide_fn("Rake It In!: Discard an equipped card to draw a second item?", log):
        discarded = unlocked[0]
        player.unequip(discarded)
        log.append(f"  Rake It In!: discarded {discarded.name}.")
        bonus_item = item_deck.draw()
        if bonus_item is not None:
            bonus_item = _check_scavenger(player, bonus_item, item_deck, log, decide_fn)
            log.append(f"  Rake It In!: drew bonus item {bonus_item.name}.")
            _offer_item(player, bonus_item, log, decide_fn)
        else:
            log.append("  Rake It In!: item deck empty — no bonus draw.")


# ------------------------------------------------------------------
# Pack / item offer helper
# ------------------------------------------------------------------

def _offer_item(
    player: Player,
    item: Item,
    log: list[str],
    decide_fn: Callable[[str, list[str]], bool],
) -> None:
    """Offer an item to the player: equip directly or add to pack.

    Handles all branching for full/empty slots and full/empty pack.
    When a pack item must be chosen to discard, index 0 is used (simulated choice).
    """
    # --- Consumable-item wrapper: add directly to player's consumables list ---
    if item.is_consumable:
        import copy as _copy
        from . import content as _C
        consumable = next((c for c in _C.CONSUMABLE_POOL if c.name == item.name), None)
        if consumable:
            if player.add_consumable_to_pack(_copy.copy(consumable)):
                log.append(f"  {item.name} added to consumables.")
            else:
                log.append(f"  {item.name} (consumable) — pack full, discarded.")
        else:
            log.append(f"  {item.name} (consumable) — unknown type, discarded.")
        return

    # --- Adaptable Blade: choose 1H (+4 Str) or 2H (+8 Str) before anything else ---
    if item.effect_id == "adaptable_blade":
        use_two_handed = decide_fn(
            "Adaptable Blade: Wield two-handed (+8 Str) instead of one-handed (+4 Str)?", log
        )
        if use_two_handed:
            item.hands = 2
            item.strength_bonus = 8
            log.append("  Adaptable Blade: configured as 2H weapon (+8 Str).")
        else:
            item.hands = 1
            item.strength_bonus = 4
            log.append("  Adaptable Blade: configured as 1H weapon (+4 Str).")

    want_equip = decide_fn(f"Equip {item.name} directly? (or add to pack)", log)

    if want_equip:
        if player.can_equip(item):
            player.equip(item)
            log.append(f"  {item.name} equipped.")
        else:
            # Slot full --- negotiate with currently equipped item
            slot_list = player._slot_list(item.slot)
            if not slot_list:
                # Can't equip and nothing to swap (e.g. weapon needs more hands than player has)
                if player.pack_slots_free > 0:
                    player.pack.append(item)
                    log.append(f"  Cannot equip {item.name} — added to pack.")
                else:
                    log.append(f"  Cannot equip {item.name} and pack is full — discarded.")
            else:
                current = slot_list[-1]
                keep_in_pack = decide_fn(
                    f"Slot full. Move {current.name} to pack to make room?", log
                )
                if keep_in_pack:
                    if player.pack_slots_free > 0:
                        player.unequip(current)
                        player.pack.append(current)
                        player.equip(item)
                        log.append(f"  {current.name} moved to pack. {item.name} equipped.")
                    else:
                        # Pack also full — discard first pack item to make room
                        evicted = player.pack.pop(0)
                        log.append(f"  Pack full \u2014 {evicted.name} discarded from pack.")
                        player.unequip(current)
                        player.pack.append(current)
                        player.equip(item)
                        log.append(f"  {current.name} moved to pack. {item.name} equipped.")
                else:
                    # Discard currently-equipped item, equip new
                    player.unequip(current)
                    player.equip(item)
                    log.append(f"  {current.name} discarded. {item.name} equipped.")
    else:
        # Add to pack
        if player.add_to_pack(item):
            log.append(f"  {item.name} added to pack.")
        else:
            # Pack full --- ask to cancel or discard a pack item
            cancel = decide_fn(f"Pack full! Cancel taking {item.name}?", log)
            if cancel:
                log.append(f"  Cancelled \u2014 {item.name} discarded.")
            else:
                evicted = player.pack.pop(0)
                player.pack.append(item)
                log.append(
                    f"  {evicted.name} discarded from pack. {item.name} added to pack."
                )


# ------------------------------------------------------------------
# Consumable phase helpers
# ------------------------------------------------------------------

_CONSUMABLE_PROXIMITY = 5  # max tile distance to allow bystander consumable play


def _apply_consumable_effect(
    consumable: Consumable,
    player: Player,
    active_player: Player,
    monster: Monster,
    ctx: GameContext,
) -> bool:
    """Apply one consumable's effect to the current encounter.

    Returns True if the monster was captured (encounter ends immediately).
    """
    log = ctx.log
    decide_fn = ctx.decide_fn
    select_fn = ctx.select_fn
    monster_decks = ctx.monster_decks or None
    trait_deck = ctx.trait_deck
    curse_deck = ctx.curse_deck
    all_players = ctx.players or [active_player]
    eid = consumable.effect_id

    if eid == "monster_str_mod":
        delta = consumable.effect_value
        old = monster.strength
        monster.strength = max(0, monster.strength + delta)
        sign = "+" if delta >= 0 else ""
        log.append(
            f"  {player.name} used {consumable.name}: "
            f"monster strength {sign}{delta} ({old} \u2192 {monster.strength})."
        )

    elif eid in ("give_curse", "gain_trait"):
        tier = consumable.effect_tier
        deck = monster_decks.get(tier) if monster_decks else None
        drawn = deck.draw() if deck else None
        if drawn is None:
            log.append(f"  {consumable.name}: Tier-{tier} monster deck empty \u2014 no effect.")
            return False
        log.append(f"  {player.name} used {consumable.name}: drew {drawn.name}.")
        if eid == "give_curse":
            curse = (
                C.curse_for_monster(drawn) if drawn.curse_name
                else (curse_deck.draw() if curse_deck else None)
            )
            if curse is None:
                log.append(f"  {consumable.name}: no curse available.")
                return False
            targets = [p for p in all_players if p is not player]
            if targets and select_fn:
                idx = select_fn(
                    f"{consumable.name}: give '{curse.name}' to which player?",
                    [p.name for p in targets], log,
                )
                target = targets[max(0, min(idx, len(targets) - 1))]
            else:
                target = targets[0] if targets else active_player
            others_of_target = [p for p in all_players if p is not target]
            _apply_curse(target, curse, drawn, log,
                         decide_fn=decide_fn, other_players=others_of_target,
                         select_fn=select_fn)
        else:  # gain_trait
            trait = (
                C.trait_for_monster(drawn) if drawn.trait_name
                else (trait_deck.draw() if trait_deck else None)
            )
            if trait is None:
                log.append(f"  {consumable.name}: no trait available.")
                return False
            player.traits.append(trait)
            log.append(f"  {player.name} gained trait '{trait.name}'.")
            trait_items, trait_minions = _fx.on_trait_gained(player, trait, log)
            player.pending_trait_items.extend(trait_items)
            player.pending_trait_minions.extend(trait_minions)
            _fx.refresh_tokens(player)

    elif eid == "capture_monster":
        tier = consumable.effect_tier
        if monster.level != tier:
            log.append(
                f"  {consumable.name} requires a Tier-{tier} monster "
                f"(this is Tier-{monster.level}) \u2014 wasted."
            )
            return False
        if player.add_captured_monster(monster):
            log.append(
                f"  {player.name} captured {monster.name}! "
                f"Added to pack. No trait or curse."
            )
            return True  # encounter ends
        else:
            log.append(
                f"  {player.name}: pack full \u2014 {monster.name} not captured. Wasted."
            )

    return False


def _consumable_phase(
    active_player: Player,
    monster: Monster,
    ctx: GameContext,
) -> bool:
    """Offer consumables to nearby bystanders (one each), then to the active player (loop).

    Returns True if the monster was captured (caller should end the encounter).
    """
    log = ctx.log
    decide_fn = ctx.decide_fn
    select_fn = ctx.select_fn
    all_players = ctx.players or [active_player]
    # Phase 1: bystanders within proximity, in player-list order
    for p in all_players:
        if p is active_player:
            continue
        if abs(p.position - active_player.position) > _CONSUMABLE_PROXIMITY:
            continue
        usable = [c for c in p.consumables if c.effect_id]
        if not usable:
            continue
        if not decide_fn(
            f"{p.name} (tile {p.position}): play a consumable on "
            f"{monster.name} (tile {active_player.position})? (Y/N)",
            log,
        ):
            continue
        names = [c.name for c in usable]
        idx = select_fn(f"{p.name}: choose a consumable:", names, log) if select_fn else 0
        chosen = usable[max(0, min(idx, len(usable) - 1))]
        p.consumables.remove(chosen)
        if _apply_consumable_effect(
            chosen, p, active_player, monster, ctx,
        ):
            return True

    # Phase 2: active player — may play multiple consumables
    while True:
        usable = [c for c in active_player.consumables if c.effect_id]
        if not usable:
            break
        if not decide_fn(
            f"{active_player.name}: play a consumable on {monster.name}? (Y/N)", log
        ):
            break
        names = [c.name for c in usable]
        idx = (
            select_fn(f"{active_player.name}: choose a consumable:", names, log)
            if select_fn else 0
        )
        chosen = usable[max(0, min(idx, len(usable) - 1))]
        active_player.consumables.remove(chosen)
        if _apply_consumable_effect(
            chosen, active_player, active_player, monster, ctx,
        ):
            return True

    return False


# ------------------------------------------------------------------
# Individual encounter handlers
# ------------------------------------------------------------------

def encounter_chest(
    player: Player,
    item_deck: Deck[Item],
    ctx: GameContext,
) -> None:
    """RULES §7.1 --- draw an item, offer equip or pack choice."""
    log = ctx.log
    decide_fn = ctx.decide_fn
    item = item_deck.draw()
    if item is None:
        log.append("Chest: item deck is empty \u2014 nothing to draw.")
        return
    # Scavenger: may reject and draw another
    if decide_fn:
        item = _check_scavenger(player, item, item_deck, log, decide_fn)
    log.append(f"Chest: found {item.name} (+{item.strength_bonus} {item.slot.value})")
    if decide_fn is None:
        # Legacy / test path: auto-equip or discard
        if player.equip(item):
            log.append(f"  {item.name} equipped.")
        else:
            log.append(f"  No {item.slot.value} slot free — {item.name} discarded.")
    else:
        _offer_item(player, item, log, decide_fn)
        # Rake It In: may discard an equip to draw a second item
        _check_rake_it_in(player, item_deck, log, decide_fn)


def encounter_monster(
    player: Player,
    monster_deck: Deck[Monster],
    ctx: GameContext,
    *,
    flee: bool = False,
    pre_drawn_monster: Optional[Monster] = None,
    extra_player_strength: int = 0,
) -> Optional[CombatResult]:
    """RULES §7.2 --- draw monster, resolve combat.

    If ``flee`` is True and the player's hero supports fleeing from
    monsters, the player escapes without penalty (no curse).
    The caller is responsible for moving the player back.

    ``ctx.players`` is the full list (for defeated-monster bonus checks).
    """
    log = ctx.log
    is_night = ctx.is_night
    decide_fn = ctx.decide_fn
    select_fn = ctx.select_fn
    other_players = ctx.others(player)
    all_players = ctx.players or [player]
    trait_deck = ctx.trait_deck
    curse_deck = ctx.curse_deck
    monster = pre_drawn_monster if pre_drawn_monster is not None else monster_deck.draw()
    if monster is None:
        log.append("Monster: monster deck is empty \u2014 no encounter.")
        return None

    # --- Transmogrifier: may redraw monster once ---
    if monster is not None and decide_fn and player.has_equipped_item("transmogrifier"):
        if decide_fn(f"Transmogrifier: Send {monster.name} back and draw a new one?", log):
            original_name = monster.name
            monster_deck.put_bottom(monster)
            replacement = monster_deck.draw()
            if replacement is not None:
                log.append(f"  Transmogrifier: {original_name} sent to bottom, drew {replacement.name}.")
                monster = replacement
            else:
                log.append("  Transmogrifier: unexpected empty deck after put_bottom.")

    # --- Face Mask: auto-win vs Coronavirus ---
    if monster is not None and monster.name == "Coronavirus" and player.has_equipped_item("face_mask"):
        face_mask_item = next(
            (item for item in player.helmets if item.effect_id == "face_mask"), None
        )
        if face_mask_item is not None:
            face_mask_item.tokens += 5
            _fx.refresh_tokens(player)
            player.defeated_monsters.add(monster.name)
            trait = C.trait_for_monster(monster) if monster.trait_name else None
            if trait is None:
                trait = _pick_random_trait(trait_deck)
            if trait:
                player.traits.append(trait)
                log.append(
                    f"  Face Mask: auto-win vs Coronavirus! +5 Str tokens on Face Mask "
                    f"(total: +{face_mask_item.tokens}). Gained trait: {trait.name}"
                )
                trait_items, trait_minions = _fx.on_trait_gained(player, trait, log)
                player.pending_trait_items.extend(trait_items)
                player.pending_trait_minions.extend(trait_minions)
            else:
                log.append(
                    f"  Face Mask: auto-win vs Coronavirus! +5 Str tokens on Face Mask "
                    f"(total: +{face_mask_item.tokens})."
                )
            return CombatResult.WIN

    # --- I See Everything / I'll Come In Again: trait-based monster redraw ---
    if monster is not None and decide_fn:
        for trait_eid in ("i_see_everything", "ill_come_in_again"):
            redraw_trait = next(
                (t for t in player.traits if t.effect_id == trait_eid), None
            )
            if redraw_trait is not None:
                if decide_fn(f"{redraw_trait.name}: Send {monster.name} back and draw another?", log):
                    original_name = monster.name
                    monster_deck.put_bottom(monster)
                    replacement = monster_deck.draw()
                    if replacement is not None:
                        log.append(f"  {redraw_trait.name}: {original_name} sent to bottom, drew {replacement.name}.")
                        monster = replacement
                    break  # only one redraw per encounter

    # --- Flee check (Billfold: Fly, you dummy!) ---
    if flee and player.hero and player.hero.can_flee_monsters:
        log.append(
            f"Monster: {monster.name} (str {monster.strength}) appeared \u2014 "
            f"{player.name} flees! No curse received."
        )
        return None  # no combat result

    # --- Swiftness: may flee any combat (except Werbler) at no cost ---
    if decide_fn and any(t.effect_id == "swiftness" for t in player.traits):
        if decide_fn(f"Swiftness: Flee from {monster.name} at no cost?", log):
            log.append(f"  Swiftness: {player.name} flees from {monster.name}! No combat.")
            return None

    log.append(f"Monster: fighting {monster.name} (str {monster.strength})")

    # --- Pre-combat consumable phase ---
    if decide_fn:
        if _consumable_phase(
            active_player=player,
            monster=monster,
            ctx=ctx,
        ):
            log.append(f"  {monster.name} was captured \u2014 encounter ends.")
            return None

    # --- Rat Smasher: auto-win vs rats or cats ---
    _RAT_CAT_KEYWORDS = ("rat", "cat")
    rat_smasher_active = any(t.effect_id == "rat_smasher" for t in player.traits)
    monster_lower = monster.name.lower()
    if rat_smasher_active and any(kw in monster_lower for kw in _RAT_CAT_KEYWORDS):
        log.append(f"  Rat Smasher: auto-win against {monster.name}!")
        result = CombatResult.WIN
    # --- Creepy Hollywood Exec / Roofie Demon bonus auto-win ---
    elif monster.name == "Creepy Hollywood Exec" and _anyone_defeated(all_players, "Roofie Demon"):
        log.append("  Bonus: Roofie Demon has been defeated \u2014 auto-win!")
        result = CombatResult.WIN
    elif monster.name == "Roofie Demon" and _anyone_defeated(all_players, "Creepy Hollywood Exec"):
        log.append("  Bonus: Creepy Hollywood Exec has been defeated \u2014 auto-win!")
        result = CombatResult.WIN
    else:
        result = _resolve_with_pvp_penalties(player, monster, is_night, other_players, decide_fn, log, extra_player_strength=extra_player_strength)

    # --- Freeze Ray: may discard a movement card to skip trait/curse ---
    freeze_ray_used = False
    if decide_fn and player.has_equipped_item("freeze_ray") and player.movement_hand:
        if decide_fn(
            f"Freeze Ray: Discard a movement card to receive no trait or curse from {monster.name}?",
            log,
        ):
            discarded_card = player.movement_hand.pop(0)
            player.movement_discard.append(discarded_card)
            freeze_ray_used = True
            log.append(
                f"  Freeze Ray: discarded movement card {discarded_card} "
                f"\u2014 {monster.name} is frozen! No trait or curse."
            )

    if not freeze_ray_used:
        if result == CombatResult.WIN:
            player.defeated_monsters.add(monster.name)
            trait = C.trait_for_monster(monster) if monster.trait_name else None
            if trait is None:
                trait = _pick_random_trait(trait_deck)
            if trait:
                player.traits.append(trait)
                log.append(f"  Victory! Gained trait: {trait.name}")
                trait_items, trait_minions = _fx.on_trait_gained(player, trait, log)
                player.pending_trait_items.extend(trait_items)
                player.pending_trait_minions.extend(trait_minions)
            else:
                log.append("  Victory! (no traits left in deck)")
        elif result == CombatResult.LOSE:
            log.append("  Defeat!")
            # --- Leather Daddy: +1 Str token on loss ---
            for t in player.traits:
                if t.effect_id == "leather_daddy":
                    t.tokens += 1
                    log.append(f"  Leather Daddy: +1 Str token (total: +{t.tokens})")
            # --- It's Not Your Fault: may discard to take Trait instead of Curse ---
            not_your_fault = next(
                (t for t in player.traits if t.effect_id == "its_not_your_fault"), None
            )
            skip_curse = False
            if not_your_fault and decide_fn:
                if decide_fn("It's Not Your Fault!: Discard to gain monster's Trait instead?", log):
                    player.traits.remove(not_your_fault)
                    _fx.on_trait_lost(player, not_your_fault, log)
                    _fx.refresh_tokens(player)
                    trait = C.trait_for_monster(monster) if monster.trait_name else None
                    if trait is None:
                        trait = _pick_random_trait(trait_deck)
                    if trait:
                        player.traits.append(trait)
                        log.append(f"  It's Not Your Fault!: gained trait {trait.name} instead of curse!")
                        trait_items, trait_minions = _fx.on_trait_gained(player, trait, log)
                        player.pending_trait_items.extend(trait_items)
                        player.pending_trait_minions.extend(trait_minions)
                    else:
                        log.append("  It's Not Your Fault!: no trait available.")
                    skip_curse = True
            if not skip_curse:
                curse = C.curse_for_monster(monster) if monster.curse_name else None
                if curse is None:
                    curse = _pick_random_curse(curse_deck)
                if curse:
                    _apply_curse(player, curse, monster, log,
                                 decide_fn=decide_fn, other_players=other_players,
                                 select_fn=select_fn)
                else:
                    log.append("  (no curses left in deck)")
            _apply_brunhilde_combat_loss(player, log)
        else:
            log.append("  Tie \u2014 no trait or curse gained.")
    return result


def _anyone_defeated(all_players: Optional[list], monster_name: str) -> bool:
    """Check if any player has defeated a specific monster."""
    if not all_players:
        return False
    return any(monster_name in p.defeated_monsters for p in all_players)


def _resolve_with_pvp_penalties(
    player: Player,
    monster: Monster,
    is_night: bool,
    other_players: Optional[list],
    decide_fn: Optional[Callable],
    log: list[str],
    extra_player_strength: int = 0,
) -> CombatResult:
    """Resolve combat, applying Strong Schlong PvP penalties first."""
    schlong_penalty = 0
    if other_players and decide_fn:
        for opp in other_players:
            schlong_trait = next(
                (t for t in opp.traits if t.effect_id == "strong_schlong" and t.tokens > 0),
                None,
            )
            if schlong_trait:
                if decide_fn(
                    f"Strong Schlong: {opp.name}, spend tokens to weaken {player.name}? "
                    f"({schlong_trait.tokens} tokens, each = -3 Str)",
                    log,
                ):
                    spent = schlong_trait.tokens
                    schlong_trait.tokens = 0
                    penalty = spent * 3
                    schlong_penalty += penalty
                    log.append(
                        f"  Strong Schlong: {opp.name} spent {spent} tokens \u2014 "
                        f"{player.name} gets -{penalty} Str this combat!"
                    )
    if schlong_penalty > 0:
        effective_monster = Monster(
            monster.name, strength=monster.strength + schlong_penalty, level=monster.level
        )
        return resolve_combat(player, effective_monster, is_night=is_night, extra_strength=extra_player_strength)
    return resolve_combat(player, monster, is_night=is_night, extra_strength=extra_player_strength)


def encounter_shop(
    player: Player,
    item_deck: Deck[Item],
    ctx: GameContext,
    choose_index: int = 0,
) -> None:
    """RULES §7.3 --- trade a trait for an item.

    ``choose_index`` selects which of the drawn items the player picks
    (default 0 = first).  In a real game this would be player input.
    The number of items drawn depends on the player's hero
    (Billfold draws 4 instead of 3).
    """
    log = ctx.log
    decide_fn = ctx.decide_fn
    if not player.traits:
        log.append("Shop: no traits to trade \u2014 shop cannot be used.")
        return

    draw_count = player.hero.shop_draw_count if player.hero else 3

    items = item_deck.draw_many(draw_count)
    if not items:
        log.append("Shop: item deck is empty \u2014 nothing to buy.")
        return

    idx = min(choose_index, len(items) - 1)
    chosen = items[idx]
    discarded_trait = player.traits.pop(0)  # discard oldest trait
    _fx.refresh_tokens(player)
    log.append(
        f"Shop: traded trait '{discarded_trait.name}' for {chosen.name}"
    )
    remaining_names = [it.name for it in items if it is not chosen]
    log.append(f"  Remaining items discarded: {remaining_names}")

    # Scavenger: may reject and draw another
    if decide_fn:
        chosen = _check_scavenger(player, chosen, item_deck, log, decide_fn)

    if decide_fn is None:
        # Legacy / test path: auto-equip or discard
        if player.equip(chosen):
            log.append(f"  {chosen.name} equipped.")
        else:
            log.append(f"  No {chosen.slot.value} slot free \u2014 {chosen.name} discarded.")
    else:
        _offer_item(player, chosen, log, decide_fn)
        # Rake It In: may discard an equip to draw a second item
        _check_rake_it_in(player, item_deck, log, decide_fn)


def encounter_blank(log: list[str]) -> None:
    """RULES §7.4 --- no effect."""
    log.append("Blank tile \u2014 nothing happens.")


def encounter_day_night(is_night: bool, log: list[str]) -> bool:
    """RULES §6 --- toggle day/night. Returns new is_night value."""
    new_state = not is_night
    if new_state:
        log.append("Day/Night tile \u2014 night falls! Fog of war descends.")
    else:
        log.append("Day/Night tile \u2014 dawn breaks! Fog lifts.")
    return new_state


