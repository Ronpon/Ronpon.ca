"""Hero definitions and ability hooks.

Each hero is represented as a Hero data object.  Ability logic is
implemented as helper functions keyed by HeroId, called from the
encounter / combat / game modules at the appropriate hook points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from .types import EquipSlot, Item


# ---------------------------------------------------------------------------
# Hero identifiers
# ---------------------------------------------------------------------------

class HeroId(Enum):
    BILLFOLD = auto()
    GREGORY = auto()
    BRUNHILDE = auto()
    RIZZT = auto()


# ---------------------------------------------------------------------------
# Hero definition
# ---------------------------------------------------------------------------

@dataclass
class Hero:
    """Static hero template — assigned to a Player at game start."""
    id: HeroId
    name: str
    title: str
    description: str

    # Slot overrides applied at player creation
    base_weapon_hands: int = 2
    base_chest_slots: int = 1
    base_helmet_slots: int = 1
    base_legs_slots: int = 1

    # Starting items (list of Item objects given at game start)
    starting_items: list[Item] = field(default_factory=list)

    # Ability flags — checked at runtime by various hooks
    shop_draw_count: int = 3        # Billfold overrides to 4
    can_flee_monsters: bool = False  # Billfold = True
    can_flee_miniboss: bool = False  # Billfold = True
    flee_move_back: int = 0         # Billfold = 13
    movement_card_bonus: int = 0    # Billfold = 1 (all movement card values +1)
    has_contagious_mutagen: bool = False   # Gregory = True
    has_luscious_locks: bool = False       # Brunhilde = True
    has_skimpy_armour: bool = False        # Brunhilde = True
    has_night_stalker: bool = False        # Rizzt = True
    night_stalker_bonus: int = 0           # Rizzt = 3
    is_male: bool = True                   # False for Brunhilde


# ---------------------------------------------------------------------------
# Predefined heroes
# ---------------------------------------------------------------------------

DARK_ELF_SCIMITAR = Item(
    name="No'Cappin's Scimitar",
    slot=EquipSlot.WEAPON,
    strength_bonus=6,
    effect_id="nocappins_scimitar",
)


HEROES: dict[HeroId, Hero] = {
    HeroId.BILLFOLD: Hero(
        id=HeroId.BILLFOLD,
        name="Billfold Baggains",
        title="The Merchant-Prince",
        description=(
            "A sharp-eyed halfling merchant-prince draped in velvet and "
            "rings, who claims he's never lost a negotiation in his life."
        ),
        shop_draw_count=4,
        can_flee_monsters=True,
        can_flee_miniboss=True,
        flee_move_back=13,
    ),
    HeroId.GREGORY: Hero(
        id=HeroId.GREGORY,
        name="Gregory",
        title="The Four-Armed Mutant",
        description="A giant mutant with 4 arms.",
        base_weapon_hands=4,
        base_chest_slots=0,
        has_contagious_mutagen=True,
    ),
    HeroId.BRUNHILDE: Hero(
        id=HeroId.BRUNHILDE,
        name="Brunhilde the Bodacious",
        title="The Barbarian",
        description="A busty and beautiful blonde barbarian.",
        has_luscious_locks=True,
        has_skimpy_armour=True,
        is_male=False,
    ),
    HeroId.RIZZT: Hero(
        id=HeroId.RIZZT,
        name="Rizzt No'Cappin",
        title="The Dark Elf Assassin",
        description=(
            "A dark elf assassin who moves as if he belongs to the "
            "night itself."
        ),
        has_night_stalker=True,
        night_stalker_bonus=3,
        starting_items=[
            Item(
                name="No'Cappin's Scimitar",
                slot=EquipSlot.WEAPON,
                strength_bonus=6,
                effect_id="nocappins_scimitar",
            ),
        ],
    ),
}
