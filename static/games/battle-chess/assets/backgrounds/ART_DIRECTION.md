# Illustrated fantasy backdrops

Original 2D raster illustrations generated with the built-in imagegen tool,
replacing the earlier modeled scenery. No new runtime dependency is used.

- `runeforge-forge.png`: intricate volcanic forge, carved basalt, brass detail,
  furnace glow, lava chasms, and atmospheric smoke.
- `elven-sanctuary.png`: intricate silverwood sanctuary, leaf-carved ivory arches,
  moonstone, foliage, turquoise pools, and layered mist.

The images are served locally as CSS backgrounds beneath a transparent WebGL
canvas. Only the playable board and pieces are visible 3D models; an invisible
shadow receiver grounds the board against the image. The artwork stays fixed
when rotating, flipping or zooming the board, and never participates in picking.
Both collections retain the original geometry and GLB exports.

The same artwork is used with a dark overlay behind the surrounding UI. Classic
view has no illustrated backdrop. A solid background remains if an image cannot
load, so gameplay is independent of the artwork.

## Final prompts

### Runeforge

Use case: stylized-concept. Asset type: finished square 2D raster background for a playable 3D fantasy chess game, 1536x1536 if possible. Create an extraordinarily intricate cinematic volcanic dwarven forge sanctuary, painted with convincing realistic 3D depth and tactile materials, not low-poly. Elevated three-quarter camera looking down about 50 degrees. The CENTER and lower-middle 65% must be an EMPTY broad dark worn basalt floor/platform, low visual contrast, because a separate chessboard will be composited there. Put the beautiful detail in the TOP QUARTER and along the LEFT and RIGHT EDGES: towering carved obsidian pillars, ancient engraved brass mechanisms, stone arches receding through atmospheric smoke, suspended iron chains, deep recessed furnace doors, fine cracks with molten orange glow, ember-lit masonry, subtle warm light on chipped rock. Foreground corners have intricately carved stone borders, a few warm embers, and lava far below; do not obstruct the empty center. Dramatic perspective, depth layers, sophisticated game environment concept art, detailed aged surfaces, restrained amber light against charcoal and cool smoky violet. Soft key light from upper-left. Full bleed edge-to-edge background only. NO chessboard, NO chess pieces, NO people, NO creatures, NO writing, NO UI, NO labels, NO watermark. One coherent scene, no collage.

### Sylvan Court

Use case: stylized-concept. Asset type: finished square 2D raster background for a playable 3D elven fantasy chess game, 1536x1536 if possible. Create an extraordinarily intricate ancient elven woodland sanctuary with convincing realistic 3D depth, a sophisticated cinematic digital matte painting rather than low-poly geometry. Elevated three-quarter camera looking down about 50 degrees. The CENTER and lower-middle 65% must be an EMPTY broad level aged moss-edged moonstone terrace with subtle stone detail and low contrast, because a separate chessboard will be composited there. Put exquisite details in the TOP QUARTER and LEFT and RIGHT EDGES: delicate ivory elven arches intricately carved with intertwining leaves and fine gold filigree, enormous ancient silver-barked trees with roots weaving around marble columns, layered fern fronds, emerald hanging vines, luminous small flowers, still turquoise lily pools, intricate distant bridges and graceful spires glimpsed through mist. At foreground corners use carved leaf balustrades and detailed ferns, keeping the center unobstructed. Emerald and deep teal foliage, pearl limestone, aged pale gold, cool moonlit haze, warm soft shafts of sunlight filtering from upper-left. Atmospheric perspective, realistic reflections, rich tiny natural details, refined fantasy realism, strong spatial depth. Full bleed edge-to-edge background only. NO chessboard, NO chess pieces, NO people, NO creatures, NO writing, NO UI, NO labels, NO watermark. One coherent scene, no collage.
