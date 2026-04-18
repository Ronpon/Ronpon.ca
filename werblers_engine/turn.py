"""Interactive turn API mixin for the Game class.

Extracted from game.py to keep the core Game class focused on state
initialisation, the legacy play_turn() auto-resolver, and shared helpers.
All step-by-step interactive methods (begin_move, fight, resolve_offer, etc.)
live here as an InteractiveTurnMixin that Game inherits from.
"""

from __future__ import annotations

import copy as _copy
import random
import re as _re
from typing import Optional

from .types import CombatResult, GameContext, GameStatus, TileType, Item
from .board import get_level
from . import content as C
from . import encounters as enc
from . import effects as _fx


def _item_to_dict(item: Item) -> dict:
    """Serialise an Item for the web UI."""
    return {
        "name":           item.name,
        "slot":           item.slot.value,
        "strength_bonus": item.strength_bonus,
        "effect_id":      item.effect_id,
        "hands":          item.hands,
        "tokens":         item.tokens,
        "is_consumable":  item.is_consumable,
    }



def _extract_gains(combat_info: dict, log: list, log_start: int, content_module) -> None:
    """Scan new log entries for trait/curse gains and add them to combat_info."""
    import re
    for entry in log[log_start:]:
        m = re.search(r"Victory! Gained trait[:\s]+(.+)", entry, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            combat_info["trait_gained"] = name
            combat_info["trait_gained_desc"] = content_module.TRAIT_DESCRIPTIONS.get(name, "")
        m = re.search(r"Gained curse[:\s]+(.+)", entry, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            combat_info["curse_gained"] = name
            combat_info["curse_gained_desc"] = content_module.CURSE_DESCRIPTIONS.get(name, "")

class InteractiveTurnMixin:
    """Step-by-step interactive turn methods mixed into Game."""

    def get_available_abilities(self) -> list[dict]:
        """Return "you may" abilities the current player can activate this turn.

        Returns a list of dicts describing each ability and any extra inputs
        the UI needs to collect (trait select, equip select, etc.).
        """
        player = self.current_player
        # Ensure the hand is populated before checking wheelies / hand size
        self.draw_movement_cards(player)
        abilities: list[dict] = []

        for trait in player.traits:
            eid = trait.effect_id
            if eid == "eight_lives" and player.curses:
                removable_curses = [
                    c for c in player.curses
                    if not c.source_monster
                    or any(
                        m.name == c.source_monster and m.level in (1, 2)
                        for pool in (C.MONSTER_POOL_L1, C.MONSTER_POOL_L2)
                        for m in pool
                    )
                ]
                if removable_curses:
                    abilities.append({
                        "id": "eight_lives",
                        "label": "Eight Lives",
                        "description": "Discard this trait to remove one of your Tier 1 or 2 curses.",
                        "type": "instant_select_curse",
                        "curses": [c.name for c in removable_curses],
                    })
            elif eid == "meat_on_menu":
                targets = [p for p in self.players if p is not player and p.minions]
                if targets:
                    abilities.append({
                        "id": "meat_on_menu",
                        "label": "Meat's Back on the Menu!",
                        "description": "Force an opponent to discard a minion. Gain +5 Str tokens.",
                        "type": "select_player_minion",
                        "targets": [
                            {"player_id": t.player_id, "name": t.name,
                             "minions": [m.name for m in t.minions]}
                            for t in targets
                        ],
                    })
            elif eid == "touchdown":
                abilities.append({
                    "id": "touchdown",
                    "label": "Touchdown!",
                    "description": "Discard this trait to teleport directly to tile 90 (The Werbler).",
                    "type": "toggle",
                })
            elif eid == "fancy_footwork":
                abilities.append({
                    "id": "fancy_footwork",
                    "label": "Fancy Footwork",
                    "description": "Reduce your movement this turn by 1 or 2.",
                    "type": "select_number",
                    "options": [1, 2],
                })
            elif eid == "phase_shift":
                all_equips = (
                    player.helmets + player.chest_armor
                    + player.leg_armor + player.weapons
                )
                unlocked = [
                    e for e in all_equips
                    if not e.locked_by_curse_id
                    or not any(c.effect_id == e.locked_by_curse_id for c in player.curses)
                ]
                if unlocked:
                    abilities.append({
                        "id": "phase_shift",
                        "label": "Phase Shift",
                        "description": "Discard an equip card to toggle the Day/Night cycle.",
                        "type": "select_equip",
                        "equips": [e.name for e in unlocked],
                    })

        for item in player.weapons:
            if item.effect_id == "mages_gauntlet" and player.traits:
                abilities.append({
                    "id": "mages_gauntlet",
                    "label": "Mage's Gauntlet",
                    "description": "Discard a trait to add a permanent +1 Str token to your Gauntlet.",
                    "type": "select_trait",
                    "traits": [t.name for t in player.traits],
                })

        # Wheelies — replaces card play entirely
        if player.has_equipped_item("wheelies") and player.last_card_played is not None:
            abilities.append({
                "id": "wheelies",
                "label": "Wheelies",
                "description": (
                    f"Reuse your last played card value ({player.last_card_played}) "
                    "instead of playing a new card."
                ),
                "type": "activate",
                "value": player.last_card_played,
            })

        # Post-card passive abilities (applied automatically after card is chosen)
        if player.has_equipped_item("hermes_shoes"):
            abilities.append({
                "id": "hermes_shoes",
                "label": "Hermes' Shoes",
                "description": "If you play a 1 or 2, treat it as 4 instead.",
                "type": "toggle",
                "timing": "post_card",
            })
        if player.has_equipped_item("boots_of_agility"):
            abilities.append({
                "id": "boots_of_agility",
                "label": "Boots of Agility",
                "description": "+1 to your movement this turn.",
                "type": "toggle",
                "timing": "post_card",
            })

        return abilities

    def begin_move(
        self,
        card_index: int = 0,
        flee: bool = False,
        activated: Optional[dict] = None,
        direction: str = "forward",
    ) -> dict:
        """Phase-1 of an interactive turn.

        Handles pre-turn abilities, card play, movement, and tile reveal.
        For CHEST / SHOP tiles the drawn item(s) are stored in
        ``self._pending_offer`` and the method returns early with
        ``phase == "offer_chest"`` or ``"offer_shop"``so the UI can ask the
        player what to do with them.  All other tile types are resolved
        automatically and return ``phase == "done"``.

        Parameters
        ----------
        card_index:
            Index of the movement card to play from the current player's hand.
        flee:
            Whether the player is fleeing (Billfold ability).
        activated:
            Dict of ability IDs → args. Supported keys:
            ``eight_lives`` (bool), ``meat_on_menu`` (dict with
            ``target_player_id`` and ``minion_index``),
            ``mages_gauntlet`` (dict with ``trait_index``),
            ``phase_shift`` (dict with ``equip_index``),
            ``touchdown`` (bool), ``wheelies`` (bool),
            ``hermes_shoes`` (bool), ``boots_of_agility`` (bool),
            ``fancy_footwork`` (dict with ``reduction``).
        """
        if activated is None:
            activated = {}

        player = self.current_player
        self.turn_number += 1
        log: list[str] = [f"[{player.name}'s turn]"]

        # 1. Draw movement cards
        self.draw_movement_cards(player)

        # 2. Residuals — automatic
        for trait in player.traits:
            if trait.effect_id == "residuals":
                trait.strength_bonus += 1
                log.append(f"  Residuals: +1 Str token (total: +{trait.strength_bonus})")

        # 3. Eight Lives — now handled by use_eight_lives() via API

        # 4. Meat's Back on Menu
        meat_args = activated.get("meat_on_menu")
        if meat_args:
            meat_trait = next(
                (t for t in player.traits if t.effect_id == "meat_on_menu"), None
            )
            if meat_trait:
                target_id = int(meat_args.get("target_player_id", -1))
                minion_idx = int(meat_args.get("minion_index", 0))
                target = next(
                    (p for p in self.players if p.player_id == target_id), None
                )
                if target and target.minions:
                    idx = min(minion_idx, len(target.minions) - 1)
                    lost = target.minions.pop(idx)
                    meat_trait.tokens += 5
                    log.append(
                        f"  Meat's Back on Menu!: {target.name} lost '{lost.name}'. "
                        f"+5 Str tokens on trait."
                    )

        # 5. Mage's Gauntlet
        gauntlet_args = activated.get("mages_gauntlet")
        if gauntlet_args:
            gauntlet = next(
                (w for w in player.weapons if w.effect_id == "mages_gauntlet"), None
            )
            if gauntlet and player.traits:
                tidx = min(int(gauntlet_args.get("trait_index", 0)), len(player.traits) - 1)
                discarded = player.traits.pop(tidx)
                gauntlet.tokens += 1
                _fx.refresh_tokens(player)
                log.append(
                    f"  Mage's Gauntlet: discarded '{discarded.name}', "
                    f"+1 Str token (total: +{gauntlet.tokens})."
                )

        # 6. Phase Shift
        phase_args = activated.get("phase_shift")
        if phase_args and any(t.effect_id == "phase_shift" for t in player.traits):
            all_equips = (
                player.helmets + player.chest_armor
                + player.leg_armor + player.weapons
            )
            unlocked = [
                e for e in all_equips
                if not e.locked_by_curse_id
                or not any(c.effect_id == e.locked_by_curse_id for c in player.curses)
            ]
            eidx = min(int(phase_args.get("equip_index", 0)), len(unlocked) - 1)
            if unlocked:
                to_discard = unlocked[eidx]
                player.unequip(to_discard)
                self.is_night = not self.is_night
                _fx.refresh_tokens(player)
                log.append(
                    f"  Phase Shift: discarded {to_discard.name}. "
                    f"{'Night' if self.is_night else 'Day'}!"
                )

        # 7. Touchdown (early exit)
        if activated.get("touchdown"):
            td = next((t for t in player.traits if t.effect_id == "touchdown"), None)
            if td:
                player.traits.remove(td)
                _fx.on_trait_lost(player, td, log)
                _fx.refresh_tokens(player)
                old_pos = player.position
                player.position = 90
                log.append("  Touchdown!: teleported to tile 90 (Werbler)!")
                tile = self.board[90]
                tile.revealed = True
                werbler = self.player_werblers.get(player.player_id)
                if werbler is None:
                    log.append("No werbler assigned — skipping.")
                    combat_result = None
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
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": 90,
                    "card_played": 0, "tile_type": TileType.WERBLER.name,
                    "combat_result": combat_result.name if combat_result else None,
                    "game_status": self.status.name, "winner": self.winner,
                }

        # 8. Empty hand check
        if not player.movement_hand:
            log.append("No movement cards — turn skipped.")
            self._finish_post_encounter(player, log)
            self._advance_turn()
            return {
                "phase": "done", "log": log,
                "moved_from": player.position, "moved_to": player.position,
                "card_played": 0, "tile_type": self.board[player.position].tile_type.name,
                "combat_result": None, "game_status": self.status.name, "winner": self.winner,
            }

        # 9. Wheelies or normal card play
        using_wheelies = False
        card_value: int
        if (
            activated.get("wheelies")
            and player.last_card_played is not None
            and player.has_equipped_item("wheelies")
        ):
            using_wheelies = True
            card_value = player.last_card_played
            log.append(f"  Wheelies! Using last card value: {card_value}")
        else:
            if any(c.effect_id == "bad_trip" for c in player.curses):
                idx = random.randrange(len(player.movement_hand))
                log.append("  Bad Trip: cards facedown — randomly selecting!")
            else:
                idx = min(card_index, len(player.movement_hand) - 1)
            card_value = player.movement_hand.pop(idx)
            player.movement_discard.append(card_value)
            player.last_card_played = card_value

        # So Lethargic
        if card_value in (3, 4):
            for c in player.curses:
                if c.effect_id == "so_lethargic":
                    c.strength_bonus -= 1
                    log.append(
                        f"  So\u2026 Lethargic\u2026: played {card_value}, "
                        f"-1 Str token ({c.strength_bonus})"
                    )

        # 10. Post-card movement modifiers
        if (
            activated.get("hermes_shoes")
            and card_value in (1, 2)
            and player.has_equipped_item("hermes_shoes")
        ):
            card_value = 4
            log.append("  Hermes' Shoes! Movement treated as 4.")

        if (
            activated.get("boots_of_agility")
            and player.has_equipped_item("boots_of_agility")
        ):
            card_value += 1
            log.append(f"  Boots of Agility! Movement +1 \u2192 {card_value}")

        ff_args = activated.get("fancy_footwork")
        if ff_args and any(t.effect_id == "fancy_footwork" for t in player.traits):
            reduction = int(ff_args.get("reduction", 1))
            card_value = max(0, card_value - reduction)
            log.append(f"  Fancy Footwork: reduced by {reduction} \u2192 {card_value}")

        # 11. Movement calculation
        modified_value = _fx.modify_movement_value(player, card_value, self.is_night)
        effective_move = max(0, modified_value + player.move_bonus)

        old_pos = player.position
        if direction == "backward":
            new_pos = max(1, old_pos - effective_move)
        else:
            new_pos = old_pos + effective_move

        # Miniboss gates — use new_pos > threshold (not old_pos < threshold)
        # so a player already stuck ON the miniboss tile after a loss cannot slip past.
        if not player.miniboss1_defeated and new_pos > 30:
            new_pos = 30
        if not player.miniboss2_defeated and new_pos > 60:
            new_pos = 60
        new_pos = min(new_pos, 90)

        player.position = new_pos
        log.append(
            f"Played card {card_value} (effective {effective_move}): "
            f"tile {old_pos} \u2192 {new_pos}"
        )

        # 12. Reveal tile
        tile = self.board[new_pos]
        if self.is_night:
            if not tile.revealed_night:
                tile.revealed_night = True
                log.append(f"Tile {new_pos} visited at night (still hidden during day)")
            else:
                log.append(f"Tile {new_pos}: {tile.tile_type.name} (night, already night-visited)")
        else:
            if not tile.revealed:
                tile.revealed = True
                log.append(f"Tile {new_pos} revealed: {tile.tile_type.name}")
            else:
                log.append(f"Tile {new_pos}: {tile.tile_type.name}")

        # 13. Determine effective encounter type (night override)
        actual_type = tile.tile_type
        if self.is_night and actual_type not in (
            TileType.MINIBOSS, TileType.WERBLER, TileType.DAY_NIGHT,
        ):
            log.append("  Night override \u2192 Monster encounter.")
            actual_type = TileType.MONSTER

        level = get_level(new_pos)

        # 14. Chest — pause for interactive offer
        if actual_type == TileType.CHEST:
            item = self.item_decks[level].draw()
            if item is None:
                log.append("Chest: item deck is empty \u2014 nothing to draw.")
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            log.append(f"Chest: found {item.name} (STR +{item.strength_bonus}, {item.slot.value})")
            self._pending_offer = {
                "type": "chest", "level": level, "items": [item],
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
            }
            return {
                "phase": "offer_chest", "log": log,
                "moved_from": old_pos, "moved_to": new_pos, "card_played": card_value,
                "tile_type": tile.tile_type.name,
                "offer": {"items": [_item_to_dict(item)]},
            }

        # 15. Shop — pause for interactive offer
        if actual_type == TileType.SHOP:
            draw_count = player.hero.shop_draw_count if player.hero else 3
            items = self.item_decks[level].draw_many(draw_count)
            if not items:
                log.append("Shop: item deck is empty \u2014 nothing to buy.")
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            log.append(f"Shop: choose from {[i.name for i in items]}")
            self._pending_offer = {
                "type": "shop", "level": level, "items": items,
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
            }
            return {
                "phase": "offer_shop", "log": log,
                "moved_from": old_pos, "moved_to": new_pos, "card_played": card_value,
                "tile_type": tile.tile_type.name,
                "offer": {
                    "items": [_item_to_dict(i) for i in items],
                },
            }

        # 15.5 MYSTERY — pause for interactive mystery event
        if actual_type == TileType.MYSTERY:
            from . import mystery as _mys
            event = _mys.roll_mystery_event(new_pos, player=player)
            log.append(f"Mystery Square: {event.name}!")
            self._pending_offer = {
                "type": "mystery",
                "event": event,
                "level": level,
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
            }
            return {
                "phase": "mystery",
                "log": log,
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
                "mystery_event": {
                    "event_id": event.event_id,
                    "name": event.name,
                    "tier": event.tier,
                    "description": event.description,
                    "image_name": event.image_name,
                },
            }

        # 15.6 MONSTER — pause for pre-fight consumable phase
        if actual_type == TileType.MONSTER:
            self._prefight_str_bonus = 0
            other_players = [p for p in self.players if p is not player]

            # Check for No More Charlie Work — pause for player decision
            if level < 3 and any(t.effect_id == "no_more_charlie_work" for t in player.traits):
                self._pending_combat = {
                    "type": "awaiting_charlie_work",
                    "level": level,
                    "other_players": other_players,
                    "log": log,
                    "old_pos": old_pos, "new_pos": new_pos,
                    "card_value": card_value, "tile_type": tile.tile_type.name,
                }
                return {
                    "phase": "charlie_work",
                    "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "level": level,
                }

            effective_monster_deck = self.monster_decks[level]
            monster = effective_monster_deck.draw()
            if monster is None:
                log.append("Monster: monster deck is empty \u2014 no encounter.")
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            reroll_count = sum(
                1 for t in player.traits
                if t.effect_id in ("ill_come_in_again", "i_see_everything")
            )
            self._pending_combat = {
                "monster": monster,
                "effective_deck": effective_monster_deck,
                "other_players": other_players,
                "level": level,
                "log": log,
                "old_pos": old_pos,
                "new_pos": new_pos,
                "card_value": card_value,
                "tile_type": tile.tile_type.name,
                "ill_come_in_again_count": reroll_count,
                "ill_come_in_again_available": reroll_count > 0,
            }
            _male_bonus = monster.bonus_vs_male if (monster.bonus_vs_male and player.hero and player.hero.is_male) else 0
            combat_info = {
                "monster_name": monster.name,
                "monster_strength": monster.strength + _male_bonus,
                "monster_bonus_vs_male": _male_bonus,
                "player_strength": player.combat_strength(),
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "monster",
                "level": level,
                "result": None,
                "ill_come_in_again_available": reroll_count > 0,
            }
            self._last_combat_info = combat_info
            return {
                "phase": "combat",
                "log": log,
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
                "combat_info": combat_info,
            }

        # 15.6 MINIBOSS — pause for pre-fight phase (like MONSTER)
        if actual_type == TileType.MINIBOSS:
            already_defeated = (
                (new_pos == 30 and player.miniboss1_defeated)
                or (new_pos == 60 and player.miniboss2_defeated)
            )
            if already_defeated:
                log.append("Miniboss already defeated \u2014 no encounter.")
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            if new_pos == 30:
                if self.active_miniboss_t1 is None:
                    self.active_miniboss_t1 = self.miniboss_deck_t1.draw()
                miniboss = self.active_miniboss_t1
                reward_deck_level = 2
            else:
                if self.active_miniboss_t2 is None:
                    self.active_miniboss_t2 = self.miniboss_deck_t2.draw()
                miniboss = self.active_miniboss_t2
                reward_deck_level = 3
            if miniboss is None:
                log.append("All minibosses for this tier have been defeated!")
                if new_pos == 30:
                    player.miniboss1_defeated = True
                else:
                    player.miniboss2_defeated = True
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            self._prefight_str_bonus = 0
            self._prefight_monster_str_bonus = 0
            self._pending_combat = {
                "type": "miniboss",
                "monster": miniboss,
                "reward_deck_level": reward_deck_level,
                "boss_tile": new_pos,
                "other_players": [p for p in self.players if p is not player],
                "level": 1 if new_pos == 30 else 2,
                "log": log,
                "old_pos": old_pos, "new_pos": new_pos,
                "card_value": card_value, "tile_type": tile.tile_type.name,
            }
            # Compute ability modifiers for pre-fight STR display
            _ab_log: list[str] = []
            _ab_player_mod, _ab_monster_mod, _ = enc._apply_miniboss_modifiers(
                player, miniboss, _ab_log, self.is_night)
            self._pending_combat["ability_player_mod"] = _ab_player_mod
            self._pending_combat["ability_monster_mod"] = _ab_monster_mod
            self._pending_combat["ability_breakdown"] = _ab_log

            # Ogre Cutpurse: discard pack items IMMEDIATELY so STR display is accurate
            ogre_player_mod = 0
            ogre_monster_mod = 0
            if miniboss.effect_id == "ogre_cutpurse":
                _ogre_log: list[str] = []
                ogre_monster_mod, ogre_player_mod = enc._ogre_pre_combat(
                    player, miniboss, _ogre_log)
                log.extend(_ogre_log)
                _ab_log.extend(_ogre_log)  # include in breakdown for tooltip
            self._pending_combat["ogre_player_mod"] = ogre_player_mod
            self._pending_combat["ogre_monster_mod"] = ogre_monster_mod

            combat_info = {
                "monster_name": miniboss.name,
                "monster_strength": miniboss.strength + _ab_monster_mod + ogre_monster_mod,
                "player_strength": max(0, player.combat_strength() + _ab_player_mod + ogre_player_mod),
                "ability_player_mod": _ab_player_mod + ogre_player_mod,
                "ability_monster_mod": _ab_monster_mod + ogre_monster_mod,
                "ability_breakdown": _ab_log,
                "description": miniboss.description,
                "effect_id": miniboss.effect_id,
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "miniboss",
                "level": 1 if new_pos == 30 else 2,
                "result": None,
            }
            self._last_combat_info = combat_info
            return {
                "phase": "combat", "log": log,
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
                "combat_info": combat_info,
            }

        # 15.7 WERBLER — pause for pre-fight phase
        if actual_type == TileType.WERBLER:
            werbler = self.player_werblers.get(player.player_id)
            if werbler is None:
                log.append("No werbler assigned \u2014 skipping.")
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            self._prefight_str_bonus = 0
            self._prefight_monster_str_bonus = 0
            # Compute ability modifiers for pre-fight STR display
            _ab_log: list[str] = []
            _ab_player_mod, _ab_monster_mod = enc._apply_werbler_modifiers(
                player, werbler, _ab_log, self.is_night)
            self._pending_combat = {
                "type": "werbler",
                "monster": werbler,
                "other_players": [p for p in self.players if p is not player],
                "level": 3,
                "log": log,
                "old_pos": old_pos, "new_pos": new_pos,
                "card_value": card_value, "tile_type": tile.tile_type.name,
                "ability_player_mod": _ab_player_mod,
                "ability_monster_mod": _ab_monster_mod,
                "ability_breakdown": _ab_log,
            }
            combat_info = {
                "monster_name": werbler.name,
                "monster_strength": werbler.strength + _ab_monster_mod,
                "player_strength": max(0, player.combat_strength() + _ab_player_mod),
                "ability_player_mod": _ab_player_mod,
                "ability_monster_mod": _ab_monster_mod,
                "ability_breakdown": _ab_log,
                "nice_hat_bonus": getattr(werbler, "_brady_nice_hat_bonus", 0),
                "description": werbler.description,
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "werbler",
                "level": 3,
                "result": None,
            }
            self._last_combat_info = combat_info
            return {
                "phase": "combat", "log": log,
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
                "combat_info": combat_info,
            }

        # 16. All other tile types — auto-resolve
        combat_result = self._resolve_auto_encounter(
            player, actual_type, tile, level, flee, log
        )
        self._finish_post_encounter(player, log)
        if self.status == GameStatus.WON:
            log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")
        self._advance_turn()
        return {
            "phase": "done", "log": log,
            "moved_from": old_pos, "moved_to": new_pos,
            "card_played": card_value, "tile_type": tile.tile_type.name,
            "combat_result": combat_result.name if combat_result else None,
            "combat_info": self._last_combat_info,
            "game_status": self.status.name, "winner": self.winner,
        }

    def use_ill_come_in_again(self) -> dict:
        """Use I'll Come In Again / I See Everything: return current monster and draw a new one.

        Supports stacking — players with both traits get 2 rerolls per encounter.
        """
        pc = self._pending_combat
        count = pc.get("ill_come_in_again_count", 1 if pc and pc.get("ill_come_in_again_available") else 0) if pc else 0
        if pc is None or count <= 0:
            return {"error": "Trait not available for this encounter"}
        monster = pc["monster"]
        deck = pc["effective_deck"]
        deck.put_bottom(monster)
        new_monster = deck.draw()
        if new_monster is None:
            # Deck was empty after returning — restore original and abort
            deck.put_bottom(monster)
            return {"error": "Monster deck is empty — cannot draw a replacement"}
        pc["monster"] = new_monster
        pc["ill_come_in_again_count"] = count - 1
        pc["ill_come_in_again_available"] = (count - 1) > 0
        player = self.current_player
        log = pc.get("log", [])
        # Use the actual trait name for the log entry
        reroll_traits = [t for t in player.traits if t.effect_id in ("ill_come_in_again", "i_see_everything")]
        trait_name = reroll_traits[0].name if reroll_traits else "I'll Come In Again!"
        log.append(f"  {trait_name}: sent {monster.name} back, drew {new_monster.name}.")
        _male_bonus3 = new_monster.bonus_vs_male if (new_monster.bonus_vs_male and player.hero and player.hero.is_male) else 0
        combat_info = {
            "monster_name": new_monster.name,
            "monster_strength": new_monster.strength + _male_bonus3,
            "monster_bonus_vs_male": _male_bonus3,
            "player_strength": player.combat_strength(),
            "player_id": player.player_id,
            "player_name": player.name,
            "hero_id": player.hero.id.name if player.hero else None,
            "category": "monster",
            "level": pc.get("level", 1),
            "result": None,
            "ill_come_in_again_available": pc["ill_come_in_again_available"],
        }
        self._last_combat_info = combat_info
        return {"phase": "combat", "combat_info": combat_info}

    def fight(self) -> dict:
        """Resolve the pending combat (monster, miniboss, or werbler) after the pre-fight phase."""
        if self._pending_combat is None:
            return {"error": "No pending combat", "phase": "error"}

        player = self.current_player  # turn has not advanced yet
        pc = self._pending_combat
        self._pending_combat = None
        # Defensive: clear any stale pending offer to prevent blocking future moves
        if self._pending_offer is not None and self._pending_offer.get("type") != "rake_it_in":
            self._pending_offer = None

        combat_type = pc.get("type", "monster")
        log = pc["log"]
        old_pos = pc["old_pos"]
        new_pos = pc["new_pos"]
        card_value = pc["card_value"]
        tile_type_name = pc["tile_type"]
        level = pc["level"]
        log_start = len(log)

        extra_str = self._prefight_str_bonus
        self._prefight_str_bonus = 0
        monster_str_delta = self._prefight_monster_str_bonus
        self._prefight_monster_str_bonus = 0
        combat_result = None

        # Capture player strength BEFORE combat so displayed value isn't
        # inflated or reduced by traits/curses gained during resolution.
        def _no_consumable_decide(prompt: str, log_: list) -> bool:
            """In interactive fights, consumables are pre-used via the UI.
            Refuse all consumable-phase auto-decisions to prevent double use."""
            if "consumable" in prompt.lower() or "play a" in prompt.lower():
                return False
            # Swiftness flee is handled via the dedicated UI button; never auto-trigger it
            if "swiftness" in prompt.lower():
                return False
            # Pre-fight monster-redraw features are handled via dedicated UI endpoints;
            # never auto-trigger them here to prevent the wrong monster being fought.
            if "transmogrifier" in prompt.lower():
                return False
            if "come in again" in prompt.lower() or "i see everything" in prompt.lower():
                return False
            return self._decide(prompt, log_)

        if combat_type == "miniboss":
            miniboss = pc["monster"]
            reward_deck_level = pc["reward_deck_level"]
            boss_tile = pc["boss_tile"]
            other_players = pc["other_players"]
            ogre_player_mod = pc.get("ogre_player_mod", 0)
            ogre_monster_mod = pc.get("ogre_monster_mod", 0)
            player_str_at_fight = player.combat_strength() + pc.get("ability_player_mod", 0) + ogre_player_mod
            # Build pre_run_ogre if pack was already discarded at fight-start
            pre_run_ogre: Optional[tuple[int, int]] = None
            if pc.get("ogre_player_mod") is not None or pc.get("ogre_monster_mod") is not None:
                pre_run_ogre = (ogre_monster_mod, ogre_player_mod)
            combat_result = enc.encounter_miniboss(
                player, miniboss, self.item_decks[reward_deck_level],
                GameContext(
                    log=log,
                    is_night=self.is_night,
                    players=self.players,
                    decide_fn=_no_consumable_decide,
                    select_fn=self._select,
                    trait_deck=self.trait_deck,
                    curse_deck=self.curse_deck,
                    item_decks=self.item_decks,
                    monster_decks=self.monster_decks,
                ),
                pre_run_ogre=pre_run_ogre,
                extra_player_strength=extra_str,
                extra_monster_strength=monster_str_delta,
            )
            # --- Crossroads Demon: Fair Exchange bonus draws ---
            crossroads_items = pc.get("crossroads_discards", [])
            if combat_result == CombatResult.WIN and crossroads_items and miniboss.effect_id == "crossroads_demon":
                n = len(crossroads_items)
                bonus_drawn: list = []
                for _ in range(n):
                    extra = self.item_decks[reward_deck_level].draw()
                    if extra:
                        bonus_drawn.append(extra)
                if bonus_drawn:
                    names = [i.name for i in bonus_drawn]
                    log.append(f"  Fair Exchange: {n} discards → {len(bonus_drawn)} T{reward_deck_level} bonus item(s): {', '.join(names)}")
                    for bonus_item in bonus_drawn:
                        player.pending_trait_items.append(bonus_item)
                else:
                    log.append(f"  Fair Exchange: {n} discards → reward deck empty, no bonus items.")
            if combat_result == CombatResult.WIN:
                if boss_tile == 30:
                    player.miniboss1_defeated = True
                    self.active_miniboss_t1 = None
                else:
                    player.miniboss2_defeated = True
                    self.active_miniboss_t2 = None
            self._last_combat_info = {
                "monster_name": miniboss.name,
                "monster_strength": miniboss.strength + pc.get("ability_monster_mod", 0) + ogre_monster_mod,
                "player_strength": max(0, player_str_at_fight),
                "ability_player_mod": pc.get("ability_player_mod", 0) + ogre_player_mod,
                "ability_monster_mod": pc.get("ability_monster_mod", 0) + ogre_monster_mod,
                "ability_breakdown": pc.get("ability_breakdown", []),
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "miniboss",
                "level": level,
                "result": combat_result.name if combat_result else None,
            }

        elif combat_type == "werbler":
            werbler = pc["monster"]
            other_players = pc["other_players"]
            player_str_at_fight = player.combat_strength()
            combat_result, self.status = enc.encounter_werbler(
                player, werbler,
                GameContext(
                    log=log,
                    is_night=self.is_night,
                    players=self.players,
                    decide_fn=_no_consumable_decide,
                    select_fn=self._select,
                    trait_deck=self.trait_deck,
                    curse_deck=self.curse_deck,
                    item_decks=self.item_decks,
                    monster_decks=self.monster_decks,
                ),
                extra_player_strength=extra_str,
                extra_monster_strength=monster_str_delta,
            )
            if self.status == GameStatus.WON:
                self.winner = player.player_id
            self._last_combat_info = {
                "monster_name": werbler.name,
                "monster_strength": werbler.strength + pc.get("ability_monster_mod", 0),
                "player_strength": max(0, player_str_at_fight + pc.get("ability_player_mod", 0)),
                "ability_player_mod": pc.get("ability_player_mod", 0),
                "ability_monster_mod": pc.get("ability_monster_mod", 0),
                "ability_breakdown": pc.get("ability_breakdown", []),
                "nice_hat_bonus": getattr(werbler, "_brady_nice_hat_bonus", 0),
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "werbler",
                "level": level,
                "result": combat_result.name if combat_result else None,
            }

        else:  # monster
            monster = pc["monster"]
            if monster_str_delta:
                monster.strength = max(0, monster.strength + monster_str_delta)
            effective_deck = pc["effective_deck"]
            other_players = pc["other_players"]
            player_str_at_fight = player.combat_strength() + extra_str
            combat_result = enc.encounter_monster(
                player,
                effective_deck,
                GameContext(
                    log=log,
                    is_night=self.is_night,
                    players=self.players,
                    decide_fn=_no_consumable_decide,
                    select_fn=self._select,
                    trait_deck=self.trait_deck,
                    curse_deck=self.curse_deck,
                    item_decks=self.item_decks,
                    monster_decks=self.monster_decks,
                ),
                pre_drawn_monster=monster,
                extra_player_strength=extra_str,
            )
            _male_bonus2 = monster.bonus_vs_male if (monster.bonus_vs_male and player.hero and player.hero.is_male) else 0
            self._last_combat_info = {
                "monster_name": monster.name,
                "monster_strength": monster.strength + _male_bonus2,
                "monster_bonus_vs_male": _male_bonus2,
                "player_strength": max(0, player_str_at_fight),
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "monster",
                "level": level,
                "result": combat_result.name if combat_result else None,
            }
            if pc.get("from_mystery"):
                self._last_combat_info["from_mystery"] = True

        # Extract trait/curse gained from new log entries
        _extract_gains(self._last_combat_info, log, log_start, C)

        self._finish_post_encounter(player, log)
        if self.status == GameStatus.WON:
            log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")
        is_summoned = pc.get("summoned_monster", False)
        if not is_summoned:
            self._advance_turn()
        return {
            "phase": "done", "log": log,
            "moved_from": old_pos, "moved_to": new_pos,
            "card_played": card_value, "tile_type": tile_type_name,
            "combat_result": combat_result.name if combat_result else None,
            "combat_info": self._last_combat_info,
            "game_status": self.status.name, "winner": self.winner,
            "summoned_monster": is_summoned,
        }

    def flee_monster(self) -> dict:
        """Billfold: Fly, you dummy! — flee from the pending monster or miniboss combat.

        Validates the pending combat type and hero flee capability, then moves
        the player back (flee_move_back spaces), resets pre-fight bonuses,
        and advances the turn.
        """
        if self._pending_combat is None:
            return {"error": "No pending combat", "phase": "error"}

        player = self.current_player
        pc = self._pending_combat
        combat_type = pc.get("type", "monster")

        if combat_type == "werbler":
            return {"error": "Cannot flee from the Werbler!", "phase": "error"}
        if combat_type == "miniboss":
            if not player.hero or not player.hero.can_flee_miniboss:
                return {"error": "This hero cannot flee a Miniboss.", "phase": "error"}
        else:  # monster
            if not player.hero or not player.hero.can_flee_monsters:
                return {"error": "This hero cannot flee.", "phase": "error"}

        self._pending_combat = None
        log = pc["log"]
        old_pos = pc["old_pos"]
        new_pos = pc["new_pos"]
        card_value = pc["card_value"]
        tile_type_name = pc["tile_type"]

        monster = pc.get("monster")
        if monster:
            log.append(
                f"  Fly, you dummy! {player.name} flees from {monster.name}! "
                f"No curse received."
            )
        self._apply_flee_move_back(player, log)
        self._prefight_str_bonus = 0
        self._prefight_monster_str_bonus = 0

        self._finish_post_encounter(player, log)
        self._advance_turn()
        return {
            "phase": "done", "log": log,
            "moved_from": old_pos, "moved_to": player.position,
            "card_played": card_value, "tile_type": tile_type_name,
            "combat_result": None,
            "game_status": self.status.name, "winner": self.winner,
        }

    def resolve_charlie_work(self, use_it: bool) -> dict:
        """Resolve the No More Charlie Work decision.

        Call after begin_move returned phase == "charlie_work".
        use_it=True → draw monster from the next tier; False → draw from current tier.
        """
        pending = self._pending_combat
        self._pending_combat = None
        if pending is None or pending.get("type") != "awaiting_charlie_work":
            return {"phase": "done", "log": ["No pending Charlie Work decision."],
                    "game_status": self.status.name, "winner": self.winner}

        player = self.current_player
        level: int = pending["level"]
        other_players: list = pending["other_players"]
        log: list[str] = pending["log"]

        if use_it:
            effective_monster_deck = self.monster_decks[level + 1]
            log.append(f"  No More Charlie Work: drawing from Tier {level + 1}!")
        else:
            effective_monster_deck = self.monster_decks[level]

        monster = effective_monster_deck.draw()
        if monster is None:
            log.append("Monster: monster deck is empty — no encounter.")
            self._finish_post_encounter(player, log)
            self._advance_turn()
            return {
                "phase": "done", "log": log,
                "moved_from": pending["old_pos"], "moved_to": pending["new_pos"],
                "card_played": pending["card_value"], "tile_type": pending["tile_type"],
                "combat_result": None, "game_status": self.status.name, "winner": self.winner,
            }

        self._pending_combat = {
            "monster": monster,
            "effective_deck": effective_monster_deck,
            "other_players": other_players,
            "level": level,
            "log": log,
            "old_pos": pending["old_pos"],
            "new_pos": pending["new_pos"],
            "card_value": pending["card_value"],
            "tile_type": pending["tile_type"],
        }
        combat_info = {
            "monster_name": monster.name,
            "monster_strength": monster.strength,
            "player_strength": player.combat_strength(),
            "player_id": player.player_id,
            "player_name": player.name,
            "hero_id": player.hero.id.name if player.hero else None,
            "category": "monster",
            "level": level,
            "result": None,
        }
        self._last_combat_info = combat_info
        return {
            "phase": "combat",
            "log": log,
            "moved_from": pending["old_pos"], "moved_to": pending["new_pos"],
            "card_played": pending["card_value"], "tile_type": pending["tile_type"],
            "combat_info": combat_info,
        }

    def resolve_offer(self, choices: Optional[dict] = None) -> dict:
        """Phase-2 of an interactive turn: apply item placement choices.

        Must be called after ``begin_move`` returned ``phase == "offer_chest"``
        or ``"offer_shop"``.

        choices (chest)::
            {
              "take":               bool,           # True = take item
              "placement":          "equip"|"pack",
              "equip_action":       "swap"|"discard",  # if slot was full
              "equip_item_index":   int,            # which item in the slot to swap/discard
              "pack_discard_index": int,            # which pack slot to evict (if pack full)
              "adaptable_blade_two_handed": bool,
            }
        choices (shop)::
            {
              "chosen_index":       int,   # which of the offered items to keep
              "trait_index":        int,   # which trait to trade away (default 0)
              plus same placement keys as chest
            }
        """
        if choices is None:
            choices = {}

        pending = self._pending_offer
        self._pending_offer = None

        if pending is None:
            return {"phase": "done", "log": ["No pending offer."],
                    "game_status": self.status.name, "winner": self.winner}

        player = self.current_player
        offer_type = pending["type"]
        log: list[str] = []

        took_item = False
        shop_remaining: list[Item] = []

        if offer_type == "chest":
            item = pending["items"][0]
            if choices.get("take", False):
                self._apply_item_to_player(player, item, choices, log)
                took_item = True
            else:
                log.append(f"  {item.name} left behind.")

        elif offer_type == "shop":
            if not choices.get("take", True):
                log.append("Shop: left without taking.")
            else:
                items: list[Item] = pending["items"]
                cidx = min(int(choices.get("chosen_index", 0)), len(items) - 1)
                chosen = items[cidx]
                log.append(f"Shop: took {chosen.name}.")
                shop_remaining = [i for i in items if i is not chosen]
                if shop_remaining:
                    log.append(f"  Remaining items put back or discarded: {[i.name for i in shop_remaining]}")
                self._apply_item_to_player(player, chosen, choices, log)
                took_item = True

        # Check for Rake It In — pause if player took an item and has unlocked equips
        # Skip if the item came from a mystery event (Rake It In should not trigger)
        from_mystery = pending.get("from_mystery", False)
        if took_item and not from_mystery and any(t.effect_id == "rake_it_in" for t in player.traits):
            all_equips = player.helmets + player.chest_armor + player.leg_armor + player.weapons
            unlocked = [
                e for e in all_equips
                if not e.locked_by_curse_id
                or not any(c.effect_id == e.locked_by_curse_id for c in player.curses)
            ]
            pack_items = list(player.pack)
            consumable_items = list(player.consumables)
            if unlocked or pack_items or consumable_items:
                self._pending_offer = {
                    "type": "rake_it_in",
                    "sub_type": offer_type,
                    "level": pending["level"],
                    "shop_remaining": shop_remaining,
                    "moved_from": pending["moved_from"],
                    "moved_to": pending["moved_to"],
                    "card_played": pending["card_played"],
                    "tile_type": pending["tile_type"],
                    "log": log,
                }
                # Build equip dicts with correct per-slot indices
                equip_dicts = []
                for e in unlocked:
                    d = _item_to_dict(e)
                    if e in player.helmets:
                        d["slot_index"] = player.helmets.index(e)
                    elif e in player.chest_armor:
                        d["slot_index"] = player.chest_armor.index(e)
                    elif e in player.leg_armor:
                        d["slot_index"] = player.leg_armor.index(e)
                    elif e in player.weapons:
                        d["slot_index"] = player.weapons.index(e)
                    equip_dicts.append(d)
                return {
                    "phase": "rake_it_in",
                    "log": log,
                    "sub_type": offer_type,
                    "equips": equip_dicts,
                    "pack_items": [_item_to_dict(i) for i in pack_items],
                    "consumable_items": [{"name": c.name, "card_image": None} for c in consumable_items],
                    "shop_remaining": [_item_to_dict(i) for i in shop_remaining],
                    "moved_from": pending["moved_from"],
                    "moved_to": pending["moved_to"],
                    "card_played": pending["card_played"],
                    "tile_type": pending["tile_type"],
                }

        self._finish_post_encounter(player, log)
        if self.status == GameStatus.WON:
            log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")
        self._advance_turn()
        return {
            "phase": "done", "log": log,
            "moved_from": pending["moved_from"], "moved_to": pending["moved_to"],
            "card_played": pending["card_played"], "tile_type": pending["tile_type"],
            "combat_result": None, "game_status": self.status.name, "winner": self.winner,
        }

    def use_eight_lives(self, curse_index: int = 0) -> dict:
        """Immediately use the Eight Lives trait to remove a curse.

        Returns {"ok": True, "log": [...]} on success.
        """
        player = self.current_player
        eight_lives = next(
            (t for t in player.traits if t.effect_id == "eight_lives"), None
        )
        if not eight_lives:
            return {"ok": False, "log": ["No Eight Lives trait."]}
        removable = [
            c for c in player.curses
            if not c.source_monster
            or any(
                m.name == c.source_monster and m.level in (1, 2)
                for pool in (C.MONSTER_POOL_L1, C.MONSTER_POOL_L2)
                for m in pool
            )
        ]
        if not removable:
            return {"ok": False, "log": ["No removable curses."]}
        idx = max(0, min(curse_index, len(removable) - 1))
        removed = removable[idx]
        player.curses.remove(removed)
        player.traits.remove(eight_lives)
        log: list[str] = []
        _fx.on_trait_lost(player, eight_lives, log)
        _fx.refresh_tokens(player)
        log.append(f"  Eight Lives: discarded trait, removed curse '{removed.name}'!")
        return {"ok": True, "log": log}

    def resolve_rake_it_in(
        self,
        use_it: bool,
        discard_slot: str = "",
        discard_idx: int = 0,
        second_item_choice: int = -1,
        placement_choices: Optional[dict] = None,
    ) -> dict:
        """Resolve the Rake It In decision after a chest or shop offer.

        Call after ``resolve_offer`` returned ``phase == "rake_it_in"``.

        use_it=True → player discards an equipped item and draws/picks a bonus item.
        discard_slot  : "equip_helmet"|"equip_chest"|"equip_leg"|"equip_weapon"
        discard_idx   : index within that slot list
        second_item_choice : for shop sub-type, which remaining item to take (0-based).
                             Ignored for chest (random draw from deck).
        placement_choices  : same placement kwargs as resolve_offer for the bonus item.
        """
        pending = self._pending_offer
        self._pending_offer = None
        if pending is None or pending.get("type") != "rake_it_in":
            return {"phase": "done", "log": ["No pending Rake It In offer."],
                    "game_status": self.status.name, "winner": self.winner}

        player = self.current_player
        log: list[str] = pending.get("log", [])
        sub_type = pending.get("sub_type", "chest")
        level: int = pending.get("level", 1)
        bonus_item_info: Optional[dict] = None

        if use_it:
            if discard_slot == "pack":
                if 0 <= discard_idx < len(player.pack):
                    discarded = player.pack.pop(discard_idx)
                    log.append(f"  Rake It In!: discarded {discarded.name} from pack.")
                else:
                    log.append("  Rake It In!: invalid pack discard choice \u2014 skipping.")
                    use_it = False
            elif discard_slot == "consumable":
                if 0 <= discard_idx < len(player.consumables):
                    discarded = player.consumables.pop(discard_idx)
                    log.append(f"  Rake It In!: discarded {discarded.name} from consumables.")
                else:
                    log.append("  Rake It In!: invalid consumable discard choice \u2014 skipping.")
                    use_it = False
            else:
                slot_map = {
                    "equip_helmet": player.helmets,
                    "equip_chest":  player.chest_armor,
                    "equip_leg":    player.leg_armor,
                    "equip_weapon": player.weapons,
                }
                slot_list = slot_map.get(discard_slot, [])
                if slot_list and 0 <= discard_idx < len(slot_list):
                    discarded = slot_list[discard_idx]
                    player.unequip(discarded)
                    log.append(f"  Rake It In!: discarded {discarded.name}.")
                else:
                    log.append("  Rake It In!: invalid discard choice \u2014 skipping.")
                    use_it = False

        if use_it:
            if sub_type == "chest":
                # Draw a random bonus item from the tier deck — player chooses placement
                bonus = self.item_decks[level].draw()
                if bonus is not None:
                    player.pending_trait_items.append(bonus)
                    log.append(f"  Rake It In!: bonus item — {bonus.name}!")
                    bonus_item_info = _item_to_dict(bonus)
                else:
                    log.append("  Rake It In!: item deck empty — no bonus draw.")
            elif sub_type == "shop":
                remaining: list[Item] = pending.get("shop_remaining", [])
                if remaining and 0 <= second_item_choice < len(remaining):
                    bonus = remaining[second_item_choice]
                    self._apply_item_to_player(player, bonus, placement_choices or {}, log)
                    log.append(f"  Rake It In!: picked bonus shop item \u2014 {bonus.name}!")
                    bonus_item_info = _item_to_dict(bonus)
                else:
                    log.append("  Rake It In!: no valid second item chosen.")
        else:
            log.append("  Rake It In!: skipped.")

        self._finish_post_encounter(player, log)
        if self.status == GameStatus.WON:
            log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")
        # Defer turn advance if the bonus chest item still needs to be placed.
        if bonus_item_info is not None and sub_type == "chest":
            self._rakeitin_pending_placement = True
        else:
            self._advance_turn()
        return {
            "phase": "done",
            "log": log,
            "bonus_item": bonus_item_info,
            "moved_from": pending.get("moved_from"), "moved_to": pending.get("moved_to"),
            "card_played": pending.get("card_played"), "tile_type": pending.get("tile_type"),
            "combat_result": None, "game_status": self.status.name, "winner": self.winner,
        }

    def _apply_item_to_player(
        self,
        player: Player,
        item: Item,
        choices: dict,
        log: list[str],
    ) -> None:
        """Apply item placement choices (mirrors _offer_item but choice-driven)."""
        # Consumable wrapper — add directly to consumables list
        if item.is_consumable:
            import copy as _copy
            consumable = next((c for c in C.CONSUMABLE_POOL if c.name == item.name), None)
            if consumable:
                if player.add_consumable_to_pack(_copy.copy(consumable)):
                    log.append(f"  {item.name} added to consumables.")
                else:
                    # Pack full — evict the chosen slot
                    discard_idx = int(choices.get("pack_discard_index", -1))
                    if discard_idx >= 0:
                        evicted_name = player.evict_pack_slot(discard_idx)
                        if evicted_name:
                            log.append(f"  {evicted_name} discarded from pack.")
                        player.consumables.append(_copy.copy(consumable))
                        log.append(f"  {item.name} added to consumables.")
                    else:
                        log.append(f"  {item.name} (consumable) — pack full, discarded.")
            else:
                log.append(f"  {item.name} (consumable) — unknown type, discarded.")
            return

        # Adaptable Blade configuration
        if item.effect_id == "adaptable_blade":
            if choices.get("adaptable_blade_two_handed"):
                item.hands = 2
                item.strength_bonus = 8
                log.append("  Adaptable Blade: configured as 2H (+8 Str).")
            else:
                item.hands = 1
                item.strength_bonus = 4
                log.append("  Adaptable Blade: configured as 1H (+4 Str).")

        placement = choices.get("placement", "pack")

        if placement == "equip":
            if player.can_equip(item):
                player.equip(item)
                log.append(f"  {item.name} equipped.")
            else:
                slot_list = player._slot_list(item.slot)
                if not slot_list:
                    # No valid slot at all — treat as pack
                    if player.add_to_pack(item):
                        log.append(f"  Cannot equip {item.name} — added to pack.")
                    else:
                        log.append(f"  Cannot equip {item.name} and pack full — discarded.")
                else:
                    # 2H weapon with both weapon slots occupied — must clear both
                    if item.slot.value == "weapon" and item.hands == 2 and len(slot_list) >= 2:
                        for act_key, pdi_key in [
                            ("equip_action", "pack_discard_index"),
                            ("equip_action_2", "pack_discard_index_2"),
                        ]:
                            if not slot_list:
                                break
                            w = slot_list[0]
                            act = choices.get(act_key, "discard")
                            pdi = int(choices.get(pdi_key, -1))
                            if act == "swap":
                                if player.pack_slots_free > 0:
                                    player.unequip(w)
                                    player.pack.append(w)
                                    log.append(f"  {w.name} moved to pack.")
                                elif pdi >= 0:
                                    evicted_name = player.evict_pack_slot(pdi)
                                    if evicted_name:
                                        log.append(f"  Pack full — {evicted_name} discarded.")
                                    player.unequip(w)
                                    player.pack.append(w)
                                    log.append(f"  {w.name} moved to pack.")
                                else:
                                    player.unequip(w)
                                    log.append(f"  Pack full — {w.name} discarded.")
                            else:
                                player.unequip(w)
                                log.append(f"  {w.name} discarded.")
                        player.equip(item)
                        log.append(f"  {item.name} (2H) equipped.")
                    else:
                        cur_idx = min(
                            int(choices.get("equip_item_index", len(slot_list) - 1)),
                            len(slot_list) - 1,
                        )
                        current = slot_list[cur_idx]
                        action = choices.get("equip_action", "swap")
                        if action == "swap":
                            if player.pack_slots_free > 0:
                                player.unequip(current)
                                player.pack.append(current)
                                player.equip(item)
                                log.append(
                                    f"  {current.name} moved to pack. {item.name} equipped."
                                )
                            else:
                                discard_idx = int(choices.get("pack_discard_index", 0))
                                evicted_name = player.evict_pack_slot(discard_idx)
                                if evicted_name:
                                    log.append(f"  Pack full — {evicted_name} discarded.")
                                player.unequip(current)
                                player.pack.append(current)
                                player.equip(item)
                                log.append(
                                    f"  {current.name} moved to pack. {item.name} equipped."
                                )
                        else:  # discard currently equipped
                            player.unequip(current)
                            player.equip(item)
                            log.append(f"  {current.name} discarded. {item.name} equipped.")
        else:  # pack
            if player.add_to_pack(item):
                log.append(f"  {item.name} added to pack.")
            else:
                discard_idx = int(choices.get("pack_discard_index", 0))
                evicted_name = player.evict_pack_slot(discard_idx)
                if evicted_name:
                    log.append(f"  {evicted_name} discarded from pack.")
                player.pack.append(item)
                log.append(f"  {item.name} added to pack.")

        _fx.refresh_tokens(player)

    def _resolve_auto_encounter(
        self,
        player: Player,
        actual_type: TileType,
        tile,
        level: int,
        flee: bool,
        log: list[str],
    ) -> Optional[CombatResult]:
        """Auto-resolve all non-chest/shop encounters (used by begin_move)."""
        import re as _re
        combat_result: Optional[CombatResult] = None
        new_pos = tile.index
        self._last_combat_info = None
        log_before = len(log)
        auto_ctx = GameContext(
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

        if actual_type == TileType.BLANK:
            enc.encounter_blank(log)

        elif actual_type == TileType.MYSTERY:
            # Auto-resolve: skip mystery event in non-interactive mode
            log.append("Mystery Square — (auto-resolved, no effect).")

        elif actual_type == TileType.DAY_NIGHT:
            self.is_night = enc.encounter_day_night(self.is_night, log)

        elif actual_type == TileType.MONSTER:
            effective_deck = self.monster_decks[level]
            if level < 3 and any(
                t.effect_id == "no_more_charlie_work" for t in player.traits
            ):
                if self._decide(
                    f"No More Charlie Work: Fight from Tier {level + 1}?", log
                ):
                    effective_deck = self.monster_decks[level + 1]
                    log.append(f"  No More Charlie Work: drawing from Tier {level + 1}!")
            combat_result = enc.encounter_monster(
                player, effective_deck, auto_ctx,
                flee=flee,
            )
            if flee and combat_result is None and player.hero and player.hero.can_flee_monsters:
                self._apply_flee_move_back(player, log)

        elif actual_type == TileType.MINIBOSS:
            already_defeated = (
                (new_pos == 30 and player.miniboss1_defeated)
                or (new_pos == 60 and player.miniboss2_defeated)
            )
            if already_defeated:
                log.append("Miniboss already defeated \u2014 no encounter.")
            else:
                if new_pos == 30:
                    if self.active_miniboss_t1 is None:
                        self.active_miniboss_t1 = self.miniboss_deck_t1.draw()
                    miniboss = self.active_miniboss_t1
                    reward_deck = self.item_decks[2]
                else:
                    if self.active_miniboss_t2 is None:
                        self.active_miniboss_t2 = self.miniboss_deck_t2.draw()
                    miniboss = self.active_miniboss_t2
                    reward_deck = self.item_decks[3]

                if miniboss is None:
                    log.append("All minibosses for this tier have been defeated!")
                    if new_pos == 30:
                        player.miniboss1_defeated = True
                    else:
                        player.miniboss2_defeated = True
                else:
                    combat_result = enc.encounter_miniboss(
                        player, miniboss, reward_deck, auto_ctx,
                        flee=flee,
                    )
                    if flee and combat_result is None and player.hero and player.hero.can_flee_miniboss:
                        self._apply_flee_move_back(player, log)
                    elif combat_result == CombatResult.WIN:
                        if new_pos == 30:
                            player.miniboss1_defeated = True
                            self.active_miniboss_t1 = None
                        else:
                            player.miniboss2_defeated = True
                            self.active_miniboss_t2 = None

        elif actual_type == TileType.WERBLER:
            werbler = self.player_werblers.get(player.player_id)
            if werbler is None:
                log.append("No werbler assigned — skipping.")
            else:
                combat_result, self.status = enc.encounter_werbler(
                    player, werbler, auto_ctx,
                )
                if self.status == GameStatus.WON:
                    self.winner = player.player_id

        # Extract combat info from log for UI battle scene
        if combat_result is not None or (actual_type in (TileType.MONSTER, TileType.MINIBOSS, TileType.WERBLER)):
            monster_name = None
            monster_str = None
            category = "monster"
            for line in log[log_before:]:
                m = _re.search(r'(?:Monster|Miniboss|THE WERBLER): fighting (.+?) \(str (\d+)\)', line)
                if m:
                    monster_name = m.group(1)
                    monster_str = int(m.group(2))
                if 'Miniboss:' in line:
                    category = "miniboss"
                if 'THE WERBLER:' in line:
                    category = "werbler"
            if monster_name:
                self._last_combat_info = {
                    "monster_name": monster_name,
                    "monster_strength": monster_str,
                    "player_strength": player.combat_strength(),
                    "player_id": player.player_id,
                    "player_name": player.name,
                    "hero_id": player.hero.id.name if player.hero else None,
                    "category": category,
                    "level": level,
                    "result": combat_result.name if combat_result else None,
                }

        return combat_result

    def _finish_post_encounter(self, player: Player, log: list[str]) -> None:
        """Handle post-encounter housekeeping: pending draws and Me Too."""
        while player._pending_movement_draws > 0:
            card = self.movement_decks[player.player_id].draw()
            if card is not None:
                player.movement_hand.append(card)
                log.append(f"  Drew movement card {card} (pending draw).")
            player._pending_movement_draws -= 1

        if len(self.players) > 1:
            for other in self.players:
                if other is player:
                    continue
                me_too = next(
                    (t for t in other.traits if t.effect_id == "me_too"), None
                )
                if me_too and other.curses:
                    if self._decide(
                        f"Me Too!: {other.name}, discard a curse?", log
                    ):
                        removed = other.curses.pop(0)
                        _fx.refresh_tokens(other)
                        log.append(
                            f"  Me Too!: {other.name} discarded curse '{removed.name}'."
                        )

