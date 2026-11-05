"""Combat totals shared by previews and resolution (see README.md)."""

from __future__ import annotations

from .types import CombatResult, Monster
from .player import Player


def combat_totals(player, monster, *, is_night=False, extra_strength=0,
                  monster_modifier=0, use_consumables=False):
    """Calculate both sides without spending anything unless explicitly asked."""
    male_bonus = monster.bonus_vs_male if monster.bonus_vs_male and player.hero and player.hero.is_male else 0
    return {
        "player_strength": max(0, player.combat_strength(use_consumables=use_consumables, is_night=is_night) + extra_strength),
        "monster_strength": max(0, max(0, monster.strength + monster_modifier) + male_bonus),
    }


def resolve_combat(
    player: Player,
    monster: Monster,
    use_consumables: bool = False,
    is_night: bool = False,
    extra_strength: int = 0,
    totals: dict | None = None,
) -> CombatResult:
    """Compare player strength to monster strength and return result.

    If ``use_consumables`` is True, all held consumables are spent and
    their bonuses are included in the player's combat strength.
    ``is_night`` is forwarded to combat_strength for night-specific bonuses.
    ``extra_strength`` adds a flat bonus (e.g. pre-fight consumable use).
    """
    values = combat_totals(player, monster, is_night=is_night, extra_strength=extra_strength,
                           use_consumables=use_consumables and not player.auto_loses_next_battle)
    if totals is not None:
        totals.update(values)
    if player.auto_loses_next_battle:
        player.auto_loses_next_battle = False
        return CombatResult.LOSE

    ps, ms = values["player_strength"], values["monster_strength"]

    if ps > ms:
        return CombatResult.WIN
    if ps < ms:
        return CombatResult.LOSE
    return CombatResult.TIE
