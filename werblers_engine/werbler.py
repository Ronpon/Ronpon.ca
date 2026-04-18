"""Werbler (final boss) encounter logic."""

from __future__ import annotations

from typing import Callable, Optional

from .types import CombatResult, Curse, GameContext, GameStatus, Monster
from .player import Player
from .combat import resolve_combat
from .deck import Deck
from . import content as C
from . import effects as _fx


def _apply_werbler_modifiers(
    player: Player,
    werbler: Monster,
    log: list[str],
    is_night: bool = False,
) -> tuple[int, int]:
    """Apply a werbler's abilities (combat modifiers only).

    Returns (player_str_mod, monster_str_mod).
    Post-combat loss effects are handled separately.
    """
    wid = werbler.effect_id
    player_mod = 0
    monster_mod = 0

    if wid == "brady":
        # Big and Tall: melee weapons have −3 Str each
        melee_count = sum(1 for w in player.weapons if not w.is_ranged)
        if melee_count:
            penalty = melee_count * 3
            player_mod -= penalty
            log.append(f"  Big and Tall: {melee_count} melee weapon(s) lose {penalty} Str.")
        # Nice Hat: accumulated bonus from prior thefts (display only)
        nice_hat = getattr(werbler, "_brady_nice_hat_bonus", 0)
        if nice_hat:
            log.append(f"  Nice Hat: +{nice_hat} Str from stolen head armour")

    elif wid == "harry":
        # Light it up!: +10 Str during the day
        if not is_night:
            monster_mod += 10
            log.append("  Light it up!: daytime — werbler gains +10 Str.")

    elif wid == "ar_meg_geddon":
        # All-Mother: minions refuse to fight
        minion_str = _fx.total_minion_strength(player)
        if minion_str:
            player_mod -= minion_str
            log.append(
                f"  All-Mother: minions refuse to fight — −{minion_str} Str."
            )

    elif wid == "johnil":
        # Stretchy: 1H weapons have −4 Str each
        one_h = sum(1 for w in player.weapons if w.hands == 1)
        if one_h:
            penalty = one_h * 4
            player_mod -= penalty
            log.append(f"  Stretchy: {one_h} one-handed weapon(s) lose {penalty} Str.")

    return player_mod, monster_mod


def _apply_werbler_loss(
    player: Player,
    werbler: Monster,
    log: list[str],
    monster_deck_l3: Optional[Deck[Monster]] = None,
    curse_deck: Optional[Deck[Curse]] = None,
    select_fn: Optional[Callable] = None,
) -> None:
    """Apply a werbler's on-loss penalty."""
    wid = werbler.effect_id

    if wid == "brady":
        # Nice Hat: steal head armour (max 2 thefts tracked on monster)
        stolen_count = getattr(werbler, "_brady_thefts", 0)
        if stolen_count >= 2:
            log.append("  Nice Hat: Brady has already stolen 2 helmets — ability inactive.")
        elif not player.helmets:
            log.append("  Nice Hat: no head armour to steal (doesn't count towards limit).")
        else:
            helmet = player.helmets.pop(0)
            stolen_str = helmet.strength_bonus
            werbler.strength += stolen_str
            werbler._brady_thefts = stolen_count + 1  # type: ignore[attr-defined]
            werbler._brady_nice_hat_bonus = getattr(werbler, "_brady_nice_hat_bonus", 0) + stolen_str  # type: ignore[attr-defined]
            _fx.refresh_tokens(player)
            log.append(
                f"  Nice Hat: Brady stole {helmet.name} (+{stolen_str} Str)! "
                f"Brady now has {werbler.strength} Str "
                f"({werbler._brady_thefts}/2 thefts)."  # type: ignore[attr-defined]
            )

    elif wid == "harry":
        # Tainted: draw T3 monster card and take its curse
        if monster_deck_l3 and curse_deck:
            m = monster_deck_l3.draw()
            if m and m.curse_name:
                curse = C.curse_for_monster(m)
                if curse:
                    player.curses.append(curse)
                    _fx.refresh_tokens(player)
                    log.append(
                        f"  Tainted: drew {m.name} — gained curse: {curse.name}."
                    )
                else:
                    log.append(f"  Tainted: drew {m.name} but curse not in registry.")
            elif m:
                log.append(f"  Tainted: drew {m.name} but it has no curse.")
            else:
                log.append("  Tainted: no L3 monsters left in deck.")

    elif wid == "ar_meg_geddon":
        # Schmegged: discard chest and leg equipment
        discarded = []
        for item in list(player.chest_armor):
            player.chest_armor.remove(item)
            discarded.append(item.name)
        for item in list(player.leg_armor):
            player.leg_armor.remove(item)
            discarded.append(item.name)
        if discarded:
            _fx.refresh_tokens(player)
            log.append(f"  Schmegged: discarded {', '.join(discarded)}.")
        else:
            log.append("  Schmegged: no chest or leg equipment to discard.")

    elif wid == "johnil":
        # Slurp!: lose 2 traits of player's choice
        if not player.traits:
            log.append("  Slurp!: no traits to lose.")
        elif len(player.traits) <= 2:
            names = [t.name for t in player.traits]
            player.traits.clear()
            _fx.refresh_tokens(player)
            log.append(f"  Slurp!: lost all traits: {', '.join(names)}.")
        else:
            # Interactive selection (via select_fn)
            if select_fn:
                chosen: list = select_fn(
                    player.traits,
                    min(2, len(player.traits)),
                    "Choose 2 traits to lose (Slurp!):",
                )
            else:
                # Fallback: lose the first 2 traits
                chosen = player.traits[:2]
            removed_names = []
            for t in list(chosen):
                if t in player.traits:
                    player.traits.remove(t)
                    _fx.on_trait_lost(player, t, log)
                    removed_names.append(t.name)
            _fx.refresh_tokens(player)
            log.append(f"  Slurp!: lost traits: {', '.join(removed_names)}.")


