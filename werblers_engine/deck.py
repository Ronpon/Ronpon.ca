"""Finite deck manager — shuffles and draws from a list of items."""

from __future__ import annotations

import random
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


class Deck(Generic[T]):
    """A finite, shuffleable deck of items.

    When the deck is exhausted, draws return ``None``.
    Optionally supports auto-reshuffle: when enabled, the discard pile
    is reshuffled into a new draw pile whenever the deck runs out.
    """

    def __init__(
        self,
        items: list[T],
        seed: Optional[int] = None,
        auto_reshuffle: bool = False,
    ) -> None:
        self._cards: list[T] = list(items)
        self._discard: list[T] = []
        self._rng = random.Random(seed)
        self._rng.shuffle(self._cards)
        self._auto_reshuffle = auto_reshuffle

    def _try_reshuffle(self) -> None:
        """Move discard pile back into draw pile and shuffle."""
        if self._discard:
            self._cards = self._discard
            self._discard = []
            self._rng.shuffle(self._cards)

    def draw(self) -> Optional[T]:
        """Draw one item from the top, or None if empty."""
        if not self._cards and self._auto_reshuffle:
            self._try_reshuffle()
        if not self._cards:
            return None
        card = self._cards.pop()
        if self._auto_reshuffle:
            self._discard.append(card)
        return card

    def draw_many(self, n: int) -> list[T]:
        """Draw up to *n* items."""
        result: list[T] = []
        for _ in range(n):
            card = self.draw()
            if card is None:
                break
            result.append(card)
        return result

    def put_bottom(self, card: T) -> None:
        """Return a card to the bottom of the draw pile."""
        self._cards.insert(0, card)

    def remaining(self) -> int:
        return len(self._cards)

    def is_empty(self) -> bool:
        return len(self._cards) == 0

    def peek_all(self) -> list:
        """Return remaining cards in draw order (next to be drawn first)."""
        return list(reversed(self._cards))

    def draw_matching(self, predicate, rng: random.Random | None = None) -> Optional[T]:
        """Draw a random item matching *predicate*, or None if none match."""
        candidates = [c for c in self._cards if predicate(c)]
        if not candidates:
            return None
        _rng = rng or random.Random()
        chosen = _rng.choice(candidates)
        self._cards.remove(chosen)
        return chosen
