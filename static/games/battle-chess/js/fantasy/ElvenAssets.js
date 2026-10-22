import * as THREE from '../../lib/three/three.module.min.js';
import { material, mesh, box, cylinder, orb, gem, rod, bake } from './RuneforgeAssets.js';

export const PIECE_NAMES = { p: 'Leafwarden', r: 'Silverwood spire', n: 'Royal stag', b: 'Moon seer', q: 'Bloom queen', k: 'Antler king' };

export function curve(g, mat, points, radius = .025) {
    return mesh(g, new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p))), 16, radius, 5, false), mat);
}

export function leaf(g, mat, x, y, z, length, width, rotation = [0, 0, 0]) {
    const shape = new THREE.Shape();
    shape.moveTo(0, 0);
    shape.bezierCurveTo(-width, length * .36, -width * .55, length * .70, 0, length);
    shape.bezierCurveTo(width * .55, length * .70, width, length * .36, 0, 0);
    const geo = new THREE.ExtrudeGeometry(shape, { depth: .025, bevelEnabled: true, bevelSize: .008, bevelThickness: .008, bevelSegments: 1, steps: 1, curveSegments: 6 });
    return mesh(g, geo, mat, x, y, z, rotation);
}

function lathe(g, mat, profile) {
    return mesh(g, new THREE.LatheGeometry(profile.map(p => new THREE.Vector2(...p)), 20), mat);
}

export function createMaterials() {
    const faction = dark => ({
        body: material(dark ? 'Midnight jade' : 'Pearlwood', dark ? 0x244f50 : 0xefead1, .25, .32),
        trim: material(dark ? 'Moon silver' : 'Sun gold', dark ? 0xb8d2d5 : 0xc8aa61, .7, .28),
        cloth: material(dark ? 'Nightbloom silk' : 'Fern silk', dark ? 0x26385e : 0x689577, .1, .7),
        inset: material('Deep leaf recesses', dark ? 0x10252c : 0x355849, .1, .65),
        gem: material(dark ? 'Moon opal' : 'Dawn opal', dark ? 0xaccaff : 0xceffbd, .2, .23, { emissive: dark ? 0x4266dc : 0x71d79e, emissiveIntensity: .5 }),
    });
    return {
        w: faction(false), b: faction(true),
        stone: material('Ancient silverwood', 0x547261, .15, .72),
        edge: material('Pearlstone', 0xc9ceac, .15, .48),
        gold: material('Elven gold filigree', 0xb69e60, .65, .36),
        dark: material('Jade squares', 0x4e8575, .2, .45),
        light: material('Moonstone squares', 0xe1e3c7, .18, .42),
        rune: material('Living light', 0xb8fbc9, .2, .3, { emissive: 0x6db991, emissiveIntensity: .45 }),
    };
}

function base(g, m) {
    lathe(g, m.trim, [[0, 0], [.29, 0], [.32, .035], [.32, .065], [.27, .09], [.25, .12], [.24, .15], [0, .15]]);
    lathe(g, m.body, [[0, .09], [.26, .09], [.27, .13], [.23, .19], [.18, .23], [0, .23]]);
    for (let i = 0; i < 6; i++) {
        const a = i * Math.PI / 3;
        leaf(g, m.trim, Math.sin(a) * .26, .11, Math.cos(a) * .26, .13, .035, [.6, a, 0]);
    }
}

function gown(g, m, height) {
    lathe(g, m.cloth, [[0, .2], [.23, .2], [.25, .26], [.20, .37], [.12, height * .63], [.10, height * .83], [.17, height], [0, height]]);
    for (let i = 0; i < 5; i++) {
        const a = i * Math.PI * 2 / 5;
        curve(g, m.trim, [[Math.sin(a) * .22, .25, Math.cos(a) * .22], [Math.sin(a + .35) * .16, .5, Math.cos(a + .35) * .16], [Math.sin(a) * .12, height * .88, Math.cos(a) * .12]], .012);
    }
}