# ------------------------------------------------------------------
# Main werbler encounter handler
# ------------------------------------------------------------------

def encounter_werbler(
    player: Player,
    werbler: Monster,
    ctx: GameContext,
    *,
    extra_player_strength: int = 0,
    extra_monster_strength: int = 0,
) -> tuple[Optional[CombatResult], GameStatus]:
    """Final boss fight. Win → game won; lose → back to tile 61."""
    log = ctx.log
    is_night = ctx.is_night
    curse_deck = ctx.curse_deck
    select_fn = ctx.select_fn
    monster_deck_l3 = ctx.monster_decks.get(3)

    log.append(f"THE WERBLER: fighting {werbler.name} (str {werbler.strength})")

    # KNEEL! curse: +10 Werbler strength per curse stack
    kneel_count = sum(1 for c in player.curses if c.effect_id == "kneel")
    kneel_bonus = 0
    if kneel_count:
        kneel_bonus = 10 * kneel_count
        log.append(
            f"  KNEEL!: Werbler strength +{kneel_bonus} "
            f"due to {kneel_count} curse(s)!"
        )

    # --- Werbler-specific combat modifiers ---
    player_mod, monster_mod = _apply_werbler_modifiers(
        player, werbler, log, is_night=is_night,
    )
    monster_mod += kneel_bonus

    # Build effective monster
    effective_strength = werbler.strength + monster_mod + extra_monster_strength - player_mod
    effective_strength = max(0, effective_strength)
    effective_werbler = Monster(
        werbler.name, strength=effective_strength, level=werbler.level,
    )
    result = resolve_combat(player, effective_werbler, is_night=is_night, extra_strength=extra_player_strength)

    if result == CombatResult.WIN:
        log.append("  VICTORY! You defeated your Werbler!")
        return result, GameStatus.WON

    elif result == CombatResult.LOSE:
        # --- Leather Daddy: +1 Str token on loss ---
        for t in player.traits:
            if t.effect_id == "leather_daddy":
                t.tokens += 1
                log.append(f"  Leather Daddy: +1 Str token (total: +{t.tokens})")
        # --- KNEEL!: self-removes on Werbler loss ---
        kneel_curses = [c for c in player.curses if c.effect_id == "kneel"]
        if kneel_curses:
            for kc in kneel_curses:
                player.curses.remove(kc)
            log.append(
                f"  KNEEL!: {len(kneel_curses)} curse(s) discarded after Werbler loss."
            )
        # --- Werbler-specific loss effects ---
        _apply_werbler_loss(
            player, werbler, log,
            monster_deck_l3=monster_deck_l3,
            curse_deck=curse_deck,
            select_fn=select_fn,
        )
        # --- Brunhilde: Skimpy Armour ---
        _fx.apply_brunhilde_combat_loss(player, log)
        # Send back to tile 61
        player.position = 61
        log.append("  Defeat! Sent back to tile 61 (start of Level 3).")
        return result, GameStatus.IN_PROGRESS
    else:
        log.append("  Tie \u2014 no progress. Remain on tile 90.")
        return result, GameStatus.IN_PROGRESS
