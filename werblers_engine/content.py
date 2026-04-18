"""Content pools for the Werblers engine.

Monster pools are derived from ALL_MONSTERS (defined at the bottom of this
file) so that trait/curse data and deck draw data are never out of sync.
Item, trait, and curse pools are defined inline.
"""

from __future__ import annotations

from typing import Optional

from .types import Consumable, EquipSlot, Item, Monster, Trait, Curse


# ---------------------------------------------------------------------------
# Monster pools — derived from ALL_MONSTERS at bottom of this file
# (assigned after ALL_MONSTERS is defined)
# ---------------------------------------------------------------------------

# Miniboss and Werbler pools (shuffled into decks at game start)
MINIBOSS_POOL_T1: list[Monster] = [
    Monster("Shielded Golem", strength=14, level=1, effect_id="shielded_golem",
            description="Each equipped card grants 1 less Str than normal (min 0). "
                        "2H weapons provide +5 additional Str."),
    Monster("Flaming Golem", strength=11, level=1, effect_id="flaming_golem",
            description="Head+chest armour provide 2 less Str each (min 0). "
                        "If wearing a gauntlet → auto-win."),
    Monster("Ghostly Golem", strength=13, level=1, effect_id="ghostly_golem",
            description="If you lose, run backwards 10 spaces. "
                        "If anything equipped has 'Iron' in the name → auto-win."),
    Monster("Goaaaaaaaalem", strength=12, level=1, effect_id="goaaaaaaaalem",
            description="If no free hand slots → −5 Str. "
                        "Leg armour has ×2 Str."),
]

MINIBOSS_POOL_T2: list[Monster] = [
    Monster("Sky Dragon", strength=22, level=2, effect_id="sky_dragon",
            description="All weapons except guns provide 0 Str. "
                        "Guns provide +5 Str."),
    Monster("Crossroads Demon", strength=23, level=2, effect_id="crossroads_demon",
            description="If not wearing head armour → −10 Str. "
                        "Before fight, may discard equipped cards; on win draw that many T3 items."),
    Monster("The Watcher", strength=24, level=2, effect_id="the_watcher",
            description="May not use consumables for this fight. "
                        "All empty equip slots provide +2 Str each."),
    Monster("Ogre Cutpurse", strength=25, level=2, effect_id="ogre_cutpurse",
            description="Discard all pack items at combat start; if any items were in pack, "
                        "add their Str to monster. If pack was ALREADY empty before pillage \u2192 +5 Str to player."),
]

WERBLER_POOL: list[Monster] = [
    Monster("Brady the Bicephalous", strength=40, level=3, effect_id="brady",
            description="All melee weapons have −3 Str. "
                        "If you lose, he steals head armour, gains that Str permanently (max 2 thefts)."),
    Monster("Harry the High Elf", strength=40, level=3, effect_id="harry",
            description="+10 Str during the day. "
                        "If you lose, draw T3 monster card and take its curse."),
    Monster("Ar-Meg-Geddon", strength=40, level=3, effect_id="ar_meg_geddon",
            description="Minions refuse to fight, don't contribute Str. "
                        "If you lose, discard chest and leg slot equipment."),
    Monster("Joh'Neil The Slimelord", strength=40, level=3, effect_id="johnil",
            description="1H weapons have −4 Str. "
                        "If you lose, lose 2 traits of your choice."),
]

# Legacy aliases — kept for any code that still references the old names.
# In practice, game.py now uses the pool + deck system.
MINIBOSS_1 = MINIBOSS_POOL_T1[0]
MINIBOSS_2 = MINIBOSS_POOL_T2[0]
THE_WERBLER = WERBLER_POOL[0]


# ---------------------------------------------------------------------------
# Item pools (finite decks, one per level)
# ---------------------------------------------------------------------------

