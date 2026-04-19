/* ================================================================
   Werblers Ã¢â‚¬â€œ iOS / Mobile Game Client
   Touch-first rewrite of the desktop game.js
   ================================================================ */

// Ã¢â€â‚¬Ã¢â€â‚¬ Globals Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
let gameState = null;
let viewingPlayerId = null;
let _lastKnownCurrentPlayerId = null;
let numPlayers = 0;
let heroSelections = {};
let heroData = [];
let heroAnimMap = {};
let abilityChoices = {};
let _activeTab = 'board';
let _carouselPlayer = 0;
let _carouselIdx = 0;
let _musicEl = null;
let _musicVol = 0.5;
let _sfxVol = 0.5;
let _pendingOfferData = null;
let _pendingOfferType = null; // 'chest' or 'shop'
let _pendingPlacement = null;
let _pendingCombatInfo = null;
let _crossroadsSelectedSources = []; // tracks selected discard items for Crossroads Demon

// Profile / Save / Achievement state
let _deviceId    = '';
let _profileId   = null;
let _profileName = '';
let _saveLoadMode = 'save';
let _selectedSlot = null;
let _savesData    = [];
let _pendingAchievements = [];
let _achievementPopupActive = false;
let _achievementsTriggeredThisSession = new Set();

// ================================================================
// INITIALIZATION
// ================================================================
document.addEventListener('DOMContentLoaded', initSetup);

function initSetup() {
  _initDeviceId();
  fetch('/games/werblers/api/heroes').then(r => r.json()).then(data => {
    heroData = Array.isArray(data) ? data : (data.heroes || []);
    heroAnimMap = {};
    for (const h of heroData) {
      if (h.animations) heroAnimMap[h.id] = h.animations;
    }
    _loadProfileScreen();
  });
}

// ================================================================
// TAB NAVIGATION
// ================================================================
function switchTab(tab) {
  _activeTab = tab;
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  const pane = document.getElementById(tab + '-tab');
  if (pane) pane.classList.add('active');
  const btn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
  if (btn) btn.classList.add('active');
}

// ================================================================
// MUSIC
// ================================================================
function playMusic(track) {
  if (!_musicEl) {
    _musicEl = document.createElement('audio');
    _musicEl.loop = true;
    document.body.appendChild(_musicEl);
  }
  const src = '/games/werblers/music/' + track;
  if (_musicEl.src && _musicEl.src.endsWith(track)) return;
  _musicEl.src = src;
  _musicEl.volume = _musicVol;
  _musicEl.play().catch(() => {});
}
function _tierMusic(tier) {
  const map = {1: 'Tier 1 Music.wav', 2: 'Tier 2 Music.wav', 3: 'Tier 3 Music.wav'};
  playMusic(map[tier] || map[1]);
}
function _resumeTierMusic() {
  if (!gameState) return;
  const p = gameState.players.find(x => x.is_current) || gameState.players[0];
  if (p) {
    const pos = p.position || 1;
    if (pos <= 30) _tierMusic(1);
    else if (pos <= 60) _tierMusic(2);
    else _tierMusic(3);
  }
}

function showStrBreakdown() {
  const el = document.getElementById('player-stats');
  const lines = el._strBreakdown || [];
  if (!lines.length) return;
  const overlay = document.createElement('div');
  overlay.className = 'action-sheet-overlay';
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  const sheet = document.createElement('div');
  sheet.className = 'action-sheet';
  sheet.innerHTML = `<div style="text-align:center;padding:8px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:16px">Strength Breakdown</div>` +
    lines.map(l => `<div class="action-sheet-item" style="justify-content:flex-start;font-size:14px;padding:8px 14px;min-height:36px">${l}</div>`).join('') +
    `<div class="action-sheet-cancel" onclick="this.closest('.action-sheet-overlay').remove()">Close</div>`;
  overlay.appendChild(sheet);
  document.body.appendChild(overlay);
}
function setMusicVolume(v) {
  _musicVol = v / 100;
  if (_musicEl) _musicEl.volume = _musicVol;
  document.getElementById('vol-music-val').textContent = v;
}
function setSfxVolume(v) {
  _sfxVol = v / 100;
  document.getElementById('vol-sfx-val').textContent = v;
}
function showOptions() { document.getElementById('options-modal').classList.remove('hidden'); }
function closeOptions() { document.getElementById('options-modal').classList.add('hidden'); }

// ================================================================
// SETUP
// ================================================================
function setNumPlayers(n) {
  numPlayers = n;
  heroSelections = {};
  document.querySelectorAll('.btn-count').forEach((b, i) => {
    b.classList.toggle('selected', i === n - 1);
  });
  document.getElementById('continue-btn').disabled = false;
}

function continueToHeroes() {
  _carouselPlayer = 0;
  _carouselIdx = 0;
  document.getElementById('setup-screen-1').classList.add('hidden');
  document.getElementById('setup-screen-2').classList.remove('hidden');
  _renderCarousel();
}

function _availableHeroes() {
  const taken = Object.entries(heroSelections)
    .filter(([k]) => parseInt(k) !== _carouselPlayer)
    .map(([, v]) => v);
  return heroData.filter(h => !taken.includes(h.id));
}

function _renderCarousel() {
  const available = _availableHeroes();
  if (!available.length) return;
  if (_carouselIdx >= available.length) _carouselIdx = 0;
  const hero = available[_carouselIdx];
  const imgPath = hero.card_image.split('/').map(encodeURIComponent).join('/');
  document.getElementById('hero-carousel-img').src = '/games/werblers/images/' + imgPath;
  document.getElementById('hero-carousel-name').textContent = hero.name;
  document.getElementById('hero-carousel-title').textContent = hero.title || '';
  document.getElementById('hero-screen-player').textContent = 'Player ' + (_carouselPlayer + 1);
}

function prevHero() {
  const n = _availableHeroes().length;
  _carouselIdx = (_carouselIdx - 1 + n) % n;
  _renderCarousel();
}

function nextHero() {
  const n = _availableHeroes().length;
  _carouselIdx = (_carouselIdx + 1) % n;
  _renderCarousel();
}

function confirmHero() {
  const available = _availableHeroes();
  if (!available.length) return;
  heroSelections[_carouselPlayer] = available[_carouselIdx].id;
  _carouselPlayer++;
  if (_carouselPlayer < numPlayers) {
    _carouselIdx = 0;
    _renderCarousel();
  } else {
    startGame();
  }
}

function openHeroZoom() {
  const src = document.getElementById('hero-carousel-img').src;
  document.getElementById('hero-zoom-img').src = src;
  document.getElementById('hero-zoom-overlay').classList.remove('hidden');
}

function closeHeroZoom() {
  document.getElementById('hero-zoom-overlay').classList.add('hidden');
}

async function startGame() {
  const hero_ids = [];
  for (let i = 0; i < numPlayers; i++) hero_ids.push(heroSelections[i]);
  const resp = await fetch('/games/werblers/api/new_game', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({hero_ids}),
  });
  const data = await resp.json();
  document.getElementById('setup-screen-2').classList.add('hidden');
  document.getElementById('game-screen').classList.remove('hidden');
  gameState = data.state;
  viewingPlayerId = data.state.players[0]?.player_id ?? 0;
  buildBoard();
  applyState(data.state);
  playMusic('Theme Music.wav');
}

// ================================================================
// BOARD
// ================================================================
function tileToGrid(tileNum) {
  const idx = tileNum - 1;
  const row = Math.floor(idx / 10);
  let col = idx % 10;
  if (row % 2 === 1) col = 9 - col;
  return {row: 8 - row, col};
}

function tileLevel(n) {
  if (n <= 30) return 1;
  if (n <= 60) return 2;
  return 3;
}

let _boardBuilt = false;
const _tileEls = {};

function buildBoard() {
  if (_boardBuilt) return;
  const grid = document.getElementById('board-grid');
  grid.innerHTML = '';
  for (let n = 1; n <= 90; n++) {
    const {row, col} = tileToGrid(n);
    const div = document.createElement('div');
    div.className = `tile tier-${tileLevel(n)}`;
    div.style.gridRow = row + 1;
    div.style.gridColumn = col + 1;
    div.dataset.index = n;
    const img = document.createElement('img');
    img.className = 'tile-bg';
    img.alt = `Tile ${n}`;
    div.appendChild(img);
    const tokenArea = document.createElement('div');
    tokenArea.className = 'tile-tokens';
    div.appendChild(tokenArea);
    grid.appendChild(div);
    _tileEls[n] = div;
  }
  _boardBuilt = true;
}

function updateBoard() {
  if (!gameState) return;
  buildBoard();
  // Determine miniboss defeat flags for the currently-viewed player
  const viewP = gameState.players.find(x => x.player_id === viewingPlayerId) || gameState.players[0];
  const mb1Done = viewP ? viewP.miniboss1_defeated : false;
  const mb2Done = viewP ? viewP.miniboss2_defeated : false;
  // Update tile images
  for (const tile of (gameState.board || [])) {
    const el = _tileEls[tile.index];
    if (!el) continue;
    let img = tile.image;
    if (tile.image_defeated) {
      const isDefeated = (tile.index === 30 && mb1Done) || (tile.index === 60 && mb2Done);
      if (isDefeated) img = tile.image_defeated;
    }
    el.querySelector('img.tile-bg').src = `/games/werblers/images/${img}`;
  }
  // Clear all token areas
  for (let n = 1; n <= 90; n++) {
    _tileEls[n].querySelector('.tile-tokens').innerHTML = '';
  }
  // Place player tokens
  const byPos = {};
  for (const p of (gameState.players || [])) {
    const pos = p.position || 1;
    (byPos[pos] = byPos[pos] || []).push(p);
  }
  for (const [posStr, players] of Object.entries(byPos)) {
    const pos = parseInt(posStr);
    const tileEl = _tileEls[pos];
    if (!tileEl) continue;
    const tokenArea = tileEl.querySelector('.tile-tokens');
    // Sort so the current player's token is appended last (renders on top)
    const sortedPlayers = [...players].sort((a, b) => a.is_current ? 1 : b.is_current ? -1 : 0);
    for (const p of sortedPlayers) {
      if (!p.token_image) continue;
      const img = document.createElement('img');
      img.className = 'tile-token' + (p.is_current ? ' current-player-token' : '');
      img.src = `/games/werblers/images/${p.token_image}`;
      img.alt = p.name;
      tokenArea.appendChild(img);
    }
  }
}

// ================================================================
// PLAYER TABS
// ================================================================
function updatePlayerTabs() {
  const container = document.getElementById('player-tabs');
  if (!gameState || gameState.players.length <= 1) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = gameState.players.map(p => {
    const cls = 'ptab' + (p.player_id === viewingPlayerId ? ' active' : '') + (p.is_current ? ' is-current' : '');
    return `<button class="${cls}" onclick="switchPlayer(${p.player_id})">${p.hero_name}</button>`;
  }).join('');
}

function switchPlayer(pid) {
  viewingPlayerId = pid;
  updatePlayerTabs();
  updatePlayerStats();
  updateEquipSummary();
}

// ================================================================
// PLAYER STATS
// ================================================================
function _playerStrBreakdown(p) {
  const lines = [];
  lines.push(`Base: ${p.base_strength || 0}`);
  for (const item of [...(p.helmets||[]), ...(p.chest_armor||[]), ...(p.leg_armor||[]), ...(p.weapons||[])]) {
    const parts = [];
    if (item.strength_bonus) parts.push(item.strength_bonus >= 0 ? `+${item.strength_bonus}` : `${item.strength_bonus}`);
    if (item.tokens) parts.push(`${item.tokens > 0 ? '+' : ''}${item.tokens} token`);
    if (parts.length) lines.push(`${item.name}: ${parts.join(', ')}`);
  }
  for (const t of (p.traits || [])) { if (t.tokens) lines.push(`${t.name}: +${t.tokens}`); if (t.strength_bonus) lines.push(`${t.name}: +${t.strength_bonus}`); }
  for (const m of (p.minions || [])) { if (m.strength_bonus) lines.push(`${m.name}: +${m.strength_bonus}`); }
  for (const c of (p.curses || [])) {
    if (c.strength_bonus) lines.push(`${c.name}: ${c.strength_bonus >= 0 ? '+' : ''}${c.strength_bonus}`);
    if (c.tokens) lines.push(`${c.name}: ${c.tokens >= 0 ? '+' : ''}${c.tokens} (conditional)`);
  }
  for (const l of (p.ability_breakdown || [])) { lines.push(l); }
  lines.push(`Total: ${p.strength}`);
  return lines;
}

function updatePlayerStats() {
  const el = document.getElementById('player-stats');
  if (!gameState) { el.innerHTML = ''; return; }
  const p = gameState.players.find(x => x.player_id === viewingPlayerId) || gameState.players[0];
  if (!p) return;
  const breakdownLines = _playerStrBreakdown(p);
  el.innerHTML = `
    <div class="player-header-ios">
      <div class="player-name-ios">${p.hero_name || p.name || 'Player'}</div>
      <div class="player-str-ios" onclick="showStrBreakdown()">STR ${p.strength} <span class="str-info-icon">Ã¢â€œËœ</span></div>
    </div>
  `;
  // Store breakdown for the tap
  el._strBreakdown = breakdownLines;
}

function updateEquipSummary() {
  const el = document.getElementById('equip-summary');
  if (!gameState) { el.innerHTML = ''; return; }
  const p = gameState.players.find(x => x.player_id === viewingPlayerId) || gameState.players[0];
  if (!p) return;

  // Build a flat equip index for manage_item actions
  let equipIdx = 0;
  function equipLine(label, items, slotKey) {
    if (!items || items.length === 0) return `<div class="equip-row"><span class="equip-slot-label">${label}</span><span class="equip-empty">Empty</span></div>`;
    return items.map((item, si) => {
      const myIdx = equipIdx++;
      const bonus = item.strength_bonus >= 0 ? `+${item.strength_bonus}` : `${item.strength_bonus}`;
      const img = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
      const thumb = img ? `<img class="equip-item-thumb" src="${img}">` : '';
      const ctx = img ? `onclick="openCardZoomWithActions('${_esc(img)}',{type:'equip',index:${myIdx},name:'${_esc(item.name)}'})"`  : '';
      return `<div class="equip-row" ${ctx}>${thumb}<span class="equip-slot-label">${label}</span><span class="equip-item-name">${item.name}</span><span class="equip-item-bonus">${bonus}</span></div>`;
    }).join('');
  }

  let html = '<div class="equip-summary-title">Equipment</div>';
  html += equipLine('Head', p.helmets, 'helmet');
  html += equipLine('Chest', p.chest_armor, 'chest');
  html += equipLine('Legs', p.leg_armor, 'legs');
  html += equipLine('Weapon', p.weapons, 'weapon');

  // Pack
  const packEquip = p.pack || [];
  const consumables = p.consumables || [];
  const captured = p.captured_monsters || [];
  const allPack = [...packEquip, ...consumables, ...captured];
  const packSize = p.pack_size || 5;
  html += `<div class="equip-summary-title" style="margin-top:10px">Pack (${allPack.length}/${packSize})</div>`;
  html += '<div class="pack-row">';
  for (let i = 0; i < packEquip.length; i++) {
    const item = packEquip[i];
    const img = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
    if (img) html += `<img class="pack-thumb" src="${img}" onclick="openCardZoomWithActions('${_esc(img)}',{type:'pack',index:${i},name:'${_esc(item.name)}'})" alt="${item.name}">`;
    else html += `<div class="pack-thumb pack-thumb-text" onclick="openCardZoomWithActions('',{type:'pack',index:${i},name:'${_esc(item.name)}'})" title="${item.name}">${item.name}</div>`;
  }
  for (let i = 0; i < consumables.length; i++) {
    const item = consumables[i];
    const img = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
    if (img) html += `<img class="pack-thumb" src="${img}" onclick="openCardZoomWithActions('${_esc(img)}',{type:'consumable',index:${i},name:'${_esc(item.name)}'})" alt="${item.name}">`;
    else html += `<div class="pack-thumb pack-thumb-text" onclick="openCardZoomWithActions('',{type:'consumable',index:${i},name:'${_esc(item.name)}'})" title="${item.name}">${item.name}</div>`;
  }
  for (let i = 0; i < captured.length; i++) {
    const item = captured[i];
    const img = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
    if (img) html += `<img class="pack-thumb" src="${img}" onclick="openCardZoomWithActions('${_esc(img)}',{type:'minion',index:${i},name:'${_esc(item.name)}'})" alt="${item.name}">`;
    else html += `<div class="pack-thumb pack-thumb-text" onclick="openCardZoomWithActions('',{type:'minion',index:${i},name:'${_esc(item.name)}'})" title="${item.name}">${item.name}</div>`;
  }
  // Empty pack slots
  const emptySlots = Math.max(0, packSize - allPack.length);
  for (let i = 0; i < emptySlots; i++) {
    html += `<div class="pack-thumb-empty"></div>`;
  }
  html += '</div>';

  // Traits & Curses
  const traits = p.traits || [];
  const curses = p.curses || [];
  if (traits.length || curses.length) {
    html += '<div class="equip-summary-title" style="margin-top:10px">Traits & Curses</div>';
    for (const t of traits) {
      const tokCount = t.effect_id === 'residuals' ? (t.strength_bonus || 0) : t.tokens;
      const tokBadge = tokCount > 0 ? ` <span class="tc-token-badge"><img src="/games/werblers/images/Assorted UI Images/+1 Token.png" style="height:14px;vertical-align:middle;margin-right:2px" onerror="this.style.display='none'">${tokCount}</span>` : '';
      html += `<div class="equip-row" onclick="showTcTooltip('${_esc(t.name)}','${_esc(t.description || '')}',this)"><span style="color:var(--trait)">Ã¢Å“Â¦ ${t.name}</span>${tokBadge}</div>`;
    }
    for (const c of curses) {
      const tokBadge = c.tokens > 0 ? ` <span class="tc-token-badge"><img src="/games/werblers/images/Assorted UI Images/+1 Token.png" style="height:14px;vertical-align:middle;margin-right:2px" onerror="this.style.display='none'">${c.tokens}</span>` : (c.tokens < 0 ? ` <span class="tc-token-badge"><img src="/games/werblers/images/Assorted UI Images/-1 Token.png" style="height:14px;vertical-align:middle;margin-right:2px" onerror="this.style.display='none'">${Math.abs(c.tokens)}</span>` : '');
      html += `<div class="equip-row" onclick="showTcTooltip('${_esc(c.name)}','${_esc(c.description || '')}',this)"><span style="color:var(--curse)">Ã¢Å“Â§ ${c.name}</span>${tokBadge}</div>`;
    }
  }

  el.innerHTML = html;
}

function _esc(s) { return (s || '').replace(/'/g, "\\'").replace(/"/g, '&quot;'); }

// ================================================================
// MOVEMENT
// ================================================================
function updateMovementHand() {
  const bar = document.getElementById('movement-bar');
  const hand = document.getElementById('movement-hand');
  if (!gameState) { bar.classList.add('hidden'); return; }
  const p = gameState.players.find(x => x.is_current);
  if (!p || !p.movement_hand || p.movement_hand.length === 0) {
    bar.classList.add('hidden');
    return;
  }
  bar.classList.remove('hidden');
  const heroBonus = p.movement_card_bonus || 0;
  const hasBotched = (p.curses || []).some(c => c.effect_id === 'botched_circumcision');
  hand.innerHTML = p.movement_hand.map((v, i) => {
    const dispVal = v + heroBonus;
    const imgVal = Math.min(Math.max(dispVal, 1), 5);
    const badge = (dispVal !== imgVal) ? `<span class="mv-card-badge">${dispVal}</span>` : '';
    const curseBanner = hasBotched ? `<span class="mv-card-curse-banner" onclick="event.stopPropagation();alert('-1 movement from Botched Circumcision')">-1</span>` : '';
    return `<div class="mv-card" onclick="promptDirection(${i}, ${dispVal})"><img class="mv-card-img" src="/games/werblers/images/Movement/Movement Card ${imgVal}.png" alt="${dispVal}">${badge}${curseBanner}</div>`;
  }).join('');
}

let _pendingCardIndex = null;
let _moveInFlight = false;

function promptDirection(cardIndex, cardValue) {
  if (_moveInFlight) return;
  if (!gameState || gameState.game_status !== 'IN_PROGRESS') return;
  const p = gameState.players.find(x => x.is_current);
  if (!p) return;
  const fwdTile = Math.min(p.position + cardValue, 90);
  const bwdTile = Math.max(p.position - cardValue, 1);
  _pendingCardIndex = cardIndex;
  document.getElementById('direction-desc').textContent =
    `Card ${cardValue}: Forward to tile ${fwdTile} or Backward to tile ${bwdTile}?`;
  const btns = document.getElementById('direction-btns');
  btns.innerHTML = `
    <button class="btn-primary direction-btn" onclick="confirmDirection('forward')">Forward</button>
    <button class="btn-secondary direction-btn" onclick="confirmDirection('backward')">Backward</button>
    <button class="btn-cancel direction-btn" onclick="cancelDirection()">Cancel</button>`;
  document.getElementById('direction-modal').classList.remove('hidden');
}

function cancelDirection() {
  document.getElementById('direction-modal').classList.add('hidden');
  _pendingCardIndex = null;
}

async function confirmDirection(dir) {
  document.getElementById('direction-modal').classList.add('hidden');
  if (_pendingCardIndex === null) return;
  const idx = _pendingCardIndex;
  _pendingCardIndex = null;
  await beginMove(idx, dir);
}

async function beginMove(cardIndex, direction = 'forward') {
  if (_moveInFlight) return;
  if (!gameState || gameState.game_status !== 'IN_PROGRESS') return;
  _moveInFlight = true;
  try {
    const activated = Object.assign({}, abilityChoices);
    const resp = await fetch('/games/werblers/api/begin_move', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({card_index: cardIndex, flee: false, activated, direction}),
    });
    if (!resp.ok) { 
      const errData = await resp.json().catch(() => ({}));
      console.error('begin_move failed', resp.status, errData);
      if (errData.error) alert(errData.error);
      return;
    }
    const data = await resp.json();
    if (data.error) { alert(data.error); return; }
    if (data.state) { viewingPlayerId = data.state.current_player_id; gameState = data.state; applyState(data.state); }
    if (data.phase === 'combat' && data.combat_info) {
      playMusic('Battle Music.wav');
      showPreFightScene(data.combat_info, data.state);
    } else if (data.phase === 'charlie_work') {
      _showCharlieWorkDecision(data.level);
    } else if (data.phase === 'done') {
      _resumeTierMusic();
      await loadAndRenderAbilities();
    } else if (data.phase === 'offer_chest') {
      _pendingOfferData = data.offer;
      playMusic('Chest Music.wav');
      showChestModal(data.offer, data);
    } else if (data.phase === 'offer_shop') {
      _pendingOfferData = data.offer;
      playMusic('Shop Music.wav');
      showShopModal(data.offer, data);
    } else if (data.phase === 'mystery') {
      showMysteryEventModal(data.mystery_event, data.state);
    } else if (data.phase === 'rake_it_in') {
      showRakeItIn(data);
    }
  } catch (err) {
    console.error('beginMove error:', err);
    // Ensure turn banner stays in sync even on error
    if (gameState) applyState(gameState);
  } finally {
    _moveInFlight = false;
  }
}

