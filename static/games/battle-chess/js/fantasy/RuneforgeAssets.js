import * as THREE from '../../lib/three/three.module.min.js';
import { mergeGeometries } from '../../lib/three/BufferGeometryUtils.js';

// Original, editable mesh assets. One unit is one chess square. Y is up.
// No downloaded models, textures, fonts, or image assets are used.
const material = (name, color, metalness = 0, roughness = 0.6, extra = {}) =>
    new THREE.MeshStandardMaterial({ name, color, metalness, roughness, ...extra });

// Shared modeling primitives for the original fantasy collections.
export { material, mesh, box, cylinder, orb, gem, rod, silhouette };

export function createMaterials() {
    const faction = (dark) => ({
        body: material(dark ? 'Obsidian armor' : 'Ivory armor', dark ? 0x343447 : 0xe4d9bb, .35, .38),
        trim: material(dark ? 'Dusksilver' : 'Antique gold', dark ? 0x9f9bbf : 0xb58b48, .72, .29),
        cloth: material(dark ? 'Plum mantle' : 'Teal mantle', dark ? 0x431c52 : 0x18585d, .05, .85),
        inset: material('Recesses', dark ? 0x100e20 : 0x283b3e, .15, .6),
        gem: material(dark ? 'Amethyst' : 'Sunstone', dark ? 0xd299ff : 0x9ffff0, .3, .2, {
            emissive: dark ? 0x9c3eff : 0x30d9c5, emissiveIntensity: .65,
        }),
    });
    return {
        w: faction(false), b: faction(true),
        stone: material('Basalt foundation', 0x28363c, .15, .84),
        edge: material('Carved slate', 0x435258, .2, .65),
        gold: material('Inlaid brass', 0xb18b4e, .72, .34),
        dark: material('Dark squares', 0x354c52, .15, .65),
        light: material('Light squares', 0xb4b6a2, .08, .72),
        rune: material('Runic turquoise', 0x6debd2, .25, .4, { emissive: 0x2bb69e, emissiveIntensity: .7 }),
    };
}

function mesh(parent, geometry, mat, x = 0, y = 0, z = 0, rotation = null) {
    const obj = new THREE.Mesh(geometry, mat);
    obj.position.set(x, y, z);
    if (rotation) obj.rotation.set(...rotation);
    obj.castShadow = true;
    obj.receiveShadow = true;
    parent.add(obj);
    return obj;
}
const box = (g, m, w, h, d, x, y, z, r) => mesh(g, new THREE.BoxGeometry(w, h, d), m, x, y, z, r);
const cylinder = (g, m, top, bottom, height, y, sides = 12, x = 0, z = 0) =>
    mesh(g, new THREE.CylinderGeometry(top, bottom, height, sides), m, x, y, z);
const orb = (g, m, radius, x, y, z, scale = [1, 1, 1]) => {
    const obj = mesh(g, new THREE.IcosahedronGeometry(radius, 1), m, x, y, z);
    obj.scale.set(...scale);
    return obj;
};
const gem = (g, m, radius, x, y, z, scale = [1, 1, 1]) => {
    const obj = mesh(g, new THREE.OctahedronGeometry(radius), m, x, y, z);
    obj.scale.set(...scale);
    return obj;
};
function rod(g, m, a, b, radius = .025) {
    const start = new THREE.Vector3(...a), end = new THREE.Vector3(...b);
    const obj = mesh(g, new THREE.CylinderGeometry(radius, radius, start.distanceTo(end), 6), m);
    obj.position.copy(start.add(end).multiplyScalar(.5));
    obj.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), end.sub(new THREE.Vector3(...a)).normalize());
    return obj;
}
function silhouette(g, m, points, depth, x = 0, y = 0, z = 0, rotation = null) {
    const shape = new THREE.Shape();
    points.forEach(([a, b], i) => i ? shape.lineTo(a, b) : shape.moveTo(a, b));
    shape.closePath();
    const geo = new THREE.ExtrudeGeometry(shape, {
        depth, bevelEnabled: true, bevelSegments: 1, steps: 1, bevelSize: .018, bevelThickness: .018,
    });
    geo.translate(0, 0, -depth / 2);
    return mesh(g, geo, m, x, y, z, rotation);
}