function head(g, m, y) {
    orb(g, m.body, .12, 0, y, 0, [.82, 1.25, .85]);
    for (const sign of [-1, 1]) {
        leaf(g, m.body, sign * .08, y - .01, 0, .18, .035, [0, 0, -sign * .9]);
    }
    box(g, m.inset, .12, .018, .02, 0, y + .02, .092);
    gem(g, m.gem, .025, 0, y + .09, .092);
}

function antlers(g, mat, y, spread = .34) {
    for (const sign of [-1, 1]) {
        curve(g, mat, [[sign * .08, y, 0], [sign * .18, y + .17, -.02], [sign * spread, y + .28, -.04], [sign * (spread - .02), y + .43, 0]], .023);
        curve(g, mat, [[sign * .17, y + .16, -.02], [sign * .14, y + .30, .01], [sign * .18, y + .37, .025]], .016);
        rod(g, mat, [sign * .27, y + .24, -.03], [sign * (spread + .05), y + .33, -.04], .016);
    }
}

export function createPiece(type, color, materials) {
    const g = new THREE.Group(), m = materials[color];
    base(g, m);
    if (type === 'p') {
        gown(g, m, .64);
        leaf(g, m.body, 0, .43, .12, .30, .15);
        head(g, m, .78);
        leaf(g, m.trim, 0, .85, -.05, .20, .07);
        // A longbow and its taut string, separate from the leaf-shaped shield.
        curve(g, m.trim, [[.24, .29, .03], [.34, .57, .02], [.24, .86, .03]], .023);
        rod(g, m.inset, [.24, .29, .03], [.24, .86, .03], .007);
        leaf(g, m.cloth, -.15, .38, .15, .33, .12, [0, 0, .20]);
        gem(g, m.gem, .04, -.18, .56, .20);
    } else if (type === 'r') {
        lathe(g, m.body, [[0, .2], [.24, .2], [.19, .32], [.14, .60], [.16, .82], [.22, .94], [0, .94]]);
        for (let i = 0; i < 5; i++) {
            const a = i * Math.PI * 2 / 5;
            const x = Math.sin(a), z = Math.cos(a);
            curve(g, m.trim, [[x * .24, .24, z * .24], [x * .27, .60, z * .27], [x * .22, 1.02, z * .22], [x * .06, 1.33, z * .06]], .032);
            leaf(g, m.body, x * .20, .82, z * .20, .37, .09, [0, a, 0]);
        }
        gem(g, m.gem, .13, 0, 1.08, 0, [1, 1.8, 1]);
    } else if (type === 'n') {
        // Stag neck, head and muzzle; antlers give a very different silhouette to the dragon.
        lathe(g, m.body, [[0, .20], [.22, .20], [.20, .40], [.11, .70], [.13, .92], [0, .94]]);
        orb(g, m.body, .18, 0, .98, .02, [.78, 1.2, 1]);
        orb(g, m.body, .12, 0, .92, .17, [.8, .8, 1.5]);
        for (const sign of [-1, 1]) {
            leaf(g, m.body, sign * .09, 1.03, 0, .23, .055, [0, 0, sign * -.8]);
            gem(g, m.gem, .028, sign * .132, 1.01, .09);
        }
        antlers(g, m.trim, 1.09, .28);
        leaf(g, m.trim, 0, .40, .18, .40, .09);
    } else if (type === 'b') {
        gown(g, m, .89);
        head(g, m, 1.01);
        leaf(g, m.body, 0, 1.05, -.07, .28, .11);
        curve(g, m.trim, [[-.24, .24, .02], [-.25, .75, .02], [-.24, 1.17, .02]], .022);
        mesh(g, new THREE.TorusGeometry(.12, .023, 6, 24, Math.PI * 1.55), m.trim, -.24, 1.25, .02, [0, 0, .7]);
        gem(g, m.gem, .065, -.24, 1.25, .02);
        leaf(g, m.body, .13, .72, 0, .32, .09, [0, 0, -.9]);
    } else if (type === 'q') {
        gown(g, m, 1.00);
        head(g, m, 1.14);
        for (let i = 0; i < 7; i++) {
            const a = i * Math.PI * 2 / 7;
            leaf(g, m.trim, Math.sin(a) * .11, 1.23, Math.cos(a) * .11, .25, .06, [.35, a, 0]);
        }
        for (const sign of [-1, 1]) leaf(g, m.body, sign * .11, .82, -.05, .42, .12, [0, 0, sign * -.65]);
        curve(g, m.trim, [[.25, .28, .04], [.23, .8, .04], [.28, 1.15, .04]], .02);
        for (let i = 0; i < 5; i++) leaf(g, m.body, .28, 1.10, .04, .18, .045, [.7, i * Math.PI * 2 / 5, 0]);
        gem(g, m.gem, .07, .28, 1.23, .04);
        gem(g, m.gem, .055, 0, .92, .15);
    } else if (type === 'k') {
        gown(g, m, .95);
        leaf(g, m.body, 0, .63, .12, .42, .19);
        head(g, m, 1.14);
        antlers(g, m.trim, 1.23, .32);
        for (const sign of [-1, 1]) leaf(g, m.body, sign * .14, .83, -.04, .32, .10, [0, 0, sign * -.9]);
        rod(g, m.trim, [.29, .23, .03], [.29, 1.21, .03], .022);
        leaf(g, m.body, .29, 1.16, .03, .28, .065);
        gem(g, m.gem, .05, 0, .91, .17);
        leaf(g, m.cloth, 0, .29, -.16, .76, .29, [0, Math.PI, 0]);
    }
    return bake(g, `${color === 'w' ? 'Sunleaf' : 'Moonveil'} / ${PIECE_NAMES[type]}`);
}