// ================================================================
// ABILITIES
// ================================================================
async function loadAndRenderAbilities() {
  if (!gameState) return;
  const p = gameState.players.find(x => x.is_current);
  if (!p) return;
  try {
    const resp = await fetch('/games/werblers/api/get_abilities');
    const data = await resp.json();
    renderAbilities(data.abilities || []);
  } catch (_) {}
}

function renderAbilities(abilities) {
  const section = document.getElementById('abilities-section');
  if (!abilities || abilities.length === 0) {
    section.innerHTML = '';
    return;
  }
  section.innerHTML = abilities.map(ab => {
    let actionHtml = '';
    if (ab.type === 'instant_select_curse') {
      const curses = ab.curses || [];
      if (curses.length === 1) {
        actionHtml = `<button class="btn-primary ability-instant-btn" onclick="useEightLives(0)">Use: Remove "${_esc(curses[0])}"</button>`;
      } else if (curses.length > 1) {
        const opts = curses.map((c, i) => `<option value="${i}">${_esc(c)}</option>`).join('');
        actionHtml = `<div class="ability-select-row">
          <select class="ability-select" id="eight-lives-sel-${ab.id}">${opts}</select>
          <button class="btn-primary ability-instant-btn" onclick="useEightLives(parseInt(document.getElementById('eight-lives-sel-${ab.id}').value))">Use Eight Lives</button>
        </div>`;
      }
    } else if (ab.type === 'activate') {
      const rawVal = ab.value || 0;
      actionHtml = `<button class="btn-primary ability-instant-btn" onclick="activateWheelies(${rawVal})">Ã°Å¸â€ºÅ¾ Use Wheelies!</button>`;
    } else if (ab.type === 'toggle') {
      const cur = abilityChoices[ab.id] !== undefined ? abilityChoices[ab.id] : ab.default;
      actionHtml = `<div class="ability-toggle">
        <button class="ability-btn ${cur ? 'active' : 'inactive'}" onclick="toggleAbility('${ab.id}', true)">On</button>
        <button class="ability-btn ${!cur ? 'active' : 'inactive'}" onclick="toggleAbility('${ab.id}', false)">Off</button>
      </div>`;
    } else if (ab.type === 'select_number') {
      const cur = abilityChoices[ab.id];
      const checked = cur !== undefined;
      const opts = (ab.options || []).map(n => `<option value="${n}" ${cur?.reduction === n ? 'selected' : ''}>Reduce by ${n}</option>`).join('');
      actionHtml = `<div class="ability-check-row">
        <label class="ability-check-label"><input type="checkbox" ${checked ? 'checked' : ''} onchange="onIosAbilityCheck(this,'${ab.id}','reduction',true)"> Activate</label>
        <select class="ability-select" id="ab-sel-${ab.id}" onchange="onIosAbilitySelectField('${ab.id}','reduction',true)">${opts}</select>
      </div>`;
    } else if (ab.type === 'select_trait') {
      const cur = abilityChoices[ab.id];
      const checked = cur !== undefined;
      const opts = (ab.traits || []).map((t, i) => `<option value="${i}" ${cur?.trait_index === i ? 'selected' : ''}>${_esc(t)}</option>`).join('');
      actionHtml = `<div class="ability-check-row">
        <label class="ability-check-label"><input type="checkbox" ${checked ? 'checked' : ''} onchange="onIosAbilityCheck(this,'${ab.id}','trait_index',true)"> Activate</label>
        <select class="ability-select" id="ab-sel-${ab.id}" onchange="onIosAbilitySelectField('${ab.id}','trait_index',true)">${opts}</select>
      </div>`;
    } else if (ab.type === 'select_equip') {
      const cur = abilityChoices[ab.id];
      const checked = cur !== undefined;
      const opts = (ab.equips || []).map((e, i) => `<option value="${i}" ${cur?.equip_index === i ? 'selected' : ''}>${_esc(e)}</option>`).join('');
      actionHtml = `<div class="ability-check-row">
        <label class="ability-check-label"><input type="checkbox" ${checked ? 'checked' : ''} onchange="onIosAbilityCheck(this,'${ab.id}','equip_index',true)"> Activate</label>
        <select class="ability-select" id="ab-sel-${ab.id}" onchange="onIosAbilitySelectField('${ab.id}','equip_index',true)">${opts}</select>
      </div>`;
    } else if (ab.type === 'select_player_minion') {
      const cur = abilityChoices[ab.id];
      const checked = cur !== undefined;
      const opts = (ab.targets || []).map(t => `<option value="${t.player_id}" ${String(cur?.target_player_id) === String(t.player_id) ? 'selected' : ''}>${_esc(t.name)}</option>`).join('');
      actionHtml = `<div class="ability-check-row">
        <label class="ability-check-label"><input type="checkbox" ${checked ? 'checked' : ''} onchange="onIosAbilityCheck(this,'${ab.id}','target_player_id',false)"> Activate</label>
        <select class="ability-select" id="ab-sel-${ab.id}" onchange="onIosAbilitySelectField('${ab.id}','target_player_id',false)">${opts}</select>
      </div>`;
    }
    return `<div class="ability-card"><div class="ability-name">${ab.label || ab.name || '?'}</div><div class="ability-desc">${ab.description || ''}</div>${actionHtml}</div>`;
  }).join('');
}

function onIosAbilityCheck(el, id, field, isInt) {
  if (!el.checked) { delete abilityChoices[id]; return; }
  abilityChoices[id] = {};
  const sel = document.getElementById(`ab-sel-${id}`);
  if (sel) abilityChoices[id][field] = isInt ? parseInt(sel.value) : sel.value;
}

function onIosAbilitySelectField(id, field, isInt) {
  const sel = document.getElementById(`ab-sel-${id}`);
  if (!sel) return;
  if (abilityChoices[id] && typeof abilityChoices[id] === 'object') {
    abilityChoices[id][field] = isInt ? parseInt(sel.value) : sel.value;
  }
}

function activateWheelies(rawVal) {
  if (_moveInFlight) return;
  const p = gameState && gameState.players.find(x => x.is_current);
  if (!p) return;
  const heroBonus = p.movement_card_bonus || 0;
  const dispVal = rawVal + heroBonus;
  abilityChoices['wheelies'] = true;
  promptDirection(0, dispVal);
}

function toggleAbility(id, val) {
  abilityChoices[id] = val;
  loadAndRenderAbilities();
}

// ================================================================
// OFFERS (CHEST / SHOP)
// ================================================================
let _invOnConfirm = null;
let _invPlacementItem = null;

function showChestModal(offer, data) {
  _pendingOfferType = 'chest';
  const modal = document.getElementById('offer-modal');
  const content = document.getElementById('offer-content');
  const item = offer.items[0];
  const img = item.card_image ? `<img class="offer-item-img" src="/games/werblers/images/${item.card_image}" onclick="openCardZoom('/games/werblers/images/${item.card_image}')">` : '';
  const strSign = item.strength_bonus >= 0 ? '+' : '';
  const strText = item.strength_bonus !== 0 ? `${strSign}${item.strength_bonus} Str` : '';
  const scavengerBtn = offer.has_scavenger
    ? `<button class="btn-secondary" onclick="scavengerSwap()">Ã°Å¸â€â€ž Scavenger: Swap</button>`
    : '';
  content.innerHTML = `<h2 class="offer-title">Found Chest</h2>
    <div class="offer-items">
      <div class="offer-item-card">${img}
        <div class="offer-item-name">${item.name}</div>
        ${strText ? `<div class="offer-item-desc">${strText}</div>` : ''}
      </div>
    </div>
    <div class="modal-btns">
      ${scavengerBtn}
      <button class="btn-primary" onclick="confirmChestTake()">Take It</button>
      <button class="btn-secondary" onclick="openPlayerSheet()">View Inventory</button>
      <button class="btn-secondary" onclick="resolveOffer({take: false})">Leave It</button>
    </div>`;
  modal.classList.remove('hidden');
}

function confirmChestTake() {
  document.getElementById('offer-modal').classList.add('hidden');
  const item = _pendingOfferData.items[0];
  showInventoryPopup(item, (placement) => {
    if (placement.discard) { resolveOffer({take: false}); }
    else { resolveOffer({take: true, ...placement}); }
  });
}

let _shopSelectedIndex = -1;

function showShopModal(offer, data) {
  _shopSelectedIndex = -1;
  _pendingOfferType = 'shop';
  const modal = document.getElementById('offer-modal');
  const content = document.getElementById('offer-content');
  const items = offer.items || [];
  let html = `<h2 class="offer-title">Shop</h2>
    <p class="modal-desc">Choose one item to take Ã¢â‚¬â€ it's free!</p>
    <div class="offer-items">`;
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const img = item.card_image ? `<img class="offer-item-img" src="/games/werblers/images/${item.card_image}" onclick="event.stopPropagation();openCardZoom('/games/werblers/images/${item.card_image}')">` : '';
    const strSign = item.strength_bonus >= 0 ? '+' : '';
    const strText = item.strength_bonus !== 0 ? `${strSign}${item.strength_bonus} Str` : '';
    html += `<div class="offer-item-card shop-selectable" data-index="${i}" onclick="selectShopItem(${i}, this)">
      ${img}<div class="offer-item-name">${item.name}</div>
      ${strText ? `<div class="offer-item-desc">${strText}</div>` : ''}
    </div>`;
  }
  html += '</div>';
  html += `<div class="modal-btns">
    <button class="btn-primary" id="shop-confirm-btn" onclick="confirmShopTake()" disabled>Take It</button>
    <button class="btn-secondary" onclick="openPlayerSheet()">View Inventory</button>
    <button class="btn-secondary" onclick="resolveOffer({take: false})">Leave Shop</button>
  </div>`;
  content.innerHTML = html;
  modal.classList.remove('hidden');
}

function selectShopItem(idx, el) {
  _shopSelectedIndex = idx;
  document.querySelectorAll('.shop-selectable').forEach(c => c.classList.remove('selected'));
  if (el) el.classList.add('selected');
  const btn = document.getElementById('shop-confirm-btn');
  if (btn) btn.disabled = false;
}

function confirmShopTake() {
  if (_shopSelectedIndex < 0) return;
  document.getElementById('offer-modal').classList.add('hidden');
  const item = _pendingOfferData.items[_shopSelectedIndex];
  showInventoryPopup(item, (placement) => {
    if (placement.discard) { resolveOffer({take: false, chosen_index: _shopSelectedIndex}); }
    else { resolveOffer({chosen_index: _shopSelectedIndex, ...placement}); }
  });
}

async function scavengerSwap() {
  const resp = await fetch('/games/werblers/api/scavenger_swap', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: '{}',
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; applyState(data.state); }
  if (data.offer) {
    _pendingOfferData = data.offer;
    showChestModal(data.offer, {});
  }
}

async function resolveOffer(choices) {
  document.getElementById('offer-modal').classList.add('hidden');
  const resp = await fetch('/games/werblers/api/resolve_offer', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(choices),
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; applyState(data.state); }
  if (data.phase === 'rake_it_in') {
    showRakeItIn(data);
    return;
  }
  // If there's a pending mystery farewell, show it now
  if (_pendingMysteryFarewell) {
    const fw = _pendingMysteryFarewell;
    _pendingMysteryFarewell = null;
    await _showCharacterFarewell(fw.event, fw.quote, () => {
      document.getElementById('battle-overlay').classList.add('hidden');
      if (gameState) {
        viewingPlayerId = gameState.current_player_id;
        applyState(gameState);
      }
      _resumeTierMusic();
      loadAndRenderAbilities();
    });
    return;
  }
  viewingPlayerId = data.state.current_player_id;
  applyState(data.state);
  _resumeTierMusic();
  await loadAndRenderAbilities();
}

// ================================================================
// INVENTORY / PLACEMENT
// ================================================================
function showInventoryPopup(item, onConfirm) {
  _invOnConfirm = onConfirm;
  _invPlacementItem = item;
  const p = gameState?.players?.find(x => x.is_current);
  if (!p) return;
  // Build placementInfo from item slot
  const equipSlot = item.slot; // 'helmet', 'chest', 'legs', 'weapon', or 'consumable'
  const validSlots = [];
  if (equipSlot && equipSlot !== 'consumable') validSlots.push(equipSlot);
  validSlots.push('pack');
  const placementInfo = { item_to_place: item, valid_slots: validSlots };
  renderPlayerSheetFull(p, placementInfo);
}

function _finishPlacement(choices) {
  _invPlacementItem = null;
  document.getElementById('player-sheet-overlay').classList.add('hidden');
  const cb = _invOnConfirm;
  _invOnConfirm = null;
  if (cb) cb(choices);
}

function _cancelPlacement() {
  _invPlacementItem = null;
  _invOnConfirm = null;
  document.getElementById('player-sheet-overlay').classList.add('hidden');
  // Re-show the offer modal (it was hidden but content is still intact)
  if (_pendingOfferData) {
    document.getElementById('offer-modal').classList.remove('hidden');
  }
}

// During pack-full placement: confirm discard of an existing item to make room
function _confirmPackReplace(unifiedIndex, itemName) {
  const overlay = document.createElement('div');
  overlay.className = 'action-sheet-overlay';
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  const sheet = document.createElement('div');
  sheet.className = 'action-sheet';
  sheet.innerHTML = `<div style="text-align:center;padding:8px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:15px">Discard to make room?</div>
    <div class="action-sheet-item" style="color:var(--text-dim);pointer-events:none">${itemName}</div>
    <div class="action-sheet-item danger" id="_cpr-confirm-btn">Discard ${itemName}</div>
    <div class="action-sheet-cancel">Cancel</div>`;
  sheet.querySelector('#_cpr-confirm-btn').onclick = () => {
    overlay.remove();
    _finishPlacement({placement: 'pack', pack_discard_index: unifiedIndex});
  };
  sheet.querySelector('.action-sheet-cancel').onclick = () => overlay.remove();
  overlay.appendChild(sheet);
  document.body.appendChild(overlay);
}

// ================================================================
// CARD ZOOM (tap-to-view) Ã¢â‚¬â€ with optional action buttons
// ================================================================
function openCardZoom(imgSrc) {
  const modal = document.getElementById('card-zoom-modal');
  modal.innerHTML = `<div class="card-zoom-inner" onclick="closeCardZoom()"><img src="${imgSrc}" alt="Card"><div class="card-zoom-actions"><button class="btn-secondary btn-sm" onclick="event.stopPropagation();closeCardZoom()">Back</button></div></div>`;
  modal.classList.remove('hidden');
}
function openCardZoomWithActions(imgSrc, itemContext) {
  // itemContext: { type: 'equip'|'pack'|'consumable'|'minion', index, name, slotKey, slotIdx }
  const modal = document.getElementById('card-zoom-modal');
  const p = gameState?.players?.find(x => x.is_current);
  const isMyTurn = p && p.player_id === viewingPlayerId;
  let btns = '';
  if (isMyTurn && itemContext) {
    if (itemContext.type === 'equip') {
      if (itemContext.source) {
        // Player sheet: source+index directly, no flat-index translation needed
        btns += `<button class="btn-secondary btn-sm" onclick="event.stopPropagation();closeCardZoom();_manageItemDirect('unequip_to_pack','${itemContext.source}',${itemContext.index})">Unequip</button>`;
        btns += `<button class="btn-danger btn-sm" onclick="event.stopPropagation();closeCardZoom();_manageItemDirect('discard_equip','${itemContext.source}',${itemContext.index})">Drop</button>`;
      } else {
        // Equip summary panel: uses flat index via _flatEquipToSource
        btns += `<button class="btn-secondary btn-sm" onclick="event.stopPropagation();closeCardZoom();_manageItem('unequip_to_pack',${itemContext.index})">Unequip</button>`;
        btns += `<button class="btn-danger btn-sm" onclick="event.stopPropagation();closeCardZoom();_manageItem('discard_equip',${itemContext.index})">Drop</button>`;
      }
    } else if (itemContext.type === 'pack') {
      btns += `<button class="btn-secondary btn-sm" onclick="event.stopPropagation();closeCardZoom();_manageItem('equip_from_pack',${itemContext.index})">Equip</button>`;
      btns += `<button class="btn-danger btn-sm" onclick="event.stopPropagation();closeCardZoom();_manageItem('discard_pack',${itemContext.index})">Drop</button>`;
    } else if (itemContext.type === 'consumable') {
      btns += `<button class="btn-primary btn-sm" onclick="event.stopPropagation();closeCardZoom();_useConsumableFromZoom(${itemContext.index})">Use</button>`;
      btns += `<button class="btn-danger btn-sm" onclick="event.stopPropagation();closeCardZoom();_discardConsumable(${itemContext.index})">Drop</button>`;
    } else if (itemContext.type === 'minion') {
      btns += `<button class="btn-secondary btn-sm" onclick="event.stopPropagation();closeCardZoom();releaseMonster(${itemContext.index})">Release</button>`;
    }
  }
  btns += `<button class="btn-secondary btn-sm" onclick="event.stopPropagation();closeCardZoom()">Back</button>`;
  const imgHtml = imgSrc ? `<img src="${imgSrc}" alt="Card">` : (itemContext?.name ? `<div class="card-zoom-placeholder">${itemContext.name}</div>` : '');
  modal.innerHTML = `<div class="card-zoom-inner">${imgHtml}<div class="card-zoom-actions">${btns}</div></div>`;
  modal.classList.remove('hidden');
}
function closeCardZoom() {
  document.getElementById('card-zoom-modal').classList.add('hidden');
}

// Use consumable from zoom Ã¢â‚¬â€ validates combat-only
function _useConsumableFromZoom(idx) {
  const p = gameState?.players?.find(x => x.is_current);
  if (!p) return;
  const c = (p.consumables || [])[idx];
  if (!c) return;
  // Check if combat-only
  const isOverworld = c.use_context === 'overworld' || c.use_context === 'both';
  const nameLC = (c.name || '').toLowerCase();
  const isBomb = nameLC.includes('bomb') || c.effect_id === 'give_curse';
  const isBlessing = nameLC.includes('priest');
  const isNectar = nameLC.includes('nectar');
  if (!isOverworld && !isBomb && !isBlessing && !isNectar) {
    _showCombatOnlyNotice(c.name);
    return;
  }
  // Bombs: show player selection first (outside combat only)
  if (isBomb && !gameState?.has_pending_combat) {
    _selectBombTarget(idx, c); return;
  }
  usePackConsumable(idx);
}

function _selectBombTarget(idx, c) {
  const currentPlayer = gameState?.players?.find(q => q.is_current);
  const allPlayers = (gameState?.players || []);
  const overlay = document.createElement('div');
  overlay.className = 'action-sheet-overlay';
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  const sheet = document.createElement('div');
  sheet.className = 'action-sheet';
  let html = `<div style="text-align:center;padding:8px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:16px">${c.name}</div>`
    + `<div class="action-sheet-item" style="color:var(--text-dim);font-style:italic;pointer-events:none">Who do you want to curse?</div>`;
  for (const target of allPlayers) {
    const isSelf = target.player_id === currentPlayer?.player_id;
    html += `<div class="action-sheet-item" data-target-id="${target.player_id}">${target.hero_name || target.name}${isSelf ? ' (You)' : ''}</div>`;
  }
  html += `<div class="action-sheet-cancel" onclick="this.closest('.action-sheet-overlay').remove()">Cancel</div>`;
  sheet.innerHTML = html;
  overlay.appendChild(sheet);
  document.body.appendChild(overlay);
  sheet.querySelectorAll('[data-target-id]').forEach(el => {
    el.onclick = () => { overlay.remove(); usePackConsumable(idx, parseInt(el.dataset.targetId)); };
  });
}

function _showCombatOnlyNotice(name) {
  const overlay = document.createElement('div');
  overlay.className = 'action-sheet-overlay';
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  const sheet = document.createElement('div');
  sheet.className = 'action-sheet';
  sheet.innerHTML = `<div style="text-align:center;padding:12px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:16px">${name}</div>
    <div class="action-sheet-item" style="color:var(--text-dim);font-style:italic">This consumable can only be used during combat.</div>
    <div class="action-sheet-cancel" onclick="this.closest('.action-sheet-overlay').remove()">OK</div>`;
  overlay.appendChild(sheet);
  document.body.appendChild(overlay);
}

// ================================================================
// TRAIT/CURSE TOOLTIP (tap-based)
// ================================================================
let _tcTooltipToken = 0;
function showTcTooltip(name, desc, el) {
  // Remove stale dismiss handlers from any previous tooltip
  document.removeEventListener('touchstart', _hideTcTooltip);
  document.removeEventListener('click', _hideTcTooltip);
  _tcTooltipToken++;
  const tooltip = document.getElementById('tc-tooltip');
  tooltip.innerHTML = `<div class="tc-tooltip-name">${name}</div>${desc ? `<div class="tc-tooltip-desc">${desc}</div>` : ''}`;
  tooltip.classList.remove('hidden');
  // Position near the tapped element
  const rect = el.getBoundingClientRect();
  tooltip.style.left = Math.min(rect.left, window.innerWidth - 290) + 'px';
  tooltip.style.top = (rect.bottom + 8) + 'px';
  // Hide on next tap anywhere (with guard against same-event race)
  const token = _tcTooltipToken;
  setTimeout(() => {
    if (token !== _tcTooltipToken) return;
    document.addEventListener('touchstart', _hideTcTooltip, {once: true});
    document.addEventListener('click', _hideTcTooltip, {once: true});
  }, 80);
}
function _hideTcTooltip() {
  document.getElementById('tc-tooltip').classList.add('hidden');
  document.removeEventListener('touchstart', _hideTcTooltip);
  document.removeEventListener('click', _hideTcTooltip);
}

// ================================================================
// DECK VIEWER
// ================================================================
function openDeckViewer(pile) {
  if (!gameState) return;
  const p = gameState.players.find(x => x.player_id === viewingPlayerId) || gameState.players[0];
  if (!p) return;
  let cards = [], title = '';
  if (pile === 'deck') {
    cards = p.movement_deck_cards || [];
    title = `Movement Deck (${cards.length})`;
  } else {
    cards = p.movement_discard_list || [];
    title = `Discard (${cards.length})`;
  }
  const grid = cards.map(v => {
    const imgVal = Math.min(Math.max(v, 1), 5);
    return `<div class="mv-card mv-card-small"><img class="mv-card-img" src="/games/werblers/images/Movement/Movement Card ${imgVal}.png" alt="${v}"></div>`;
  }).join('') || '<div class="dv-empty">Empty</div>';
  document.getElementById('deck-viewer-title').textContent = title;
  document.getElementById('deck-viewer-grid').innerHTML = grid;
  document.getElementById('deck-viewer-modal').classList.remove('hidden');
}
function closeDeckViewer() { document.getElementById('deck-viewer-modal').classList.add('hidden'); }

