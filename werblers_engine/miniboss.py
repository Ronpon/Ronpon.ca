"""Mini-boss encounter logic (Tier 1 & 2 bosses)."""

from __future__ import annotations

from typing import Callable, Optional

from .types import CombatResult, GameContext, Item, Monster
from .player import Player
from .combat import resolve_combat
from .deck import Deck
from . import effects as _fx


# ------------------------------------------------------------------
# Boss combat modifiers
# ------------------------------------------------------------------

def _count_empty_equip_slots(player: Player) -> int:
    """Count unoccupied equipment slots (helmets + chest + legs + free weapon hands)."""
    empty = 0
    empty += max(0, player.helmet_slots - len(player.helmets))
    empty += max(0, player.chest_slots - len(player.chest_armor))
    empty += max(0, player.legs_slots - len(player.leg_armor))
    used_hands = sum(w.hands for w in player.weapons)
    empty += max(0, player.weapon_hands - used_hands)
    return empty


def _apply_miniboss_modifiers(
    player: Player,
    miniboss: Monster,
    log: list[str],
    is_night: bool = False,
) -> tuple[int, int, bool]:
    """Apply a mini-boss's ability (penalty) and weakness (bonus).

    Returns (player_str_mod, monster_str_mod, auto_win).
    """
    pid = miniboss.effect_id
    player_mod = 0
    monster_mod = 0
    auto_win = False

    # ── Tier 1 ─────────────────────────────────────────────────────

    if pid == "shielded_golem":
        # Ability (Armoured): each equipped card grants 1 less Str (min 0 per card)
        all_equipped = player.helmets + player.chest_armor + player.leg_armor + player.weapons
        penalty = sum(min(1, item.strength_bonus) for item in all_equipped)
        if penalty:
            player_mod -= penalty
            log.append(f"  Armoured: {penalty} equipped items each lose 1 Str.")
        # Weakness (Gotta Give 'Er): 2H weapons provide +5 additional Str
        two_h = sum(1 for w in player.weapons if w.hands >= 2)
        if two_h:
            bonus = two_h * 5
            player_mod += bonus
            log.append(f"  Gotta Give 'Er: {two_h} two-handed weapon(s) grant +{bonus} Str.")

    elif pid == "flaming_golem":
        # Ability (My Fajitas!): head+chest armour provide 2 less Str each (min 0)
        for item in player.helmets + player.chest_armor:
            reduction = min(2, item.strength_bonus)
            if reduction:
                player_mod -= reduction
        reduced = sum(min(2, i.strength_bonus) for i in player.helmets + player.chest_armor)
        if reduced:
            log.append(f"  My Fajitas!: head+chest armour lose {reduced} total Str.")
        # Weakness (Ross, Oven Mitts!): gauntlet → auto-win
        for item in player.helmets + player.chest_armor + player.leg_armor + player.weapons:
            if "gauntlet" in item.name.lower():
                auto_win = True
                log.append(f"  Ross, Oven Mitts!: {item.name} is a gauntlet — auto-win!")
                break

    elif pid == "ghostly_golem":
        # Ability (Run awaaaaaay!): handled post-combat (run back 10 on loss)
        # Weakness: if any equipped item has "Iron" in name → auto-win
        for item in player.helmets + player.chest_armor + player.leg_armor + player.weapons:
            if "iron" in item.name.lower():
                auto_win = True
                log.append(
                    f"  I Learned it from Supernatural: {item.name} contains iron — auto-win!"
                )
                break

    elif pid == "goaaaaaaaalem":
        # Ability (Make a Wall): if no free hand slots → −5 Str
        used_hands = sum(w.hands for w in player.weapons)
        if used_hands >= player.weapon_hands:
            player_mod -= 5
            log.append("  Make a Wall: no free hand slots — −5 Str.")
        # Weakness (No Jock): leg armour has ×2 Str (add the base leg str again)
        leg_bonus = sum(item.strength_bonus for item in player.leg_armor)
        if leg_bonus:
            player_mod += leg_bonus
            log.append(f"  No Jock: leg armour doubled — +{leg_bonus} Str.")

    # ── Tier 2 ─────────────────────────────────────────────────────

    elif pid == "sky_dragon":
        # Ability: all weapons except guns provide 0 Str
        non_gun_str = sum(w.strength_bonus for w in player.weapons if not w.is_gun)
        if non_gun_str:
            player_mod -= non_gun_str
            log.append(f"  You Will Not Get This: non-gun weapons lose {non_gun_str} Str.")
        # Weakness: guns provide +5 Str each
        gun_count = sum(1 for w in player.weapons if w.is_gun)
        if gun_count:
            bonus = gun_count * 5
            player_mod += bonus
            log.append(f"  You Got This: {gun_count} gun(s) grant +{bonus} Str.")

    elif pid == "crossroads_demon":
        # Ability (Hypnotic Gaze): if not wearing head armour → −10 Str
        if not player.helmets:
            player_mod -= 10
            log.append("  Hypnotic Gaze: no head armour — −10 Str.")
        # Weakness (A Fair Exchange): handled via pre-combat interactive prompt

    elif pid == "the_watcher":
        # Ability (I Consume All): cannot use consumables — handled by caller
        # (resolve_combat called with use_consumables=False)
        # Weakness (Call of the Void): empty equip slots provide +2 Str each
        empty = _count_empty_equip_slots(player)
        if empty:
            bonus = empty * 2
            player_mod += bonus
            log.append(f"  Call of the Void: {empty} empty slot(s) grant +{bonus} Str.")

    elif pid == "ogre_cutpurse":
        # Ability + Weakness: handled by pre-combat function _ogre_pre_combat
        pass

    return player_mod, monster_mod, auto_win


