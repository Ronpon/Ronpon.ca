"""Combat resolution — RULES.md §8."""

from __future__ import annotations

from .types import CombatResult, Monster
from .player import Player


def resolve_combat(
    player: Player,
    monster: Monster,
    use_consumables: bool = False,
    is_night: bool = False,
    extra_strength: int = 0,
) -> CombatResult:
    """Compare player strength to monster strength and return result.

    If ``use_consumables`` is True, all held consumables are spent and
    their bonuses are included in the player's combat strength.
    ``is_night`` is forwarded to combat_strength for night-specific bonuses.
    ``extra_strength`` adds a flat bonus (e.g. pre-fight consumable use).
    """
    if player.auto_loses_next_battle:
        player.auto_loses_next_battle = False
        return CombatResult.LOSE

    ps = max(0, player.combat_strength(use_consumables=use_consumables, is_night=is_night) + extra_strength)
    ms = monster.strength

    # Monster bonus vs male heroes (e.g. Penis Fly Trap: +3 vs men)
    if monster.bonus_vs_male and player.hero and player.hero.is_male:
        ms += monster.bonus_vs_male

    if ps > ms:
        return CombatResult.WIN
    if ps < ms:
        return CombatResult.LOSE
    return CombatResult.TIE
