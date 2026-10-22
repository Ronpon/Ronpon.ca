# Three.js 0.180.0

Downloaded from the pinned npm distribution on jsDelivr:
`https://cdn.jsdelivr.net/npm/three@0.180.0/`.

| Local file | Upstream path |
| --- | --- |
| three.module.min.js | build/three.module.min.js |
| three.core.min.js | build/three.core.min.js |
| BufferGeometryUtils.js | examples/jsm/utils/BufferGeometryUtils.js |
| GLTFExporter.js | examples/jsm/exporters/GLTFExporter.js |
| LICENSE | LICENSE |

The addons' bare `from 'three'` imports are rewritten to
`from './three.module.min.js'` for buildless, same-origin ES module loading.
The library is otherwise unchanged. The exporter is loaded only when the user
requests a GLB download. The MIT license is included in `LICENSE`.

No npm setup or CDN connection is required to run the game. To upgrade, replace
all library files with one consistent release and repeat the browser checks.
