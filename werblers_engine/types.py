"""Core enums, dataclasses and small value types used across the engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TileType(Enum):
    CHEST = auto()
    MONSTER = auto()
    SHOP = auto()
    BLANK = auto()
    DAY_NIGHT = auto()
    MINIBOSS = auto()
    WERBLER = auto()
    MYSTERY = auto()


class EquipSlot(Enum):
    HELMET = "helmet"
    CHEST = "chest"
    LEGS = "legs"
    WEAPON = "weapon"  # each weapon costs 1 hand
    CONSUMABLE = "consumable"  # consumable items drawn from item pools


class CombatResult(Enum):
    WIN = auto()
    LOSE = auto()
    TIE = auto()


class GameStatus(Enum):
    IN_PROGRESS = auto()
    WON = auto()
    LOST = auto()  # reserved for future use


# ---------------------------------------------------------------------------
# Data classes — Content
# ---------------------------------------------------------------------------

@dataclass
class Item:
    """An equippable item."""
    name: str
    slot: EquipSlot
    strength_bonus: int = 0
    effect_id: str = ""            # hook identifier for item abilities
    weapon_hand_bonus: int = 0     # extra weapon hand slots granted while equipped (e.g. Bionic Arms)
    hands: int = 1                 # hand cost when equipped as a weapon (1 = one-handed, 2 = two-handed)
    locked_by_curse_id: str = ""   # if set, cannot be unequipped while that curse is active
    tokens: int = 0                # event-driven conditional bonus (updated by refresh_tokens)
    is_ranged: bool = False        # True for guns, bows, crossbows, etc.
    is_gun: bool = False           # True for firearms specifically (subset of ranged)
    is_consumable: bool = False    # True for consumable-item wrappers drawn from item pools


@dataclass
class Consumable:
    """A one-use item that can be activated during combat."""
    name: str
    effect_id: str = ""          # "" = legacy strength bonus; see _apply_consumable_effect
    effect_value: int = 0        # e.g. delta for monster_str_mod
    effect_tier: int = 0         # tier for give_curse / gain_trait / capture_monster draws
    strength_bonus: int = 0      # only used when effect_id == ""


@dataclass
class Minion:
    """A companion minion card held in a player's minion area.

    Minions have no slot limit — a player may hold any number.
    Each minion contributes its strength_bonus to the player's total
    strength.  Minions with a special effect_id may interact with
    other minions (e.g. Skeletal Minion buffs all others by +1 Str).
    """
    name: str
    strength_bonus: int = 0
    effect_id: str = ""


@dataclass
class Monster:
    """A monster (or miniboss / Werbler) the player can fight."""
    name: str
    strength: int
    level: int = 1  # 1 (str 1-10), 2 (str 11-20), or 3 (str 21-30)
    description: str = ""         # flavour blurb on the card
    trait_name: str = ""          # name of trait earned on victory
    trait_text: str = ""          # full text of the trait
    curse_name: str = ""          # name of curse suffered on defeat
    curse_text: str = ""          # full text of the curse
    bonus_text: str = ""          # special bonus condition
    active: bool = True           # False = no card yet; excluded from game decks
    effect_id: str = ""           # hook identifier for boss-specific combat modifiers
    bonus_vs_male: int = 0         # extra strength when fighting a male hero


@dataclass
class Trait:
    """A beneficial modifier gained from winning combat."""
    name: str
    effect_id: str = ""            # hook identifier for complex effects
    source_monster: str = ""       # which monster granted this
    strength_bonus: int = 0
    hand_size_bonus: int = 0
    move_bonus: int = 0  # flat bonus added when a movement card is played
    # Inventory slot limit overrides (additive)
    helmet_slot_bonus: int = 0
    chest_slot_bonus: int = 0
    legs_slot_bonus: int = 0
    weapon_hand_bonus: int = 0
    tokens: int = 0                # event-driven conditional bonus (updated by refresh_tokens)


@dataclass
class Curse:
    """A negative modifier gained from losing combat."""
    name: str
    effect_id: str = ""            # hook identifier for complex effects
    source_monster: str = ""       # which monster inflicted this
    linked_item_name: str = ""     # item this curse is anchored to (legacy field, reserved for future use)
    strength_bonus: int = 0   # typically negative
    hand_size_bonus: int = 0  # typically negative or 0
    move_bonus: int = 0
    helmet_slot_bonus: int = 0
    chest_slot_bonus: int = 0
    legs_slot_bonus: int = 0
    weapon_hand_bonus: int = 0
    tokens: int = 0                # event-driven conditional bonus (updated by refresh_tokens)


# ---------------------------------------------------------------------------
# Tile
# ---------------------------------------------------------------------------

@dataclass
class Tile:
    """A single board tile."""
    index: int                     # 1–90
    tile_type: TileType
    revealed: bool = False         # True once explored during daytime
    revealed_night: bool = False   # True once visited at night (not daytime reveal)

    def __repr__(self) -> str:
        vis = "visible" if self.revealed else "hidden"
        return f"Tile({self.index}, {self.tile_type.name}, {vis})"


# ---------------------------------------------------------------------------
# Encounter context
# ---------------------------------------------------------------------------

@dataclass
class GameContext:
    """Lightweight bundle of shared game state passed to encounter functions.

    Replaces the 10+ individual parameters (decks, night flag, callbacks,
    player list) that were threaded through every encounter call.
    """
    log: list[str]
    is_night: bool = False
    players: list = field(default_factory=list)
    decide_fn: Optional[Callable] = None
    select_fn: Optional[Callable] = None
    trait_deck: Optional[object] = None   # Deck[Trait]
    curse_deck: Optional[object] = None   # Deck[Curse]
    item_decks: dict = field(default_factory=dict)    # {level: Deck[Item]}
    monster_decks: dict = field(default_factory=dict)  # {level: Deck[Monster]}

    def others(self, player) -> list:
        """Return all players except *player*."""
        return [p for p in self.players if p is not player]


# ---------------------------------------------------------------------------
# Action result (returned to caller after each turn)
# ---------------------------------------------------------------------------

@dataclass
class TurnResult:
    """Summary of what happened during a turn."""
    turn_number: int
    player_id: int
    card_played: int
    moved_from: int
    moved_to: int
    tile_type_encountered: TileType
    encounter_log: list[str] = field(default_factory=list)
    combat_result: Optional[CombatResult] = None
    game_status: GameStatus = GameStatus.IN_PROGRESS