// Bake transformed parts together by material: richly detailed assets with few draw calls.
export function bake(source, name) {
    source.updateMatrixWorld(true);
    const batches = new Map();
    source.traverse(obj => {
        if (!obj.isMesh) return;
        const geo = obj.geometry.index ? obj.geometry.toNonIndexed() : obj.geometry.clone();
        geo.applyMatrix4(obj.matrixWorld);
        // Primitive geometries do not all have UVs; these assets use solid materials.
        for (const key of Object.keys(geo.attributes)) {
            if (key !== 'position' && key !== 'normal') geo.deleteAttribute(key);
        }
        if (!batches.has(obj.material)) batches.set(obj.material, []);
        batches.get(obj.material).push(geo);
    });
    const result = new THREE.Group();
    result.name = name;
    for (const [mat, geometries] of batches) {
        mesh(result, mergeGeometries(geometries), mat);
        geometries.forEach(geo => geo.dispose());
    }
    source.traverse(obj => { if (obj.isMesh) obj.geometry.dispose(); });
    return result;
}

function pedestal(g, m) {
    cylinder(g, m.inset, .31, .34, .07, .035, 16);
    cylinder(g, m.trim, .34, .34, .045, .085, 16);
    cylinder(g, m.body, .26, .32, .10, .155, 16);
    cylinder(g, m.trim, .26, .27, .035, .22, 16);
    for (let i = 0; i < 8; i++) {
        const a = i * Math.PI / 4;
        gem(g, m.gem, .025, Math.cos(a) * .305, .15, Math.sin(a) * .305);
    }
}
function crown(g, m, y, radius, count = 5) {
    cylinder(g, m.trim, radius, radius, .08, y, count * 2);
    for (let i = 0; i < count; i++) {
        const angle = i * Math.PI * 2 / count;
        const x = Math.cos(angle) * radius, z = Math.sin(angle) * radius;
        mesh(g, new THREE.ConeGeometry(.055, .19, 4), m.trim, x, y + .12, z);
        gem(g, m.gem, .035, x, y + .22, z);
    }
}
function blade(g, m, x, y, z, height = .6) {
    silhouette(g, m.trim, [[-.045, 0], [-.045, height * .8], [0, height], [.045, height * .8], [.045, 0]], .035, x, y, z);
    box(g, m.trim, .23, .045, .065, x, y + .04, z);
    rod(g, m.inset, [x, y, z], [x, y - .15, z], .035);
    gem(g, m.gem, .04, x, y - .17, z);
}

export const PIECE_NAMES = { p: 'Sentinel', r: 'Runic keep', n: 'Wyrm knight', b: 'Crystal sage', q: 'Starweaver', k: 'Oathbound king' };