def _ogre_pre_combat(player: Player, miniboss: Monster, log: list[str]) -> tuple[int, int]:
    """Ogre Cutpurse: discard all pack items; add equipped items' Str to monster.

    Also grants +5 player Str if pack was already empty.
    Returns (monster_str_modifier, player_str_modifier).
    """
    monster_mod = 0
    player_mod = 0
    pack_was_empty = (
        len(player.pack) == 0
        and len(player.captured_monsters) == 0
        and len(player.consumables) == 0
    )

    if pack_was_empty:
        log.append("  Empty-Handed: pack was already empty — +5 Str to player!")
        player_mod = 5
    else:
        # Discard all pack contents
        equip_str_total = 0
        if player.pack:
            for item in player.pack:
                equip_str_total += item.strength_bonus
            names = [i.name for i in player.pack]
            log.append(f"  Ogre Cutpurse: discarded pack items: {', '.join(names)}")
            player.pack.clear()
        if player.captured_monsters:
            names = [m.name for m in player.captured_monsters]
            log.append(f"  Ogre Cutpurse: discarded captured monsters: {', '.join(names)}")
            player.captured_monsters.clear()
        if player.consumables:
            names = [c.name for c in player.consumables]
            log.append(f"  Ogre Cutpurse: discarded consumables: {', '.join(names)}")
            player.consumables.clear()
        if equip_str_total:
            monster_mod += equip_str_total
            log.append(
                f"  Ogre Cutpurse: discarded items add +{equip_str_total} "
                f"Str to the Ogre!"
            )

    return monster_mod, player_mod


# ------------------------------------------------------------------
# Main miniboss encounter handler
# ------------------------------------------------------------------

def encounter_miniboss(
    player: Player,
    miniboss: Monster,
    item_deck: Deck[Item],
    ctx: GameContext,
    *,
    flee: bool = False,
    crossroads_discards: Optional[list[Item]] = None,
    pre_run_ogre: Optional[tuple[int, int]] = None,
    extra_player_strength: int = 0,
    extra_monster_strength: int = 0,
) -> Optional[CombatResult]:
    """Fight a miniboss. Must win to progress. No items are awarded.

    ``pre_run_ogre`` (monster_mod, player_mod): when provided, skip calling
    ``_ogre_pre_combat`` — it was already run at fight-start to update display.
    """
    log = ctx.log
    is_night = ctx.is_night
    # --- Flee check (Billfold: Fly, you dummy!) ---
    if flee and player.hero and player.hero.can_flee_miniboss:
        log.append(
            f"Miniboss: {miniboss.name} (str {miniboss.strength}) \u2014 "
            f"{player.name} flees! No curse received."
        )
        return None  # no combat, caller handles backward move

    log.append(f"Miniboss: fighting {miniboss.name} (str {miniboss.strength})")

    # --- Pre-combat: Ogre Cutpurse pack pillage ---
    if pre_run_ogre is not None:
        # Already run at fight-start (pre-fight display); use stored values.
        ogre_monster_mod, ogre_player_mod_enc = pre_run_ogre
    else:
        ogre_monster_mod, ogre_player_mod_enc = 0, 0
        if miniboss.effect_id == "ogre_cutpurse":
            ogre_monster_mod, ogre_player_mod_enc = _ogre_pre_combat(player, miniboss, log)

    # --- Boss combat modifiers ---
    player_mod, monster_mod, auto_win = _apply_miniboss_modifiers(
        player, miniboss, log, is_night=is_night,
    )
    monster_mod += ogre_monster_mod
    player_mod += ogre_player_mod_enc

    if auto_win:
        result = CombatResult.WIN
        log.append("  AUTO-WIN triggered!")
    else:
        # Build effective monster with modified strength
        effective_strength = miniboss.strength + monster_mod + extra_monster_strength
        # Player modifier applied via a temporary one-shot approach:
        # We adjust monster strength in the opposite direction to avoid
        # touching the player's real combat_strength calculation.
        effective_strength -= player_mod
        effective_strength = max(0, effective_strength)
        effective_monster = Monster(
            miniboss.name, strength=effective_strength, level=miniboss.level,
        )
        result = resolve_combat(player, effective_monster, is_night=is_night, extra_strength=extra_player_strength)

    if result == CombatResult.WIN:
        player.defeated_monsters.add(miniboss.name)
        log.append(f"  Victory over {miniboss.name}!")
        return result

    elif result == CombatResult.LOSE:
        # --- Leather Daddy: +1 Str token on loss ---
        for t in player.traits:
            if t.effect_id == "leather_daddy":
                t.tokens += 1
                log.append(f"  Leather Daddy: +1 Str token (total: +{t.tokens})")
        log.append("  Defeat! You remain on the miniboss tile.")
        # --- Ghostly Golem: run back 10 spaces ---
        if miniboss.effect_id == "ghostly_golem":
            new_pos = max(1, player.position - 10)
            log.append(
                f"  Run awaaaaaay!: sent back 10 spaces to tile {new_pos}."
            )
            player.position = new_pos
        # --- Brunhilde: Skimpy Armour ---
        _fx.apply_brunhilde_combat_loss(player, log)
    else:
        log.append("  Tie \u2014 no progress, remain on tile.")
    return result
