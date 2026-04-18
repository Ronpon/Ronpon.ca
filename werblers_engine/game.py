"""Game orchestrator — ties board, player, decks, and encounters together.

Supports 1-4 players in competitive mode with fixed turn rotation.
"""

from __future__ import annotations

import random
from typing import Callable, Optional

from .types import (
    CombatResult,
    GameContext,
    GameStatus,
    Tile,
    TileType,
    TurnResult,
    Item,
    Monster,
    Trait,
    Curse,
)
from .board import generate_board, get_level
from .player import Player
from .deck import Deck
from .heroes import Hero, HeroId, HEROES
from . import content as C
from . import encounters as enc
from . import effects as _fx
from .turn import InteractiveTurnMixin




class Game(InteractiveTurnMixin):
    """Top-level game state machine for Werblers (1-4 players, competitive).

    Parameters
    ----------
    num_players :
        Number of players (1-4).  When 1, behaves like the original
        single-player mode.
    hero_ids :
        Optional list of HeroId values, one per player.  If ``None``,
        players have no hero (vanilla stats).  Length must match
        ``num_players`` when provided.
    seed :
        Random seed for reproducible games.
    """

    MAX_PLAYERS = 4

    def __init__(
        self,
        num_players: int = 1,
        hero_ids: Optional[list[HeroId]] = None,
        seed: Optional[int] = None,
    ) -> None:
        if not 1 <= num_players <= self.MAX_PLAYERS:
            raise ValueError(f"num_players must be 1\u2013{self.MAX_PLAYERS}")
        if hero_ids is not None and len(hero_ids) != num_players:
            raise ValueError("hero_ids length must match num_players")

        self.board: list[Tile] = generate_board(seed)
        self.is_night: bool = False
        self.turn_number: int = 0
        self.status: GameStatus = GameStatus.IN_PROGRESS
        self.winner: Optional[int] = None  # player_id of winner

        # --- Players ---
        self.players: list[Player] = []
        for i in range(num_players):
            p = Player(player_id=i, name=f"Player {i + 1}")
            if hero_ids is not None:
                hero = HEROES[hero_ids[i]]
                p.assign_hero(hero)
                p.name = hero.name
            self.players.append(p)

        # Turn rotation (fixed order: 0, 1, 2, ...)
        self._current_player_idx: int = 0

        # --- Shared finite content decks (one per level) ---
        self.monster_decks: dict[int, Deck[Monster]] = {
            1: Deck(list(C.MONSTER_POOL_L1), seed),
            2: Deck(list(C.MONSTER_POOL_L2), seed),
            3: Deck(list(C.MONSTER_POOL_L3), seed),
        }
        self.item_decks: dict[int, Deck[Item]] = {
            1: Deck(list(C.ITEM_POOL_L1), seed),
            2: Deck(list(C.ITEM_POOL_L2), seed),
            3: Deck(list(C.ITEM_POOL_L3), seed),
        }
        self.trait_deck: Deck[Trait] = Deck(list(C.TRAIT_POOL), seed)
        self.curse_deck: Deck[Curse] = Deck(list(C.CURSE_POOL), seed)

        # Each player gets their own movement deck
        self.movement_decks: dict[int, Deck[int]] = {
            i: Deck(list(C.MOVEMENT_DECK), seed, auto_reshuffle=True)
            for i in range(num_players)
        }

        # --- Mini-boss decks (shuffled pools, one active per tier) ---
        self.miniboss_deck_t1: Deck[Monster] = Deck(list(C.MINIBOSS_POOL_T1), seed)
        self.miniboss_deck_t2: Deck[Monster] = Deck(list(C.MINIBOSS_POOL_T2), seed)
        self.active_miniboss_t1: Optional[Monster] = None
        self.active_miniboss_t2: Optional[Monster] = None

        # --- Werbler assignment (random, one per player, all different) ---
        rng = random.Random(seed)
        werbler_pool = list(C.WERBLER_POOL)
        rng.shuffle(werbler_pool)
        self.player_werblers: dict[int, Monster] = {}
        for i, p in enumerate(self.players):
            self.player_werblers[p.player_id] = werbler_pool[i]

        # Simulated yes/no decision toggle for "you may" item prompts.
        # Even counter = Yes, odd counter = No (alternates each prompt).
        self._decision_counter: int = 0

        # Pending offer state — set by begin_move(), consumed by resolve_offer()
        self._pending_offer: Optional[dict] = None

        # Last combat info — set by _resolve_auto_encounter for UI battle scene
        self._last_combat_info: Optional[dict] = None
        # Pending monster combat — set when a monster tile is hit (pre-fight pause)
        self._pending_combat: Optional[dict] = None
        # Extra STR bonus accumulated from consumables used in the pre-fight phase
        self._prefight_str_bonus: int = 0
        # Monster STR modifier accumulated from consumables used in the pre-fight phase
        self._prefight_monster_str_bonus: int = 0
        # Deferred turn advance flag — set when Rake It In draws a chest bonus item
        # that the player must place before the turn ends.
        self._rakeitin_pending_placement: bool = False

    # ------------------------------------------------------------------
    # Convenience --- single-player backward compat
    # ------------------------------------------------------------------

    @property
    def player(self) -> Player:
        """Shortcut for single-player games (returns player 0)."""
        return self.players[0]

    @property
    def current_player(self) -> Player:
        """The player whose turn it is."""
        return self.players[self._current_player_idx]

    # ------------------------------------------------------------------
    # Decision helper (simulated for v0.1 — no real UI yet)
    # ------------------------------------------------------------------

    def _decide(self, prompt: str, log: list[str]) -> bool:
        """Simulated player decision: alternates Yes/No each time it is called.

        In v0.1 with no real UI, this stand-in lets us exercise both branches
        of every 'you may' ability prompt during testing.
        """
        result = self._decision_counter % 2 == 0
        self._decision_counter += 1
        log.append(f"  [Decision] {prompt} \u2192 {'Yes' if result else 'No'}")
        return result

    def _select(self, prompt: str, options: list[str], log: list[str]) -> int:
        """Simulated item selection: always picks the first option (index 0).

        In a real UI this would present a list and wait for the player to click
        a card.  The engine API accepts any callable with the same signature:
        ``(prompt: str, options: list[str], log: list[str]) -> int``
        """
        chosen = options[0] if options else "(none)"
        log.append(f"  [Select] {prompt} \u2192 {chosen}")
        return 0

    # ------------------------------------------------------------------
    # Movement deck helpers
    # ------------------------------------------------------------------

    def draw_movement_cards(self, player: Player) -> None:
        """Draw cards until hand reaches effective_max_hand_size."""
        deck = self.movement_decks[player.player_id]
        while len(player.movement_hand) < player.effective_max_hand_size:
            card = deck.draw()
            if card is None:
                break
            player.movement_hand.append(card)

    # ------------------------------------------------------------------
    # Mage's Gauntlet — explicit turn action
    # ------------------------------------------------------------------

    def use_mages_gauntlet(self, player_id: int, trait_index: int = 0) -> list[str]:
        """Discard a trait to add a +1 Str token to an equipped Mage's Gauntlet.

        Can be called at any time during the current player's turn by a UI.
        Returns log lines describing what happened.
        """
        log: list[str] = []
        player = self.players[player_id]
        gauntlet = next(
            (w for w in player.weapons if w.effect_id == "mages_gauntlet"), None
        )
        if gauntlet is None:
            log.append("Mage's Gauntlet: not equipped.")
            return log
        if not player.traits:
            log.append("Mage's Gauntlet: no traits to discard.")
            return log
        idx = min(trait_index, len(player.traits) - 1)
        discarded_trait = player.traits.pop(idx)
        gauntlet.tokens += 1
        _fx.refresh_tokens(player)
        log.append(
            f"Mage's Gauntlet: discarded '{discarded_trait.name}', "
            f"added +1 Str token (gauntlet total: +{gauntlet.tokens} Str)."
        )
        return log

    # ------------------------------------------------------------------
    # Flee helper (Billfold: Fly, you dummy!)
    # ------------------------------------------------------------------

    def _apply_flee_move_back(self, player: Player, log: list[str]) -> None:
        """Move a player backward after fleeing (Billfold ability)."""
        if player.hero is None:
            return
        move_back = player.hero.flee_move_back
        old_pos = player.position
        new_pos = max(1, old_pos - move_back)
        player.position = new_pos
        log.append(
            f"  Fly, you dummy! {player.name} moves back {old_pos - new_pos} "
            f"spaces to tile {new_pos}."
        )

    # ------------------------------------------------------------------
    # Contagious Mutagen (Gregory)
    # ------------------------------------------------------------------

    def use_contagious_mutagen(
        self,
        source_player_id: int,
        target_player_id: int,
        curse_index: int = 0,
    ) -> list[str]:
        """Gregory's once-per-game ability: remove a curse and give it
        to another player.

        Returns log lines describing what happened.
        """
        log: list[str] = []
        source = self.players[source_player_id]
        target = self.players[target_player_id]

        if source.hero is None or not source.hero.has_contagious_mutagen:
            log.append("This player does not have the Contagious Mutagen ability.")
            return log
        if source.mutagen_used:
            log.append("Contagious Mutagen has already been used this game.")
            return log
        if source_player_id == target_player_id:
            log.append("Cannot target yourself with Contagious Mutagen.")
            return log
        if not source.curses:
            log.append("No curses to transfer.")
            return log

        idx = min(curse_index, len(source.curses) - 1)
        curse = source.curses.pop(idx)
        target.curses.append(curse)
        source.mutagen_used = True
        log.append(
            f"Contagious Mutagen: {source.name} transferred curse "
            f"'{curse.name}' to {target.name}!"
        )
        return log

    # ------------------------------------------------------------------
    # Me Too — PvP trigger when any player discards a curse
    # ------------------------------------------------------------------

    def _check_me_too(self, source_player: Player, log: list[str]) -> None:
        """When a player discards a curse, other players with Me Too may discard one."""
        for p in self.players:
            if p is source_player:
                continue
            me_too = next(
                (t for t in p.traits if t.effect_id == "me_too"), None
            )
            if me_too and p.curses:
                if self._decide(
                    f"Me Too!: {p.name}, discard a curse too?", log
                ):
                    removed = p.curses.pop(0)
                    _fx.refresh_tokens(p)
                    log.append(
                        f"  Me Too!: {p.name} discarded curse '{removed.name}'!"
                    )

    # ------------------------------------------------------------------
    # Turn execution
    # ------------------------------------------------------------------

    def play_turn(
        self,
        card_index: int = 0,
        shop_choice: int = 0,
        flee: bool = False,
    ) -> TurnResult:
        """Execute one full turn for the current player.

        Parameters
        ----------
        card_index:
            Index into the player's movement_hand for the card to play.
        shop_choice:
            If landing on a Shop tile, the index of the item to pick.
        flee:
            If True and the player's hero supports fleeing, the player
            will flee instead of fighting (Billfold ability).

        Returns
        -------
        TurnResult with full log of what happened.
        """
        player = self.current_player

        if self.status != GameStatus.IN_PROGRESS:
            return TurnResult(
                turn_number=self.turn_number,
                player_id=player.player_id,
                card_played=0,
                moved_from=player.position,
                moved_to=player.position,
                tile_type_encountered=self.board[player.position].tile_type,
                encounter_log=["Game is already over."],
                game_status=self.status,
            )

        self.turn_number += 1
        log: list[str] = [f"[{player.name}'s turn]"]

        # 1. Draw movement cards
        self.draw_movement_cards(player)

        # --- Residuals: +1 Str every turn ---
        for trait in player.traits:
            if trait.effect_id == "residuals":
                trait.strength_bonus += 1
                log.append(
                    f"  Residuals: +1 Str token added (total: +{trait.strength_bonus})"
                )

        # --- Eight Lives: offer to discard trait to remove a T1/T2 curse ---
        eight_lives = next(
            (t for t in player.traits if t.effect_id == "eight_lives"), None
        )
        if eight_lives and player.curses and self._decide(
            "Eight Lives: Discard this trait to remove a Tier 1 or 2 curse?", log
        ):
            # Find a T1/T2 curse (source monsters level 1 or 2, or random curses)
            removable = [
                c for c in player.curses
                if not c.source_monster
                or any(
                    m.name == c.source_monster and m.level in (1, 2)
                    for pool in (C.MONSTER_POOL_L1, C.MONSTER_POOL_L2)
                    for m in pool
                )
            ]
            if removable:
                removed = removable[0]
                player.curses.remove(removed)
                player.traits.remove(eight_lives)
                _fx.on_trait_lost(player, eight_lives, log)
                _fx.refresh_tokens(player)
                log.append(f"  Eight Lives: discarded trait, removed curse '{removed.name}'!")
            else:
                log.append("  Eight Lives: no Tier 1/2 curses to remove.")

        # --- Meat's Back On the Menu: PvP — force opponent to discard minion ---
        meat_trait = next(
            (t for t in player.traits if t.effect_id == "meat_on_menu"), None
        )
        other_with_minions = [
            p for p in self.players
            if p is not player and p.minions
        ]
        if meat_trait and other_with_minions and self._decide(
            "Meat's Back On the Menu!: Force an opponent to discard a minion? (+5 Str tokens)", log
        ):
            target = other_with_minions[0]
            if target.minions:
                names = [m.name for m in target.minions]
                idx = self._select(
                    f"Meat's Back On the Menu!: Select one of {target.name}'s minions to discard:",
                    names,
                    log,
                )
                idx = max(0, min(idx, len(target.minions) - 1))
                lost_minion = target.minions.pop(idx)
                meat_trait.tokens += 5
                log.append(
                    f"  Meat's Back On the Menu!: {target.name} lost minion '{lost_minion.name}'. "
                    f"+5 Str tokens (total: +{meat_trait.tokens})."
                )

        # --- Mage's Gauntlet: offer once at start of turn (simulated) ---
        for gauntlet in list(player.weapons):
            if gauntlet.effect_id == "mages_gauntlet" and player.traits:
                if self._decide(
                    f"Mage's Gauntlet: Discard a trait for +1 Str token on {gauntlet.name}?",
                    log,
                ):
                    discarded_trait = player.traits.pop(0)
                    gauntlet.tokens += 1
                    _fx.refresh_tokens(player)
                    log.append(
                        f"  Mage's Gauntlet: discarded '{discarded_trait.name}', "
                        f"added +1 Str token (total: +{gauntlet.tokens} Str)."
                    )

        if not player.movement_hand:
            log.append("No movement cards available \u2014 turn skipped.")
            self._advance_turn()
            return TurnResult(
                turn_number=self.turn_number,
                player_id=player.player_id,
                card_played=0,
                moved_from=player.position,
                moved_to=player.position,
                tile_type_encountered=self.board[player.position].tile_type,
                encounter_log=log,
                game_status=self.status,
            )

        # 2. Movement phase
        # --- Phase Shift: discard equip to toggle day/night ---
        if any(t.effect_id == "phase_shift" for t in player.traits):
            all_equips = (
                player.helmets + player.chest_armor
                + player.leg_armor + player.weapons
            )
            unlocked = [
                e for e in all_equips
                if not e.locked_by_curse_id
                or not any(c.effect_id == e.locked_by_curse_id for c in player.curses)
            ]
            if unlocked and self._decide(
                "Phase Shift: Discard an equip card to toggle day/night?", log
            ):
                discarded = unlocked[0]
                player.unequip(discarded)
                self.is_night = not self.is_night
                _fx.refresh_tokens(player)
                state = "Night" if self.is_night else "Day"
                log.append(f"  Phase Shift: discarded {discarded.name}. Time changed to {state}!")

        # --- Touchdown: may discard trait to teleport to Werbler tile ---
        td_trait = next(
            (t for t in player.traits if t.effect_id == "touchdown"), None
        )
        if td_trait and self._decide(
            "Touchdown!: Discard this trait to teleport to the Werbler tile (tile 90)?", log
        ):
            player.traits.remove(td_trait)
            _fx.on_trait_lost(player, td_trait, log)
            _fx.refresh_tokens(player)
            player.position = 90
            log.append("  Touchdown!: teleported to tile 90 (Werbler)!")
            # Skip normal movement and go directly to encounter
            tile = self.board[90]
            tile.revealed = True
            log.append(f"Tile 90: {tile.tile_type.name}")
            werbler = self.player_werblers.get(player.player_id)
            if werbler is None:
                log.append("No werbler assigned — skipping.")
            else:
                td_ctx = GameContext(
                    log=log,
                    is_night=self.is_night,
                    players=self.players,
                    decide_fn=self._decide,
                    select_fn=self._select,
                    trait_deck=self.trait_deck,
                    curse_deck=self.curse_deck,
                    item_decks=self.item_decks,
                    monster_decks=self.monster_decks,
                )
                combat_result, self.status = enc.encounter_werbler(
                    player, werbler, td_ctx,
                )
            if self.status == GameStatus.WON:
                self.winner = player.player_id
                log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")
            self._advance_turn()
            return TurnResult(
                turn_number=self.turn_number,
                player_id=player.player_id,
                card_played=0,
                moved_from=player.position,
                moved_to=90,
                tile_type_encountered=TileType.WERBLER,
                encounter_log=log,
                combat_result=combat_result,
                game_status=self.status,
            )

        # --- Wheelies: may reuse last played card value instead of playing new ---
        using_wheelies = False
        card_value: int
        if (
            player.last_card_played is not None
            and player.has_equipped_item("wheelies")
        ):
            if self._decide(
                f"Do you want to use Wheelies? (Last card played: {player.last_card_played})",
                log,
            ):
                using_wheelies = True
                card_value = player.last_card_played
                log.append(f"  Wheelies activated! Using last card value: {card_value}")

        if not using_wheelies:
            # Bad Trip curse: movement hand is kept facedown, card played randomly
            if any(c.effect_id == "bad_trip" for c in player.curses):
                idx = random.randrange(len(player.movement_hand))
                log.append("  Bad Trip: cards facedown \u2014 randomly selecting!")
            else:
                idx = min(card_index, len(player.movement_hand) - 1)
            card_value = player.movement_hand.pop(idx)
            # Track to discard pile and record as last played
            player.movement_discard.append(card_value)
            player.last_card_played = card_value

        # --- So Lethargic: -1 Str token when playing a 3 or 4 ---
        if card_value in (3, 4):
            for lethargic_curse in player.curses:
                if lethargic_curse.effect_id == "so_lethargic":
                    lethargic_curse.strength_bonus -= 1
                    log.append(
                        f"  So\u2026 Lethargic\u2026: played a {card_value}, "
                        f"-1 Str token added (now {lethargic_curse.strength_bonus})"
                    )

        # --- Hermes' Shoes: treat 1 or 2 as 4 (optional) ---
        if card_value in (1, 2) and player.has_equipped_item("hermes_shoes"):
            if self._decide(
                f"Do you want to use Hermes' Shoes? (Card value: {card_value} \u2192 4)",
                log,
            ):
                card_value = 4
                log.append("  Hermes' Shoes activated! Movement treated as 4.")

        # --- Boots of Agility: +1 to movement (optional) ---
        if player.has_equipped_item("boots_of_agility"):
            if self._decide(
                "Do you want to use Boots of Agility? (+1 to movement)",
                log,
            ):
                card_value += 1
                log.append(f"  Boots of Agility activated! Movement +1 \u2192 {card_value}")

        # --- Fancy Footwork: optionally reduce movement by 1 or 2 ---
        if any(t.effect_id == "fancy_footwork" for t in player.traits):
            if self._decide("Fancy Footwork: Reduce your movement this turn?", log):
                reduce_two = self._decide(
                    "Fancy Footwork: Reduce by 2? (No = reduce by 1)", log
                )
                reduction = 2 if reduce_two else 1
                card_value = max(0, card_value - reduction)
                log.append(f"  Fancy Footwork: movement reduced by {reduction} \u2192 {card_value}")

        modified_value = _fx.modify_movement_value(player, card_value, self.is_night)
        effective_move = modified_value + player.move_bonus
        effective_move = max(0, effective_move)

        old_pos = player.position
        new_pos = old_pos + effective_move

        # Truncate at miniboss if not defeated.
        # Uses new_pos > 30/60 (not old_pos < 30/60) so that a player who
        # remains ON the miniboss tile after a loss cannot slip past it on
        # their next turn without winning the fight.
        if not player.miniboss1_defeated and new_pos > 30:
            new_pos = 30
        if not player.miniboss2_defeated and new_pos > 60:
            new_pos = 60

        # Truncate at tile 90
        new_pos = min(new_pos, 90)

        player.position = new_pos
        log.append(
            f"Played card {card_value} (effective move {effective_move}): "
            f"tile {old_pos} \u2192 tile {new_pos}"
        )

        # 3. Reveal tile
        tile = self.board[new_pos]
        if not tile.revealed:
            tile.revealed = True
            log.append(f"Tile {new_pos} revealed: {tile.tile_type.name}")
        else:
            log.append(f"Tile {new_pos} already revealed: {tile.tile_type.name}")

        # 4. Determine effective encounter (Night overrides)
        actual_type = tile.tile_type

        if self.is_night and actual_type not in (
            TileType.MINIBOSS,
            TileType.WERBLER,
            TileType.DAY_NIGHT,
        ):
            log.append("  Night override \u2192 treated as Monster encounter.")
            actual_type = TileType.MONSTER

        # 5. Resolve encounter
        combat_result: Optional[CombatResult] = None
        level = get_level(new_pos)

        ctx = GameContext(
            log=log,
            is_night=self.is_night,
            players=self.players,
            decide_fn=self._decide,
            select_fn=self._select,
            trait_deck=self.trait_deck,
            curse_deck=self.curse_deck,
            item_decks=self.item_decks,
            monster_decks=self.monster_decks,
        )

        if actual_type == TileType.CHEST:
            enc.encounter_chest(player, self.item_decks[level], ctx)

        elif actual_type == TileType.MONSTER:
            # --- No More Charlie Work: may draw from next tier ---
            effective_monster_deck = self.monster_decks[level]
            if level < 3 and any(
                t.effect_id == "no_more_charlie_work" for t in player.traits
            ):
                if self._decide(
                    f"No More Charlie Work: Fight from Tier {level + 1} instead of Tier {level}?",
                    log,
                ):
                    effective_monster_deck = self.monster_decks[level + 1]
                    log.append(f"  No More Charlie Work: drawing from Tier {level + 1}!")

            combat_result = enc.encounter_monster(
                player,
                effective_monster_deck,
                ctx,
                flee=flee,
            )
            if flee and combat_result is None and player.hero and player.hero.can_flee_monsters:
                self._apply_flee_move_back(player, log)

        elif actual_type == TileType.SHOP:
            enc.encounter_shop(player, self.item_decks[level], ctx, shop_choice)

        elif actual_type == TileType.BLANK:
            enc.encounter_blank(log)

        elif actual_type == TileType.DAY_NIGHT:
            self.is_night = enc.encounter_day_night(self.is_night, log)

        elif actual_type == TileType.MINIBOSS:
            already_defeated = (
                (new_pos == 30 and player.miniboss1_defeated)
                or (new_pos == 60 and player.miniboss2_defeated)
            )
            if already_defeated:
                log.append("Miniboss already defeated \u2014 no encounter.")
            else:
                # Determine which tier and get/reveal the active miniboss
                if new_pos == 30:
                    if self.active_miniboss_t1 is None:
                        self.active_miniboss_t1 = self.miniboss_deck_t1.draw()
                    miniboss = self.active_miniboss_t1
                    reward_deck = self.item_decks[2]  # T1 boss → T2 reward
                else:
                    if self.active_miniboss_t2 is None:
                        self.active_miniboss_t2 = self.miniboss_deck_t2.draw()
                    miniboss = self.active_miniboss_t2
                    reward_deck = self.item_decks[3]  # T2 boss → T3 reward

                if miniboss is None:
                    # All bosses for this tier defeated; player passes freely
                    log.append("All minibosses for this tier have been defeated!")
                    if new_pos == 30:
                        player.miniboss1_defeated = True
                    else:
                        player.miniboss2_defeated = True
                else:
                    combat_result = enc.encounter_miniboss(
                        player, miniboss, reward_deck, ctx,
                        flee=flee,
                    )
                    if flee and combat_result is None and player.hero and player.hero.can_flee_miniboss:
                        self._apply_flee_move_back(player, log)
                    elif combat_result == CombatResult.WIN:
                        if new_pos == 30:
                            player.miniboss1_defeated = True
                            self.active_miniboss_t1 = None  # defeated → next visitor reveals new one
                        else:
                            player.miniboss2_defeated = True
                            self.active_miniboss_t2 = None

        elif actual_type == TileType.WERBLER:
            # Cannot flee the Werbler
            werbler = self.player_werblers.get(player.player_id)
            if werbler is None:
                log.append("No werbler assigned — skipping.")
            else:
                combat_result, self.status = enc.encounter_werbler(
                    player, werbler, ctx,
                )
                if self.status == GameStatus.WON:
                    self.winner = player.player_id

        # --- Pending movement draws (Quite the Setback, My Hands are Awesome, etc.) ---
        while player._pending_movement_draws > 0:
            card = self.movement_decks[player.player_id].draw()
            if card is not None:
                player.movement_hand.append(card)
                log.append(f"  Drew movement card {card} (pending draw).")
            player._pending_movement_draws -= 1

        # --- Me Too: when an opponent loses a curse, player with Me Too may discard one ---
        if len(self.players) > 1:
            for other in self.players:
                if other is player:
                    continue
                me_too = next(
                    (t for t in other.traits if t.effect_id == "me_too"), None
                )
                if me_too and other.curses:
                    # "When another player discards a curse, discard one of yours too"
                    # For now, trigger once per turn if the active player lost any curse
                    # (covers combat-loss curse removal via It's Not Your Fault, Kamikaze Gun, etc.)
                    if self._decide(
                        f"Me Too!: {other.name}, discard one of your curses? "
                        f"(triggered by {player.name}'s turn)", log
                    ):
                        removed = other.curses.pop(0)
                        _fx.refresh_tokens(other)
                        log.append(f"  Me Too!: {other.name} discarded curse '{removed.name}'.")

        # Game-over message
        if self.status == GameStatus.WON:
            log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")

        result = TurnResult(
            turn_number=self.turn_number,
            player_id=player.player_id,
            card_played=card_value if not using_wheelies else 0,
            moved_from=old_pos,
            moved_to=new_pos,
            tile_type_encountered=tile.tile_type,
            encounter_log=log,
            combat_result=combat_result,
            game_status=self.status,
        )

        # Advance to next player
        self._advance_turn()

        return result


    # ------------------------------------------------------------------
    # Turn rotation
    # ------------------------------------------------------------------

    def _advance_turn(self) -> None:
        """Move to the next player in rotation and prefill their hand."""
        if len(self.players) > 1:
            self._current_player_idx = (
                (self._current_player_idx + 1) % len(self.players)
            )
        # Prefill current player's hand so they see a full hand when it's their turn
        self.draw_movement_cards(self.current_player)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def player_summary(self, player_id: int = 0) -> str:
        p = self.players[player_id]
        hero_name = p.hero.name if p.hero else "No hero"
        lines = [
            f"--- {p.name} ({hero_name}) ---",
            f"Position: tile {p.position} (Level {get_level(p.position)})",
            f"Strength: {p.total_strength}  (base {p.base_strength})",
            f"  Helmets:  {[i.name for i in p.helmets]}",
            f"  Chest:    {[i.name for i in p.chest_armor]}",
            f"  Legs:     {[i.name for i in p.leg_armor]}",
            f"  Weapons:  {[i.name for i in p.weapons]}",
            f"  Pack:     {[i.name for i in p.pack]}",
            f"Consumables: {[c.name for c in p.consumables]}",
            f"Traits:  {[t.name for t in p.traits]}",
            f"Curses:  {[c.name for c in p.curses]}",
            f"Hand:    {p.movement_hand}  Discard: {p.movement_discard}",
            f"Night:   {self.is_night}",
        ]
        return "\n".join(lines)

    def all_players_summary(self) -> str:
        """Return a summary of all players."""
        return "\n\n".join(
            self.player_summary(p.player_id) for p in self.players
        )

    def visible_tiles(self) -> list[Tile]:
        """Return tiles currently visible.

        During Night (fog of war): only DayNight, Miniboss, and Werbler
        tiles are visible.  All other previously-revealed tiles are hidden.
        During Day: all revealed tiles are visible.
        """
        always_visible_types = (TileType.DAY_NIGHT, TileType.MINIBOSS, TileType.WERBLER)
        result: list[Tile] = []
        for tile in self.board[1:]:
            if tile.tile_type in always_visible_types:
                result.append(tile)
            elif not self.is_night and tile.revealed:
                result.append(tile)
        return result
