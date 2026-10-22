import * as THREE from '../../lib/three/three.module.min.js';
import { createMaterials, createPiece, createBoardAsset, PIECE_NAMES } from './RuneforgeAssets.js';
import * as ElvenAssets from './ElvenAssets.js';
import { SQUARE_SIZE } from '../Constants.js';

const position = square => new THREE.Vector3(square.charCodeAt(0) - 100.5, .105, 4.5 - Number(square[1]));

export class FantasyBoard {
    constructor(canvas, onFailure, theme = 'runeforge') {
        this.canvas = canvas;
        this.scene = new THREE.Scene();
        // The illustrated environment is a CSS raster backdrop beneath this canvas.
        this.scene.background = null;
        this.camera = new THREE.OrthographicCamera(-6.5, 6.5, 6.5, -6.5, .1, 100);
        this.yaw = .20;
        this.elevation = .88;
        this.zoom = 1;
        this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'low-power' });
        this.renderer.setClearColor(0x000000, 0);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.3;
        this.renderer.shadowMap.autoUpdate = false;
        this.assetCache = new Map();
        this.pieces = new THREE.Group();
        this.scene.add(this.pieces);
        this.markers = new THREE.Group();
        this.scene.add(this.markers);
        this.markerGeometry = new THREE.RingGeometry(.32, .40, 40);
        this.dotGeometry = new THREE.CircleGeometry(.13, 24);
        this.markerMaterials = {};
        for (const [key, color] of Object.entries({ selected: 0xffdb83, move: 0x9cffe0, capture: 0xffb16e, last: 0x6cd6cb, check: 0xff4c6e, hover: 0xffffff })) {
            this.markerMaterials[key] = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: key === 'last' ? .55 : .95, depthWrite: false });
        }
        this.raycaster = new THREE.Raycaster();
        this.plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -.105);
        this._lights();
        // Invisible contact-shadow receiver grounds the board in the illustration.
        // It contributes only shadows, not modeled background scenery.
        const contactShadow = new THREE.Mesh(new THREE.PlaneGeometry(18, 18), new THREE.ShadowMaterial({ opacity: .24 }));
        contactShadow.name = 'Board contact shadow';
        contactShadow.rotation.x = -Math.PI / 2;
        contactShadow.position.y = -.88;
        contactShadow.receiveShadow = true;
        this.scene.add(contactShadow);
        this.setTheme(theme);
        this._coordinates();
        this._camera();
        this.resizeObserver = new ResizeObserver(() => this.resize());
        this.resizeObserver.observe(canvas.parentElement);
        canvas.addEventListener('webglcontextlost', event => {
            event.preventDefault();
            this.contextLost = true;
            onFailure('3D was interrupted. Play in Classic, or reload for 3D.');
        });
        canvas.addEventListener('contextmenu', event => event.preventDefault());
        // A short tap is a chess click; movement beyond the threshold is an orbit.
        // Consume the browser's release-click after dragging, before it reaches input.
        canvas.addEventListener('click', event => {
            if (!this.suppressClick) return;
            this.suppressClick = false;
            event.preventDefault();
            event.stopImmediatePropagation();
        }, true);
        canvas.addEventListener('pointerdown', event => {
            if (this.drag || !event.isPrimary || ![0, 2].includes(event.button)) return;
            this.suppressClick = false;
            this.drag = {
                id: event.pointerId, x: event.clientX, y: event.clientY,
                yaw: this.yaw, elevation: this.elevation, moved: false,
            };
            canvas.setPointerCapture(event.pointerId);
        });
        canvas.addEventListener('pointermove', event => {
            const drag = this.drag;
            if (!drag || event.pointerId !== drag.id) return;
            const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
            if (!drag.moved && Math.hypot(dx, dy) < 6) return;
            drag.moved = true;
            canvas.classList.add('is-dragging');
            this.yaw = drag.yaw - dx * .008;
            this.elevation = Math.max(.55, Math.min(Math.PI / 2 - .001, drag.elevation - dy * .006));
            this._camera();
            this.render(this.state);
        });
        const stopDrag = event => {
            const drag = this.drag;
            if (!drag || (event.pointerId !== undefined && event.pointerId !== drag.id)) return;
            this.suppressClick = drag.moved || event.type !== 'pointerup';
            this.drag = null;
            canvas.classList.remove('is-dragging');
            if (canvas.hasPointerCapture(drag.id)) canvas.releasePointerCapture(drag.id);
        };
        canvas.addEventListener('pointerup', stopDrag);
        canvas.addEventListener('pointercancel', stopDrag);
        canvas.addEventListener('lostpointercapture', stopDrag);
        window.addEventListener('blur', stopDrag);
        this.resize();
    }

    _lights() {
        this.ambientLight = new THREE.HemisphereLight(0xc9e4f1, 0x3a313d, 2.4);
        this.scene.add(this.ambientLight);
        const key = new THREE.DirectionalLight(0xffe5b7, 3.5);
        key.position.set(-5, 11, 6);
        key.castShadow = true;
        key.shadow.mapSize.set(2048, 2048);
        Object.assign(key.shadow.camera, { left: -8, right: 8, top: 8, bottom: -8, near: .5, far: 30 });
        key.shadow.normalBias = .035;
        key.shadow.bias = -.0003;
        this.scene.add(key);
        const rim = new THREE.DirectionalLight(0x9b9cff, 2.2);
        rim.position.set(5, 5, -7);
        this.scene.add(rim);
        this.rimLight = rim;
        const fill = new THREE.DirectionalLight(0x7fdfd0, .6);
        fill.position.set(0, 3, 9);
        this.scene.add(fill);
        this.fillLight = fill;
    }

    setTheme(theme) {
        if (this.theme === theme) return;
        if (!this.assetCache.has(theme)) {
            const assets = theme === 'elven' ? ElvenAssets : { createMaterials, createPiece, createBoardAsset, PIECE_NAMES };
            const materials = assets.createMaterials(), templates = {};
            for (const color of ['w', 'b']) for (const type of Object.keys(assets.PIECE_NAMES)) {
                templates[color + type] = assets.createPiece(type, color, materials);
            }
            this.assetCache.set(theme, { materials, templates, boardAsset: assets.createBoardAsset(materials) });
        }
        if (this.boardAsset) this.scene.remove(this.boardAsset);
        Object.assign(this, this.assetCache.get(theme));
        this.theme = theme;
        this.scene.add(this.boardAsset);
        this.ambientLight.groundColor.set(theme === 'elven' ? 0x365c48 : 0x59342f);
        this.rimLight.color.set(theme === 'elven' ? 0x99ddce : 0xff916c);
        this.fillLight.color.set(theme === 'elven' ? 0xbbe6a6 : 0x9fb8ee);
        this.signature = null;
        this.renderer.shadowMap.needsUpdate = true;
        this._camera();
    }

    _coordinates() {
        // Locally drawn lettering: no font or texture downloads.
        for (let i = 0; i < 8; i++) for (let side = 0; side < 4; side++) {
            const canvas = document.createElement('canvas');
            canvas.width = canvas.height = 64;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#e5cf9d';
            ctx.font = '40px Georgia';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(side < 2 ? String.fromCharCode(97 + i) : String(8 - i), 32, 34);
            const map = new THREE.CanvasTexture(canvas);
            map.colorSpace = THREE.SRGBColorSpace;
            const label = new THREE.Mesh(new THREE.PlaneGeometry(.23, .23), new THREE.MeshBasicMaterial({ map, transparent: true, depthWrite: false }));
            label.rotation.x = -Math.PI / 2;
            label.position.set(side < 2 ? i - 3.5 : (side === 2 ? -4.04 : 4.04), .11, side < 2 ? (side === 0 ? 4.04 : -4.04) : i - 3.5);
            if (side === 1) label.rotation.z = Math.PI;
            this.scene.add(label);
        }
    }

    _camera() {
        const radius = 19;
        this.camera.position.set(Math.sin(this.yaw) * Math.cos(this.elevation) * radius,
            Math.sin(this.elevation) * radius, Math.cos(this.yaw) * Math.cos(this.elevation) * radius);
        this.camera.lookAt(0, 0, 0);
        this.camera.zoom = this.zoom;
        this.camera.updateProjectionMatrix();
        this.camera.updateMatrixWorld();
        this.canvas.dispatchEvent(new CustomEvent('boardcamerachange', { detail: { topView: this.elevation > 1.4 } }));
        this.renderer.shadowMap.needsUpdate = true;
    }

    setView(action) {
        if (action === 'left') this.yaw -= Math.PI / 4;
        if (action === 'right') this.yaw += Math.PI / 4;
        if (action === 'flip') this.yaw += Math.PI;
        if (action === 'top') this.elevation = this.elevation > 1.4 ? .88 : Math.PI / 2 - .001;
        if (action === 'in') this.zoom = Math.min(1.25, this.zoom + .1);
        if (action === 'out') this.zoom = Math.max(.8, this.zoom - .1);
        if (action === 'reset') { this.yaw = .20; this.elevation = .88; this.zoom = 1; }
        this._camera();
        this.render(this.state);
    }

    resize() {
        const width = this.canvas.parentElement.clientWidth || 640;
        this.renderer.setSize(width, width, false);
        this.render(this.state);
    }

    getSquareFromPixel(x, y) {
        this.scene.updateMatrixWorld(true);
        this.raycaster.setFromCamera(new THREE.Vector2(x / this.canvas.width * 2 - 1, 1 - y / this.canvas.height * 2), this.camera);
        // Clicking a tall piece selects its square, even when it overlaps the next rank.
        const hit = this.raycaster.intersectObjects(this.pieces.children, true)[0];
        if (hit) {
            let obj = hit.object;
            while (obj && !obj.userData.square) obj = obj.parent;
            if (obj) return obj.userData.square;
        }
        const point = this.raycaster.ray.intersectPlane(this.plane, new THREE.Vector3());
        if (!point || point.x < -4 || point.x >= 4 || point.z < -4 || point.z >= 4) return null;
        return String.fromCharCode(97 + Math.floor(point.x + 4)) + (8 - Math.floor(point.z + 4));
    }

    // Useful to UI automation and future board annotations. Coordinates are CSS pixels.
    squareToScreen(square) {
        const model = this.pieces.children.find(piece => piece.userData.square === square);
        const point = model ? new THREE.Box3().setFromObject(model).getCenter(new THREE.Vector3()) : position(square);
        const projected = point.project(this.camera);
        const rect = this.canvas.getBoundingClientRect();
        return { x: (projected.x + 1) * rect.width / 2, y: (1 - projected.y) * rect.height / 2 };
    }

    _marker(square, style, dot = false) {
        const marker = new THREE.Mesh(dot ? this.dotGeometry : this.markerGeometry, this.markerMaterials[style]);
        marker.rotation.x = -Math.PI / 2;
        marker.position.copy(position(square));
        marker.position.y = .112;
        this.markers.add(marker);
    }

    render(state) {
        if (state) this.state = state;
        if (this.canvas.hidden || !this.renderer) return;
        if (state?.boardState) {
            const signature = JSON.stringify(state.boardState);
            if (signature !== this.signature) {
                this.signature = signature;
                this.pieces.clear();
                for (let row = 0; row < 8; row++) for (let col = 0; col < 8; col++) {
                    const piece = state.boardState[row][col];
                    if (!piece) continue;
                    const square = String.fromCharCode(97 + col) + (8 - row);
                    const model = this.templates[piece.color + piece.type].clone();
                    model.userData.square = square;
                    model.position.copy(position(square));
                    model.rotation.y = (piece.color === 'b' ? Math.PI : 0) + (piece.type === 'n' ? (this.theme === 'elven' ? -.45 : Math.PI / 2) : 0);
                    this.pieces.add(model);
                }
                this.renderer.shadowMap.needsUpdate = true;
            }
            this.markers.clear();
            if (state.lastMove) for (const square of [state.lastMove.from, state.lastMove.to]) this._marker(square, 'last');
            if (state.selectedSquare) this._marker(state.selectedSquare, 'selected');
            if (state.checkSquare) this._marker(state.checkSquare, 'check');
            for (const move of state.validMoves) this._marker(move.to, move.captured ? 'capture' : 'move', !move.captured);
            for (const model of this.pieces.children) {
                model.position.copy(position(model.userData.square));
                const a = state._animation;
                if (a && model.userData.square === a.hideSquare) {
                    const t = Math.min(1, (performance.now() - a.start) / a.duration);
                    const ease = 1 - (1 - t) ** 3;
                    model.position.x = (a.fromX + (a.toX - a.fromX) * ease) / SQUARE_SIZE - 3.5;
                    model.position.z = (a.fromY + (a.toY - a.fromY) * ease) / SQUARE_SIZE - 3.5;
                    model.position.y += Math.sin(t * Math.PI) * .18;
                }
            }
            // The final resting position also needs a fresh shadow after an animation.
            if (state._animation || this.wasAnimating) this.renderer.shadowMap.needsUpdate = true;
            this.wasAnimating = !!state._animation;
        }
        this.renderer.render(this.scene, this.camera);
    }

    async exportAssets() {
        // Keep the requested collection stable if the player switches themes while
        // the exporter module is loading.
        const { theme, boardAsset, templates } = this;
        const { GLTFExporter } = await import('../../lib/three/GLTFExporter.js');
        const collection = new THREE.Group();
        collection.name = `${theme === 'elven' ? 'Sylvan Court' : 'Runeforge'} - original Battle Chess set`;
        collection.add(boardAsset.clone());
        const back = ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'];
        for (const color of ['w', 'b']) for (let col = 0; col < 8; col++) for (const pawn of [true, false]) {
            const type = pawn ? 'p' : back[col];
            const model = templates[color + type].clone();
            model.position.set(col - 3.5, .105, color === 'w' ? (pawn ? 2.5 : 3.5) : (pawn ? -2.5 : -3.5));
            model.rotation.y = (color === 'b' ? Math.PI : 0) + (type === 'n' ? (theme === 'elven' ? -.45 : Math.PI / 2) : 0);
            collection.add(model);
        }
        return new GLTFExporter().parseAsync(collection, { binary: true });
    }
}