// ================================================================
// BATTLE SYSTEM
// ================================================================
function showPreFightScene(combat, state) {
  _pendingCombatInfo = combat;

  // Check for bystander queue first
  if (combat.nearby_queue && combat.nearby_queue.length > 0) {
    _showBystander(combat, state);
    return;
  }

  // Cinematic intro inside battle-overlay
  const overlay = document.getElementById('battle-overlay');
  const p = state.players.find(x => x.player_id === combat.player_id) || state.players.find(x => x.is_current) || state.players[0];
  const bg = combat.background ? `/games/werblers/images/${combat.background}` : '';
  const heroImg = combat.hero_card_image ? `/games/werblers/images/${combat.hero_card_image}` : (p && p.hero_card_image ? `/games/werblers/images/${p.hero_card_image}` : '');
  const playerName = combat.player_name || (p ? p.name : '');
  const monsterImg = combat.card_image ? `/games/werblers/images/${combat.card_image}` : '';

  // Use hero general animation if available
  const heroAnims = combat.hero_animations || (p && heroAnimMap[p.hero_id]) || {};
  const generalAnimSrc = heroAnims.general ? `/games/werblers/videos/${heroAnims.general}` : '';
  const heroVisual = generalAnimSrc
    ? `<video class="fight-intro-card" src="${generalAnimSrc}" autoplay muted playsinline loop style="border-radius:10px"></video>`
    : (heroImg ? `<img class="fight-intro-card" src="${heroImg}" alt="${playerName}">` : '');

  overlay.innerHTML = `
    <div class="battle-bg" style="background-image:url('${bg}')"></div>
    <div class="fight-intro-content">
      <div class="fight-intro-hero fight-intro-offscreen-left">
        <div class="fight-intro-name">${playerName}</div>
        ${heroVisual}
      </div>
      <div class="fight-intro-vs fight-intro-offscreen-top">VS</div>
      <div class="fight-intro-monster fight-intro-offscreen-right">
        <div class="fight-intro-name">${combat.monster_name || 'Monster'}</div>
        ${monsterImg ? `<img class="fight-intro-card" src="${monsterImg}" alt="${combat.monster_name}">` : ''}
      </div>
      <div class="fight-intro-continue">
        <button class="btn-primary" id="fight-intro-btn">Continue</button>
      </div>
    </div>`;
  overlay.classList.remove('hidden');

  const heroEl = overlay.querySelector('.fight-intro-hero');
  const vsEl = overlay.querySelector('.fight-intro-vs');
  const monsterEl = overlay.querySelector('.fight-intro-monster');

  // Beat 1: Hero slides in from left
  requestAnimationFrame(() => {
    heroEl.classList.remove('fight-intro-offscreen-left');
    heroEl.classList.add('fight-intro-animate-in');
  });
  // Beat 2: VS appears
  setTimeout(() => {
    vsEl.classList.remove('fight-intro-offscreen-top');
    vsEl.classList.add('fight-intro-animate-in');
  }, 800);
  // Beat 3: Monster slides in from right
  setTimeout(() => {
    monsterEl.classList.remove('fight-intro-offscreen-right');
    monsterEl.classList.add('fight-intro-animate-in');
  }, 1600);

  document.getElementById('fight-intro-btn').addEventListener('click', () => {
    _renderPreFight(combat, state);
  });
}

function _showBystander(combat, state) {
  const by = combat.nearby_queue[0];
  const overlay = document.getElementById('battle-overlay');
  const bg = combat.background ? `/games/werblers/images/${combat.background}` : '';
  const tokenImg = by.token_image ? `/games/werblers/images/${by.token_image}` : '';

  let consumableHtml = '';
  if (by.consumables && by.consumables.length > 0) {
    consumableHtml = by.consumables.map((c, i) => {
      const img = c.card_image ? `<img class="prefight-consumable-img" src="/games/werblers/images/${c.card_image}" onclick="openCardZoom('/games/werblers/images/${c.card_image}')">` : '';
      return `<div class="prefight-consumable">${img}<div class="prefight-consumable-info"><div class="prefight-consumable-name">${c.name}</div>
        ${c.strength_bonus ? `<div class="prefight-consumable-bonus">+${c.strength_bonus} Str</div>` : ''}
      </div><button class="btn-use-consumable" onclick="useBystander(${by.player_id},${i})">Use</button></div>`;
    }).join('');
  } else {
    consumableHtml = '<div class="prefight-no-consumables">No usable consumables</div>';
  }

  overlay.innerHTML = `
    <div class="battle-bg" style="background-image:url('${bg}')"></div>
    <div class="battle-content">
      <div class="battle-title">Nearby Ally</div>
      <div class="bystander-banner">
        ${tokenImg ? `<img class="bystander-token" src="${tokenImg}">` : ''}
        <div class="bystander-info"><div class="bystander-name">${by.hero_name || by.name}</div>
        <div class="bystander-subtitle">is nearby and can help!</div></div>
      </div>
      <div class="prefight-consumables-section">
        <div class="prefight-consumables-title">Combat Consumables</div>
        <div class="prefight-consumables-list">${consumableHtml}</div>
      </div>
      <div class="battle-actions">
        <button class="btn-secondary" onclick="skipBystander()">Skip</button>
      </div>
    </div>`;
  overlay.classList.remove('hidden');
}

async function useBystander(pid, idx) {
  const resp = await fetch('/games/werblers/api/bystander_consumable', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({player_id: pid, consumable_index: idx}),
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; }
  if (data.combat_info) _pendingCombatInfo = data.combat_info;
  // Check for more bystanders
  if (data.combat_info?.nearby_queue?.length > 0) {
    _showBystander(data.combat_info, data.state);
  } else {
    _renderPreFight(data.combat_info || _pendingCombatInfo, data.state);
  }
}

async function skipBystander() {
  const combat = _pendingCombatInfo;
  if (!combat?.nearby_queue?.length) {
    _renderPreFight(combat, gameState);
    return;
  }
  const by = combat.nearby_queue[0];
  // Notify server so the queue stays in sync
  const resp = await fetch('/games/werblers/api/bystander_consumable', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({player_id: by.player_id, skip: true}),
  });
  const data = await resp.json();
  if (data.state) { gameState = data.state; }
  if (data.combat_info) _pendingCombatInfo = data.combat_info;
  const updatedCombat = data.combat_info || _pendingCombatInfo;
  if (updatedCombat?.nearby_queue?.length > 0) {
    _showBystander(updatedCombat, gameState);
  } else {
    _renderPreFight(updatedCombat, gameState);
  }
}

function _renderPreFight(combat, state) {
  const isNewEncounter = !_pendingCombatInfo || _pendingCombatInfo.monster_name !== combat.monster_name;
  if (isNewEncounter) _crossroadsSelectedSources = [];
  _pendingCombatInfo = combat;
  const overlay = document.getElementById('battle-overlay');
  const p = state.players.find(x => x.player_id === combat.player_id) || state.players.find(x => x.is_current) || state.players[0];
  const bg = combat.background ? `/games/werblers/images/${combat.background}` : '';
  const heroImg = combat.hero_card_image ? `/games/werblers/images/${combat.hero_card_image}` : (p && p.hero_card_image ? `/games/werblers/images/${p.hero_card_image}` : '');
  const monsterCard = combat.card_image ? `/games/werblers/images/${combat.card_image}` : '';
  const pStr = Math.max(0, combat.player_strength || 0);
  const mStr = combat.monster_strength || 0;
  const pName = combat.player_name || 'Hero';
  const mName = combat.monster_name || 'Monster';
  const catTitle = combat.category === 'werbler' ? 'THE WERBLER' : combat.category === 'miniboss' ? 'MINIBOSS ENCOUNTER' : 'MONSTER ENCOUNTER';

  // Gear section
  const gearHtml = _buildBattleGearSection(combat);

  // Boss description
  const bossDesc = combat.description || combat.boss_description || '';
  const bossDescHtml = bossDesc ? `<div class="battle-boss-desc">${bossDesc}</div>` : '';

  // Pre-fight consumables
  let consumHtml = '';
  const consumables = combat.player_consumables || [];
  const combatConsumables = consumables.filter(c => c.use_context === 'combat' || c.use_context === 'both' || c.strength_bonus > 0 || c.effect_id === 'monster_str_mod' || c.effect_id === 'capture_monster');
  if (combatConsumables.length > 0) {
    consumHtml = `<div class="prefight-consumables-section"><div class="prefight-consumables-title">Combat Consumables</div>
      <div class="prefight-consumables-list">${combatConsumables.map((c, i) => {
        const img = c.card_image ? `<img class="prefight-consumable-img" src="/games/werblers/images/${c.card_image}" onclick="openCardZoom('/games/werblers/images/${c.card_image}')">` : '';
        let bonusText = '';
        if (c.strength_bonus > 0) bonusText = `+${c.strength_bonus} STR`;
        else if (c.effect_id === 'monster_str_mod') bonusText = c.effect_value > 0 ? `+${c.effect_value} Monster STR` : `${c.effect_value} Monster STR`;
        else if (c.effect_id === 'capture_monster') bonusText = `Captures Monster`;
        return `<div class="prefight-consumable">${img}<div class="prefight-consumable-info"><div class="prefight-consumable-name">${c.name}</div>
          ${bonusText ? `<div class="prefight-consumable-bonus">${bonusText}</div>` : ''}</div>
          <button class="btn-use-consumable" onclick="usePreFightConsumable(${c._original_index !== undefined ? c._original_index : i})">Use</button></div>`;
      }).join('')}</div></div>`;
  }

  // Flee options
  let fleeHtml = '';
  const canFleeCat = combat.category === 'monster' || combat.category === 'miniboss';
  const isBillfold = canFleeCat && combat.hero_id === 'BILLFOLD';
  const hasSwiftness = canFleeCat && combat.has_swiftness;
  if (isBillfold) {
    const tokenImg = p && p.token_image ? `<img class="flee-token-img" src="/games/werblers/images/${p.token_image}">` : '';
    fleeHtml = `<div class="billfold-flee-box" onclick="flee()">${tokenImg}<span class="btn-flee">Flee back 13</span></div>`;
  } else if (hasSwiftness) {
    fleeHtml = `<button class="btn-flee-swiftness" onclick="swiftnessFlee()">Flee (Swiftness)</button>`;
  }

  // Crossroads Demon Ã¢â‚¬â€ Fair Exchange section
  let crossroadsHtml = '';
  if (combat.effect_id === 'crossroads_demon') {
    const allEquipped = [];
    if (p) {
      (p.helmets || []).forEach((item, i) => allEquipped.push({item, source: 'equip_helmet', index: i}));
      (p.chest_armor || []).forEach((item, i) => allEquipped.push({item, source: 'equip_chest', index: i}));
      (p.leg_armor || []).forEach((item, i) => allEquipped.push({item, source: 'equip_leg', index: i}));
      (p.weapons || []).forEach((item, i) => allEquipped.push({item, source: 'equip_weapon', index: i}));
    }
    const alreadyDiscarded = combat.crossroads_discards_count || 0;
    if (allEquipped.length > 0) {
      const itemsHtml = allEquipped.map(({item, source, index}) => {
        const selKey = `${source}:${index}`;
        const isSelected = _crossroadsSelectedSources.some(s => s.source === source && s.index === index);
        const img = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
        const thumb = img ? `<img class="prefight-consumable-img" src="${img}" style="width:36px;height:auto" onclick="openCardZoom('${_esc(img)}')">` : '';
        return `<div class="prefight-consumable crossroads-item${isSelected ? ' crossroads-selected' : ''}" id="cditem-${source}-${index}" onclick="toggleCrossroadsItem('${source}',${index})">
          ${thumb}<div class="prefight-consumable-info"><div class="prefight-consumable-name">${item.name}</div>
          <div class="prefight-consumable-bonus" style="color:var(--text-dim);font-size:10px">${source.replace('equip_','').replace('_',' ')}</div></div>
          <span class="crossroads-check">${isSelected ? 'Ã¢Å“â€' : 'Ã¢â€”â€¹'}</span></div>`;
      }).join('');
      const selectedCount = _crossroadsSelectedSources.length;
      const confirmDisabled = selectedCount === 0 ? 'disabled' : '';
      crossroadsHtml = `<div class="prefight-consumables-section">
        <div class="prefight-consumables-title" style="color:#e8c55a">Ã¢Å¡Â¡ Fair Exchange</div>
        <div style="font-size:11px;color:var(--text-dim);margin-bottom:6px">Select equipment to offer. On a win, draw 1 higher-tier item per piece offered.</div>
        ${alreadyDiscarded > 0 ? `<div style="font-size:11px;color:#e8c55a;margin-bottom:4px">${alreadyDiscarded} item(s) already offered.</div>` : ''}
        <div class="prefight-consumables-list">${itemsHtml}</div>
        <button class="btn-secondary" style="margin-top:6px;width:100%" ${confirmDisabled} onclick="_performCrossroadsDiscard()">
          Offer ${selectedCount > 0 ? selectedCount : ''} Item${selectedCount !== 1 ? 's' : ''}
        </button>
      </div>`;
    }
  }

  // Monster reroll
  let rerollHtml = '';
  if (combat.can_reroll_monster || combat.ill_come_in_again_available) {
    rerollHtml = `<button class="btn-secondary" onclick="rerollMonster()">Reroll Monster</button>`;
  }

  overlay.innerHTML = `
    <div class="battle-bg" style="background-image:url('${bg}')"></div>
    <div class="battle-content">
      <div class="battle-title">${catTitle}</div>
      ${bossDescHtml}
      <div class="battle-arena">
        <div class="battle-side">
          ${heroImg ? `<img class="battle-card-img" src="${heroImg}" onclick="openCardZoom('${heroImg}')" alt="${pName}">` : ''}
          <div class="battle-name">${pName}</div>
          <div class="battle-str">STR ${pStr} <span class="str-info-btn" onclick="showStrBreakdownBattle('player')">&#9432;</span></div>
        </div>
        <div class="battle-vs">VS</div>
        <div class="battle-side">
          ${monsterCard ? `<img class="battle-card-img" src="${monsterCard}" onclick="openCardZoom('${monsterCard}')" alt="${mName}">` : ''}
          <div class="battle-name">${mName}</div>
          <div class="battle-str">STR ${mStr} <span class="str-info-btn" onclick="showStrBreakdownBattle('monster')">&#9432;</span></div>
        </div>
      </div>
      ${gearHtml}
      ${consumHtml}
      ${crossroadsHtml}
      <div class="battle-actions">
        <button class="btn-primary btn-fight" onclick="doFight()">Fight!</button>
        ${fleeHtml}
        ${rerollHtml}
      </div>
    </div>`;
  overlay.classList.remove('hidden');
}

function toggleCrossroadsItem(source, index) {
  const existing = _crossroadsSelectedSources.findIndex(s => s.source === source && s.index === index);
  if (existing >= 0) {
    _crossroadsSelectedSources.splice(existing, 1);
  } else {
    _crossroadsSelectedSources.push({source, index});
  }
  // Re-render to update selection state
  _renderPreFight(_pendingCombatInfo, gameState);
}

