"""Player state and inventory management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .types import Consumable, Curse, EquipSlot, Item, Minion, Monster, Trait
from . import effects as _fx

if TYPE_CHECKING:
    from .heroes import Hero


@dataclass
class Player:
    """Represents a single player in the game."""

    player_id: int = 0
    name: str = "Player"

    position: int = 1
    base_strength: int = 1

    # Equipment slots — None means empty.
    helmets: list[Item] = field(default_factory=list)
    chest_armor: list[Item] = field(default_factory=list)
    leg_armor: list[Item] = field(default_factory=list)
    weapons: list[Item] = field(default_factory=list)

    # Consumables — no slot limit
    consumables: list[Consumable] = field(default_factory=list)

    # Minions — max 6
    minions: list[Minion] = field(default_factory=list)
    MAX_MINIONS: int = 6

    # Pack — stores items not currently equipped (max 3)
    pack: list[Item] = field(default_factory=list)
    captured_monsters: list[Monster] = field(default_factory=list)
    _base_pack_size: int = 3

    # Combat state flags
    auto_loses_next_battle: bool = False

    # Movement discard pile — most recently played card is last (index -1)
    movement_discard: list[int] = field(default_factory=list)
    last_card_played: Optional[int] = None

    # Base slot limits (before modifiers)
    _base_helmet_slots: int = 1
    _base_chest_slots: int = 1
    _base_legs_slots: int = 1
    _base_weapon_hands: int = 2

    traits: list[Trait] = field(default_factory=list)
    curses: list[Curse] = field(default_factory=list)

    movement_hand: list[int] = field(default_factory=list)
    max_hand_size: int = 4

    # Boss defeat tracking (per player in competitive mode)
    miniboss1_defeated: bool = False
    miniboss2_defeated: bool = False

    # Monster defeat tracking (for bonus conditions like Exec/Roofie)
    defeated_monsters: set[str] = field(default_factory=set)

    # Pending movement card draws (e.g. Quite the Setback redraws)
    _pending_movement_draws: int = 0

    # Hero reference (set after creation via assign_hero)
    _hero: Optional[Hero] = field(default=None, repr=False)

    # Gregory: Contagious Mutagen once-per-game tracker
    mutagen_used: bool = False

    # Beggar encounter tracking (per-player, persists across turns)
    _beggar_gifts: int = 0
    _beggar_completed: bool = False

    # Items received from traits that need manual placement by the player
    pending_trait_items: list[Item] = field(default_factory=list)

    # Minions waiting for player to choose a replacement (at cap)
    pending_trait_minions: list[Minion] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Hero assignment
    # ------------------------------------------------------------------

    def assign_hero(self, hero: Hero) -> None:
        """Apply a hero template to this player."""
        from .heroes import Hero as _H  # avoid circular at module level
        self._hero = hero
        self._base_weapon_hands = hero.base_weapon_hands
        self._base_chest_slots = hero.base_chest_slots
        self._base_helmet_slots = hero.base_helmet_slots
        self._base_legs_slots = hero.base_legs_slots
        # Equip starting items
        for item in hero.starting_items:
            self.equip(item)

    @property
    def hero(self) -> Optional[Hero]:
        return self._hero

    # ------------------------------------------------------------------
    # Computed properties (include modifiers from traits / curses)
    # ------------------------------------------------------------------

    def _sum_modifier(self, attr: str) -> int:
        total = 0
        for t in self.traits:
            total += getattr(t, attr, 0)
        for c in self.curses:
            total += getattr(c, attr, 0)
        return total

    @property
    def helmet_slots(self) -> int:
        return max(0, self._base_helmet_slots + self._sum_modifier("helmet_slot_bonus"))

    @property
    def chest_slots(self) -> int:
        return max(0, self._base_chest_slots + self._sum_modifier("chest_slot_bonus"))

    @property
    def legs_slots(self) -> int:
        return max(0, self._base_legs_slots + self._sum_modifier("legs_slot_bonus"))

    @property
    def weapon_hands(self) -> int:
        total = self._base_weapon_hands + self._sum_modifier("weapon_hand_bonus")
        for item in self.helmets + self.chest_armor + self.leg_armor + self.weapons:
            total += item.weapon_hand_bonus
        return max(0, total)

    @property
    def effective_max_hand_size(self) -> int:
        base = max(1, self.max_hand_size + self._sum_modifier("hand_size_bonus"))
        cap = _fx.hand_size_cap(self)
        if cap is not None:
            base = min(base, cap)
        return base

    @property
    def move_bonus(self) -> int:
        return self._sum_modifier("move_bonus")

    @property
    def pack_size(self) -> int:
        if any(c.effect_id == "out_of_phase" for c in self.curses):
            return 1
        return self._base_pack_size

    @property
    def is_rooting_immune(self) -> bool:
        """True when Boots of Rooting are currently equipped."""
        return any(item.effect_id == "boots_of_rooting" for item in self.leg_armor)

    def has_equipped_item(self, effect_id: str) -> bool:
        """Return True if any currently-equipped item has the given effect_id."""
        for item in self.helmets + self.chest_armor + self.leg_armor + self.weapons:
            if item.effect_id == effect_id:
                return True
        return False

    # ------------------------------------------------------------------
    # Strength calculation
    # ------------------------------------------------------------------

    def _chest_armor_strength(self, is_night: bool = False) -> int:
        """Chest armour contribution, with Brunhilde's Skimpy Armour hook."""
        total = 0
        for item in self.chest_armor:
            bonus = item.strength_bonus
            # Brunhilde: Skimpy Armour — chest armour gives minimum +8
            if self._hero and self._hero.has_skimpy_armour:
                bonus = max(bonus, 8)
            total += bonus
        return total

    @property
    def total_strength(self) -> int:
        """Compute total player strength per RULES.md §8 (without consumables)."""
        return self.combat_strength(use_consumables=False, is_night=False)

    def combat_strength(
        self,
        use_consumables: bool = False,
        is_night: bool = False,
    ) -> int:
        """Strength for combat, optionally consuming all held consumables.

        When ``use_consumables`` is True, every consumable's bonus is added
        and the consumable list is cleared (they are one-use).
        ``is_night`` enables Rizzt's Night Stalker bonus.
        """
        s = self.base_strength
        for item in self.helmets + self.leg_armor + self.weapons:
            s += item.strength_bonus
        s += self._chest_armor_strength(is_night)
        s += self._sum_modifier("strength_bonus")
        # Brunhilde: Luscious Locks
        if self._hero and self._hero.has_luscious_locks and len(self.helmets) == 0:
            s += 5
        # Rizzt: Night Stalker — +3 Str during Night
        if self._hero and self._hero.has_night_stalker and is_night:
            s += self._hero.night_stalker_bonus
        # Conditional trait/curse effects
        s += _fx.total_trait_effect_bonus(self)
        s += _fx.total_curse_effect_bonus(self)
        # Conditional item effects
        s += _fx.total_item_effect_bonus(self)
        # Minion strength contributions
        s += _fx.total_minion_strength(self)
        if use_consumables and self.consumables:
            for c in self.consumables:
                s += c.strength_bonus
            self.consumables.clear()
        return max(0, s)

    # ------------------------------------------------------------------
    # Equipment helpers
    # ------------------------------------------------------------------

    def _slot_list(self, slot: EquipSlot) -> list[Item]:
        mapping = {
            EquipSlot.HELMET: self.helmets,
            EquipSlot.CHEST: self.chest_armor,
            EquipSlot.LEGS: self.leg_armor,
            EquipSlot.WEAPON: self.weapons,
            EquipSlot.CONSUMABLE: [],  # consumables are never placed in an equip slot
        }
        return mapping[slot]

    def _slot_limit(self, slot: EquipSlot) -> int:
        mapping = {
            EquipSlot.HELMET: self.helmet_slots,
            EquipSlot.CHEST: self.chest_slots,
            EquipSlot.LEGS: self.legs_slots,
            EquipSlot.WEAPON: self.weapon_hands,
            EquipSlot.CONSUMABLE: 0,  # cannot be equipped
        }
        return mapping[slot]

    def can_equip(self, item: Item) -> bool:
        if item.is_consumable or item.slot == EquipSlot.CONSUMABLE:
            return False  # consumable items go to consumables list, not equip slots
        if item.slot == EquipSlot.WEAPON:
            used = sum(w.hands for w in self.weapons)
            return used + item.hands <= self.weapon_hands
        return len(self._slot_list(item.slot)) < self._slot_limit(item.slot)

    def equip(self, item: Item) -> bool:
        """Equip an item if a slot is available. Returns True on success."""
        if not self.can_equip(item):
            return False
        self._slot_list(item.slot).append(item)
        _fx.refresh_tokens(self)
        return True

    def unequip(self, item: Item) -> bool:
        """Remove an item from its equipped slot. Returns True if found.

        Returns False if the item is locked by an active curse, or if it
        is not currently equipped.
        """
        if item.locked_by_curse_id:
            if any(c.effect_id == item.locked_by_curse_id for c in self.curses):
                return False  # cannot unequip while the anchoring curse is active
        slot_list = self._slot_list(item.slot)
        if item in slot_list:
            slot_list.remove(item)
            _fx.refresh_tokens(self)
            return True
        return False

    def add_to_pack(self, item: Item) -> bool:
        """Add item to pack if space available. Returns True on success."""
        if self.pack_slots_free == 0:
            return False
        self.pack.append(item)
        return True

    @property
    def pack_slots_used(self) -> int:
        """Total occupied pack slots across items, consumables, and captured monsters."""
        return len(self.pack) + len(self.consumables) + len(self.captured_monsters)

    @property
    def pack_slots_free(self) -> int:
        return max(0, self.pack_size - self.pack_slots_used)

    def add_consumable_to_pack(self, c: Consumable) -> bool:
        """Add a consumable to the pack, counting toward the 3-slot limit."""
        if self.pack_slots_free == 0:
            return False
        self.consumables.append(c)
        return True

    def add_captured_monster(self, m: Monster) -> bool:
        """Add a captured monster to the pack, counting toward the 3-slot limit."""
        if self.pack_slots_free == 0:
            return False
        self.captured_monsters.append(m)
        return True

    @property
    def minion_slots_free(self) -> int:
        return max(0, self.MAX_MINIONS - len(self.minions))

    def add_minion(self, minion: Minion, replace_index: int = -1) -> bool:
        """Add a minion, respecting the 6-slot cap.

        If at cap and ``replace_index`` >= 0, replace that minion.
        Returns True if added, False if at cap and no replacement chosen.
        """
        if len(self.minions) < self.MAX_MINIONS:
            self.minions.append(minion)
            return True
        if 0 <= replace_index < len(self.minions):
            self.minions[replace_index] = minion
            return True
        return False

    def evict_pack_slot(self, unified_idx: int) -> Optional[str]:
        """Remove the item at *unified_idx* (pack ++ consumables ++ captured).

        Returns the evicted item's name, or ``None`` when the index is out
        of range.  The unified ordering matches the frontend pack grid.
        """
        np = len(self.pack)
        nc = len(self.consumables)
        nm = len(self.captured_monsters)
        if unified_idx < 0 or unified_idx >= np + nc + nm:
            return None
        if unified_idx < np:
            return self.pack.pop(unified_idx).name
        unified_idx -= np
        if unified_idx < nc:
            return self.consumables.pop(unified_idx).name
        unified_idx -= nc
        return self.captured_monsters.pop(unified_idx).name