export function createPiece(type, color, materials) {
    const g = new THREE.Group(), m = materials[color];
    pedestal(g, m);
    if (type === 'p') {
        cylinder(g, m.cloth, .12, .21, .29, .38);
        orb(g, m.body, .20, 0, .59, 0, [1, 1.1, .8]);
        orb(g, m.body, .145, 0, .84, 0, [1, 1.12, 1]);
        box(g, m.inset, .21, .045, .035, 0, .855, .13);
        box(g, m.trim, .025, .16, .03, 0, .87, .15);
        silhouette(g, m.cloth, [[-.08, 0], [-.08, .12], [.11, .05], [.09, 0]], .035, 0, .98, 0, [0, Math.PI / 2, 0]);
        silhouette(g, m.trim, [[-.16, .10], [.16, .10], [.14, -.12], [0, -.23], [-.14, -.12]], .055, -.13, .59, .22);
        gem(g, m.gem, .065, -.13, .57, .26, [1, 1.6, .4]);
        blade(g, m, .24, .50, .08, .40);
    } else if (type === 'r') {
        cylinder(g, m.body, .24, .29, .64, .56, 8);
        cylinder(g, m.trim, .32, .25, .09, .91, 8);
        cylinder(g, m.inset, .24, .24, .03, .965, 8);
        for (let i = 0; i < 8; i++) {
            const a = i * Math.PI / 4;
            box(g, m.body, .14, .19, .13, .265 * Math.sin(a), 1.04, .265 * Math.cos(a), [0, a, 0]);
        }
        for (let i = 0; i < 4; i++) {
            const a = i * Math.PI / 2;
            const window = new THREE.Group();
            box(window, m.inset, .13, .28, .03, 0, .64, .25);
            gem(window, m.gem, .08, 0, .65, .276, [.5, 1.6, .2]);
            window.rotation.y = a;
            g.add(window);
        }
        cylinder(g, m.trim, .26, .28, .035, .36, 8);
        gem(g, m.gem, .10, 0, 1.05, 0, [1, 1.8, 1]);
    } else if (type === 'n') {
        // A dragon profile, extruded across its shoulders, with swept horns and scales.
        silhouette(g, m.body, [[-.23, .25], [.20, .25], [.23, .50], [.08, .76], [.31, .82], [.37, .97], [.19, 1.13], [.02, 1.25], [-.18, 1.11], [-.27, .81]], .30, 0, 0, 0, [0, -Math.PI / 2, 0]);
        for (let i = 0; i < 5; i++) {
            mesh(g, new THREE.ConeGeometry(.085 - i * .006, .20, 4), m.trim, 0, .53 + i * .13, -.26 + i * .015, [-.65, 0, 0]);
        }
        for (const side of [-1, 1]) {
            gem(g, m.gem, .045, side * .17, 1.04, .17, [.4, .7, 1.2]);
            mesh(g, new THREE.ConeGeometry(.055, .26, 5), m.trim, side * .12, 1.26, -.035, [-.4, 0, side * -.3]);
            silhouette(g, m.cloth, [[0, 0], [.15, .35], [.35, .46], [.29, .13], [.13, .16]], .045, side * .12, .36, -.05, [0, side * Math.PI / 2, 0]);
        }
        box(g, m.inset, .24, .025, .18, 0, .90, .29);
        cylinder(g, m.trim, .23, .25, .06, .31);
    } else if (type === 'b') {
        cylinder(g, m.cloth, .105, .25, .66, .57);
        cylinder(g, m.trim, .16, .23, .08, .31);
        orb(g, m.body, .18, 0, .83, 0, [1.15, .7, .85]);
        orb(g, m.inset, .12, 0, 1.0, .035);
        // Split, pointed mitre makes the bishop legible from either side.
        for (const side of [-1, 1]) {
            silhouette(g, m.body, [[-.045, 0], [.045, 0], [.045, .18], [0, .31], [-.045, .18]], .19, side * .065, 1.01, 0);
        }
        gem(g, m.gem, .06, 0, 1.12, .12);
        rod(g, m.trim, [.26, .27, .02], [.26, 1.18, .02], .026);
        const ring = mesh(g, new THREE.TorusGeometry(.12, .025, 6, 16), m.trim, .26, 1.23, .02);
        ring.rotation.y = .2;
        gem(g, m.gem, .09, .26, 1.24, .02, [.8, 1.6, .8]);
        silhouette(g, m.trim, [[-.025, 0], [.025, 0], [.075, -.42], [-.075, -.42]], .025, 0, .83, .15);
    } else if (type === 'q') {
        cylinder(g, m.cloth, .11, .28, .63, .57);
        cylinder(g, m.body, .18, .12, .30, .87);
        orb(g, m.body, .13, 0, 1.15, 0);
        crown(g, m, 1.24, .14, 7);
        for (const side of [-1, 1]) {
            silhouette(g, m.trim, [[0, 0], [.15, .30], [.34, .40], [.24, .05], [.10, -.14]], .045, side * .14, .91, -.07, [0, side < 0 ? Math.PI : 0, 0]);
        }
        rod(g, m.trim, [-.24, .45, .04], [-.24, 1.05, .04]);
        gem(g, m.gem, .115, -.24, 1.13, .04, [.7, 1.5, .7]);
        gem(g, m.gem, .09, 0, .89, .15, [1, 1.4, .5]);
        for (let i = 0; i < 6; i++) {
            const a = i * Math.PI / 3;
            rod(g, m.trim, [.25 * Math.cos(a), .29, .25 * Math.sin(a)], [.12 * Math.cos(a), .78, .12 * Math.sin(a)], .014);
        }
    } else if (type === 'k') {
        cylinder(g, m.cloth, .17, .27, .65, .58);
        silhouette(g, m.cloth, [[-.23, 0], [.23, 0], [.31, -.67], [-.31, -.67]], .07, 0, 1.02, -.16);
        cylinder(g, m.body, .23, .14, .36, .86, 6);
        for (const side of [-1, 1]) orb(g, m.trim, .14, side * .24, 1.0, 0, [1, .7, 1]);
        orb(g, m.body, .15, 0, 1.20, 0, [1, 1.1, 1]);
        box(g, m.inset, .21, .045, .03, 0, 1.22, .13);
        crown(g, m, 1.32, .17, 5);
        blade(g, m, 0, .55, .29, .53);
        gem(g, m.gem, .06, 0, 1.01, .21);
        box(g, m.trim, .29, .05, .30, 0, .72, 0);
    }
    return bake(g, `${color === 'w' ? 'Dawn' : 'Dusk'} / ${PIECE_NAMES[type]}`);
}