async function _performCrossroadsDiscard() {
  if (_crossroadsSelectedSources.length === 0) return;
  const resp = await fetch('/games/werblers/api/crossroads_discard', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({equip_sources: _crossroadsSelectedSources})
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  _crossroadsSelectedSources = [];
  if (data.state) gameState = data.state;
  if (data.combat_info) {
    _renderPreFight(data.combat_info, gameState);
  }
}

async function doFight() {
  const resp = await fetch('/games/werblers/api/fight', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; }
  showBattleScene(data);
}

function showBattleScene(data) {
  const combat = data.combat_info || _pendingCombatInfo || {};
  _pendingCombatInfo = combat;
  const overlay = document.getElementById('battle-overlay');
  const p = gameState?.players?.find(x => x.player_id === combat.player_id) || gameState?.players?.find(x => x.is_current) || gameState?.players?.[0];
  const bg = combat.background ? `/games/werblers/images/${combat.background}` : '';
  const heroImg = combat.hero_card_image ? `/games/werblers/images/${combat.hero_card_image}` : (p && p.hero_card_image ? `/games/werblers/images/${p.hero_card_image}` : '');
  const monsterCard = combat.card_image ? `/games/werblers/images/${combat.card_image}` : '';
  const won = data.result === 'win' || combat.result === 'WIN';
  const lost = data.result === 'lose' || combat.result === 'LOSE';
  const resultText = won ? 'VICTORY!' : lost ? 'DEFEAT' : 'TIE';
  const resultClass = won ? 'won' : lost ? 'lost' : '';
  const pName = combat.player_name || (p ? p.name : 'Hero');
  const mName = combat.monster_name || 'Monster';
  const catLabel = combat.category === 'werbler' ? 'THE WERBLER' : combat.category === 'miniboss' ? 'MINIBOSS' : 'MONSTER';

  overlay.innerHTML = `
    <div class="battle-bg" style="background-image:url('${bg}')"></div>
    <div class="battle-content">
      <div class="battle-title">${catLabel} ENCOUNTER</div>
      <div class="battle-result ${resultClass}">${resultText}</div>
      <div class="battle-arena">
        <div class="battle-side">
          ${heroImg ? `<img class="battle-card-img" src="${heroImg}" onclick="openCardZoom('${heroImg}')">` : ''}
          <div class="battle-name">${pName}</div>
          <div class="battle-str">STR ${Math.max(0, combat.player_strength || 0)}</div>
        </div>
        <div class="battle-vs">VS</div>
        <div class="battle-side">
          ${monsterCard ? `<img class="battle-card-img" src="${monsterCard}" onclick="openCardZoom('${monsterCard}')">` : ''}
          <div class="battle-name">${mName}</div>
          <div class="battle-str">STR ${combat.monster_strength || '?'}</div>
        </div>
      </div>
      <button class="btn-primary" onclick="closeBattleScene()">Continue</button>
    </div>`;
  overlay.classList.remove('hidden');

  // Store gains and combat result for the gain/animation screen
  _lastBattleResult = { won, lost, combat };
  if (data.gains && data.gains.length > 0) {
    _pendingGains = data.gains;
    _pendingGainState = data.state;
  } else {
    _pendingGains = null;
  }

  // Store trait/curse from combat_info for gain modal
  if (combat.trait_gained || combat.curse_gained) {
    _pendingCombatGains = combat;
  } else {
    _pendingCombatGains = null;
  }

  // Eight lives
  if (data.can_use_eight_lives) {
    _showEightLivesPrompt(data);
  }
}

let _pendingGains = null;
let _pendingGainState = null;
let _lastBattleResult = null;
let _pendingCombatGains = null;

function closeBattleScene() {
  // Check if we have an animation to show (victory/defeat hero animation fullscreen)
  const combat = _pendingCombatInfo || {};
  const br = _lastBattleResult || {};
  const hasGains = (_pendingGains && _pendingGains.length > 0) || _pendingCombatGains;
  // Use the player who fought (combat.player_id) not the current player (turn may have advanced)
  const p = (combat.player_id !== undefined
    ? gameState?.players?.find(x => x.player_id === combat.player_id)
    : null) || gameState?.players?.find(x => x.is_current) || gameState?.players?.[0];
  const heroId = p?.hero_id;
  const animType = br.won ? 'victory' : br.lost ? 'defeat' : null;
  const animSrc = animType && heroId && heroAnimMap[heroId]?.[animType] ? `/games/werblers/videos/${heroAnimMap[heroId][animType]}` : '';

  if (animSrc && hasGains) {
    // Show animation screen first, then gains
    _showBattleAnimationScreen(animSrc, br.won, combat, () => {
      _showGainsScreen();
    });
  } else if (animSrc) {
    // Just animation, no gains
    _showBattleAnimationScreen(animSrc, br.won, combat, () => {
      _finishBattle();
    });
  } else if (hasGains) {
    // No animation, just gains
    _showGainsScreen();
  } else {
    _finishBattle();
  }
}

let _battleAnimContinueCallback = null;

function _showBattleAnimationScreen(animSrc, won, combat, onContinue) {
  _battleAnimContinueCallback = onContinue;
  const overlay = document.getElementById('battle-overlay');
  const bg = combat.background ? `/games/werblers/images/${combat.background}` : '';
  const resultText = won ? 'VICTORY!' : 'DEFEAT';
  const resultClass = won ? 'won' : 'lost';

  overlay.innerHTML = `
    <div class="battle-bg" style="background-image:url('${bg}');filter:brightness(0.4)"></div>
    <div class="battle-content" style="justify-content:center">
      <div class="battle-result ${resultClass}" style="font-size:28px;margin-bottom:12px">${resultText}</div>
      <video autoplay muted playsinline loop style="max-width:320px;width:80%;border-radius:12px;box-shadow:0 0 30px rgba(0,0,0,0.8)" src="${animSrc}"></video>
      <button class="btn-primary" style="margin-top:20px" id="battle-anim-continue-btn">Continue</button>
    </div>`;
  overlay.classList.remove('hidden');
  document.getElementById('battle-anim-continue-btn').addEventListener('click', function() {
    this.disabled = true;
    if (_battleAnimContinueCallback) { _battleAnimContinueCallback(); _battleAnimContinueCallback = null; }
  });
}

function _showGainsScreen() {
  const overlay = document.getElementById('battle-overlay');
  const combat = _pendingCombatInfo || {};
  const bg = combat.background ? `/games/werblers/images/${combat.background}` : '';
  const monsterCard = combat.card_image ? `/games/werblers/images/${combat.card_image}` : '';

  let gainsHtml = '';

  // Monster card header (shown when gain is from a combat monster)
  if (monsterCard && (_pendingCombatGains?.trait_gained || _pendingCombatGains?.curse_gained)) {
    gainsHtml += `<img src="${monsterCard}" onclick="openCardZoom('${monsterCard}')" style="max-width:130px;border-radius:8px;box-shadow:0 2px 14px rgba(0,0,0,0.6);margin-bottom:10px" onerror="this.style.display='none'">`;
  }

  // From combat_info trait/curse
  if (_pendingCombatGains) {
    const cg = _pendingCombatGains;
    const pState = gameState?.players?.find(x => x.is_current);
    if (cg.trait_gained) {
      const matching = (pState?.traits || []).find(t => t.name === cg.trait_gained);
      const tok = matching?.tokens || 0;
      const tokHtml = tok > 0 ? `<div style="margin-top:4px"><img src="/games/werblers/images/Assorted UI Images/+1 Token.png" style="height:16px;vertical-align:middle" onerror="this.style.display='none'"> Ãƒâ€”${tok} Strength Token${tok > 1 ? 's' : ''}</div>` : '';
      gainsHtml += `<div class="gain-modal-item is-trait"><div class="gain-modal-type">Trait Gained</div>
        <div class="gain-modal-name">${cg.trait_gained}</div>
        ${cg.trait_gained_desc ? `<div class="gain-modal-desc">${cg.trait_gained_desc}</div>` : ''}${tokHtml}</div>`;
    }
    if (cg.curse_gained) {
      gainsHtml += `<div class="gain-modal-item is-curse"><div class="gain-modal-type">Curse Gained</div>
        <div class="gain-modal-name">${cg.curse_gained}</div>
        ${cg.curse_gained_desc ? `<div class="gain-modal-desc">${cg.curse_gained_desc}</div>` : ''}</div>`;
    }
  }

  // Check log for curse-block messages (Immunized, Vaxxed, etc.)
  if (gameState?.log) {
    const blockPatterns = [
      /Immunized:\s*(.+?)\s*negated/i,
      /Phallic Dexterity:\s*(.+?)\s*blocked/i,
      /Rust Immunity:\s*(.+?)\s*blocked/i,
      /Vaxxed!?:\s*(.+?)\s*blocked/i,
    ];
    for (const entry of gameState.log) {
      for (const pat of blockPatterns) {
        const m = entry.match(pat);
        if (m) {
          gainsHtml += `<div class="gain-modal-item is-trait" style="border-color:var(--gold)"><div class="gain-modal-type" style="color:var(--gold)">Curse Blocked!</div>
            <div class="gain-modal-desc">${entry.trim()}</div></div>`;
        }
      }
    }
  }

  // From gains array
  if (_pendingGains) {
    const pState = gameState?.players?.find(x => x.is_current);
    for (const g of _pendingGains) {
      if (g.type === 'trait') {
        const matching = (pState?.traits || []).find(t => t.name === g.name);
        const tok = matching?.tokens || 0;
        const tokHtml = tok > 0 ? `<div style="margin-top:4px"><img src="/games/werblers/images/Assorted UI Images/+1 Token.png" style="height:16px;vertical-align:middle" onerror="this.style.display='none'"> Ãƒâ€”${tok} Strength Token${tok > 1 ? 's' : ''}</div>` : '';
        gainsHtml += `<div class="gain-modal-item is-trait"><div class="gain-modal-type">Trait Gained</div>
          <div class="gain-modal-name">${g.name}</div><div class="gain-modal-desc">${g.description || ''}</div>${tokHtml}</div>`;
      } else if (g.type === 'curse') {
        gainsHtml += `<div class="gain-modal-item is-curse"><div class="gain-modal-type">Curse!</div>
          <div class="gain-modal-name">${g.name}</div><div class="gain-modal-desc">${g.description || ''}</div></div>`;
      } else if (g.type === 'item') {
        const img = g.card_image ? `<div style="margin:8px 0"><img src="/games/werblers/images/${g.card_image}" onclick="openCardZoom('/games/werblers/images/${g.card_image}')" style="max-width:120px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.5)"></div>` : '';
        gainsHtml += `<div class="gain-modal-item is-trait"><div class="gain-modal-type">Item Won</div>
          <div class="gain-modal-name">${g.name}</div>${img}</div>`;
      }
    }
  }

  if (!gainsHtml) {
    _finishBattle();
    return;
  }

  overlay.innerHTML = `
    <div class="battle-bg" style="background-image:url('${bg}');filter:brightness(0.3)"></div>
    <div class="battle-content" style="justify-content:center">
      ${gainsHtml}
      <button class="btn-primary" style="margin-top:16px" onclick="closeGainModal()">Continue</button>
    </div>`;
  overlay.classList.remove('hidden');
}

function showGainModal(gains, state) {
  // Redirect to the new gains screen flow
  _pendingGains = gains;
  _pendingGainState = state;
  _showGainsScreen();
}

async function closeGainModal() {
  _pendingGains = null;
  _pendingCombatGains = null;
  _lastBattleResult = null;
  await _finishBattle();
}

async function _finishBattle() {
  document.getElementById('battle-overlay').classList.add('hidden');
  document.getElementById('gain-modal').classList.add('hidden');
  _resumeTierMusic();
  _pendingGains = null;
  _pendingCombatGains = null;
  _lastBattleResult = null;
  _pendingCombatInfo = null;
  if (gameState) {
    viewingPlayerId = gameState.current_player_id;
    applyState(gameState);
  }

  // Handle pending trait items (e.g. Ball and Chain equip after defeating Wrecking Ball)
  await _placePendingTraitItems();
  // Handle pending trait minions (when at minion cap)
  await _placePendingTraitMinions();

  // Check for post-combat offers
  if (gameState?.phase === 'offer_chest' && gameState.offer) {
    _pendingOfferData = gameState.offer;
    playMusic('Chest Music.wav');
    showChestModal(gameState.offer, {});
  } else if (gameState?.phase === 'offer_shop' && gameState.offer) {
    _pendingOfferData = gameState.offer;
    playMusic('Shop Music.wav');
    showShopModal(gameState.offer, {});
  } else {
    loadAndRenderAbilities();
  }
}

async function _placePendingTraitItems() {
  if (!gameState) return;
  const p = gameState.players.find(x => x.is_current);
  if (!p || !p.pending_trait_items || !p.pending_trait_items.length) return;
  for (let i = 0; i < p.pending_trait_items.length; i++) {
    const item = p.pending_trait_items[i];
    // Show "Received!" popup
    await new Promise(resolve => {
      const img = item.card_image ? `<img src="/games/werblers/images/${item.card_image}" style="max-width:130px;border-radius:8px;box-shadow:0 2px 14px rgba(0,0,0,0.6);margin:8px 0" onclick="openCardZoom('/games/werblers/images/${item.card_image}')" onerror="this.style.display='none'">` : '';
      const strSign = item.strength_bonus >= 0 ? '+' : '';
      const strText = item.strength_bonus !== 0 ? `<div style="color:var(--gold);font-size:14px;margin-top:4px">${strSign}${item.strength_bonus} Str (${item.slot || 'equip'})</div>` : '';
      const overlay = document.getElementById('battle-overlay');
      overlay.innerHTML = `<div class="battle-content" style="justify-content:center;text-align:center">
        <div style="font-family:'Cinzel',serif;font-size:20px;color:var(--gold);margin-bottom:8px">Received!</div>
        ${img}
        <div style="font-size:16px;margin:4px 0;color:var(--text)">${item.name}</div>
        ${strText}
        <button class="btn-primary" style="margin-top:16px" id="_pti-continue-btn">Place Item</button>
      </div>`;
      overlay.classList.remove('hidden');
      document.getElementById('_pti-continue-btn').addEventListener('click', function() {
        overlay.classList.add('hidden');
        resolve();
      });
    });
    // Open placement screen
    await new Promise(resolve => {
      showInventoryPopup(item, async (choices) => {
        const body = { placement_choices: choices };
        const resp = await fetch('/games/werblers/api/place_trait_item', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await resp.json();
        if (data.state) { gameState = data.state; applyState(data.state); }
        resolve();
      });
    });
  }
}

async function _placePendingTraitMinions() {
  if (!gameState) return;
  const p = gameState.players.find(x => x.is_current);
  if (!p || !p.pending_trait_minions || !p.pending_trait_minions.length) return;
  await new Promise(resolve => {
    function checkDone() {
      const latest = gameState.players.find(x => x.is_current);
      if (!latest || !latest.pending_trait_minions || latest.pending_trait_minions.length === 0) {
        resolve();
      }
    }
    _showMinionReplacementModal(p, checkDone);
  });
}

let _minionReplaceDone = null;

function _showMinionReplacementModal(player, onDone) {
  if (onDone) _minionReplaceDone = onDone;
  const pending = player.pending_trait_minions[0];
  const overlay = document.getElementById('battle-overlay');
  const currentMinions = player.minions || [];
  const slots = currentMinions.map((m, i) => {
    const img = m.card_image ? `<img src="/games/werblers/images/${m.card_image}" style="width:80px;height:auto;border-radius:6px;margin-bottom:4px" onerror="this.style.display='none'">` : '';
    return `<div class="ps-slot ps-slot-card ps-slot-filled" onclick="_resolveMinion(${i})" style="cursor:pointer">
      ${img}<div class="ps-slot-label">${m.name}</div><div style="font-size:12px;color:var(--text-dim)">+${m.strength_bonus} Str</div>
    </div>`;
  }).join('');

  const pendingImg = pending.card_image ? `<img src="/games/werblers/images/${pending.card_image}" style="width:120px;height:auto;border-radius:8px;margin:8px auto;display:block" onerror="this.style.display='none'">` : '';

  overlay.innerHTML = `<div class="battle-content" style="justify-content:center;text-align:center">
    <div style="font-family:'Cinzel',serif;font-size:18px;color:var(--gold);margin-bottom:6px">Minion Slots Full!</div>
    <div style="font-size:14px;color:var(--text);margin-bottom:8px">${pending.name} (+${pending.strength_bonus} Str) wants to join.</div>
    ${pendingImg}
    <div style="font-size:14px;color:var(--text-dim);margin:8px 0">Choose a minion to replace:</div>
    <div class="ps-pack-grid">${slots}</div>
    <button class="btn-secondary" onclick="_resolveMinion(-1)" style="margin-top:10px">Discard ${pending.name}</button>
  </div>`;
  overlay.classList.remove('hidden');
}

async function _resolveMinion(replaceIndex) {
  try {
    const body = replaceIndex < 0 ? {discard: true} : {replace_index: replaceIndex};
    const resp = await fetch('/games/werblers/api/resolve_minion', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (data.state) { gameState = data.state; applyState(data.state); }
    const player = data.state?.players?.find(p => p.is_current);
    if (player && player.pending_trait_minions && player.pending_trait_minions.length > 0) {
      _showMinionReplacementModal(player);
    } else {
      document.getElementById('battle-overlay').classList.add('hidden');
      if (_minionReplaceDone) { const cb = _minionReplaceDone; _minionReplaceDone = null; cb(); }
    }
  } catch (err) {
    console.error('resolveMinion error:', err);
  }
}

async function flee() {
  const resp = await fetch('/games/werblers/api/flee', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; applyState(data.state); }
  document.getElementById('battle-overlay').classList.add('hidden');
  _resumeTierMusic();
  await loadAndRenderAbilities();
}

async function swiftnessFlee() {
  const resp = await fetch('/games/werblers/api/swiftness_flee', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; applyState(data.state); }
  document.getElementById('battle-overlay').classList.add('hidden');
  _resumeTierMusic();
  await loadAndRenderAbilities();
}

async function rerollMonster() {
  // This is handled via use_ill_come_in_again endpoint
  const resp = await fetch('/games/werblers/api/use_ill_come_in_again', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; }
  if (data.combat_info) {
    _renderPreFight(data.combat_info, data.state);
  }
}

async function usePreFightConsumable(idx) {
  const resp = await fetch('/games/werblers/api/use_consumable', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({consumable_index: idx, context: 'combat'}),
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; }
  if (data.combat_info) _renderPreFight(data.combat_info, data.state);
}

function _showEightLivesPrompt(data) {
  const overlay = document.getElementById('battle-overlay');
  const existing = overlay.querySelector('.battle-actions');
  if (existing) {
    existing.innerHTML = `<button class="btn-primary" onclick="useEightLives()">Use Eight Lives</button>
      <button class="btn-secondary" onclick="closeBattleScene()">Accept Defeat</button>`;
  }
}

async function useEightLives(curseIndex) {
  curseIndex = curseIndex !== undefined ? curseIndex : 0;
  const resp = await fetch('/games/werblers/api/use_eight_lives', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({curse_index: curseIndex})});
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; applyState(data.state); }
  if (data.combat_info) {
    showBattleScene(data);
  } else {
    await loadAndRenderAbilities();
  }
}

// Battle gear section builder (adapted from desktop)
function _buildBattleGearSection(combat) {
  const gear = combat.player_gear || [];
  const traits = combat.player_traits || [];
  const curses = combat.player_curses || [];
  const minions = combat.player_minions || [];
  if (!gear.length && !traits.length && !curses.length && !minions.length) return '';

  const helmets = gear.filter(i => i.slot === 'helmet');
  const chests = gear.filter(i => i.slot === 'chest');
  const legs = gear.filter(i => i.slot === 'legs');
  const weapons = gear.filter(i => i.slot === 'weapon');
  const helmetSlots = combat.player_helmet_slots || 1;
  const chestSlots = combat.player_chest_slots || 1;
  const legSlots = combat.player_legs_slots || 1;
  const weaponHands = combat.player_weapon_hands || 2;

  function eSlot(item, label) {
    if (item) {
      const img = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
      if (img) return `<div class="battle-equip-slot" onclick="openCardZoom('${_esc(img)}')"><img src="${img}" alt="${item.name}"></div>`;
      return `<div class="battle-equip-slot" style="display:flex;align-items:center;justify-content:center;font-size:7px;text-align:center;padding:2px">${item.name}</div>`;
    }
    return `<div class="battle-equip-slot is-empty"></div>`;
  }

  const handRows = Math.ceil(weaponHands / 2);
  const extraRows = Math.max(chestSlots - 1, handRows - 1);
  const rows = [];

  for (let i = helmetSlots - 1; i >= 1; i--)
    rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell"></div><div class="battle-equip-cell">${eSlot(helmets[i]||null,'Head')}</div><div class="battle-equip-cell"></div></div>`);
  rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell"></div><div class="battle-equip-cell">${eSlot(helmets[0]||null,'Head')}</div><div class="battle-equip-cell"></div></div>`);
  const rw0 = weaponHands >= 1 ? eSlot(weapons[0]||null,'R.Hand') : '';
  const lw0 = weaponHands >= 2 ? eSlot(weapons[1]||null,'L.Hand') : '';
  rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell">${rw0}</div><div class="battle-equip-cell">${eSlot(chests[0]||null,'Chest')}</div><div class="battle-equip-cell">${lw0}</div></div>`);
  for (let i = 0; i < extraRows; i++) {
    const rIdx = (i+1)*2, lIdx = (i+1)*2+1, cIdx = i+1;
    rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell">${rIdx<weaponHands?eSlot(weapons[rIdx]||null,'Hand'):''}</div><div class="battle-equip-cell">${cIdx<chestSlots?eSlot(chests[cIdx]||null,'Chest'):''}</div><div class="battle-equip-cell">${lIdx<weaponHands?eSlot(weapons[lIdx]||null,'Hand'):''}</div></div>`);
  }
  rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell"></div><div class="battle-equip-cell">${eSlot(legs[0]||null,'Feet')}</div><div class="battle-equip-cell"></div></div>`);
  for (let i = 1; i < legSlots; i++)
    rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell"></div><div class="battle-equip-cell">${eSlot(legs[i]||null,'Feet')}</div><div class="battle-equip-cell"></div></div>`);

  let html = `<div class="battle-equip-grid">${rows.join('')}</div>`;

  if (minions.length) {
    html += `<div class="battle-left-section-label" style="margin-top:6px">Minions</div>`;
    for (const m of minions) {
      if (m.card_image) {
        html += `<div class="battle-equip-slot" onclick="openCardZoom('/games/werblers/images/${m.card_image}')" style="width:50px;height:70px;margin:2px auto"><img src="/games/werblers/images/${m.card_image}" alt="${m.name}"></div>`;
      }
    }
  }
  if (traits.length) {
    html += `<div class="battle-left-section-label" style="margin-top:6px">Traits</div>`;
    for (const t of traits) html += `<div class="battle-left-tag is-trait" onclick="showTcTooltip('${_esc(t.name)}','${_esc(t.description||'')}',this)">${t.name}</div>`;
  }
  if (curses.length) {
    html += `<div class="battle-left-section-label" style="margin-top:6px">Curses</div>`;
    for (const c of curses) html += `<div class="battle-left-tag is-curse" onclick="showTcTooltip('${_esc(c.name)}','${_esc(c.description||'')}',this)">${c.name}</div>`;
  }
  return html;
}

function _strBreakdownTitle(combat) {
  const lines = [];
  const base = combat.player_base_strength;
  if (base !== undefined) lines.push(`Base: ${base}`);
  for (const item of (combat.player_gear || [])) {
    const parts = [];
    if (item.strength_bonus) parts.push(item.strength_bonus >= 0 ? `+${item.strength_bonus}` : `${item.strength_bonus}`);
    if (item.tokens) parts.push(`+${item.tokens} ability`);
    if (parts.length) lines.push(`${item.name}: ${parts.join(', ')}`);
  }
  for (const t of (combat.player_traits || [])) { if (t.tokens) lines.push(`${t.name}: +${t.tokens}`); }
  for (const m of (combat.player_minions || [])) lines.push(`${m.name}: +${m.strength_bonus}`);
  for (const c of (combat.player_curses || [])) { if (c.tokens) lines.push(`${c.name}: ${c.tokens >= 0 ? '+' : ''}${c.tokens}`); }
  if (combat.prefight_str_bonus) lines.push(`Consumable: +${combat.prefight_str_bonus}`);
  for (const l of (combat.ability_breakdown || [])) lines.push(l.trim());
  lines.push(`Total: ${Math.max(0, combat.player_strength)}`);
  return lines.join('\n');
}

function _monsterStrBreakdownTitle(combat) {
  const lines = [];
  const abilityMod = combat.ability_monster_mod || 0;
  const niceHat = combat.nice_hat_bonus || 0;
  const maleBon = combat.monster_bonus_vs_male || 0;
  const baseSt = (combat.monster_strength || 0) - abilityMod - niceHat - maleBon;
  lines.push(`Base: ${baseSt}`);
  if (maleBon) lines.push(`+${maleBon} vs Men`);
  for (const l of (combat.ability_breakdown || [])) {
    const t = l.trim();
    if (t) lines.push(t);
  }
  lines.push(`Total: ${combat.monster_strength}`);
  return lines.join('\n');
}

function showStrBreakdownBattle(who) {
  const combat = _pendingCombatInfo;
  if (!combat) return;
  const title = who === 'monster' ? `${combat.monster_name || 'Monster'} Strength` : `${combat.player_name || 'Hero'} Strength`;
  const raw = who === 'monster' ? _monsterStrBreakdownTitle(combat) : _strBreakdownTitle(combat);
  const lines = raw.split('\n').filter(l => l.trim());
  const overlay = document.createElement('div');
  overlay.className = 'action-sheet-overlay';
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  const sheet = document.createElement('div');
  sheet.className = 'action-sheet';
  sheet.innerHTML = `<div style="text-align:center;padding:8px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:16px">${title}</div>` +
    lines.map(l => `<div class="action-sheet-item" style="justify-content:flex-start;font-size:14px;padding:8px 14px;min-height:36px">${l}</div>`).join('') +
    `<div class="action-sheet-cancel" onclick="this.closest('.action-sheet-overlay').remove()">Close</div>`;
  overlay.appendChild(sheet);
  document.body.appendChild(overlay);
}

// ================================================================
// PLAYER SHEET (Full Overlay)
// ================================================================
function openPlayerSheet() {
  const p = gameState?.players?.find(x => x.player_id === viewingPlayerId) || gameState?.players?.[0];
  if (!p) return;
  renderPlayerSheetFull(p, null);
}

function renderPlayerSheetFull(player, placementInfo) {
  const overlay = document.getElementById('player-sheet-overlay');
  const content = document.getElementById('player-sheet-content');
  const isPlacement = !!placementInfo;
  const itemToPlace = placementInfo?.item_to_place || null;
  const validSlots = placementInfo?.valid_slots || [];

  const helmetSlots = player.helmet_slots || 1;
  const chestSlots = player.chest_slots || 1;
  const legSlots = player.legs_slots || 1;
  const weaponHands = player.weapon_hands || 2;
  const hasChestAccess = (player.chest_slots ?? 1) > 0;

  // Slot type Ã¢â€ â€™ manage_item source string mapping
  const _slotSrcMap = {helmet:'equip_helmet', chest:'equip_chest', legs:'equip_leg', weapon:'equip_weapon'};

  function slotHtml(item, label, slotKey, idx) {
    const isTarget = isPlacement && validSlots.includes(slotKey);
    if (item) {
      const img = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
      const bonus = item.strength_bonus >= 0 ? `+${item.strength_bonus}` : `${item.strength_bonus}`;
      const itemSrc = _slotSrcMap[slotKey] || 'equip_helmet';
      const tapAction = isTarget
        ? `onclick="_placeIntoSlot('${slotKey}',${idx})"`
        : `onclick="openCardZoomWithActions('${img ? _esc(img) : ''}',{type:'equip',source:'${itemSrc}',index:${idx},name:'${_esc(item.name)}'})"`;
      if (img) {
        return `<div class="ps-slot ps-slot-card ps-slot-filled ${isTarget ? 'ps-slot-placement-target' : ''}" ${tapAction}>
          <img class="ps-slot-card-img" src="${img}" alt="${item.name}">
          <div class="ps-slot-label">${label}</div></div>`;
      }
      return `<div class="ps-slot ps-slot-filled ${isTarget ? 'ps-slot-placement-target' : ''}" ${tapAction}>
        <div class="ps-slot-label">${label}</div><div class="ps-slot-divider"></div><div class="ps-slot-name">${item.name}</div><div class="ps-slot-sub">${bonus}</div></div>`;
    } else {
      // Empty slot
    }
    if (isTarget) {
      return `<div class="ps-slot ps-slot-empty ps-slot-placement-target" onclick="_placeIntoSlot('${slotKey}',${idx})">
        <div class="ps-slot-label">${label}</div></div>`;
    }
    return `<div class="ps-slot ps-slot-empty"><div class="ps-slot-label">${label}</div></div>`;
  }

  let html = `<div class="ps-header"><div class="ps-title">${player.hero_name || 'Player Sheet'}</div>
    <button class="ps-close" onclick="closePlayerSheet()">Ã¢Å“â€¢</button></div>`;

  // Placement banner
  if (isPlacement && itemToPlace) {
    html += `<div id="ps-placement-banner"><span>Place <strong>${itemToPlace.name}</strong></span>
      <button class="btn-secondary ps-back-btn" onclick="_cancelPlacement()">Back</button>
      <button class="btn-danger ps-discard-btn" onclick="_finishPlacement({discard:true})">Discard</button></div>`;
  }

  // Equipment grid
  html += '<div class="ps-equip-grid">';
  // Helmet rows
  for (let i = helmetSlots - 1; i >= 0; i--) {
    html += `<div class="ps-equip-row"><div class="ps-equip-cell"></div><div class="ps-equip-cell">${slotHtml((player.helmets||[])[i], 'Head', 'helmet', i)}</div><div class="ps-equip-cell"></div></div>`;
  }
  // Chest + weapons row
  const rw = weaponHands >= 1 ? slotHtml((player.weapons||[])[0], 'R.Hand', 'weapon', 0) : '<div class="ps-slot ps-slot-disabled"></div>';
  const lw = weaponHands >= 2 ? slotHtml((player.weapons||[])[1], 'L.Hand', 'weapon', 1) : '';
  const ch = hasChestAccess ? slotHtml((player.chest_armor||[])[0], 'Chest', 'chest', 0) : '<div class="ps-slot ps-slot-disabled"></div>';
  html += `<div class="ps-equip-row"><div class="ps-equip-cell">${rw}</div><div class="ps-equip-cell">${ch}</div><div class="ps-equip-cell">${lw}</div></div>`;
  // Extra chest/weapon rows
  const handRows = Math.ceil(weaponHands / 2);
  const extraRows = Math.max(chestSlots - 1, handRows - 1);
  for (let i = 0; i < extraRows; i++) {
    const rIdx = (i+1)*2, lIdx = (i+1)*2+1, cIdx = i+1;
    html += `<div class="ps-equip-row">
      <div class="ps-equip-cell">${rIdx<weaponHands ? slotHtml((player.weapons||[])[rIdx],'Hand','weapon',rIdx) : ''}</div>
      <div class="ps-equip-cell">${cIdx<chestSlots && hasChestAccess ? slotHtml((player.chest_armor||[])[cIdx],'Chest','chest',cIdx) : ''}</div>
      <div class="ps-equip-cell">${lIdx<weaponHands ? slotHtml((player.weapons||[])[lIdx],'Hand','weapon',lIdx) : ''}</div></div>`;
  }
  // Leg rows
  for (let i = 0; i < legSlots; i++) {
    html += `<div class="ps-equip-row"><div class="ps-equip-cell"></div><div class="ps-equip-cell">${slotHtml((player.leg_armor||[])[i], 'Legs', 'legs', i)}</div><div class="ps-equip-cell"></div></div>`;
  }
  html += '</div>';

  // Pack
  const packItems = player.pack || [];
  const consumables = player.consumables || [];
  const captured = player.captured_monsters || [];
  const allPack = [...packItems, ...consumables, ...captured];
  const packSize = player.pack_size || 5;
  html += `<div class="ps-section-title">Pack (${allPack.length}/${packSize})</div>`;
  html += '<div class="ps-pack-grid">';
  const isPackTarget = isPlacement && validSlots.includes('pack');
  const packIsFull = allPack.length >= packSize;
  // Pack equip items
  for (let i = 0; i < packItems.length; i++) {
    const item = packItems[i];
    const img = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
    const unifiedIdx = i; // pack items start at 0
    let tapAction;
    if (isPackTarget && packIsFull) {
      tapAction = `onclick="_confirmPackReplace(${unifiedIdx},'${_esc(item.name)}')"`;
    } else if (isPlacement) {
      tapAction = '';
    } else {
      tapAction = `onclick="openCardZoomWithActions('${img ? _esc(img) : ''}',{type:'pack',index:${i},name:'${_esc(item.name)}'})"`;
    }
    const replaceClass = (isPackTarget && packIsFull) ? ' ps-slot-placement-target' : '';
    html += `<div class="ps-slot ps-slot-card ps-slot-filled${replaceClass}" ${tapAction}>${img ? `<img class="ps-slot-card-img" src="${img}">` : ''}<div class="ps-slot-label">${item.name}</div></div>`;
  }
  // Consumables
  for (let i = 0; i < consumables.length; i++) {
    const item = consumables[i];
    const img = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
    const unifiedIdx = packItems.length + i;
    let tapAction;
    if (isPackTarget && packIsFull) {
      tapAction = `onclick="_confirmPackReplace(${unifiedIdx},'${_esc(item.name)}')"`;
    } else if (isPlacement) {
      tapAction = '';
    } else {
      tapAction = `onclick="openCardZoomWithActions('${img ? _esc(img) : ''}',{type:'consumable',index:${i},name:'${_esc(item.name)}'})"`;
    }
    const replaceClass = (isPackTarget && packIsFull) ? ' ps-slot-placement-target' : '';
    html += `<div class="ps-slot ps-slot-card ps-slot-filled${replaceClass}" ${tapAction}>${img ? `<img class="ps-slot-card-img" src="${img}">` : ''}<div class="ps-slot-label">${item.name}</div></div>`;
  }
  // Captured monsters
  for (let i = 0; i < captured.length; i++) {
    const item = captured[i];
    const img = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
    const unifiedIdx = packItems.length + consumables.length + i;
    let tapAction;
    if (isPackTarget && packIsFull) {
      tapAction = `onclick="_confirmPackReplace(${unifiedIdx},'${_esc(item.name)}')"`;
    } else if (isPlacement) {
      tapAction = '';
    } else {
      tapAction = `onclick="openCardZoomWithActions('${img ? _esc(img) : ''}',{type:'minion',index:${i},name:'${_esc(item.name)}'})"`;
    }
    const replaceClass = (isPackTarget && packIsFull) ? ' ps-slot-placement-target' : '';
    html += `<div class="ps-slot ps-slot-card ps-slot-filled${replaceClass}" ${tapAction}>${img ? `<img class="ps-slot-card-img" src="${img}">` : ''}<div class="ps-slot-label">${item.name}</div></div>`;
  }
  // When pack has room AND is a target, show an empty clickable slot
  if (isPackTarget && !packIsFull) {
    html += `<div class="ps-slot ps-slot-empty ps-slot-placement-target" onclick="_finishPlacement({placement:'pack'})"><div class="ps-slot-label">Pack</div></div>`;
  }
  // Empty pack slots (non-target)
  const emptyPsSlots = Math.max(0, packSize - allPack.length - (isPackTarget && !packIsFull ? 1 : 0));
  for (let i = 0; i < emptyPsSlots; i++) {
    html += `<div class="ps-slot ps-slot-empty"><div class="ps-slot-label">Empty</div></div>`;
  }
  // Hint label when pack is full and items are replacement targets
  if (isPackTarget && packIsFull) {
    html += `<div style="grid-column:1/-1;text-align:center;color:var(--text-dim);font-size:12px;padding:4px 0">Tap an item to discard it and place here</div>`;
  }
  html += '</div>';

  // Minions
  if ((player.minions || []).length > 0) {
    html += '<div class="ps-section-title">Minions</div><div class="ps-minion-pool">';
    for (let mi = 0; mi < player.minions.length; mi++) {
      const m = player.minions[mi];
      const img = m.card_image ? `/games/werblers/images/${m.card_image}` : '';
      html += `<div class="ps-minion-card" onclick="openCardZoomWithActions('${_esc(img)}',{type:'minion',index:${mi},name:'${_esc(m.name)}'})"><img src="${img}" alt="${m.name}"></div>`;
    }
    html += '</div>';
  }

  // Movement piles
  html += '<div class="ps-section-title">Movement</div><div class="ps-mv-section">';
  html += `<div class="ps-mv-pile" onclick="openDeckViewer('deck')"><div class="ps-mv-pile-label">Deck (${(player.movement_deck_cards||[]).length})</div><img class="ps-mv-pile-img" src="/games/werblers/images/Cards/Movement Card Back.png"></div>`;
  const _discardTop = player.movement_discard_top;
  const _discardImg = _discardTop ? `/games/werblers/images/Movement/Movement Card ${Math.min(Math.max(_discardTop,1),5)}.png` : '/games/werblers/images/Cards/Movement Card Back.png';
  const _discardOpacity = _discardTop ? '1' : '0.5';
  html += `<div class="ps-mv-pile" onclick="openDeckViewer('discard')"><div class="ps-mv-pile-label">Discard (${(player.movement_discard_list||[]).length})</div><img class="ps-mv-pile-img" src="${_discardImg}" style="opacity:${_discardOpacity}"></div>`;
  html += '</div>';

  // Traits & Curses
  const traits = player.traits || [];
  const curses = player.curses || [];
  if (traits.length || curses.length) {
    html += '<div class="ps-tc-area"><div class="ps-tc-row">';
    if (traits.length) {
      html += '<div><div class="ps-tc-label ps-tc-label-trait">Traits</div><div class="ps-tc-stack">';
      for (const t of traits) {
        const residualsBadge = t.effect_id === 'residuals' && t.strength_bonus > 0 ? ` <span class="tc-token-badge" style="font-size:10px;margin-left:4px">+${t.strength_bonus}</span>` : '';
        html += `<div class="ps-tc-card is-trait" onclick="showTcTooltip('${_esc(t.name)}','${_esc(t.description||'')}',this)">${t.name}${residualsBadge}</div>`;
      }
      html += '</div></div>';
    }
    if (curses.length) {
      html += '<div><div class="ps-tc-label ps-tc-label-curse">Curses</div><div class="ps-tc-stack">';
      for (const c of curses) html += `<div class="ps-tc-card is-curse" onclick="showTcTooltip('${_esc(c.name)}','${_esc(c.description||'')}',this)">${c.name}</div>`;
      html += '</div></div>';
    }
    html += '</div></div>';
  }

  // Hero card
  if (player.hero_card_image) {
    html += `<div class="ps-hero-card"><img src="/games/werblers/images/${player.hero_card_image}" onclick="openCardZoom('/games/werblers/images/${player.hero_card_image}')"></div>`;
  }

  content.innerHTML = html;
  overlay.classList.remove('hidden');
}

function closePlayerSheet() {
  // If in placement mode, don't allow closing without resolving
  if (_invPlacementItem) return;
  document.getElementById('player-sheet-overlay').classList.add('hidden');
}

function _placeIntoSlot(slotKey, idx) {
  const p = gameState?.players?.find(pl => pl.is_current);
  // Special case: placing a 2H weapon when weapon slots are actually full
  if (slotKey === 'weapon' && _invPlacementItem && _invPlacementItem.hands === 2) {
    const weaponHands = p?.weapon_hands || 2;
    const handsUsed = (p?.weapons || []).reduce((sum, w) => sum + (w.hands || 1), 0);
    if (handsUsed + 2 > weaponHands && (p?.weapons || []).length >= 2) {
      _handle2HFullEquip(p.weapons[0], p.weapons[1], p);
      return;
    }
  }
  // Check if slot is occupied
  let existingItem = null;
  if (slotKey === 'helmet') existingItem = (p?.helmets || [])[idx];
  else if (slotKey === 'chest') existingItem = (p?.chest_armor || [])[idx];
  else if (slotKey === 'legs') existingItem = (p?.leg_armor || [])[idx];
  else if (slotKey === 'weapon') {
    existingItem = (p?.weapons || [])[idx];
    // If the slot appears empty, check if a 2H weapon at a lower index is virtually occupying it
    if (!existingItem && idx > 0) {
      let handsUsed = 0;
      for (let wi = 0; wi < (p?.weapons || []).length; wi++) {
        const w = p.weapons[wi];
        const wHands = w.hands || 1;
        if (handsUsed + wHands > idx) {
          existingItem = w;
          idx = wi;
          break;
        }
        handsUsed += wHands;
      }
    }
  }

  if (existingItem) {
    _showOccupiedSlotModal(existingItem.name, slotKey, idx);
  } else {
    _finishPlacement({placement: 'equip', equip_action: 'place', equip_item_index: idx});
  }
}

// ================================================================
// OCCUPIED SLOT
// ================================================================
let _occupiedSlotKey = null;
let _occupiedSlotIdx = null;
function _showOccupiedSlotModal(existingName, slotKey, idx) {
  _occupiedSlotKey = slotKey;
  _occupiedSlotIdx = idx;
  const p = gameState?.players?.find(pl => pl.is_current);
  // Get existing item for card image
  let existingItem = null;
  if (slotKey === 'helmet') existingItem = (p?.helmets || [])[idx];
  else if (slotKey === 'chest') existingItem = (p?.chest_armor || [])[idx];
  else if (slotKey === 'legs') existingItem = (p?.leg_armor || [])[idx];
  else if (slotKey === 'weapon') existingItem = (p?.weapons || [])[idx];
  const newItem = _invPlacementItem;

  const overlay = document.createElement('div');
  overlay.className = 'action-sheet-overlay';
  overlay.id = 'occupied-slot-overlay';
  const sheet = document.createElement('div');
  sheet.className = 'action-sheet';

  // Card comparison
  const existImg = existingItem?.card_image ? `<img class="occupied-slot-card-img" src="/games/werblers/images/${existingItem.card_image}" onclick="openCardZoom('/games/werblers/images/${existingItem.card_image}')">` : `<div class="occupied-slot-card-name">${existingName}</div>`;
  const newImg = newItem?.card_image ? `<img class="occupied-slot-card-img" src="/games/werblers/images/${newItem.card_image}" onclick="openCardZoom('/games/werblers/images/${newItem.card_image}')">` : (newItem ? `<div class="occupied-slot-card-name">${newItem.name}</div>` : '');
  const packFree = p ? (p.pack_slots_free ?? (p.pack_size || 5) - ((p.pack||[]).length + (p.consumables||[]).length + (p.captured_monsters||[]).length)) : 0;

  sheet.innerHTML = `<div style="text-align:center;padding:8px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:16px">Replace Item?</div>
    <div class="occupied-slot-cards">
      <div class="occupied-slot-card-wrap"><div class="occupied-slot-card-label">Current</div>${existImg}</div>
      <div class="occupied-slot-arrow">&rarr;</div>
      <div class="occupied-slot-card-wrap"><div class="occupied-slot-card-label">New</div>${newImg}</div>
    </div>
    <div class="action-sheet-item" id="occ-to-pack">Move "${existingName}" to Pack${packFree <= 0 ? ' (full)' : ''}</div>
    <div class="action-sheet-item danger" id="occ-discard">Discard "${existingName}"</div>
    <div class="action-sheet-cancel" id="occ-cancel">Cancel</div>`;

  sheet.querySelector('#occ-to-pack').onclick = () => { overlay.remove(); _occupiedSlotAction('to_pack'); };
  sheet.querySelector('#occ-discard').onclick = () => { overlay.remove(); _occupiedSlotAction('discard'); };
  sheet.querySelector('#occ-cancel').onclick = () => overlay.remove();
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  overlay.appendChild(sheet);
  document.body.appendChild(overlay);
}

function _occupiedSlotAction(action) {
  // Remove overlay if it still exists
  const existingOverlay = document.getElementById('occupied-slot-overlay');
  if (existingOverlay) existingOverlay.remove();
  document.getElementById('occupied-slot-modal').classList.add('hidden');
  if (action === 'discard') {
    _finishPlacement({placement: 'equip', equip_action: 'discard', equip_item_index: _occupiedSlotIdx});
  } else if (action === 'to_pack') {
    const p = gameState?.players?.find(pl => pl.is_current);
    if (p && p.pack_slots_free <= 0) {
      _showPlacementPackDiscardChoice(_occupiedSlotIdx);
    } else {
      _finishPlacement({placement: 'equip', equip_action: 'swap', equip_item_index: _occupiedSlotIdx});
    }
  }
}

function _showPlacementPackDiscardChoice(equipItemIdx) {
  const p = gameState?.players?.find(pl => pl.is_current);
  if (!p) return;
  const packItems = [
    ...(p.pack || []).map((item, i) => ({name: item.name, card_image: item.card_image, idx: i})),
    ...(p.consumables || []).map((item, i) => ({name: item.name, card_image: item.card_image, idx: p.pack.length + i})),
    ...(p.captured_monsters || []).map((item, i) => ({name: item.name, card_image: item.card_image, idx: p.pack.length + (p.consumables || []).length + i})),
  ];
  const overlay = document.createElement('div');
  overlay.className = 'action-sheet-overlay';
  overlay.id = 'placement-pack-discard-overlay';
  const box = document.createElement('div');
  box.className = 'action-sheet';
  box.innerHTML = `<div style="text-align:center;margin-bottom:12px"><div class="modal-title">Pack Full</div>
    <div class="modal-desc">Choose an item to discard:</div></div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center">${packItems.map(pi => {
      const img = pi.card_image ? `<img src="/games/werblers/images/${pi.card_image}" style="width:60px;border-radius:4px">` : '';
      return `<div class="rake-equip-btn" onclick="window._confirmPlacementPackDiscard(${pi.idx})">${img}<div class="rake-item-name">${pi.name}</div></div>`;
    }).join('')}</div>
    <div class="action-sheet-cancel" onclick="window._cancelPlacementPackDiscard()">Cancel</div>`;
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  window._confirmPlacementPackDiscard = (dpi) => {
    overlay.remove();
    _finishPlacement({placement: 'equip', equip_action: 'swap', equip_item_index: equipItemIdx, pack_discard_index: dpi});
  };
  window._cancelPlacementPackDiscard = () => overlay.remove();
}

// 2H weapon full-equip: sequentially ask what to do with each of the two occupied weapon slots.
function _handle2HFullEquip(w0, w1, player) {
  _show2HDisplaceModal(w0, player.pack_slots_free, (action1, pdi1, packFreeAfter1) => {
    _show2HDisplaceModal(w1, packFreeAfter1, (action2, pdi2) => {
      _finishPlacement({
        placement: 'equip',
        equip_item_index: 0,
        equip_action: action1,
        pack_discard_index: pdi1,
        equip_action_2: action2,
        pack_discard_index_2: pdi2,
      });
    });
  });
}

function _show2HDisplaceModal(weapon, packFree, onChoice) {
  const overlay = document.createElement('div');
  overlay.className = 'action-sheet-overlay';
  const sheet = document.createElement('div');
  sheet.className = 'action-sheet';
  const imgHtml = weapon.card_image
    ? `<img src="/games/werblers/images/${weapon.card_image}" style="width:90px;border-radius:6px;margin:0 auto 10px;display:block" onclick="openCardZoom('/games/werblers/images/${weapon.card_image}')">`
    : '';
  sheet.innerHTML = `
    <div style="text-align:center;padding:6px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:15px">Equipping 2-Handed Weapon</div>
    ${imgHtml}
    <div style="text-align:center;font-size:13px;color:var(--text);margin-bottom:14px">What should happen to <b>${weapon.name}</b>?</div>
    <div class="action-sheet-item" id="btn-2h-pack">Move to Pack${packFree <= 0 ? ' (full)' : ''}</div>
    <div class="action-sheet-item danger" id="btn-2h-discard">Discard</div>`;
  overlay.appendChild(sheet);
  document.body.appendChild(overlay);

  sheet.querySelector('#btn-2h-discard').onclick = () => {
    overlay.remove();
    onChoice('discard', -1, packFree);
  };
  sheet.querySelector('#btn-2h-pack').onclick = () => {
    overlay.remove();
    if (packFree > 0) {
      onChoice('swap', -1, packFree - 1);
    } else {
      _show2HPackDiscardChoice(weapon, (pdi) => onChoice('swap', pdi, 0));
    }
  };
}

function _show2HPackDiscardChoice(weapon, onChoice) {
  const p = gameState?.players?.find(pl => pl.is_current);
  const packItems = [
    ...(p?.pack || []).map((item, i) => ({ name: item.name, card_image: item.card_image, idx: i })),
    ...(p?.consumables || []).map((item, i) => ({ name: item.name, card_image: item.card_image, idx: (p.pack || []).length + i })),
    ...(p?.captured_monsters || []).map((item, i) => ({ name: item.name, card_image: item.card_image, idx: (p.pack || []).length + (p.consumables || []).length + i })),
  ];
  const overlay = document.createElement('div');
  overlay.className = 'action-sheet-overlay';
  const box = document.createElement('div');
  box.className = 'action-sheet';
  box.innerHTML = `
    <div style="text-align:center;margin-bottom:10px"><div style="font-family:'Cinzel',serif;color:var(--gold)">Pack Full</div>
    <div style="font-size:12px;color:var(--text-dim);margin-top:6px">Discard a pack item to make room for <b>${weapon.name}</b>:</div></div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center">${packItems.map(pi => {
      const img = pi.card_image ? `<img src="/games/werblers/images/${pi.card_image}" style="width:60px;border-radius:4px">` : '';
      return `<div class="rake-equip-btn" data-pack-idx="${pi.idx}">${img}<div class="rake-item-name">${pi.name}</div></div>`;
    }).join('')}</div>
    <div class="action-sheet-cancel">Cancel</div>`;
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  box.querySelectorAll('[data-pack-idx]').forEach(el => {
    el.addEventListener('click', () => { overlay.remove(); onChoice(parseInt(el.dataset.packIdx)); });
  });
  box.querySelector('.action-sheet-cancel').onclick = () => overlay.remove();
}

// ================================================================
// CHARLIE WORK
// ================================================================
let _charlieWorkLevel = null;
function _showCharlieWorkDecision(level) {
  _charlieWorkLevel = level;
  const modal = document.getElementById('charlie-work-modal');
  modal.querySelector('.modal-desc').textContent =
    `You have "No More Charlie Work". Fight a harder Tier ${level + 1} monster for better rewards, or fight a normal Tier ${level} monster?`;
  modal.classList.remove('hidden');
}
async function resolveCharlieWork(useIt) {
  document.getElementById('charlie-work-modal').classList.add('hidden');
  const resp = await fetch('/games/werblers/api/resolve_charlie_work', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({use_it: useIt}),
  });
  const data = await resp.json();
  if (data.state) { gameState = data.state; applyState(data.state); }
  if (data.phase === 'combat' && data.combat_info) {
    playMusic('Battle Music.wav');
    showPreFightScene(data.combat_info, data.state);
  } else {
    await loadAndRenderAbilities();
  }
}