ITEM_POOL_L1: list[Item] = [
    Item("Spork", EquipSlot.WEAPON, strength_bonus=1),
    Item("Rusty Blade", EquipSlot.WEAPON, strength_bonus=2),
    # Chest armour (Tier 1)
    Item("Sweater Vest", EquipSlot.CHEST, strength_bonus=1),
    Item("Peasant's Robes", EquipSlot.CHEST, strength_bonus=1),
    Item("Puffy Shirt", EquipSlot.CHEST, strength_bonus=2),
    Item("Junk Mail", EquipSlot.CHEST, strength_bonus=2),
    Item("Leather Armour", EquipSlot.CHEST, strength_bonus=3),
    Item("Fan Mail", EquipSlot.CHEST, strength_bonus=3),
    Item("Barbarian Armour", EquipSlot.CHEST, strength_bonus=3, effect_id="barbarian_armour"),
    # Leg armour (Tier 1)
    Item("Flip Flops", EquipSlot.LEGS, strength_bonus=1),
    Item("Sandals", EquipSlot.LEGS, strength_bonus=1),
    Item("Pumped Up Kicks", EquipSlot.LEGS, strength_bonus=2),
    Item("Rubber Boots", EquipSlot.LEGS, strength_bonus=2),
    Item("Soccer Cleats", EquipSlot.LEGS, strength_bonus=3),
    Item("Steel-Toed Boots", EquipSlot.LEGS, strength_bonus=3),
    Item("Pot Lid", EquipSlot.WEAPON, strength_bonus=1),
    Item("Poin-ted Stick", EquipSlot.WEAPON, strength_bonus=2),
    Item("Mirror Shield", EquipSlot.WEAPON, strength_bonus=2),
    Item("Rat Basher", EquipSlot.WEAPON, strength_bonus=3),
    Item("Rubber Chicken", EquipSlot.WEAPON, strength_bonus=1),
    Item("Spear Head", EquipSlot.WEAPON, strength_bonus=3),
    Item("Steak Knife", EquipSlot.WEAPON, strength_bonus=2),
    Item("Sweeney's Razor", EquipSlot.WEAPON, strength_bonus=4),
    Item("Big Ol' Hammer", EquipSlot.WEAPON, strength_bonus=4, hands=2),
    Item("Steel Katar", EquipSlot.WEAPON, strength_bonus=4),
    Item("Long Poking Device", EquipSlot.WEAPON, strength_bonus=3, hands=2),
    Item("Hiking Boots", EquipSlot.LEGS, strength_bonus=2),
    # Head armours (Level 1, simple)
    Item("Colander", EquipSlot.HELMET, strength_bonus=1),  # You just look dumb.
    Item("Propeller Hat", EquipSlot.HELMET, strength_bonus=2),  # It’s fun, but not the most effective.
    Item("Leather Cap", EquipSlot.HELMET, strength_bonus=3),  # Fairly functional.
    Item("Sweet bandana", EquipSlot.HELMET, strength_bonus=2),  # Lookin’ good!
    Item("Miner’s Helmet", EquipSlot.HELMET, strength_bonus=3),  # It has a snazzy light!
    Item("Baseball Cap", EquipSlot.HELMET, strength_bonus=2),  # Please don’t wear it backwards.
    Item("Nazi Helmet", EquipSlot.HELMET, strength_bonus=3),  # Is it worth it? Really?
    Item("Lupine Helm", EquipSlot.HELMET, strength_bonus=4),  # It’s a wolf skull. From a dead wolf. Wicked.
    Item("Paper Bag", EquipSlot.HELMET, strength_bonus=1),  # Ability: Enemies cannot see your gender or class.

    Item("Squire’s Helm", EquipSlot.HELMET, strength_bonus=4),  # It’s like the Knight’s Helm… but slightly worse.
    Item("Swiss Guard Helmet", EquipSlot.HELMET, strength_bonus=5),  # Feathers? How fancy!
    # Tier 1 consumables (2 copies each)
    Item("Monster Capture Device Mark I",  EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Monster Capture Device Mark I",  EquipSlot.CONSUMABLE, is_consumable=True),
    Item("H-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("H-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("H-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("H-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Priest\u2019s Blessing",          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Priest\u2019s Blessing",          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Vial of Nervous Shrinkage",       EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Vial of Nervous Shrinkage",       EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Potion of Minor Embiggening",     EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Potion of Minor Embiggening",     EquipSlot.CONSUMABLE, is_consumable=True),
]

ITEM_POOL_L2: list[Item] = [
    # Chest armour (Tier 2)
    Item("Iron Armour", EquipSlot.CHEST, strength_bonus=4),
    Item("3D-Printed Armour", EquipSlot.CHEST, strength_bonus=5),
    Item("Steel Plate Armour", EquipSlot.CHEST, strength_bonus=6),
    Item("Chain Mail", EquipSlot.CHEST, strength_bonus=6),
    Item("Bulletproof Vest", EquipSlot.CHEST, strength_bonus=6),
    Item("Wizard's Robes", EquipSlot.CHEST, strength_bonus=1, effect_id="wizards_robes"),
    # Leg armour (Tier 2)
    Item("Iron Greaves", EquipSlot.LEGS, strength_bonus=4),
    Item("Pointy Shoes", EquipSlot.LEGS, strength_bonus=4),
    Item("Homelander's Heels", EquipSlot.LEGS, strength_bonus=5),
    Item("Wheelies", EquipSlot.LEGS, strength_bonus=2, effect_id="wheelies"),
    Item("Steel Greaves", EquipSlot.LEGS, strength_bonus=6),
    Item("Cool Hwip", EquipSlot.WEAPON, strength_bonus=5),
    Item("Barbarian Sword", EquipSlot.WEAPON, strength_bonus=5, effect_id="barbarian_sword"),
    Item("No'Cappin's Scimitar", EquipSlot.WEAPON, strength_bonus=6, effect_id="nocappins_scimitar"),
    Item("No'Cappin's Scimitar", EquipSlot.WEAPON, strength_bonus=6, effect_id="nocappins_scimitar"),
    Item("Tower Shield", EquipSlot.WEAPON, strength_bonus=6),
    Item("Caped Longsword", EquipSlot.WEAPON, strength_bonus=5),
    Item("Rapier of Taltos", EquipSlot.WEAPON, strength_bonus=7),
    Item("Transmogrifier", EquipSlot.WEAPON, strength_bonus=0, effect_id="transmogrifier"),
    Item("Freeze Ray", EquipSlot.WEAPON, strength_bonus=2, hands=2, effect_id="freeze_ray", is_ranged=True),
    Item("Football Helmet", EquipSlot.HELMET, strength_bonus=5),  # Won't prevent concussion.
    # Tier 2 consumables (2 copies each)
    Item("Monster Capture Device Mark II",  EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Monster Capture Device Mark II",  EquipSlot.CONSUMABLE, is_consumable=True),
    Item("S-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("S-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("S-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("S-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Many Priests\u2019 Blessings",   EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Many Priests\u2019 Blessings",   EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Vial Was in the Pool",            EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Vial Was in the Pool",            EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Potion of Moderate Embiggening", EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Potion of Moderate Embiggening", EquipSlot.CONSUMABLE, is_consumable=True),
]

ITEM_POOL_L3: list[Item] = [
    # Chest armour (Tier 3)
    Item("Padded Doublet of Light", EquipSlot.CHEST, strength_bonus=7),
    Item("Bionic Arms", EquipSlot.CHEST, strength_bonus=1, effect_id="bionic_arms", weapon_hand_bonus=2),
    Item("Mithril Chain Vest", EquipSlot.CHEST, strength_bonus=8),
    Item("Dragonscale Chestplate", EquipSlot.CHEST, strength_bonus=8),
    Item("Chestplate Made of What the Black Box is Made of", EquipSlot.CHEST, strength_bonus=8),
    # Leg armour (Tier 3)
    Item("Boots of Agility", EquipSlot.LEGS, strength_bonus=1, effect_id="boots_of_agility"),
    Item("Dragonskin Boots", EquipSlot.LEGS, strength_bonus=7),
    Item("Boots of Rooting", EquipSlot.LEGS, strength_bonus=5, effect_id="boots_of_rooting"),
    Item("Hermes' Shoes", EquipSlot.LEGS, strength_bonus=5, effect_id="hermes_shoes"),
    Item("Boots of Streaking", EquipSlot.LEGS, strength_bonus=7, effect_id="boots_of_streaking"),
    Item("Armoured Jordans", EquipSlot.LEGS, strength_bonus=8),
    Item("Patriotic Shield", EquipSlot.WEAPON, strength_bonus=8),
    Item("Mage's Gauntlet", EquipSlot.WEAPON, strength_bonus=5, effect_id="mages_gauntlet"),
    Item("Mistress Sword", EquipSlot.WEAPON, strength_bonus=8),
    Item("Claymore of Freedom", EquipSlot.WEAPON, strength_bonus=11, hands=2),
    Item("Giant's Short Sword", EquipSlot.WEAPON, strength_bonus=10, hands=2),
    Item("Plasma Blaster", EquipSlot.WEAPON, strength_bonus=14, hands=2, is_ranged=True, is_gun=True),
    Item("Devil's Guitar", EquipSlot.WEAPON, strength_bonus=13, hands=2),
    Item("Laser Rifle", EquipSlot.WEAPON, strength_bonus=16, hands=2, is_ranged=True, is_gun=True),
    Item("Flaming Claymore", EquipSlot.WEAPON, strength_bonus=12, hands=2),
    Item("Motha-flippin' Machine Gun", EquipSlot.WEAPON, strength_bonus=12, hands=2, is_ranged=True, is_gun=True),
    Item("Alien Rifle", EquipSlot.WEAPON, strength_bonus=17, hands=2, is_ranged=True, is_gun=True),
    Item("Inconveniently Large Sword", EquipSlot.WEAPON, strength_bonus=25, hands=4),
    Item("Bugger Blaster", EquipSlot.WEAPON, strength_bonus=10, is_ranged=True, is_gun=True),
    Item("Crown of the Colossus", EquipSlot.HELMET, strength_bonus=7),  # It's a bit bulky
    Item("Astronaut Helmet", EquipSlot.HELMET, strength_bonus=6),  # You're not the man they think you are at home
    Item("Horned Helm", EquipSlot.HELMET, strength_bonus=7),  # They look so cool in Skyrim
    Item("Knight's Helm", EquipSlot.HELMET, strength_bonus=7),  # So noble. So powerful. So… hard to see…
    Item("Crown of Thorns", EquipSlot.HELMET, strength_bonus=1, effect_id="crown_of_thorns"),  # Ability: +1 Str per Trait
    Item("Face Mask", EquipSlot.HELMET, strength_bonus=5, effect_id="face_mask"),  # Ability: Coronavirus auto-win; +5 Str tokens on kill
    # Tier 3 consumables (2 copies each)
    Item("Monster Capture Device Mark III", EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Monster Capture Device Mark III", EquipSlot.CONSUMABLE, is_consumable=True),
    Item("F-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("F-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("F-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("F-Bomb",                          EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Nectar of the Gods",              EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Nectar of the Gods",              EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Ice Bath Vial",                   EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Ice Bath Vial",                   EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Potion of Major Embiggening",     EquipSlot.CONSUMABLE, is_consumable=True),
    Item("Potion of Major Embiggening",     EquipSlot.CONSUMABLE, is_consumable=True),
]


# ---------------------------------------------------------------------------
# Trait / Curse pools (placeholder)
# ---------------------------------------------------------------------------

TRAIT_POOL: list[Trait] = [
    Trait("Strong Arm", strength_bonus=1),
    Trait("Quick Feet", move_bonus=1),
    Trait("Eagle Eye", strength_bonus=1),
    Trait("Iron Will", strength_bonus=2),
    Trait("Big Pockets", weapon_hand_bonus=1),
    Trait("Keen Senses", hand_size_bonus=1),
]

CURSE_POOL: list[Curse] = [
    Curse("Weakness", strength_bonus=-1),
    Curse("Sluggish", move_bonus=-1),
    Curse("Clumsy", strength_bonus=-1),
    Curse("Cursed Grip", weapon_hand_bonus=-1),
    Curse("Brain Fog", hand_size_bonus=-1),
]


# ---------------------------------------------------------------------------
# Movement deck (placeholder)
# ---------------------------------------------------------------------------

MOVEMENT_DECK: list[int] = [1,1,1,1,1,1, 2,2,2,2,2,2, 3,3,3,3,3,3, 4,4,4,4,4,4, 5,5,5,5,5,5]
"""Default finite movement deck.  Contains cards valued 1–5."""


# ---------------------------------------------------------------------------
# Trait / Curse description lookups (for UI tooltips)
# ---------------------------------------------------------------------------

TRAIT_DESCRIPTIONS: dict[str, str] = {
    # Generic pool traits
    "Strong Arm": "+1 Str permanently.",
    "Quick Feet": "+1 to all movement card values.",
    "Eagle Eye": "+1 Str permanently.",
    "Iron Will": "+2 Str permanently.",
    "Big Pockets": "+1 weapon hand slot.",
    "Keen Senses": "+1 max hand size.",
    # Monster traits — flat bonuses
    "Hard Shell": "+2 Str permanently.",
    "Stomach of Steel": "+3 Str permanently.",
    "Spiked Hide": "+4 Str permanently.",
    "Battle Hardened": "+5 Str permanently.",
    "Blood Pact": "+3 Str permanently.",
    "Gremlin's Cunning": "+2 Str permanently.",
    "Adorable": "Gain a Cute Gremlin Minion Card (+2 Str).",
    # Monster traits — conditional
    "Calloused": "+3 Str when not wearing any headgear.",
    "BDE": "+5 Str. If you have no foot armour.",
    "Tough Skin": "When you have no Chest armour, gain +10 Str.",
    "Bark Worse Than its Bite": "+3 Str for each empty equipment slot.",
    "Strengthened by Taint": "+2 Str for each curse you have.",
    # Monster traits — on-gain items / special
    "Ball and Chain": "Gain the Ball and Chain item (Weapon, +5 Str).",
    "You Got a Birdie!": "Take a Power Driver Equip Card (2H, +10 Str).",
    "Kapwing!": "Gain a Bulletproof Vest (+6 chest armour).",
    "I'm a Grown-up Now!": "Gain a Ted Bearson Minion Card (+3 Str).",
    "Alpha": "Gain a Pet Velociraptor Minion Card (+5 Str).",
    "She's Melting!": "Gain a Vial of Liquid Witch consumable (+10 Str in one battle).",
    "My Hands are Awesome\u2026": "+1 max hand size.",
    "Big Boned!": "+1 chest armour slot.",
    "Touchdown!": "+3 Str. Discard to teleport directly to the Werbler tile (90).",
    "Rake It In!": "At chests/shops, you may discard an equipped item to draw a second item.",
    "No More Charlie Work!": "Once per turn, may fight monsters from the next tier up.",
    "Rat Smasher": "Auto-win against any monster with 'rat' or 'cat' in its name.",
    "Immunized": "Negate the next curse you would receive.",
    "Rust Immunity": "Immune to curses that destroy or damage your weapons.",
    "Phallic Dexterity": "Immune to curses that destroy or interact with your footgear.",
    "8 Lives to Go!": "Discard this trait to remove one of your Tier 1 or 2 curses.",
    "I See Everything!": "Once per encounter, send a monster back and draw another.",
    "Leather Daddy": "+1 Str token each time you lose a fight.",
    "It's Not Your Fault!": "On defeat, discard this to gain the monster's trait instead of its curse.",
    "Strong Schlong": "Spend tokens to reduce an opponent's Str by 3 each during their fight.",
    "Phase Shift": "Discard an equipped item to toggle Day/Night.",
    "I'll Come In Again": "Once per encounter, send a monster back and draw another.",
    "Me Too!": "When another player discards a curse, you may also discard one of yours.",
    "Fancy Footwork": "Reduce your movement value by 1 or 2 this turn.",
    "Residuals": "+1 Str token at the start of each of your turns.",
    "Vaxxed!": "Immune to all Tier 2 curses.",
    "You're the Alpha!": "Each of your minions (current and future) gains +1 Str while you hold this trait. Tokens are removed if you lose it.",
    "He's Just Misunderstood!": "Gain a Swamp Friend Minion Card (+7 Str).",
    "I'm De Overlord Now.": "Gain a Minion Wrangler (+3 Str, buffs all other minions +2 Str each).",
    "New Lord in Town.": "Gain a Demon Spawn Minion Card (+6 Str).",
    "Meat's Back On the Menu!": "Force an opponent to discard a minion; gain +5 Str tokens.",
    "Scavenger": "At chests/shops, may reject an item and draw another instead.",
    "Swiftness": "Flee any monster encounter at no cost (not the Werbler).",
}

CURSE_DESCRIPTIONS: dict[str, str] = {
    # Generic pool curses
    "Weakness": "-1 Str permanently.",
    "Sluggish": "-1 to all movement card values.",
    "Clumsy": "-1 Str permanently.",
    "Cursed Grip": "-1 weapon hand slot.",
    "Brain Fog": "-1 max hand size.",
    # Monster curses — flat penalties
    "Bit o' the Plague": "-2 Str permanently.",
    "Bad Vibes": "-1 Str permanently.",
    "Sapped": "-3 Str permanently.",
    "Blood Drain": "-4 Str permanently.",
    "Don't Get It Wet!": "-2 Str permanently.",
    "Don't Get it Wet": "Gain a Crazed Gremlin Minion Card (-2 Str).",
    "Bit More Plague": "-3 Str permanently.",
    "That'll Leave a Mark!": "-3 Str permanently.",
    "Termites!": "-5 Str permanently.",
    "Shot Through the Heart!": "Discard chest armour. Gunshot Wound (-3 Str, locked) placed in chest slot.",
    # Monster curses — conditional / equipment
    "Nevernude": "-5 Str for each empty equipment slot.",
    "Facial Coverings Required": "-10 Str if you have no headgear equipped.",
    "Stabbed": "-1 Str for each curse afflicting you.",
    "It Got In!": "Your footgear is destroyed immediately.",
    "The Rust is Spreading!": "Discard all equipped weapons immediately.",
    "I Need a Place to Go!": "If you're wearing boots, discard them.",
    "Laundry Day!": "All armour (helmet, chest, legs) moved to pack or discarded.",
    "The Smell Won't Come Out!": "Discard 2 equipped items.",
    "My Drink Tastes Funny\u2026": "Discard 2 equipped items.",
    "Now, Cardinal, the Rack!": "Discard 1 trait or equipped item per curse you have.",
    "Roughing the Kicker!": "Move back 15 spaces immediately.",
    "Blacklisted!": "Sent back to Start (tile 1).",
    "Quite the Setback!": "Move back 10 spaces. Discard all 3 and 4 movement cards.",
    "Yer a Hare, Wizard!": "5 movement cards are treated as a 1.",
    "Eughghghghgh": "Snap! If you have more curses than traits, treat all 1 movement cards as a 0. If you play a 0, reactivate the current tile.",
    "Botched Circumcision": "All movement cards −1 permanently (min 1).",
    "Scared of the Dark": "-1 to all movement card values during Night.",
    "Dude, Where's My Card?": "-1 max hand size.",
    "Together Forever!": "Lonely Teddy (-2 Str minion) joins your party.",
    "Get Rekt!": "Discard your highest-Str equipped item immediately.",
    "They Flooded Your Base!": "Your entire pack is cleared.",
    "Clever Girl\u2026": "Your entire pack is cleared.",
    "Out of Phase": "Pack limit reduced to 1 item.",
    "Can't Stop the Music!": "Dancing Shoes (+1 Str, locked) forced onto your feet.",
    "Enslaved!": "Give 2 of your items to an opponent.",
    "I Drank its Blood!": "-3 Str. Each vampire-type monster gains +5 Str against you.",
    "KNEEL!": "+10 Str to the Werbler per stack of this curse you have.",
    "It's Wriggling!": "Each time you gain a new curse, also lose one trait.",
    "You're On the Menu\u2026": "Bloody Stump (-2 Str, locked) placed in weapon or boot slot.",
    "Wait, You Lost to THIS?": "...nothing happens. Absolutely mortifying.",
    "It's Taking Over!": "Discard all items equipped to your legs and chest.",
    "So\u2026 Lethargic\u2026": "Each time you play a 3 or 4 movement card, lose 1 Str token.",
    "Bad Trip": "Your movement cards are drawn and played blind (random).",
    "Cursed!": "Auto-lose your next fight.",
    "He Drank Your Blood. Then Ate Your Arm.": "-3 Str. Lose one equipped item immediately.",
}


# ---------------------------------------------------------------------------
# Consumable pool
# ---------------------------------------------------------------------------

CONSUMABLE_POOL: list[Consumable] = [
    # Monster strength modifiers (negative = weaken, positive = strengthen)
    Consumable("Vial of Nervous Shrinkage",       effect_id="monster_str_mod", effect_value=-3),
    Consumable("Vial Was in the Pool",             effect_id="monster_str_mod", effect_value=-5),
    Consumable("Ice Bath Vial",                    effect_id="monster_str_mod", effect_value=-7),
    Consumable("Potion of Minor Embiggening",      effect_id="monster_str_mod", effect_value=3),
    Consumable("Potion of Moderate Embiggening",   effect_id="monster_str_mod", effect_value=5),
    Consumable("Potion of Major Embiggening",      effect_id="monster_str_mod", effect_value=7),
    # Bombs: draw a Tier-N monster, give its curse to a chosen player
    Consumable("H-Bomb", effect_id="give_curse", effect_tier=1),
    Consumable("S-Bomb", effect_id="give_curse", effect_tier=2),
    Consumable("F-Bomb", effect_id="give_curse", effect_tier=3),
    # Blessings: draw a Tier-N monster, gain its trait for yourself
    Consumable("Priest\u2019s Blessing",      effect_id="gain_trait", effect_tier=1),
    Consumable("Many Priests\u2019 Blessings", effect_id="gain_trait", effect_tier=2),
    Consumable("Nectar of the Gods",          effect_id="gain_trait", effect_tier=3),
    # Capture devices: capture the monster being fought (tier must match)
    Consumable("Monster Capture Device Mark I",   effect_id="capture_monster", effect_tier=1),
    Consumable("Monster Capture Device Mark II",  effect_id="capture_monster", effect_tier=2),
    Consumable("Monster Capture Device Mark III", effect_id="capture_monster", effect_tier=3),
]


# ---------------------------------------------------------------------------
# Monster → trait / curse factory
# ---------------------------------------------------------------------------

# Keyed by exact trait/curse name from the Monster card.
# Only the non-default fields need listing (name and source_monster are set
# dynamically by the factory functions below).
_TRAIT_REGISTRY: dict[str, dict] = {
    # Flat strength bonuses
    "Hard Shell":              {"strength_bonus": 2},
    "Stomach of Steel":        {"strength_bonus": 3},
    "Spiked Hide":             {"strength_bonus": 4},
    "Battle Hardened":         {"strength_bonus": 5},
    "Iron Will":               {"strength_bonus": 2},
    "Blood Pact":              {"strength_bonus": 3},
    "Gremlin's Cunning":       {"strength_bonus": 2},
    # Conditional strength hooks
    "Calloused":               {"effect_id": "calloused"},
    "BDE":                     {"effect_id": "bde"},
    "Tough Skin":              {"effect_id": "tough_skin"},
    "Bark Worse Than its Bite":{"effect_id": "bark_worse_than_bite"},
    "Strengthened by Taint":   {"effect_id": "strengthened_by_taint"},
    # On-gain item grants
    "Ball and Chain":          {"effect_id": "ball_and_chain"},
    "You Got a Birdie!":       {"effect_id": "birdie"},
    "Kapwing!":                {"effect_id": "kapwing"},
    # Deferred (minion / special item)
    "I'm a Grown-up Now!":          {"effect_id": "grown_up"},
    "Alpha":                        {"effect_id": "alpha"},
    "She's Melting!":               {"effect_id": "shes_melting"},
    # --- Traits added with real monster roster ---
    # Flat hand-size bonuses
    "My Hands are Awesome\u2026":  {"hand_size_bonus": 1, "effect_id": "my_hands_awesome"},
    # Extra chest slot
    "Big Boned!":              {"chest_slot_bonus": 1},
    # Gremlin minion grant
    "Adorable":                {"effect_id": "adorable"},
    # Flat strength bonuses (already-registered entries: Hard Shell, Stomach of Steel, etc.)
    "Touchdown!":              {"effect_id": "touchdown", "strength_bonus": 3},
    # Deferred — complex behaviour not yet wired to engine
    "Rake It In!":             {"effect_id": "rake_it_in"},
    "No More Charlie Work!":   {"effect_id": "no_more_charlie_work"},
    "Rat Smasher":             {"effect_id": "rat_smasher"},
    "Immunized":               {"effect_id": "immunized"},
    "Rust Immunity":           {"effect_id": "rust_immunity"},
    "Phallic Dexterity":       {"effect_id": "phallic_dexterity"},
    "8 Lives to Go!":          {"effect_id": "eight_lives"},
    "I See Everything!":       {"effect_id": "i_see_everything"},
    "Leather Daddy":           {"effect_id": "leather_daddy"},
    "It's Not Your Fault!":    {"effect_id": "its_not_your_fault"},
    "Strong Schlong":          {"effect_id": "strong_schlong"},
    "Phase Shift":             {"effect_id": "phase_shift"},
    "I'll Come In Again":      {"effect_id": "ill_come_in_again"},
    "Me Too!":                 {"effect_id": "me_too"},
    "Fancy Footwork":          {"effect_id": "fancy_footwork"},
    "Residuals":               {"effect_id": "residuals"},
    "Vaxxed!":                 {"effect_id": "vaxxed"},
    "You're the Alpha!":       {"effect_id": "youre_the_alpha"},
    # Real card names for renamed / activated traits
    "He's Just Misunderstood!":    {"effect_id": "misunderstood"},
    "I'm De Overlord Now.":        {"effect_id": "overlord"},
    "New Lord in Town.":           {"effect_id": "new_lord"},
    "Meat's Back On the Menu!":    {"effect_id": "meat_on_menu"},
    "Scavenger":                   {"effect_id": "scavenger"},
    "Swiftness":                   {"effect_id": "swiftness"},
}

_CURSE_REGISTRY: dict[str, dict] = {
    # Flat strength penalties
    "Bit o' the Plague":       {"strength_bonus": -2},
    "Bad Vibes":               {"strength_bonus": -1},
    "Sapped":                  {"strength_bonus": -3},
    "Blood Drain":             {"strength_bonus": -4},
    "Don't Get It Wet!":       {"strength_bonus": -2},
    "Don't Get it Wet":        {"effect_id": "dont_get_it_wet_gremlin"},
    # Conditional strength hooks
    "Nevernude":               {"effect_id": "nevernude"},
    "Facial Coverings Required":{"effect_id": "facial_coverings"},
    "Stabbed":                 {"effect_id": "stabbed"},
    # Equipment destruction
    "It Got In!":              {"effect_id": "it_got_in"},
    "The Rust is Spreading!":  {"effect_id": "rust_spreading"},
    "I Need a Place to Go!":   {"effect_id": "need_a_place"},
    "Laundry Day!":            {"effect_id": "laundry_day"},
    "The Smell Won't Come Out!":{"effect_id": "smell_wont_come_out"},
    "My Drink Tastes Funny\u2026":  {"effect_id": "drink_tastes_funny"},
    "Shot Through the Heart!":  {"effect_id": "shot_through_heart", "strength_bonus": -5},
    "Now, Cardinal, the Rack!": {"effect_id": "the_rack"},
    # Move-back
    "Roughing the Kicker!":    {"effect_id": "roughing_kicker"},
    "Blacklisted!":            {"effect_id": "blacklisted"},
    "Quite the Setback!":      {"effect_id": "quite_setback"},
    # Movement modification
    "Yer a Hare, Wizard!":     {"effect_id": "yer_a_hare"},
    "Eughghghghgh":            {"effect_id": "eughghghghgh"},
    "Botched Circumcision":    {"effect_id": "botched_circumcision"},
    "Scared of the Dark":      {"effect_id": "scared_of_dark"},
    # Hand size
    "Dude, Where's My Card?":  {"effect_id": "dude_wheres_my_card"},
    # Deferred
    "Together Forever!":           {"effect_id": "together_forever"},
    "Get Rekt!":                   {"effect_id": "get_rekt"},
    "They Flooded Your Base!":     {"effect_id": "flooded_base"},
    "Clever Girl\u2026":            {"effect_id": "clever_girl"},
    "Out of Phase":                {"effect_id": "out_of_phase"},
    "Can't Stop the Music!":       {"effect_id": "cant_stop_music"},
    "Enslaved!":                   {"effect_id": "enslaved"},
    "I Drank its Blood!":          {"effect_id": "drank_blood"},
    "KNEEL!":                      {"effect_id": "kneel"},
    "It's Wriggling!":             {"effect_id": "its_wriggling"},
    "You're On the Menu\u2026":    {"effect_id": "youre_on_menu"},
    # --- Curses added with real monster roster ---
    # Flat strength penalties
    "Bit More Plague":         {"strength_bonus": -3},
    "That'll Leave a Mark!":   {"strength_bonus": -3},
    "Termites!":               {"strength_bonus": -5},
    # Newly implemented effects
    "Wait, You Lost to THIS?": {"effect_id": "walk_of_shame"},  # self-removes on gain; never in pool
    "It's Taking Over!":       {"effect_id": "its_taking_over", "strength_bonus": 0},
    "So\u2026 Lethargic\u2026": {"effect_id": "so_lethargic"},
    "Bad Trip":                {"effect_id": "bad_trip"},
    "Cursed!":                 {"effect_id": "cursed_auto_lose"},
    "He Drank Your Blood. Then Ate Your Arm.": {"effect_id": "drank_blood"},
}


def trait_for_monster(monster: Monster) -> Optional[Trait]:
    """Return the named Trait associated with this monster, or None.

    Returns None when the monster has no ``trait_name`` or when the name
    is not yet in the registry (placeholder monsters).
    """
    if not monster.trait_name:
        return None
    entry = _TRAIT_REGISTRY.get(monster.trait_name)
    if entry is None:
        return None
    return Trait(name=monster.trait_name, source_monster=monster.name, **entry)


def curse_for_monster(monster: Monster) -> Optional[Curse]:
    """Return the named Curse associated with this monster, or None.

    Returns None when the monster has no ``curse_name`` or when the name
    is not yet in the registry.
    """
    if not monster.curse_name:
        return None
    entry = _CURSE_REGISTRY.get(monster.curse_name)
    if entry is None:
        return None
    return Curse(name=monster.curse_name, source_monster=monster.name, **entry)


# Full roster of real (non-placeholder) monsters.
# Every entry here must have both trait_name and curse_name in the registries.
# Placeholder monsters in MONSTER_POOL_* are NOT included.
ALL_MONSTERS: list[Monster] = [
    # ── Level 1 (strength 1-10) ──────────────────────────────────────────
    Monster("Nose Goblin",          strength=1,  level=1,
            trait_name="Calloused",              curse_name="Wait, You Lost to THIS?"),
    Monster("Attack Turtle",         strength=2,  level=1,
            trait_name="Hard Shell",              curse_name="Yer a Hare, Wizard!"),
    Monster("Rake",                  strength=2,  level=1,
            trait_name="Rake It In!",             curse_name="Eughghghghgh"),
    Monster("Cursed Teddy Bear",     strength=2,  level=1,
            trait_name="I'm a Grown-up Now!",     curse_name="Together Forever!"),
    Monster("Trouser Snake",         strength=3,  level=1,
            trait_name="BDE",                     curse_name="It Got In!"),
    Monster("Big Rat",               strength=3,  level=1,
            trait_name="No More Charlie Work!",   curse_name="Bit o' the Plague"),
    Monster("Slightly Bigger Rat",   strength=4,  level=1,
            trait_name="Rat Smasher",             curse_name="Bit More Plague"),
    Monster("Diseased Gnome",        strength=5,  level=1,
            trait_name="Immunized",               curse_name="It's Taking Over!"),
    Monster("Rusty Golem",           strength=6,  level=1,
            trait_name="Rust Immunity",           curse_name="The Rust is Spreading!"),
    Monster("Penis Fly Trap",        strength=6,  level=1,
            trait_name="Phallic Dexterity",       curse_name="Botched Circumcision",
            bonus_vs_male=3),
    Monster("Wrecking Ball",         strength=8,  level=1,
            trait_name="Ball and Chain",          curse_name="Get Rekt!"),
    Monster("Cat with a Grudge",     strength=9,  level=1,
            trait_name="8 Lives to Go!",          curse_name="That'll Leave a Mark!"),
    Monster("Gremlin Warrior",       strength=7,  level=1,
            description="Surprisingly Disciplined.",
            trait_name="Adorable",               curse_name="Don't Get it Wet"),
    # ── Level 2 (strength 11-20) ─────────────────────────────────────────
    Monster("Stoned Golem",          strength=11, level=2,
            trait_name="My Hands are Awesome\u2026", curse_name="Dude, Where's My Card?"),
    Monster("Acid Dragon",           strength=13, level=2,
            trait_name="I See Everything!",       curse_name="Bad Trip"),
    Monster("Sinkhole",              strength=14, level=2,
            trait_name="Swiftness",               curse_name="Quite the Setback!"),
    Monster("Demonic Analrapist",    strength=14, level=2,
            trait_name="Leather Daddy",           curse_name="Nevernude"),
    Monster("Smelly Cat",            strength=16, level=2,
            trait_name="It's Not Your Fault!",   curse_name="The Smell Won't Come Out!"),
    Monster("Twisted Treant",        strength=17, level=2,
            trait_name="Tough Skin",              curse_name="They Flooded Your Base!"),
    Monster("Bogeyman",              strength=18, level=2,
            trait_name="You Got a Birdie!",       curse_name="Scared of the Dark"),
    Monster("Wood Golem",            strength=18, level=2,
            trait_name="Bark Worse Than its Bite", curse_name="Termites!"),
    Monster("Bad Mexican Food",      strength=19, level=2,
            trait_name="Stomach of Steel",        curse_name="I Need a Place to Go!"),
    Monster("Coronavirus",           strength=19, level=2,
            trait_name="Vaxxed!",                 curse_name="Facial Coverings Required"),
    Monster("Blood Golem",           strength=15, level=2,
            trait_name="Blood Pact",              curse_name="Blood Drain"),
    Monster("Fat Troll",             strength=20, level=2,
            trait_name="Big Boned!",              curse_name="So\u2026 Lethargic\u2026"),
    # ── Level 3 (strength 21-30) ─────────────────────────────────────────
    Monster("One of Those Fish That Swim Up Your Urethra", strength=21, level=3,
            trait_name="Strong Schlong",          curse_name="It's Wriggling!"),
    Monster("Zombie Linebacker",     strength=22, level=3,
            trait_name="Touchdown!",              curse_name="Roughing the Kicker!"),
    Monster("Large Orc",             strength=23, level=3,
            trait_name="Meat's Back On the Menu!", curse_name="You're On the Menu\u2026"),
    Monster("Spooky Ghost",          strength=23, level=3,
            trait_name="Phase Shift",             curse_name="Out of Phase"),
    Monster("Wicked Witch",          strength=23, level=3,
            trait_name="She's Melting!",          curse_name="Cursed!"),
    Monster("Swamp Monster",         strength=24, level=3,
            trait_name="He's Just Misunderstood!", curse_name="Laundry Day!"),
    Monster("Creepy Hollywood Exec", strength=25, level=3,
            trait_name="Me Too!",                 curse_name="Blacklisted!"),
    Monster("Necrodancer",           strength=25, level=3,
            trait_name="Fancy Footwork",          curse_name="Can't Stop the Music!"),
    Monster("Spanish Inquisition",   strength=25, level=3,
            trait_name="I'll Come In Again",      curse_name="Now, Cardinal, the Rack!"),
    Monster("Goblin Warrior",        strength=26, level=3,
            trait_name="Scavenger",               curse_name="Stabbed"),
    Monster("Guy With a Gun",        strength=26, level=3,
            trait_name="Kapwing!",                curse_name="Shot Through the Heart!"),
    Monster("Demon Lord",            strength=27, level=3,
            trait_name="New Lord in Town.",       curse_name="KNEEL!"),
    Monster("Skeletal Overlord",     strength=27, level=3,
            trait_name="I'm De Overlord Now.",    curse_name="Enslaved!"),
    Monster("Velociraptor",          strength=28, level=3,
            trait_name="You're the Alpha!",       curse_name="Clever Girl\u2026"),
    Monster("Roofie Demon",          strength=29, level=3,
            trait_name="Residuals",               curse_name="My Drink Tastes Funny\u2026"),
    Monster("Jeffrey Dahmer as a Vampire", strength=30, level=3,
            trait_name="Strengthened by Taint",
            curse_name="He Drank Your Blood. Then Ate Your Arm."),
]
"""Real monster roster — 41 monsters with confirmed trait/curse registry entries."""

# ---------------------------------------------------------------------------
# Monster draw pools — one per level, derived from ALL_MONSTERS
# ---------------------------------------------------------------------------

MONSTER_POOL_L1: list[Monster] = [m for m in ALL_MONSTERS if m.level == 1]
MONSTER_POOL_L2: list[Monster] = [m for m in ALL_MONSTERS if m.level == 2]
MONSTER_POOL_L3: list[Monster] = [m for m in ALL_MONSTERS if m.level == 3]