export function createBoardAsset(m) {
    const g = new THREE.Group();
    box(g, m.stone, 9.6, .34, 9.6, 0, -.58, 0);
    box(g, m.gold, 9.38, .055, 9.38, 0, -.38, 0);
    box(g, m.edge, 9.2, .28, 9.2, 0, -.22, 0);
    box(g, m.gold, 8.18, .06, 8.18, 0, -.045, 0);
    box(g, m.stone, 8.08, .08, 8.08, 0, 0, 0);
    for (let row = 0; row < 8; row++) {
        for (let col = 0; col < 8; col++) {
            const mat = (row + col) % 2 === 0 ? m.light : m.dark;
            box(g, mat, .977, .12, .977, col - 3.5, .035, row - 3.5);
            // Chisel marks near square corners, cut in matching stone tones.
            for (const side of [-1, 1]) {
                box(g, m.edge, .11, .008, .014, col - 3.5 + side * .39, .099, row - 3.5 + side * .39);
            }
        }
    }
    for (let side = 0; side < 4; side++) {
        const rail = new THREE.Group();
        box(rail, m.gold, 8.7, .025, .035, 0, -.055, 4.48);
        box(rail, m.gold, 8.7, .025, .025, 0, -.055, 4.13);
        for (let i = 0; i < 17; i++) {
            const x = (i - 8) * .49;
            // Original angular runes, etched into each side of the frame.
            rod(rail, m.rune, [x - .055, -.05, 4.25], [x, -.05, 4.37], .012);
            rod(rail, m.rune, [x, -.05, 4.37], [x + .055, -.05, 4.25], .012);
            if (i % 2 === 0) rod(rail, m.rune, [x, -.05, 4.25], [x, -.05, 4.41], .012);
        }
        rail.rotation.y = side * Math.PI / 2;
        g.add(rail);
    }
    for (const x of [-4.5, 4.5]) for (const z of [-4.5, 4.5]) {
        cylinder(g, m.stone, .36, .45, .38, -.38, 4, x, z);
        cylinder(g, m.gold, .32, .36, .06, -.15, 4, x, z);
        gem(g, m.rune, .19, x, .02, z, [1, .55, 1]);
        box(g, m.stone, .70, .19, .70, x * .91, -.83, z * .91);
    }
    return bake(g, 'Runeforge / carved arena');
}