// ================================================================
// CONSUMABLES (overworld)
// ================================================================
async function usePackConsumable(idx, targetPlayerId) {
  const p = gameState?.players?.find(x => x.is_current);
  if (!p) return;
  const c = (p.consumables || [])[idx];
  if (!c) return;
  // Show confirmation
  const overlay = document.createElement('div');
  overlay.className = 'consumable-modal-overlay';
  const img = c.card_image ? `<img class="consumable-modal-card-img" src="/games/werblers/images/${c.card_image}" onclick="openCardZoom('/games/werblers/images/${c.card_image}')">` : '';
  overlay.innerHTML = `<div class="consumable-modal-box">
    <div class="consumable-modal-title">${c.name}</div>${img}
    <div class="consumable-modal-msg">${c.description || 'Use this consumable?'}</div>
    <div class="consumable-modal-actions">
      <button class="btn-primary" id="confirm-use-cons">Use</button>
      <button class="btn-secondary" id="cancel-use-cons">Cancel</button>
    </div></div>`;
  document.body.appendChild(overlay);
  overlay.querySelector('#confirm-use-cons').onclick = async () => {
    overlay.remove();
    const body = {consumable_index: idx};
    if (targetPlayerId !== undefined) body.target_player_id = targetPlayerId;
    const resp = await fetch('/games/werblers/api/use_consumable', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (data.error) { alert(data.error); return; }
    if (data.state) { gameState = data.state; applyState(data.state); }
    // Handle give_curse (bomb) response
    if (data.phase === 'curse_given') {
      _showConsumableResultPopup(data.target_name, data.curse_name, data.curse_desc, false);
    }
    // Handle trait_gained response (e.g. Nectar of the Gods, Priest's Blessing)
    if (data.phase === 'trait_gained') {
      _showConsumableResultPopup(p.hero_name || p.name, data.trait_name, data.trait_desc, true);
      await _placePendingTraitItems();
      await _placePendingTraitMinions();
    }
    await loadAndRenderAbilities();
  };
  overlay.querySelector('#cancel-use-cons').onclick = () => overlay.remove();
}

function _showConsumableResultPopup(targetName, effectName, effectDesc, isTrait) {
  const overlay = document.createElement('div');
  overlay.className = 'consumable-modal-overlay';
  const label = isTrait ? `${targetName} received trait:` : `${targetName} received curse:`;
  overlay.innerHTML = `<div class="consumable-modal-box">
    <div class="consumable-modal-title">${effectName}</div>
    <div class="consumable-modal-msg">${label} <strong>${effectName}</strong>!</div>
    ${effectDesc ? `<div class="consumable-modal-msg" style="font-style:italic;color:var(--text-dim);font-size:13px">${effectDesc}</div>` : ''}
    <div class="consumable-modal-actions">
      <button class="btn-primary" onclick="this.closest('.consumable-modal-overlay').remove()">OK</button>
    </div></div>`;
  document.body.appendChild(overlay);
}

// ================================================================
// MYSTERY EVENTS
// ================================================================
let _pendingMysteryEvent = null;
let _mysterySelectedIdx = -1;
let _pendingMysteryFarewell = null;

function showMysteryEventModal(event, state) {
  _pendingMysteryEvent = event;
  _mysterySelectedIdx = -1;
  const overlay = document.getElementById('battle-overlay');
  const bg = event.image ? `/games/werblers/images/${event.image}` : '';
  const player = state.players.find(p => p.is_current) || state.players[0];

  let bodyHtml = '';
  if (event.event_id === 'mystery_box') {
    bodyHtml = `<div class="mystery-speech-bubble"><p>"Hey, wanna know what's in this box?"</p></div>
      <div class="mystery-btn-row">
        <button class="btn-primary" onclick="_showMysteryBoxWager()">Yes (discard one item)</button>
        <button class="btn-secondary" onclick="_mysteryBoxDecline()">Decline</button>
      </div>`;
  } else if (event.event_id === 'the_wheel') {
    bodyHtml = _renderTheWheel(event);
  } else if (event.event_id === 'the_smith') {
    bodyHtml = _renderTheSmith(event, player);
  } else if (event.event_id === 'bandits') {
    bodyHtml = _renderBandits(event);
  } else if (event.event_id === 'thief') {
    bodyHtml = _renderThief(event);
  } else if (event.event_id === 'beggar') {
    bodyHtml = _renderBeggar(event, player);
  }

  const showDesc = event.event_id !== 'the_wheel';
  const bgPos = event.event_id === 'thief' ? ';background-position:20% center' : '';
  overlay.innerHTML = `
    <div class="battle-bg" style="background-image:url('${bg}')${bgPos}"></div>
    <div class="battle-content mystery-fullscreen">
      <div class="mystery-fs-inner">
        <h2 class="mystery-fs-title">${event.name}</h2>
        ${showDesc ? `<p class="mystery-fs-desc">${event.description || ''}</p>` : ''}
        <div class="mystery-fs-body">${bodyHtml}</div>
      </div>
    </div>`;
  overlay.classList.remove('hidden');
}

function _showMysteryBoxWager() {
  const player = gameState?.players?.find(p => p.is_current) || gameState?.players?.[0];
  const bodyEl = document.querySelector('.mystery-fs-body');
  if (!bodyEl) return;
  bodyEl.innerHTML = _renderMysteryBox(_pendingMysteryEvent, player);
}

async function _mysteryBoxDecline() {
  await _showCharacterFarewell(_pendingMysteryEvent, '"A pity\u2026"', () => {});
  await _postResolveMystery({action: 'skip'});
}

function _renderMysteryBox(event, player) {
  const packItems = _getUnifiedPack(player);
  const equipped = _getAllEquipped(player);
  if (packItems.length === 0 && equipped.length === 0) {
    return `<p class="mystery-info">You have nothing to wager!</p><button class="btn-primary" onclick="_resolveMysterySkip()">Continue</button>`;
  }
  function makeBtn(item, idx) {
    const img = item.img ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.img}" onerror="this.style.display='none'">` : '';
    return `<div class="mystery-selectable-item" data-idx="${idx}" onclick="_selectMysteryItem(${idx}, this)">${img}<div class="mystery-item-label">${item.name}</div></div>`;
  }
  let html = '<p class="mystery-info">Choose an item to discard:</p>';
  if (packItems.length > 0) {
    html += `<div class="mystery-section-label">Pack</div><div class="mystery-item-grid">${packItems.map((item, i) => makeBtn({name: item.name, img: item.card_image}, i)).join('')}</div>`;
  }
  if (equipped.length > 0) {
    html += `<div class="mystery-section-label">Equipped</div><div class="mystery-item-grid">${equipped.map((item, i) => makeBtn({name: item.name, img: item.card_image}, packItems.length + i)).join('')}</div>`;
  }
  html += `<div class="mystery-btn-row">
    <button class="btn-secondary" onclick="_mysteryBoxBack()">Back</button>
    <button class="btn-primary" id="mystery-confirm-btn" onclick="_resolveMysteryBox(_mysterySelectedIdx)" disabled>Discard & Open</button></div>`;
  return html;
}