export function createBoardAsset(m) {
    const g = new THREE.Group();
    box(g, m.stone, 9.1, .24, 9.1, 0, -.38, 0);
    box(g, m.gold, 8.94, .04, 8.94, 0, -.23, 0);
    box(g, m.edge, 8.8, .21, 8.8, 0, -.10, 0);
    for (let row = 0; row < 8; row++) for (let col = 0; col < 8; col++) {
        box(g, (row + col) % 2 === 0 ? m.light : m.dark, .983, .10, .983, col - 3.5, .043, row - 3.5);
        // Gold leaf inlay at one corner of every square.
        leaf(g, m.gold, col - 3.85, .097, row - 3.16, .12, .028, [-Math.PI / 2, 0, -.7]);
    }
    for (let side = 0; side < 4; side++) {
        const rail = new THREE.Group();
        for (const sign of [-1, 1]) {
            const points = [];
            for (let i = 0; i <= 32; i++) points.push([-4.3 + i * .269, -.01, 4.22 + Math.sin(i * Math.PI / 4) * .085 * sign]);
            curve(rail, m.gold, points, .018);
        }
        for (let i = 0; i < 14; i++) leaf(rail, m.stone, -3.9 + i * .6, .013, 4.27, .19, .06, [-Math.PI / 2, 0, i % 2 ? -.7 : .7]);
        rail.rotation.y = side * Math.PI / 2;
        g.add(rail);
    }
    for (const x of [-4.35, 4.35]) for (const z of [-4.35, 4.35]) {
        cylinder(g, m.stone, .24, .38, .37, -.31, 8, x, z);
        for (let i = 0; i < 6; i++) leaf(g, m.edge, x, -.14, z, .40, .12, [.85, i * Math.PI / 3, 0]);
        gem(g, m.rune, .14, x, .12, z);
        curve(g, m.stone, [[x, -.5, z], [x * .9, -.70, z * .96], [x * .8, -.80, z]], .09);
    }
    return bake(g, 'Sylvan Court / living moonstone board');
}
