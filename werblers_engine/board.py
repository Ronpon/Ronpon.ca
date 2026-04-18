"""Board generation and tile management."""

from __future__ import annotations

import random
from typing import Optional

from .types import Tile, TileType


# Fixed tile assignments
_FIXED_TILES: dict[int, TileType] = {
    1:  TileType.BLANK,    # START tile — always blank, always revealed
    30: TileType.MINIBOSS,
    60: TileType.MINIBOSS,
    90: TileType.WERBLER,
}

# Fixed tile-type counts for the 86 non-fixed tiles (rules.md §1).
# Tile 1 (START) is in _FIXED_TILES, so it is excluded from the pool.
# DayNight tiles are placed one per row by generate_board (9 total).
# The remaining 77 slots are filled from this pool.
_TILE_COUNTS: list[tuple[TileType, int]] = [
    (TileType.MONSTER,   16),
    (TileType.CHEST,     33),
    (TileType.SHOP,      10),
    (TileType.MYSTERY,   18),  # replaces 15 blank + 3 shop
]

# Number of DayNight tiles (exactly 1 per row of 10).
_DAY_NIGHT_PER_BOARD = 9




def generate_board(seed: Optional[int] = None) -> list[Tile]:
    """Create a list of 90 Tile objects (indices 1–90).

    Index 0 of the returned list is a dummy so that ``board[n]`` gives
    tile *n* directly (1-indexed).

    Fixed tiles: 30 → Miniboss, 60 → Miniboss, 90 → Werbler.
    Exactly one DAY_NIGHT tile is placed in each row of 10 tiles (9 total).
    The remaining 77 slots are filled from the pool in _TILE_COUNTS, shuffled.
    DayNight, Miniboss, and Werbler tiles start revealed; all others start hidden.
    """
    rng = random.Random(seed)

    # Build pool of non-fixed, non-DayNight tiles (exactly 78 tiles needed).
    pool: list[TileType] = []
    for tile_type, count in _TILE_COUNTS:
        pool.extend([tile_type] * count)
    assert len(pool) == 77, f"Non-DN pool should be 77, got {len(pool)}"
    rng.shuffle(pool)
    pool_iter = iter(pool)

    # Placeholder at index 0 (unused).
    board: list[Tile] = [Tile(index=0, tile_type=TileType.BLANK, revealed=True)]

    # For each row of 10, pick one non-fixed slot for DAY_NIGHT.
    for row in range(9):
        start = row * 10 + 1
        end = start + 10  # exclusive
        non_fixed = [i for i in range(start, end) if i not in _FIXED_TILES]
        dn_tile = rng.choice(non_fixed)  # tile 1 is in _FIXED_TILES, never chosen here
        for i in range(start, end):
            if i in _FIXED_TILES:
                tile_type = _FIXED_TILES[i]
            elif i == dn_tile:
                tile_type = TileType.DAY_NIGHT
            else:
                tile_type = next(pool_iter)
            always_visible = tile_type in (
                TileType.DAY_NIGHT,
                TileType.MINIBOSS,
                TileType.WERBLER,
            ) or i == 1  # tile 1 (START) is always visible
            board.append(Tile(index=i, tile_type=tile_type, revealed=always_visible))

    return board


def get_level(position: int) -> int:
    """Return the level (1, 2, or 3) for a tile position."""
    if position <= 30:
        return 1
    if position <= 60:
        return 2
    return 3