function _mysteryBoxBack() {
  const bodyEl = document.querySelector('.mystery-fs-body');
  if (!bodyEl || !_pendingMysteryEvent) return;
  bodyEl.innerHTML = `<p class="mystery-info">Discard an item to open?</p>
    <div class="mystery-btn-row">
      <button class="btn-primary" onclick="_showMysteryBoxWager()">Yes (discard one item)</button>
      <button class="btn-secondary" onclick="_mysteryBoxDecline()">Decline</button>
    </div>`;
}

function _renderTheWheel(event) {
  const tier = event.tier || 1;
  return `<div class="mystery-speech-bubble"><p>"Step right up! Spin the wheel!"</p></div>
    <img class="mystery-wheel-img" src="/games/werblers/images/Events/Wheel Tier ${tier}.png" alt="The Wheel" onerror="this.style.display='none'">
    <div class="mystery-btn-row">
      <button class="btn-primary" onclick="_resolveMysteryWheel()">Spin</button>
      <button class="btn-secondary" onclick="_wheelDecline()">Decline</button>
    </div>`;
}

async function _wheelDecline() {
  await _showCharacterFarewell(_pendingMysteryEvent, '"Well, coward, don\'t forget to have your minions spayed and neutered."', () => {});
  await _postResolveMystery({action: 'skip'});
}

function _renderTheSmith(event, player) {
  _smithSelected.clear();
  _smithSelected3.clear();
  const packItems = _getUnifiedPack(player);
  if (event.tier < 3) {
    const equipped = _getAllEquipped(player);
    const allItems = [...packItems.map((item, i) => ({name: item.name, img: item.card_image, idx: i})),
                      ...equipped.map((item, i) => ({name: item.name, img: item.card_image, idx: packItems.length + i}))];
    if (allItems.length < 3) return `<div style="text-align:center;padding:16px 0">
      <div style="font-size:48px;margin-bottom:12px">Ã°Å¸â€Â¨</div>
      <div class="mystery-speech-bubble"><p>"Heh... sorry pal, you're gonna need at least 3 items before I can work my magic."</p></div>
      <p class="mystery-info" style="color:var(--text-dim)">You only have ${allItems.length} item${allItems.length === 1 ? '' : 's'}.</p>
      </div><div class="mystery-btn-row"><button class="btn-primary" onclick="_resolveMysterySkip()">Leave</button></div>`;
    const itemBtns = allItems.map(item => {
      const img = item.img ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.img}" onerror="this.style.display='none'">` : '';
      return `<div class="mystery-selectable-item smith-item" data-idx="${item.idx}" onclick="_toggleSmithItem(this)">${img}<div class="mystery-item-label">${item.name}</div></div>`;
    }).join('');
    return `<p class="mystery-info">Select 3 items to trade for a Tier ${Math.min(event.tier + 1, 3)} item:</p>
      <div class="mystery-item-grid" id="smith-grid">${itemBtns}</div>
      <div class="mystery-btn-row">
        <button class="btn-primary" id="smith-confirm-btn" onclick="_resolveMysterySmith()" disabled>Trade (select 3)</button>
        <button class="btn-secondary" onclick="_resolveMysterySkip()">Decline</button></div>`;
  } else {
    const equipped = _getAllEquipped(player);
    if (packItems.length < 3) return `<div style="text-align:center;padding:16px 0">
      <div style="font-size:48px;margin-bottom:12px">Ã°Å¸â€Â¨</div>
      <div class="mystery-speech-bubble"><p>"Heh... sorry pal, you're gonna need at least 3 pack items before I can work my magic."</p></div>
      <p class="mystery-info" style="color:var(--text-dim)">You only have ${packItems.length} pack item${packItems.length === 1 ? '' : 's'}.</p>
      </div><div class="mystery-btn-row"><button class="btn-primary" onclick="_resolveMysterySkip()">Leave</button></div>`;
    if (equipped.length === 0) return `<p class="mystery-info">No equipped items to enhance.</p><button class="btn-primary" onclick="_resolveMysterySkip()">Leave</button>`;
    const wagerBtns = packItems.map((item, i) => {
      const img = item.card_image ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.card_image}" onerror="this.style.display='none'">` : '';
      return `<div class="mystery-selectable-item smith3-wager" data-idx="${i}" onclick="_toggleSmithT3Item(this)">${img}<div class="mystery-item-label">${item.name}</div></div>`;
    }).join('');
    const enhanceBtns = equipped.map((item, i) => {
      const img = item.card_image ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.card_image}" onerror="this.style.display='none'">` : '';
      return `<div class="mystery-selectable-item" data-idx="${i}" onclick="_selectMysteryItem(${i}, this)">${img}<div class="mystery-item-label">${item.name} (+${item.strength_bonus})</div></div>`;
    }).join('');
    return `<p class="mystery-info">Select 3 pack items to trade:</p>
      <div class="mystery-item-grid">${wagerBtns}</div>
      <p class="mystery-info" style="margin-top:12px">Choose an equipped item for +3 Str:</p>
      <div class="mystery-item-grid">${enhanceBtns}</div>
      <div class="mystery-btn-row">
        <button class="btn-primary" id="smith3-confirm-btn" onclick="_resolveSmithT3()" disabled>Trade & Enhance</button>
        <button class="btn-secondary" onclick="_resolveMysterySkip()">Decline</button></div>`;
  }
}

function _renderBandits() {
  return `<p class="mystery-info">Bandits ambush you and steal one of your equipped items!</p>
    <div class="mystery-btn-row"><button class="btn-primary" onclick="_resolveMysteryAuto('bandits')">Face the Bandits</button></div>`;
}

function _renderThief() {
  return `<p class="mystery-info">A thief sneaks up and steals everything from your pack!</p>
    <div class="mystery-btn-row"><button class="btn-primary" onclick="_resolveMysteryAuto('thief')">Encounter the Thief</button></div>`;
}

function _renderBeggar(event, player) {
  if (player.beggar_completed) return `<div class="mystery-speech-bubble"><p>"I have nothing more for you."</p></div><div class="mystery-btn-row"><button class="btn-primary" onclick="_resolveMysterySkip()">Continue</button></div>`;
  const packItems = _getUnifiedPack(player);
  const equipped = _getAllEquipped(player);
  if (packItems.length + equipped.length === 0) return `<div class="mystery-speech-bubble"><p>"Do you have anything to spare?"</p></div><p class="mystery-info">You have nothing to give.</p><div class="mystery-btn-row"><button class="btn-primary" onclick="_resolveMysterySkip()">Continue</button></div>`;
  return `<div class="mystery-speech-bubble"><p>"Do you have anything to spare for an old man?"</p></div>
    <div class="mystery-btn-row">
      <button class="btn-primary" onclick="_beggarShowItemPicker()">Yes</button>
      <button class="btn-secondary" onclick="_beggarSayNo()">No</button></div>`;
}

function _beggarSayNo() {
  const bodyEl = document.querySelector('.mystery-fs-body');
  if (bodyEl) bodyEl.innerHTML = `<div class="mystery-speech-bubble"><p>"Thank you anyway..."</p></div><div class="mystery-btn-row"><button class="btn-primary" onclick="_resolveMysterySkip()">Continue</button></div>`;
}

function _beggarShowItemPicker() {
  const player = gameState?.players?.find(p => p.is_current) || gameState?.players?.[0];
  if (!player) return;
  const packItems = _getUnifiedPack(player);
  const equipped = _getAllEquipped(player);
  _mysterySelectedIdx = -1;
  function makeBtn(item, idx) {
    const img = item.img ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.img}" onerror="this.style.display='none'">` : '';
    return `<div class="mystery-selectable-item" data-idx="${idx}" onclick="_selectMysteryItem(${idx}, this)">${img}<div class="mystery-item-label">${item.name}</div></div>`;
  }
  const bodyEl = document.querySelector('.mystery-fs-body');
  if (!bodyEl) return;
  let html = '<p class="mystery-info">Choose an item to give:</p>';
  if (packItems.length > 0) html += `<div class="mystery-section-label">Pack</div><div class="mystery-item-grid">${packItems.map((item, i) => makeBtn({name: item.name, img: item.card_image}, i)).join('')}</div>`;
  if (equipped.length > 0) html += `<div class="mystery-section-label">Equipped</div><div class="mystery-item-grid">${equipped.map((item, i) => makeBtn({name: item.name, img: item.card_image}, packItems.length + i)).join('')}</div>`;
  html += `<div class="mystery-btn-row"><button class="btn-primary" id="mystery-confirm-btn" onclick="_resolveBeggarGive(_mysterySelectedIdx)" disabled>Give Item</button></div>`;
  bodyEl.innerHTML = html;
}

function _selectMysteryItem(idx, el) {
  _mysterySelectedIdx = idx;
  document.querySelectorAll('.mystery-selectable-item').forEach(b => b.classList.remove('selected'));
  if (el) el.classList.add('selected');
  const btn = document.getElementById('mystery-confirm-btn');
  if (btn) btn.disabled = false;
  const smith3Btn = document.getElementById('smith3-confirm-btn');
  if (smith3Btn) smith3Btn.disabled = !(_smithSelected3.size === 3 && _mysterySelectedIdx >= 0);
}

function _getUnifiedPack(player) {
  return [...(player.pack || []), ...(player.consumables || []), ...(player.captured_monsters || [])];
}

function _getAllEquipped(player) {
  return [...(player.helmets || []), ...(player.chest_armor || []), ...(player.leg_armor || []), ...(player.weapons || [])];
}

// Smith item selection
let _smithSelected = new Set();
let _smithSelected3 = new Set();

function _toggleSmithItem(el) {
  const idx = parseInt(el.dataset.idx);
  if (_smithSelected.has(idx)) { _smithSelected.delete(idx); el.classList.remove('selected'); }
  else { if (_smithSelected.size >= 3) return; _smithSelected.add(idx); el.classList.add('selected'); }
  const btn = document.getElementById('smith-confirm-btn');
  if (btn) { btn.disabled = _smithSelected.size !== 3; btn.textContent = _smithSelected.size === 3 ? 'Trade!' : `Trade (select ${3 - _smithSelected.size} more)`; }
}

function _toggleSmithT3Item(el) {
  const idx = parseInt(el.dataset.idx);
  if (_smithSelected3.has(idx)) { _smithSelected3.delete(idx); el.classList.remove('selected'); }
  else { if (_smithSelected3.size >= 3) return; _smithSelected3.add(idx); el.classList.add('selected'); }
  const btn = document.getElementById('smith3-confirm-btn');
  if (btn) { btn.disabled = !(_smithSelected3.size === 3 && _mysterySelectedIdx >= 0); btn.textContent = _smithSelected3.size < 3 ? `Trade (select ${3 - _smithSelected3.size} more)` : 'Trade & Enhance'; }
}

// Mystery resolution handlers
async function _resolveMysteryBox(wagerIndex) { if (wagerIndex < 0) return; await _postResolveMystery({action: 'open', wager_index: wagerIndex}); }
async function _resolveMysteryWheel() { await _postResolveMystery({action: 'spin'}); }
async function _resolveMysterySmith() { const indices = Array.from(_smithSelected).sort((a,b)=>b-a); _smithSelected.clear(); await _postResolveMystery({action: 'smith', smith_indices: indices}); }
async function _resolveSmithT3() {
  if (_smithSelected3.size < 3 || _mysterySelectedIdx < 0) return;
  const indices = Array.from(_smithSelected3).sort((a,b)=>b-a);
  const enhanceIdx = _mysterySelectedIdx;
  _smithSelected3.clear(); _mysterySelectedIdx = -1;
  await _postResolveMystery({action: 'smith', smith_indices: indices, smith_equip_index: enhanceIdx});
}
async function _resolveMysteryAuto() { await _postResolveMystery({action: 'accept'}); }
async function _resolveBeggarGive(giveIndex) { if (giveIndex < 0) return; await _postResolveMystery({action: 'give', wager_index: giveIndex}); }
async function _resolveMysterySkip() { await _postResolveMystery({action: 'skip'}); }

async function _postResolveMystery(body) {
  try {
    const resp = await fetch('/games/werblers/api/resolve_mystery', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      let errMsg = `HTTP ${resp.status}`;
      let errData = {};
      try { errData = await resp.json(); errMsg = errData.error || errMsg; } catch (_) {}
      if (errData.state) { gameState = errData.state; applyState(errData.state); }
      const isWagerError = _pendingMysteryEvent?.event_id === 'mystery_box' && errMsg.includes('Invalid');
      if (isWagerError) { alert('Please select a valid item.'); _showMysteryBoxWager(); }
      else { alert(`Mystery event error:\n${errMsg}`); _closeMysteryResult(); }
      return;
    }
    const data = await resp.json();
    // Save the player who encountered this event BEFORE the turn advances in the state
    const mysteryPlayer = gameState?.players?.find(x => x.is_current) || null;
    if (data.state) { gameState = data.state; applyState(data.state); }

    const isWheel = _pendingMysteryEvent?.event_id === 'the_wheel';
    const isBandits = _pendingMysteryEvent?.event_id === 'bandits';
    const isMysteryBox = _pendingMysteryEvent?.event_id === 'mystery_box';
    const wheelFarewell = '"Congratulations or sorry that happened! Remember to spay and neuter your minions!"';
    const boxFarewell = '"Wow, I\'m envious\u2026"';

    if (data.phase === 'offer_chest') {
      const farewellQuote = isWheel ? wheelFarewell : isMysteryBox ? boxFarewell : null;
      await _showMysteryOutcome(data, () => {
        if (farewellQuote) _pendingMysteryFarewell = {event: _pendingMysteryEvent, quote: farewellQuote};
        _pendingMysteryEvent = null;
        _pendingOfferData = data.offer;
        document.getElementById('battle-overlay').classList.add('hidden');
        showChestModal(data.offer, {});
      }, mysteryPlayer);
    } else if (data.phase === 'beggar_thank') {
      _showBeggarThankYou(data, mysteryPlayer);
    } else if (data.phase === 'fairy_king_reveal') {
      _showFairyKingReveal(data);
    } else {
      if (data.prize_type === 'skip') {
        _closeMysteryResult();
      } else if (isWheel) {
        await _showMysteryOutcome(data, async () => { await _showCharacterFarewell(_pendingMysteryEvent, wheelFarewell, () => _closeMysteryResult()); }, mysteryPlayer);
      } else if (isMysteryBox) {
        await _showMysteryOutcome(data, async () => { await _showCharacterFarewell(_pendingMysteryEvent, boxFarewell, () => _closeMysteryResult()); }, mysteryPlayer);
      } else if (isBandits && data.prize_type === 'stolen') {
        await _showMysteryOutcome(data, async () => { await _showCharacterFarewell(_pendingMysteryEvent, '"Thank you for your\u2026 heh\u2026 generosity."', () => _closeMysteryResult()); }, mysteryPlayer);
      } else {
        await _showMysteryOutcome(data, () => _closeMysteryResult(), mysteryPlayer);
      }
    }
  } catch (err) { console.error('resolve_mystery error:', err); if (gameState) applyState(gameState); }
}

function _closeMysteryResult() {
  _pendingMysteryEvent = null;
  document.getElementById('battle-overlay').classList.add('hidden');
  _resumeTierMusic();
  if (gameState) applyState(gameState);
  loadAndRenderAbilities();
}

function _checkMysteryFarewell() {
  if (!_pendingMysteryFarewell) return;
  const {event, quote} = _pendingMysteryFarewell;
  _pendingMysteryFarewell = null;
  _showCharacterFarewell(event, quote, () => {});
}

async function _showCharacterFarewell(event, quoteText, onContinue) {
  const tier = event?.tier || 1;
  const imgName = event?.image_name || event?.name || '';
  const bg = imgName ? `/games/werblers/images/Events/${imgName} Tier ${tier}.png` : '';
  const title = event?.name || '';
  const overlay = document.getElementById('battle-overlay');
  overlay.innerHTML = `
    <div class="battle-bg" style="background-image:url('${bg}')"></div>
    <div class="battle-content mystery-fullscreen">
      <div class="mystery-fs-inner">
        <h2 class="mystery-fs-title">${title}</h2>
        <div class="mystery-speech-bubble"><p>${quoteText}</p></div>
        <div class="mystery-btn-row"><button class="btn-primary" id="mystery-farewell-btn">Continue</button></div>
      </div>
    </div>`;
  overlay.classList.remove('hidden');
  return new Promise(resolve => {
    document.getElementById('mystery-farewell-btn').onclick = () => { if (typeof onContinue === 'function') onContinue(); resolve(); };
  });
}

function _getMysteryOutcomeContent(data) {
  const eventId = data.event_id || (_pendingMysteryEvent?.event_id) || '';
  const prizeType = data.prize_type || '';
  const label = data.mystery_result || '';
  const itemName = data.offer?.items?.[0]?.name || '';
  let title = '', outcomeText = '', quoteText = '';

  switch (eventId) {
    case 'mystery_box':
      title = 'Mystery Box';
      if (prizeType === 'nothing') outcomeText = 'You got nothing! Good day sir!';
      else if (prizeType === 'trait') {
        const mn = data.monster_name || '', tn = data.trait_name || 'a trait', td = data.trait_description ? `<br><span style="font-size:0.85em;opacity:0.7;font-style:italic">${data.trait_description}</span>` : '';
        outcomeText = mn ? `The box contained\u2026 a dead <strong>${mn}</strong>! Trait: <strong>${tn}</strong>!${td}` : `Trait: <strong>${tn}</strong>!${td}`;
      } else if (prizeType === 'item' || prizeType === 'item_up' || prizeType === 'item_t3') outcomeText = `The box contained\u2026 <strong>${itemName || 'an item'}</strong>!`;
      else if (prizeType === 'curse') {
        const cd = data.curse_description ? `<br><span style="font-size:0.85em;opacity:0.7;font-style:italic">${data.curse_description}</span>` : '';
        outcomeText = `<strong>A CURSE!</strong> ${data.curse_name || 'a curse'}!${cd}`;
      } else outcomeText = label || 'Mystery resolved.';
      break;
    case 'the_wheel':
      title = 'The Wheel';
      if (prizeType === 'nothing') outcomeText = 'You got nothing!';
      else if (prizeType === 'trait') { const tn = data.trait_name || 'trait'; outcomeText = `Trait: <strong>${tn}</strong>!`; }
      else if (prizeType === 'item' || prizeType === 'item_up' || prizeType === 'item_t3') outcomeText = `You got <strong>${itemName || 'an item'}</strong>!`;
      else if (prizeType === 'curse') outcomeText = `<strong>A CURSE!</strong> ${data.curse_name || 'a curse'}!`;
      else outcomeText = label || 'The wheel has spoken.';
      break;
    case 'the_smith':
      title = 'The Smith';
      if (prizeType === 'smith_enhance') { outcomeText = `Enhanced <strong>${data.item_name || 'your item'}</strong> with +3 Str!`; quoteText = '"Fine work."'; }
      else if (prizeType === 'item') { outcomeText = `Forged: <strong>${itemName || 'a new item'}</strong>!`; quoteText = '"Use it well."'; }
      else outcomeText = label || 'The Smith nods.';
      break;
    case 'bandits':
      title = 'Bandits';
      if (prizeType === 'stolen' && data.item_name) outcomeText = `Stole your <strong>${data.item_name}</strong>!`;
      else outcomeText = label || 'The bandits vanish.';
      break;
    case 'thief':
      title = 'Thief';
      if (prizeType === 'stolen' && data.stolen_items?.length > 0) outcomeText = `Stole: <strong>${data.stolen_items.join(', ')}</strong>!`;
      else outcomeText = label || 'The thief disappears.';
      quoteText = '"Nothing personal, mate."';
      break;
    case 'beggar':
      title = 'Beggar'; quoteText = '"Thank you for your generosity."'; break;
    default:
      title = _pendingMysteryEvent?.name || 'Mystery';
      outcomeText = label || 'Mystery resolved.';
  }
  return {title, outcomeText, quoteText};
}

async function _showMysteryOutcome(data, onContinue, overrideAnimPlayer = null) {
  const {title, outcomeText, quoteText} = _getMysteryOutcomeContent(data);
  const tier = _pendingMysteryEvent?.tier || 1;
  const imgName = _pendingMysteryEvent?.image_name || _pendingMysteryEvent?.name || title;
  const bg = `/games/werblers/images/Events/${imgName} Tier ${tier}.png`;
  const featuredCard = data.card_image || null;

  let animVideoHtml = '';
  if (gameState) {
    const eventId = data.event_id || _pendingMysteryEvent?.event_id || '';
    const prizeType = data.prize_type || '';
    let animType = null;
    if ((eventId === 'thief' || eventId === 'bandits') && prizeType === 'stolen') animType = 'defeat';
    else if (prizeType === 'trait') animType = 'victory';
    else if (prizeType === 'curse') animType = 'defeat';
    if (animType) {
      const p = overrideAnimPlayer || gameState.players.find(x => x.is_current) || gameState.players[0];
      if (p?.hero_id && heroAnimMap[p.hero_id]?.[animType]) {
        animVideoHtml = `<video autoplay muted playsinline style="max-width:180px;width:50%;border-radius:10px;box-shadow:0 0 20px rgba(0,0,0,0.7)" src="/games/werblers/videos/${heroAnimMap[p.hero_id][animType]}"></video>`;
      }
    }
  }

  const overlay = document.getElementById('battle-overlay');
  overlay.innerHTML = `
    <div class="battle-bg" style="background-image:url('${bg}')"></div>
    <div class="battle-content mystery-fullscreen">
      <div class="mystery-fs-inner">
        <h2 class="mystery-fs-title">${title}</h2>
        ${featuredCard ? `<img class="mystery-fs-img" src="/games/werblers/images/${featuredCard}" alt="${title}" onerror="this.style.display='none'">` : ''}
        ${outcomeText ? `<p class="mystery-outcome-text">${outcomeText}</p>` : ''}
        ${quoteText ? `<div class="mystery-speech-bubble"><p>${quoteText}</p></div>` : ''}
        ${animVideoHtml}
        <div class="mystery-btn-row"><button class="btn-primary" id="mystery-outcome-btn">Continue</button></div>
      </div>
    </div>`;
  overlay.classList.remove('hidden');

  return new Promise(resolve => {
    document.getElementById('mystery-outcome-btn').onclick = () => { if (typeof onContinue === 'function') onContinue(); resolve(); };
  });
}

// Beggar thank-you phase Ã¢â‚¬â€ just show outcome and close (don't send extra 'skip')
function _showBeggarThankYou(data, mysteryPlayer) {
  _showMysteryOutcome(data, () => _closeMysteryResult(), mysteryPlayer || null);
}

// Fairy King reveal Ã¢â‚¬â€ animated transformation from beggar to fairy king, then item selection
let _fkRewardIdx = -1;
function _showFairyKingReveal(data) {
  const overlay = document.getElementById('battle-overlay');
  const tier = _pendingMysteryEvent?.tier || 1;
  const beggarImg = `/games/werblers/images/Events/Beggar Tier ${tier}.png`;
  const fkImg = `/games/werblers/images/Events/Fairy King Tier ${tier}.png`;

  // Start with beggar image
  overlay.innerHTML = `
    <div class="battle-bg" id="fk-bg" style="background-image:url('${beggarImg}')"></div>
    <div class="battle-content mystery-fullscreen">
      <div class="mystery-fs-inner" id="fk-reveal-inner">
        <h2 class="mystery-fs-title" id="fk-title">The Beggar</h2>
      </div>
    </div>`;
  overlay.classList.remove('hidden');

  // Transform to Fairy King after a pause
  setTimeout(() => {
    const bgEl = document.getElementById('fk-bg');
    const titleEl = document.getElementById('fk-title');
    if (bgEl) { bgEl.classList.add('fk-reveal-flash'); bgEl.style.backgroundImage = `url('${fkImg}')`; }
    if (titleEl) titleEl.textContent = 'The Fairy King';
    const inner = document.getElementById('fk-reveal-inner');
    if (inner) {
      inner.insertAdjacentHTML('beforeend', `<div class="mystery-speech-bubble"><p>"You are very kind. Your generosity shall be rewarded."</p></div>`);
    }

    // Show item choices after another delay
    setTimeout(() => {
      const items = data.reward_items || [];
      const inner2 = document.getElementById('fk-reveal-inner');
      if (!inner2) return;
      if (items.length === 0) {
        inner2.insertAdjacentHTML('beforeend', `<div class="mystery-btn-row"><button class="btn-primary" onclick="_closeMysteryResult()">Continue</button></div>`);
        return;
      }
      const itemsHtml = items.map((item, i) => {
        const img = item.card_image ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.card_image}" onerror="this.style.display='none'">` : '';
        const bonusText = item.strength_bonus ? ` (+${item.strength_bonus})` : '';
        return `<div class="mystery-selectable-item" data-idx="${i}" onclick="_selectFairyKingReward(${i}, this)">
          ${img}<div class="mystery-item-label">${item.name}${bonusText}</div>
        </div>`;
      }).join('');
      inner2.insertAdjacentHTML('beforeend', `
        <p class="mystery-info" style="margin-top:16px">Choose your reward:</p>
        <div class="mystery-item-grid">${itemsHtml}</div>
        <div class="mystery-btn-row">
          <button class="btn-primary" id="fk-reward-btn" onclick="_resolveFairyKingReward()" disabled>Take Item</button>
        </div>`);
    }, 2500);
  }, 2000);
}

function _selectFairyKingReward(idx, el) {
  _fkRewardIdx = idx;
  document.querySelectorAll('.mystery-selectable-item').forEach(b => b.classList.remove('selected'));
  if (el) el.classList.add('selected');
  const btn = document.getElementById('fk-reward-btn');
  if (btn) btn.disabled = false;
}

async function _resolveFairyKingReward() {
  if (_fkRewardIdx < 0) return;
  try {
    const resp = await fetch('/games/werblers/api/resolve_fairy_king_reward', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({choice_index: _fkRewardIdx}),
    });
    if (!resp.ok) { console.error('fairy king reward failed'); return; }
    const data = await resp.json();
    if (data.state) { gameState = data.state; applyState(data.state); }
    _fkRewardIdx = -1;

    // Show farewell screen
    const tier = _pendingMysteryEvent?.tier || 1;
    const fkImg = `/games/werblers/images/Events/Fairy King Tier ${tier}.png`;
    const overlay = document.getElementById('battle-overlay');
    overlay.innerHTML = `
      <div class="battle-bg" style="background-image:url('${fkImg}')"></div>
      <div class="battle-content mystery-fullscreen">
        <div class="mystery-fs-inner">
          <h2 class="mystery-fs-title">The Fairy King</h2>
          <div class="mystery-speech-bubble"><p>"Goodbye, and good luck."</p></div>
          <div class="mystery-btn-row"><button class="btn-primary" id="fk-farewell-btn">Continue</button></div>
        </div>
      </div>`;
    overlay.classList.remove('hidden');
    await new Promise(resolve => {
      document.getElementById('fk-farewell-btn').onclick = () => resolve();
    });
    _pendingMysteryEvent = null;
    if (data.phase === 'offer_chest' && data.offer) {
      _pendingOfferData = data.offer;
      document.getElementById('battle-overlay').classList.add('hidden');
      showChestModal(data.offer, {});
    } else {
      _closeMysteryResult();
    }
  } catch(e) { console.error('fairy king reward error:', e); }
}

// ================================================================
// RAKE IT IN
// ================================================================
function showRakeItIn(data) {
  const modal = document.getElementById('rake-it-in-modal');
  const content = document.getElementById('rake-it-in-content');
  const player = gameState?.players?.find(p => p.is_current);
  if (!player) return;
  _rakeSelectedSlot = null;
  _rakeSelectedIdx = -1;
  _rakeItInData = data;

  const subType = data.sub_type || 'chest';
  const equips = data.equips || [];
  const packItems = data.pack_items || [];
  const consumableItems = data.consumable_items || [];
  const shopRemaining = data.shop_remaining || [];

  function makeBtn(item, slot, idx) {
    const img = item.card_image ? `<img src="/games/werblers/images/${item.card_image}" style="width:60px;border-radius:4px">` : '';
    return `<div class="rake-equip-btn" data-slot="${slot}" data-idx="${idx}" onclick="_selectRakeDiscard('${slot}',${idx},this)">${img}<div class="rake-item-name">${item.name}</div></div>`;
  }

  const descText = subType === 'shop'
    ? 'Discard an equipped or packed item to take a second item from the shop!'
    : 'Discard an equipped or packed item to draw a bonus item from the deck!';

  let html = `<div class="rake-title">Rake It In</div>
    <p class="mystery-info">${descText}</p>`;

  // Equipped items to discard
  if (equips.length > 0) {
    const equipsHtml = equips.map((e, i) => {
      const slot = e.slot === 'helmet' ? 'equip_helmet' : e.slot === 'chest' ? 'equip_chest' : e.slot === 'legs' ? 'equip_leg' : 'equip_weapon';
      const slotIdx = e.slot_index !== undefined ? e.slot_index : i;
      return makeBtn(e, slot, slotIdx);
    }).join('');
    html += `<div class="rake-section-label">Equipped</div><div class="rake-items-row">${equipsHtml}</div>`;
  }

  // Pack items to discard
  if (packItems.length > 0) {
    html += `<div class="rake-section-label">Pack</div><div class="rake-items-row">${packItems.map((p, i) => makeBtn(p, 'pack', i)).join('')}</div>`;
  }

  // Consumables to discard
  if (consumableItems.length > 0) {
    html += `<div class="rake-section-label">Consumables</div><div class="rake-items-row">${consumableItems.map((c, i) => makeBtn(c, 'consumable', i)).join('')}</div>`;
  }

  // Shop remaining or bonus draw
  _rakeSelectedShopItem = subType === 'chest' ? 0 : -1;
  if (subType === 'shop' && shopRemaining.length > 0) {
    html += `<div class="rake-section-label">Choose a 2nd item from the shop:</div>
      <div class="rake-items-row">${shopRemaining.map((it, i) => {
        const img = it.card_image ? `<img src="/games/werblers/images/${it.card_image}" style="width:60px;border-radius:4px">` : '';
        return `<div class="rake-equip-btn" data-shop-idx="${i}" onclick="_selectRakeShopItem(${i},this)">${img}<div class="rake-item-name">${it.name}</div></div>`;
      }).join('')}</div>`;
  }

  html += `<div class="modal-btns">
    <button class="btn-primary" id="rake-confirm-btn" onclick="_resolveRakeItIn()" disabled>Take Item</button>
    <button class="btn-secondary" onclick="_skipRakeItIn()">Skip</button></div>`;

  content.innerHTML = html;
  modal.classList.remove('hidden');
}

let _rakeSelectedSlot = null;
let _rakeSelectedIdx = -1;
let _rakeSelectedShopItem = -1;
let _rakeItInData = null;

function _selectRakeDiscard(slot, idx, el) {
  _rakeSelectedSlot = slot;
  _rakeSelectedIdx = idx;
  document.querySelectorAll('#rake-it-in-content .rake-equip-btn').forEach(b => b.classList.remove('selected'));
  if (el) el.classList.add('selected');
  _updateRakeConfirmBtn();
}

function _selectRakeShopItem(idx, el) {
  _rakeSelectedShopItem = idx;
  document.querySelectorAll('[data-shop-idx]').forEach(b => b.classList.remove('selected'));
  if (el) el.classList.add('selected');
  _updateRakeConfirmBtn();
}

function _updateRakeConfirmBtn() {
  const btn = document.getElementById('rake-confirm-btn');
  if (!btn) return;
  const subType = _rakeItInData?.sub_type || 'chest';
  const discardOk = _rakeSelectedSlot !== null && _rakeSelectedIdx >= 0;
  const shopOk = subType !== 'shop' || _rakeSelectedShopItem >= 0;
  btn.disabled = !(discardOk && shopOk);
}

async function _resolveRakeItIn() {
  if (_rakeSelectedSlot === null || _rakeSelectedIdx < 0) return;
  document.getElementById('rake-it-in-modal').classList.add('hidden');
  const body = {
    use_it: true,
    discard_slot: _rakeSelectedSlot,
    discard_idx: _rakeSelectedIdx,
  };
  if (_rakeItInData?.sub_type === 'shop' && _rakeSelectedShopItem >= 0) {
    body.second_item_choice = _rakeSelectedShopItem;
  }
  const resp = await fetch('/games/werblers/api/resolve_rake_it_in', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; applyState(data.state); }
  _rakeItInData = null;
  // For chest rake-it-in, the bonus item is in pending_trait_items Ã¢â‚¬â€ show popup + placement
  await _placePendingTraitItems();
  // After placement, the backend advances the turn Ã¢â‚¬â€ refresh state
  if (gameState) { viewingPlayerId = gameState.current_player_id; applyState(gameState); }
  await loadAndRenderAbilities();
}

async function _skipRakeItIn() {
  document.getElementById('rake-it-in-modal').classList.add('hidden');
  const resp = await fetch('/games/werblers/api/resolve_rake_it_in', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({use_it: false}),
  });
  const data = await resp.json();
  if (data.state) { gameState = data.state; viewingPlayerId = data.state.current_player_id; applyState(data.state); }
  _rakeItInData = null;
  await loadAndRenderAbilities();
}

// ================================================================
// ITEM MANAGEMENT (action sheet for equipped/pack items)
// ================================================================
function showItemActions(itemType, itemIndex, itemName) {
  const overlay = document.createElement('div');
  overlay.className = 'action-sheet-overlay';
  const sheet = document.createElement('div');
  sheet.className = 'action-sheet';

  let actions = [];
  if (itemType === 'pack') {
    actions.push({label: 'Move to Equipment', action: () => { overlay.remove(); _manageItem('equip_from_pack', itemIndex); }});
    actions.push({label: 'Discard', danger: true, action: () => { overlay.remove(); _manageItem('discard_pack', itemIndex); }});
  } else if (itemType === 'equip') {
    actions.push({label: 'Unequip to Pack', action: () => { overlay.remove(); _manageItem('unequip_to_pack', itemIndex); }});
    actions.push({label: 'Discard', danger: true, action: () => { overlay.remove(); _manageItem('discard_equip', itemIndex); }});
  } else if (itemType === 'consumable') {
    actions.push({label: 'Use', action: () => { overlay.remove(); usePackConsumable(itemIndex); }});
    actions.push({label: 'Discard', danger: true, action: () => { overlay.remove(); _discardConsumable(itemIndex); }});
  }

  sheet.innerHTML = `<div style="text-align:center;padding:8px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:16px">${itemName}</div>` +
    actions.map(a => `<div class="action-sheet-item ${a.danger ? 'danger' : ''}">${a.label}</div>`).join('') +
    `<div class="action-sheet-cancel">Cancel</div>`;

  sheet.querySelectorAll('.action-sheet-item').forEach((el, i) => {
    el.onclick = actions[i].action;
  });
  sheet.querySelector('.action-sheet-cancel').onclick = () => overlay.remove();
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  overlay.appendChild(sheet);
  document.body.appendChild(overlay);
}

// Convert a flat equip index (helmets Ã¢â€ â€™ chest Ã¢â€ â€™ legs Ã¢â€ â€™ weapons) to {source, index}
function _flatEquipToSource(flatIdx) {
  const p = gameState?.players?.find(x => x.is_current);
  if (!p) return null;
  const helmets = p.helmets || [];
  const chest   = p.chest_armor || [];
  const legs    = p.leg_armor || [];
  const weapons = p.weapons || [];
  let offset = 0;
  if (flatIdx < offset + helmets.length) return {source: 'equip_helmet', index: flatIdx - offset};
  offset += helmets.length;
  if (flatIdx < offset + chest.length)   return {source: 'equip_chest',  index: flatIdx - offset};
  offset += chest.length;
  if (flatIdx < offset + legs.length)    return {source: 'equip_leg',    index: flatIdx - offset};
  offset += legs.length;
  if (flatIdx < offset + weapons.length) return {source: 'equip_weapon', index: flatIdx - offset};
  return null;
}

async function _manageItem(action, index) {
  if (action === 'equip_from_pack') {
    await _equipFromPack(index);
    return;
  }
  let body = {};
  if (action === 'discard_equip') {
    const src = _flatEquipToSource(index);
    if (!src) { alert('Item not found'); return; }
    body = {action: 'discard', source: src.source, index: src.index};
  } else if (action === 'unequip_to_pack') {
    const src = _flatEquipToSource(index);
    if (!src) { alert('Item not found'); return; }
    body = {action: 'to_pack', source: src.source, index: src.index};
  } else if (action === 'discard_pack') {
    body = {action: 'discard', source: 'pack', index: index};
  } else {
    alert('Unknown action: ' + action);
    return;
  }
  const resp = await fetch('/games/werblers/api/manage_item', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (data.error) {
    if (data.error.includes('pack') && data.error.toLowerCase().includes('full')) {
      _showPackFullNotice();
      return;
    }
    alert(data.error);
    return;
  }
  if (data.state) { gameState = data.state; applyState(data.state); }
}

// Direct equip/unequip/discard using source+index (bypasses flat index mapping)
async function _manageItemDirect(action, source, index) {
  let apiAction;
  if (action === 'discard_equip') apiAction = 'discard';
  else if (action === 'unequip_to_pack') apiAction = 'to_pack';
  else { alert('Unknown action: ' + action); return; }
  const resp = await fetch('/games/werblers/api/manage_item', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: apiAction, source, index}),
  });
  const data = await resp.json();
  if (data.error) {
    if (data.error === 'pack_full') { _showPackFullNotice(); return; }
    alert(data.error);
    return;
  }
  if (data.state) { gameState = data.state; applyState(data.state); }
}

// Equip an item from pack using the full displacement chain
async function _equipFromPack(packIndex) {
  const resp = await fetch('/games/werblers/api/equip_from_pack', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({pack_index: packIndex}),
  });
  const data = await resp.json();
  if (!data.error) {
    if (data.state) { gameState = data.state; applyState(data.state); }
    return;
  }
  if (data.error === 'multi_displace' && data.displaced_items) {
    await _showIOSMultiDisplace(packIndex, data.displaced_items, data.pack_slots_free);
    return;
  }
  if (data.error && data.error.includes('no free slot')) {
    const p = gameState?.players?.find(pl => pl.is_current);
    const item = p?.pack?.[packIndex];
    if (item) {
      const slotMap = {helmet: p.helmets, chest: p.chest_armor, legs: p.leg_armor, weapon: p.weapons};
      const occupied = slotMap[item.slot] || [];
      const equippedItem = occupied[0] || null;
      await _showIOSOccupiedSlot(packIndex, item, equippedItem, p.pack_slots_free || 0);
      return;
    }
  }
  alert(data.error);
}

function _showIOSOccupiedSlot(packIndex, newItem, equippedItem, packSlotsFree) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'action-sheet-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) { overlay.remove(); resolve(); } };
    const sheet = document.createElement('div');
    sheet.className = 'action-sheet';
    const newImg = newItem?.card_image ? `<img src="/games/werblers/images/${newItem.card_image}" style="width:80px;border-radius:6px;margin:4px auto;display:block" onerror="this.style.display='none'">` : '';
    const curImg = equippedItem?.card_image ? `<img src="/games/werblers/images/${equippedItem.card_image}" style="width:80px;border-radius:6px;margin:4px auto;display:block" onerror="this.style.display='none'">` : '';
    sheet.innerHTML = `<div style="text-align:center;padding:8px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:15px">Slot Occupied</div>
      <div style="display:flex;gap:16px;justify-content:center;padding:8px 16px">
        <div style="text-align:center;flex:1"><div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">Equipping</div>${newImg}<div style="font-size:12px;color:var(--text)">${newItem?.name||''}</div></div>
        <div style="align-self:center;font-size:20px;color:var(--gold)">Ã¢â€¡Å’</div>
        <div style="text-align:center;flex:1"><div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">Replaces</div>${curImg}<div style="font-size:12px;color:var(--text)">${equippedItem?.name||'?'}</div></div>
      </div>
      <div class="action-sheet-item" id="_occ-pack-btn">${packSlotsFree > 0 ? 'Move Replaced to Pack' : 'Move Replaced to Pack (Pack Full Ã¢â‚¬â€ Choose Discard)'}</div>
      <div class="action-sheet-item danger" id="_occ-discard-btn">Discard Replaced &amp; Equip</div>
      <div class="action-sheet-cancel" id="_occ-cancel">Cancel</div>`;
    sheet.querySelector('#_occ-pack-btn').onclick = async () => {
      overlay.remove();
      const slotIdx = await _pickPackInsertSlot(packIndex, equippedItem?.name || 'item');
      if (slotIdx === null) { resolve(); return; }
      await _doEquipWithDisplace(packIndex, true, false, slotIdx);
      resolve();
    };
    sheet.querySelector('#_occ-discard-btn').onclick = async () => {
      overlay.remove();
      await _doEquipWithDisplace(packIndex, false, true);
      resolve();
    };
    sheet.querySelector('#_occ-cancel').onclick = () => { overlay.remove(); resolve(); };
    overlay.appendChild(sheet);
    document.body.appendChild(overlay);
  });
}

async function _doEquipWithDisplace(packIndex, toPackFirst, forceDiscard, toPackIndex) {
  const body = {pack_index: packIndex, force: true, to_pack: toPackFirst && !forceDiscard};
  if (toPackFirst && !forceDiscard && toPackIndex !== undefined) body.to_pack_index = toPackIndex;
  const resp = await fetch('/games/werblers/api/equip_from_pack', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (data.error === 'pack_full' && data.pack) {
    await _showEquipPackDiscardPicker(data.pack, packIndex);
    return;
  }
  if (data.error === 'multi_displace' && data.displaced_items) {
    await _showIOSMultiDisplace(packIndex, data.displaced_items, data.pack_slots_free);
    return;
  }
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; applyState(data.state); }
}

// Show pack slot chooser so player can pick WHERE to put a displaced item.
// equippingPackIndex: index of the item being equipped (will leave pack).
// itemName: display name of the displaced item being placed.
// Returns chosen insert index (0-based in the post-removal array), or null if cancelled.
function _pickPackInsertSlot(equippingPackIndex, itemName) {
  return new Promise(resolve => {
    const p = gameState?.players?.find(pl => pl.is_current);
    if (!p) { resolve(0); return; }
    // Pack after the equipping item leaves
    const packItems = (p.pack || []).filter((_, i) => i !== equippingPackIndex);
    const packSize = p.pack_size || 5;
    const overlay = document.createElement('div');
    overlay.className = 'action-sheet-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) { overlay.remove(); resolve(null); } };
    const sheet = document.createElement('div');
    sheet.className = 'action-sheet';
    let slotsHtml = '<div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center;padding:8px 4px">';
    // Show filled slots then empty slots (up to packSize, displaced takes one)
    const totalDisplaySlots = Math.min(packSize, packItems.length + 1);
    for (let i = 0; i < totalDisplaySlots; i++) {
      if (i < packItems.length) {
        const itm = packItems[i];
        const imgTag = itm.card_image ? `<img src="/games/werblers/images/${itm.card_image}" style="width:100%;height:100%;object-fit:cover;border-radius:4px">` : '';
        const label = (itm.name || '').substring(0, 12);
        slotsHtml += `<div data-slot="${i}" style="width:60px;height:84px;border:2px solid var(--gold);border-radius:6px;overflow:hidden;cursor:pointer;position:relative;flex-shrink:0">${imgTag}<div style="position:absolute;bottom:0;left:0;right:0;font-size:8px;text-align:center;background:rgba(0,0,0,0.75);color:var(--gold);padding:2px;line-height:1.2">${label}</div></div>`;
      } else {
        slotsHtml += `<div data-slot="${i}" style="width:60px;height:84px;border:2px dashed var(--border);border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0"><span style="font-size:10px;color:var(--text-dim)">Empty</span></div>`;
      }
    }
    slotsHtml += '</div>';
    sheet.innerHTML = `<div style="text-align:center;padding:8px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:15px">Choose Pack Slot</div>
      <div style="font-size:12px;color:var(--text-dim);text-align:center;padding:0 8px 4px">Where to place <strong style="color:var(--text)">${itemName}</strong>:</div>
      ${slotsHtml}
      <div class="action-sheet-cancel">Cancel</div>`;
    sheet.querySelectorAll('[data-slot]').forEach(el => {
      el.onclick = () => { overlay.remove(); resolve(parseInt(el.dataset.slot)); };
    });
    sheet.querySelector('.action-sheet-cancel').onclick = () => { overlay.remove(); resolve(null); };
    overlay.appendChild(sheet);
    document.body.appendChild(overlay);
  });
}

function _showEquipPackDiscardPicker(packItems, origPackIndex) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'action-sheet-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) { overlay.remove(); resolve(); } };
    const sheet = document.createElement('div');
    sheet.className = 'action-sheet';
    sheet.innerHTML = `<div style="text-align:center;padding:8px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:15px">Pack Full</div>
      <div style="font-size:12px;color:var(--text-dim);text-align:center;padding:4px 8px 8px">Choose a pack item to discard to make room:</div>` +
      packItems.map((item, i) => {
        const img = item.card_image ? `<img src="/games/werblers/images/${item.card_image}" style="width:36px;border-radius:4px;vertical-align:middle;margin-right:8px" onerror="this.style.display='none'">` : '';
        return `<div class="action-sheet-item" data-dpi="${i}">${img}${item.name}</div>`;
      }).join('') +
      `<div class="action-sheet-cancel">Cancel</div>`;
    sheet.querySelectorAll('[data-dpi]').forEach(el => {
      el.onclick = async () => {
        overlay.remove();
        const dpi = parseInt(el.dataset.dpi);
        const resp = await fetch('/games/werblers/api/equip_from_pack', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({pack_index: origPackIndex, force: true, to_pack: true, discard_pack_index: dpi}),
        });
        const data = await resp.json();
        if (data.error) { alert(data.error); }
        else if (data.state) { gameState = data.state; applyState(data.state); }
        resolve();
      };
    });
    sheet.querySelector('.action-sheet-cancel').onclick = () => { overlay.remove(); resolve(); };
    overlay.appendChild(sheet);
    document.body.appendChild(overlay);
  });
}

async function _showIOSMultiDisplace(packIndex, displacedItems, packSlotsFree) {
  const actions = [];
  let slotsAvailable = packSlotsFree;
  const p = gameState?.players?.find(pl => pl.is_current);
  for (let i = 0; i < displacedItems.length; i++) {
    const item = displacedItems[i];
    // Ask what to do with this displaced weapon
    const choice = await new Promise(resolve => {
      const overlay = document.createElement('div');
      overlay.className = 'action-sheet-overlay';
      overlay.onclick = (e) => { if (e.target === overlay) { overlay.remove(); resolve(null); } };
      const sheet = document.createElement('div');
      sheet.className = 'action-sheet';
      const img = item.card_image ? `<img src="/games/werblers/images/${item.card_image}" style="width:80px;border-radius:6px;margin:6px auto;display:block" onerror="this.style.display='none'">` : '';
      const packHint = slotsAvailable <= 0 ? ' (choose item to drop)' : '';
      sheet.innerHTML = `<div style="text-align:center;padding:8px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:15px">Replaced Weapon ${i+1}/${displacedItems.length}</div>
        <div style="font-size:12px;color:var(--text);text-align:center;padding:4px">${item.name} (+${item.strength_bonus} Str) must be removed.</div>
        ${img}
        <div class="action-sheet-item" id="_md-pack">Move to Pack${packHint}</div>
        <div class="action-sheet-item danger" id="_md-discard">Discard</div>
        <div class="action-sheet-cancel" id="_md-cancel">Cancel</div>`;
      sheet.querySelector('#_md-pack').onclick = () => { overlay.remove(); resolve('pack'); };
      sheet.querySelector('#_md-discard').onclick = () => { overlay.remove(); resolve('discard'); };
      sheet.querySelector('#_md-cancel').onclick = () => { overlay.remove(); resolve(null); };
      overlay.appendChild(sheet);
      document.body.appendChild(overlay);
    });
    if (choice === null) return;
    if (choice === 'discard') {
      actions.push({action: 'discard'});
    } else {
      if (slotsAvailable > 0) {
        // Free pack slot available Ã¢â‚¬â€ just move it
        actions.push({action: 'to_pack'});
        slotsAvailable--;
      } else {
        // Pack is full Ã¢â‚¬â€ prompt to choose a pack item to drop first
        const packItems = p?.pack || [];
        const pickedIdx = await _pickPackItemToDiscard(packItems, item.name, i + 1, displacedItems.length);
        if (pickedIdx === null) return; // cancelled
        actions.push({action: 'to_pack', discard_pack_index: pickedIdx});
        // net slots unchanged (one evicted, one added)
      }
    }
  }
  const resp = await fetch('/games/werblers/api/equip_from_pack', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({pack_index: packIndex, force: true, displaced_actions: actions}),
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; applyState(data.state); }
}

// Show a picker to choose which pack item to discard, returns chosen index or null
function _pickPackItemToDiscard(packItems, displacedName, itemNum, totalItems) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'action-sheet-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) { overlay.remove(); resolve(null); } };
    const sheet = document.createElement('div');
    sheet.className = 'action-sheet';
    sheet.innerHTML = `<div style="text-align:center;padding:8px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:15px">Pack Full (${itemNum}/${totalItems})</div>
      <div style="font-size:12px;color:var(--text-dim);text-align:center;padding:4px 8px 8px">Drop a pack item to keep <strong>${displacedName}</strong>:</div>` +
      packItems.map((itm, idx) => {
        const img = itm.card_image ? `<img src="/games/werblers/images/${itm.card_image}" style="width:36px;border-radius:4px;vertical-align:middle;margin-right:8px" onerror="this.style.display='none'">` : '';
        return `<div class="action-sheet-item" data-pi="${idx}">${img}${itm.name}</div>`;
      }).join('') +
      `<div class="action-sheet-cancel">Cancel</div>`;
    sheet.querySelectorAll('[data-pi]').forEach(el => {
      el.onclick = () => { overlay.remove(); resolve(parseInt(el.dataset.pi)); };
    });
    sheet.querySelector('.action-sheet-cancel').onclick = () => { overlay.remove(); resolve(null); };
    overlay.appendChild(sheet);
    document.body.appendChild(overlay);
  });
}

function _showPackFullNotice() {
  const overlay = document.createElement('div');
  overlay.className = 'action-sheet-overlay';
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  const sheet = document.createElement('div');
  sheet.className = 'action-sheet';
  sheet.innerHTML = `<div style="text-align:center;padding:12px 0;font-family:'Cinzel',serif;color:var(--gold);font-size:16px">Pack Full</div>
    <div class="action-sheet-item" style="color:var(--text-dim)">Your pack is full. Drop an item from your pack first.</div>
    <div class="action-sheet-cancel" onclick="this.closest('.action-sheet-overlay').remove()">OK</div>`;
  overlay.appendChild(sheet);
  document.body.appendChild(overlay);
}

async function _discardConsumable(idx) {
  const resp = await fetch('/games/werblers/api/discard_consumable', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({consumable_index: idx}),
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; applyState(data.state); }
}

// Re-sync turn banner when tab becomes visible again (prevent stale banner)
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && gameState) applyState(gameState);
});

// ================================================================
// APPLY STATE (central state Ã¢â€ â€™ UI sync)
// ================================================================
function applyState(state) {
  gameState = state;
  // Auto-switch viewingPlayerId only when the current player actually changes (turn advance)
  const newCurrent = (state.players.find(p => p.is_current) || state.players[0]);
  if (newCurrent) {
    const newCurrentId = newCurrent.player_id;
    if (viewingPlayerId === null || viewingPlayerId === undefined) {
      viewingPlayerId = newCurrentId;
      _lastKnownCurrentPlayerId = newCurrentId;
    } else if (_lastKnownCurrentPlayerId !== newCurrentId) {
      // Turn changed Ã¢â‚¬â€ switch view to the new current player
      viewingPlayerId = newCurrentId;
      _lastKnownCurrentPlayerId = newCurrentId;
    }
  }

  updateBoard();
  updatePlayerTabs();
  updatePlayerStats();
  updateEquipSummary();
  updateMovementHand();
  loadAndRenderAbilities();

  // Update turn banner (with night indicator)
  const p = state.players.find(x => x.is_current);
  if (p) {
    const nightTag = state.is_night ? ' Ã°Å¸Å’â„¢' : ' Ã¢Ëœâ‚¬';
    document.getElementById('turn-banner').textContent = `${p.hero_name || p.name}'s Turn Ã¢â‚¬â€ Tile ${p.position}${nightTag}`;
  }

  // Update log
  if (state.log) {
    const logEl = document.getElementById('turn-log');
    logEl.innerHTML = state.log.map(l => `<div class="log-entry">${l}</div>`).join('');
    logEl.scrollTop = logEl.scrollHeight;
  }

  // Handle winner
  if (state.game_status === 'WON' && state.winner !== null && state.winner !== undefined) {
    const winnerP = state.players.find(x => x.player_id === state.winner);
    document.getElementById('winner-title').textContent = `${winnerP?.hero_name || 'Someone'} Wins!`;
    document.getElementById('winner-text').textContent = 'Congratulations!';
    document.getElementById('winner-modal').classList.remove('hidden');
    _checkAchievement('victory');
    if (state.players.length > 1) _checkAchievement('champion');
  }
  // Check miniboss achievements
  const curP = state.players.find(p => p.is_current);
  if (curP && curP.miniboss1_defeated) _checkAchievement('a_strong_start');
  if (curP && curP.miniboss2_defeated) _checkAchievement('getting_closer');

  // Phase-specific triggers are handled by the callers (beginMove, resolveOffer, etc.)
  // applyState only updates UI state
}

// ================================================================
// MINION MANAGEMENT
// ================================================================
async function releaseMonster(idx) {
  const resp = await fetch('/games/werblers/api/release_monster', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({monster_index: idx}),
  });
  const data = await resp.json();
  if (data.state) { gameState = data.state; applyState(data.state); }
}

async function summonMonster(idx) {
  const resp = await fetch('/games/werblers/api/summon_monster', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({monster_index: idx}),
  });
  const data = await resp.json();
  if (data.state) { gameState = data.state; applyState(data.state); }
}

// ================================================================
// DEVICE ID
// ================================================================
function _initDeviceId() {
  let id = localStorage.getItem('werblers_device_id');
  if (!id) {
    id = 'dev_' + crypto.randomUUID();
    localStorage.setItem('werblers_device_id', id);
  }
  _deviceId = id;
}

// ================================================================
// PROFILE SCREEN
// ================================================================
async function _loadProfileScreen() {
  const resp = await fetch('/games/werblers/api/profiles?device_id=' + encodeURIComponent(_deviceId));
  const data = await resp.json();
  const profiles = data.profiles || [];
  if (profiles.length === 0) {
    document.getElementById('profile-create-section').classList.remove('hidden');
    document.getElementById('profile-select-section').classList.add('hidden');
  } else {
    _renderProfileList(profiles);
    document.getElementById('profile-create-section').classList.add('hidden');
    document.getElementById('profile-select-section').classList.remove('hidden');
  }
  document.getElementById('profile-screen').classList.remove('hidden');
  document.getElementById('main-menu-screen').classList.add('hidden');
  document.getElementById('setup-screen-1').classList.add('hidden');
  document.getElementById('setup-screen-2').classList.add('hidden');
  document.getElementById('game-screen').classList.add('hidden');
}

function _renderProfileList(profiles) {
  const list = document.getElementById('profile-list');
  list.innerHTML = '';
  for (const p of profiles) {
    const btn = document.createElement('button');
    btn.className = 'btn-primary btn-lg btn-profile';
    btn.textContent = p.name;
    btn.addEventListener('click', () => selectProfile(p));
    list.appendChild(btn);
  }
}

function showCreateProfile() {
  document.getElementById('profile-create-section').classList.remove('hidden');
  document.getElementById('profile-select-section').classList.add('hidden');
}

async function createProfile() {
  const nameInput = document.getElementById('profile-name-input');
  const name = nameInput.value.trim();
  if (!name) return;
  const resp = await fetch('/games/werblers/api/profiles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_id: _deviceId, name }),
  });
  const data = await resp.json();
  nameInput.value = '';
  selectProfile(data.profile);
}

function selectProfile(profile) {
  _profileId = profile.id;
  _profileName = profile.name;
  document.getElementById('profile-screen').classList.add('hidden');
  document.getElementById('main-menu-screen').classList.remove('hidden');
  document.getElementById('menu-profile-name').textContent = 'Welcome, ' + _profileName + '!';
}

function changeProfile() {
  _profileId = null;
  _profileName = '';
  _loadProfileScreen();
}

function exitGame() {
  _profileId = null;
  _profileName = '';
  _loadProfileScreen();
}

// ================================================================
// MAIN MENU
// ================================================================
function goToNewGame() {
  document.getElementById('main-menu-screen').classList.add('hidden');
  document.getElementById('setup-screen-1').classList.remove('hidden');
}

// ================================================================
// SAVE / LOAD MODAL
// ================================================================
function openSaveLoadModal() {
  _saveLoadMode = 'save';
  _selectedSlot = null;
  document.getElementById('saveload-modal').classList.remove('hidden');
  _refreshSaveSlots();
}
function closeSaveLoadModal() { document.getElementById('saveload-modal').classList.add('hidden'); }

function setSaveLoadMode(mode) {
  _saveLoadMode = mode;
  _selectedSlot = null;
  document.querySelectorAll('.saveload-tab').forEach(t => t.classList.toggle('active', t.dataset.mode === mode));
  const btn = document.getElementById('saveload-confirm-btn');
  btn.textContent = mode === 'save' ? 'Save' : 'Load';
  btn.disabled = true;
  _refreshSaveSlots();
}

async function _refreshSaveSlots() {
  if (!_profileId) return;
  const resp = await fetch('/games/werblers/api/saves?profile_id=' + _profileId);
  const data = await resp.json();
  _savesData = data.saves || [];
  _renderSaveSlots('saveload-slots');
}

function _renderSaveSlots(containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  const isMenuLoad = containerId === 'menu-load-slots';
  for (let i = 1; i <= 10; i++) {
    const save = _savesData.find(s => s.slot_number === i);
    const slot = document.createElement('div');
    slot.className = 'save-slot' + (_selectedSlot === i ? ' selected' : '');
    if (save) {
      const dt = new Date(save.saved_at);
      const timeStr = dt.toLocaleString();
      slot.innerHTML = `<span class="slot-label">Slot ${i}</span>
        <span class="slot-info">${save.hero_names} Ã‚Â· ${save.num_players}P Ã‚Â· Turn ${save.turn_number}</span>
        <span class="slot-time">${timeStr}</span>`;
    } else {
      slot.innerHTML = `<span class="slot-label">Slot ${i}</span><span class="slot-info slot-empty">Ã¢â‚¬â€ Empty Ã¢â‚¬â€</span>`;
    }
    slot.addEventListener('click', () => {
      _selectedSlot = i;
      const btnId = isMenuLoad ? 'menu-load-btn' : 'saveload-confirm-btn';
      const btn = document.getElementById(btnId);
      if ((_saveLoadMode === 'load' || isMenuLoad) && !save) { btn.disabled = true; } else { btn.disabled = false; }
      container.querySelectorAll('.save-slot').forEach(s => s.classList.remove('selected'));
      slot.classList.add('selected');
    });
    container.appendChild(slot);
  }
}

async function confirmSaveLoad() {
  if (_selectedSlot === null) return;
  if (_saveLoadMode === 'save') {
    const existing = _savesData.find(s => s.slot_number === _selectedSlot);
    if (existing) { document.getElementById('overwrite-modal').classList.remove('hidden'); return; }
    await _doSave();
  } else {
    await _doLoad();
  }
}
async function confirmOverwrite(yes) {
  document.getElementById('overwrite-modal').classList.add('hidden');
  if (yes) await _doSave();
}
async function _doSave() {
  const resp = await fetch('/games/werblers/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: _profileId, slot_number: _selectedSlot }),
  });
  const data = await resp.json();
  if (data.ok) closeSaveLoadModal();
}
async function _doLoad() {
  const resp = await fetch('/games/werblers/api/load', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: _profileId, slot_number: _selectedSlot }),
  });
  const data = await resp.json();
  if (data.ok) {
    closeSaveLoadModal();
    document.getElementById('setup-screen-1').classList.add('hidden');
    document.getElementById('setup-screen-2').classList.add('hidden');
    document.getElementById('main-menu-screen').classList.add('hidden');
    document.getElementById('profile-screen').classList.add('hidden');
    document.getElementById('game-screen').classList.remove('hidden');
    _boardBuilt = false;
    gameState = data.state;
    viewingPlayerId = data.state.current_player_id;
    buildBoard();
    applyState(data.state);
  }
}

// ================================================================
// LOAD FROM MAIN MENU
// ================================================================
async function openLoadFromMenu() {
  _selectedSlot = null;
  _saveLoadMode = 'load';
  const resp = await fetch('/games/werblers/api/saves?profile_id=' + _profileId);
  const data = await resp.json();
  _savesData = data.saves || [];
  _renderSaveSlots('menu-load-slots');
  document.getElementById('menu-load-modal').classList.remove('hidden');
}
function closeMenuLoadModal() { document.getElementById('menu-load-modal').classList.add('hidden'); }

async function menuLoadGame() {
  if (_selectedSlot === null) return;
  const resp = await fetch('/games/werblers/api/load', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: _profileId, slot_number: _selectedSlot }),
  });
  const data = await resp.json();
  if (data.ok) {
    closeMenuLoadModal();
    document.getElementById('main-menu-screen').classList.add('hidden');
    document.getElementById('game-screen').classList.remove('hidden');
    _boardBuilt = false;
    gameState = data.state;
    viewingPlayerId = data.state.current_player_id;
    buildBoard();
    applyState(data.state);
  }
}

// ================================================================
// ACHIEVEMENTS
// ================================================================
async function openAchievementsModal() {
  if (!_profileId) return;
  const resp = await fetch('/games/werblers/api/achievements?profile_id=' + _profileId);
  const data = await resp.json();
  const list = document.getElementById('achievements-list');
  list.innerHTML = '';
  for (const a of (data.achievements || [])) {
    const row = document.createElement('div');
    row.className = 'achievement-row' + (a.achieved ? ' achieved' : '');
    row.innerHTML = `<span class="achievement-check">${a.achieved ? 'Ã¢Å“â€¦' : 'Ã¢Â¬Å“'}</span>
                     <span class="achievement-desc">${a.description}</span>`;
    list.appendChild(row);
  }
  document.getElementById('achievements-modal').classList.remove('hidden');
}
function closeAchievementsModal() { document.getElementById('achievements-modal').classList.add('hidden'); }

async function _checkAchievement(key) {
  if (!_profileId) return;
  if (_achievementsTriggeredThisSession.has(key)) return;
  _achievementsTriggeredThisSession.add(key);
  const resp = await fetch('/games/werblers/api/achievements', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: _profileId, achievement: key }),
  });
  const data = await resp.json();
  if (data.newly_granted) {
    const ach = (data.achievements || []).find(a => a.key === key);
    const desc = ach ? ach.description : key;
    _pendingAchievements.push(desc);
    _showNextAchievementPopup();
    const totalV = (data.achievements || []).find(a => a.key === 'total_victory' && a.achieved);
    if (totalV && !_achievementsTriggeredThisSession.has('total_victory_shown')) {
      _achievementsTriggeredThisSession.add('total_victory_shown');
      const tvDesc = (data.achievements || []).find(a => a.key === 'total_victory');
      if (tvDesc) _pendingAchievements.push(tvDesc.description);
    }
  }
}

function _showNextAchievementPopup() {
  if (_achievementPopupActive || _pendingAchievements.length === 0) return;
  _achievementPopupActive = true;
  const desc = _pendingAchievements.shift();
  document.getElementById('achievement-popup-name').textContent = desc;
  document.getElementById('achievement-popup').classList.remove('hidden');
}

function dismissAchievementPopup() {
  document.getElementById('achievement-popup').classList.add('hidden');
  _achievementPopupActive = false;
  _showNextAchievementPopup();
}
