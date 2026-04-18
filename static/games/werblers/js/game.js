// ================================================================ GLOBAL STATE
let gameState   = null;
let viewingPlayerId = 0;
let numPlayers  = 1;
let heroSelections = {};   // slot (int) -> heroId string
let heroData    = [];      // hero definitions from server
let heroAnimMap = {};      // heroId -> {general, victory, defeat}
// Ability toggles collected before playing a card
let abilityChoices = {};   // { ability_id: true | {args} }

// ================================================================ PROFILE / SAVE / ACHIEVEMENT STATE
let _deviceId    = '';
let _profileId   = null;
let _profileName = '';
let _saveLoadMode = 'save';  // 'save' or 'load'
let _selectedSlot = null;
let _savesData    = [];       // cached save slot list
let _pendingAchievements = []; // queue for popups
let _achievementPopupActive = false;

// Werbler win counter stored client-side per session (for "this_is_easy" / "champion" tracking)
let _werblerWins = 0;
let _multiplayerWins = 0;

// ================================================================ MUSIC
const _music = { audio: null, current: null, masterVol: 0.8, musicVol: 0.8 };

function _musicVol() { return Math.min(1, _music.masterVol * _music.musicVol); }

function playMusic(name) {
  if (_music.current === name) return;
  if (_music.audio) { _music.audio.pause(); _music.audio = null; }
  _music.current = name;
  const audio = new Audio('/games/werblers/music/' + encodeURIComponent(name));
  audio.loop = true;
  audio.volume = _musicVol();
  audio.play().catch(() => {});
  _music.audio = audio;
}

function _updateAudioVolume() {
  if (_music.audio) _music.audio.volume = _musicVol();
}

function _tierMusic(pos) {
  if (pos <= 30) return 'Tier 1 Music.wav';
  if (pos <= 60) return 'Tier 2 Music.wav';
  return 'Tier-3 Music.wav';
}

function _resumeTierMusic(state) {
  const s = state || gameState;
  if (!s) { playMusic('Theme Music.wav'); return; }
  const p = s.players.find(x => x.is_current) || s.players[0];
  if (p) playMusic(_tierMusic(p.position));
}

// ================================================================ OPTIONS
function openOptionsModal()  { document.getElementById('options-modal').classList.remove('hidden'); }
function closeOptionsModal() { document.getElementById('options-modal').classList.add('hidden'); }

function setMasterVolume(val) {
  _music.masterVol = parseInt(val) / 100;
  document.getElementById('vol-master-val').textContent = val;
  _updateAudioVolume();
}
function setMusicVolume(val) {
  _music.musicVol = parseInt(val) / 100;
  document.getElementById('vol-music-val').textContent = val;
  _updateAudioVolume();
}
// ================================================================ SETUP
async function initSetup() {
  playMusic('Theme Music.wav');
  // Browsers block autoplay before a user gesture. Retry on first interaction.
  document.addEventListener('click', function _unlockAudio() {
    document.removeEventListener('click', _unlockAudio, true);
    if (_music.audio && _music.audio.paused) _music.audio.play().catch(() => {});
  }, true);
  const resp = await fetch('/games/werblers/api/heroes');
  heroData = await resp.json();
  heroAnimMap = {};
  for (const h of heroData) {
    if (h.animations) heroAnimMap[h.id] = h.animations;
  }
  // Initialise device ID (stored in localStorage)
  _initDeviceId();
  // Check for existing profiles
  await _loadProfileScreen();
}
function setNumPlayers(n) {
  numPlayers = n;
  document.querySelectorAll('.count-btn').forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.dataset.n) === n);
  });
  for (let i = n; i < 4; i++) delete heroSelections[i];
  renderHeroSelectors();
}
function renderHeroSelectors() {
  const container = document.getElementById('hero-selectors');
  container.innerHTML = '';
  for (let slot = 0; slot < numPlayers; slot++) {
    const slotDiv = document.createElement('div');
    slotDiv.className = 'hero-slot';
    const label = document.createElement('div');
    label.className = 'slot-label';
    label.textContent = numPlayers > 1 ? `Player ${slot + 1}` : 'Choose Your Hero';
    slotDiv.appendChild(label);
    const cardRow = document.createElement('div');
    cardRow.className = 'hero-cards-row';
    for (const hero of heroData) {
      const takenByOther = Object.entries(heroSelections)
        .some(([s, id]) => parseInt(s) !== slot && id === hero.id);
      const isSelected = heroSelections[slot] === hero.id;
      const card = document.createElement('div');
      card.className = 'hero-card-option'
        + (isSelected   ? ' selected' : '')
        + (takenByOther ? ' taken'    : '');
      const img = document.createElement('img');
      img.src = `/games/werblers/images/${hero.card_image}`;
      img.alt = hero.name;
      const nameEl = document.createElement('span');
      nameEl.className = 'hero-option-name';
      nameEl.textContent = hero.name;
      card.appendChild(img);
      card.appendChild(nameEl);
      if (!takenByOther) {
        // Click card: select hero and play animation
        card.addEventListener('click', () => {
          heroSelections[slot] = hero.id;
          renderHeroSelectors();
          checkStartEnabled();
          _showHeroAnimation(hero.id, 'general');
        });
        // Click image only: zoom the card (no animation)
        img.title = 'Click to zoom';
        img.style.cursor = 'zoom-in';
        img.addEventListener('click', (e) => {
          e.stopPropagation();
          heroSelections[slot] = hero.id;
          renderHeroSelectors();
          checkStartEnabled();
          zoomCard(`/games/werblers/images/${hero.card_image}`);
        });
      }
      cardRow.appendChild(card);
    }
    slotDiv.appendChild(cardRow);
    container.appendChild(slotDiv);
  }
  checkStartEnabled();
}
function checkStartEnabled() {
  let ok = true;
  for (let i = 0; i < numPlayers; i++) if (!heroSelections[i]) { ok = false; break; }
  document.getElementById('start-btn').disabled = !ok;
}
async function startGame() {
  const heroIds = [];
  for (let i = 0; i < numPlayers; i++) heroIds.push(heroSelections[i]);
  // Stop any hero animation currently playing
  const existingPanel = document.getElementById('hero-anim-panel');
  if (existingPanel) existingPanel.remove();
  const resp = await fetch('/games/werblers/api/new_game', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hero_ids: heroIds }),
  });
  const data = await resp.json();
  document.getElementById('setup-screen').classList.add('hidden');
  document.getElementById('game-screen').classList.remove('hidden');
  document.getElementById('game-side-buttons').classList.remove('hidden');
  viewingPlayerId = data.state.current_player_id;
  applyState(data.state);
  _resumeTierMusic(data.state);
  await loadAndRenderAbilities();
}
// ================================================================ BOARD
function tileToGrid(n) {
  const rowFromBottom = Math.floor((n - 1) / 10);
  const colInRow      = (n - 1) % 10;
  const row = 8 - rowFromBottom;
  const col = rowFromBottom % 2 === 0 ? colInRow : 9 - colInRow;
  return { row, col };
}
function tileLevel(n) {
  if (n <= 30) return 1;
  if (n <= 60) return 2;
  return 3;
}
let _boardBuilt = false;
const _tileEls  = {};
function buildBoard() {
  if (_boardBuilt) return;
  const grid = document.getElementById('board-grid');
  grid.innerHTML = '';
  for (let n = 1; n <= 90; n++) {
    const { row, col } = tileToGrid(n);
    const div = document.createElement('div');
    div.className = `tile level-${tileLevel(n)}`;
    div.style.gridRow    = row + 1;
    div.style.gridColumn = col + 1;
    div.dataset.index = n;
    const img = document.createElement('img');
    img.className = 'tile-bg';
    img.alt = `Tile ${n}`;
    div.appendChild(img);
    const numLabel = document.createElement('span');
    numLabel.className = 'tile-number';
    numLabel.textContent = n === 1 ? 'Start' : n;
    div.appendChild(numLabel);
    const tokenArea = document.createElement('div');
    tokenArea.className = 'token-area';
    div.appendChild(tokenArea);
    grid.appendChild(div);
    _tileEls[n] = div;
  }
  _boardBuilt = true;
}
function updateBoard(state) {
  buildBoard();
  // Determine miniboss defeat flags for the currently-viewed player
  const viewP = state.players.find(x => x.player_id === viewingPlayerId) || state.players[0];
  const mb1Done = viewP ? viewP.miniboss1_defeated : false;
  const mb2Done = viewP ? viewP.miniboss2_defeated : false;
  for (const tile of state.board) {
    const el = _tileEls[tile.index];
    if (!el) continue;
    let img = tile.image;
    // Override miniboss tile image per-player
    if (tile.image_defeated) {
      const isDefeated = (tile.index === 30 && mb1Done) || (tile.index === 60 && mb2Done);
      if (isDefeated) img = tile.image_defeated;
    }
    el.querySelector('img.tile-bg').src = `/games/werblers/images/${img}`;
  }
  for (let n = 1; n <= 90; n++) {
    _tileEls[n].querySelector('.token-area').innerHTML = '';
  }
  const byPos = {};
  for (const p of state.players) {
    (byPos[p.position] = byPos[p.position] || []).push(p);
  }
  for (const [posStr, players] of Object.entries(byPos)) {
    const pos = parseInt(posStr);
    const tileEl = _tileEls[pos];
    if (!tileEl) continue;
    const sorted = [...players].sort((a, b) => {
      if (a.is_current) return 1;
      if (b.is_current) return -1;
      return a.player_id - b.player_id;
    });
    const tokenArea = tileEl.querySelector('.token-area');
    sorted.forEach((p, stackIdx) => {
      if (!p.token_image) return;
      const img = document.createElement('img');
      img.className = 'player-token' + (p.is_current ? ' current-player-token' : '');
      img.src   = `/games/werblers/images/${p.token_image}`;
      img.alt   = p.name;
      img.title = p.name;
      img.style.right  = `${4 + stackIdx * 8}px`;
      img.style.bottom = `${4 + stackIdx * 8}px`;
      img.style.zIndex = stackIdx + 10;
      tokenArea.appendChild(img);
    });
  }
  const timeEl = document.getElementById('time-indicator');
  if (state.is_night) {
    timeEl.textContent = '\uD83C\uDF19 Night';
    timeEl.className = 'night';
  } else {
    timeEl.textContent = '\u2600 Day';
    timeEl.className = 'day';
  }
}
// ================================================================ PLAYER TABS
function updatePlayerTabs(state) {
  const tabs = document.getElementById('player-tabs');
  tabs.innerHTML = '';
  for (const p of state.players) {
    const btn = document.createElement('button');
    btn.className = 'tab-btn'
      + (p.player_id === viewingPlayerId ? ' active' : '')
      + (p.is_current ? ' current-turn' : '');
    btn.textContent = p.name;
    btn.addEventListener('click', () => {
      viewingPlayerId = p.player_id;
      updatePlayerTabs(state);
      updatePlayerStats(state);
      updateMovementSection(state);
      updateBoard(state);
      renderPlayerSheet(state);
    });
    tabs.appendChild(btn);
  }
}
// ================================================================ TOKEN IMAGES
function tokenBadges(tokens) {
  if (!tokens) return '';
  const img = tokens > 0 ? '+1 Token.png' : '-1 Token.png';
  const count = Math.abs(tokens);
  let html = '';
  for (let i = 0; i < Math.min(count, 6); i++) {
    html += `<img class="str-token" src="/games/werblers/images/Assorted UI Images/${img}" title="${tokens > 0 ? '+' : ''}${tokens} Str" alt="">`;
  }
  if (count > 6) html += `<span class="token-overflow">x${count}</span>`;
  return html;
}
function renderItemRow(item) {
  const badges = tokenBadges(item.tokens);
  const img = item.card_image ? ` data-card-image="/games/werblers/images/${item.card_image}"` : '';
  return `<div class="stat-item has-card-preview"${img}>${item.name}${badges ? ' ' + badges : ''}</div>`;
}
function renderPackItemRow(item, packIndex, isCurrentViewing, canUseOverworld) {
  const badges = tokenBadges(item.tokens);
  const img = item.card_image ? ` data-card-image="/games/werblers/images/${item.card_image}"` : '';
  let actions = '';
  if (item.is_consumable && canUseOverworld) {
    // Consumable pack item — show Use button instead of Equip
    actions = ` <button class="btn-tiny btn-equip-pack" onclick="usePackConsumable(${packIndex})">Use</button>`;
  } else if (isCurrentViewing && !item.is_consumable) {
    actions = ` <button class="btn-tiny btn-equip-pack" onclick="equipFromPack(${packIndex})">Equip</button>`;
  }
  return `<div class="stat-item has-card-preview"${img}>${item.name}${badges ? ' ' + badges : ''}${actions}</div>`;
}
function renderTraitRow(t) {
  const badges = tokenBadges(t.tokens);
  const desc = t.description ? ` data-tc-desc="${t.description.replace(/"/g, '&quot;')}"` : '';
  return `<div class="stat-item trait-item tc-hoverable" data-tc-name="${t.name}"${desc}>${t.name}${badges ? ' ' + badges : ''}</div>`;
}
function renderCurseRow(c) {
  const badges = tokenBadges(c.tokens);
  const desc = c.description ? ` data-tc-desc="${c.description.replace(/"/g, '&quot;')}"` : '';
  return `<div class="stat-item curse-item tc-hoverable" data-tc-name="${c.name}"${desc}>${c.name}${badges ? ' ' + badges : ''}</div>`;
}
// ================================================================ PLAYER STATS
function updatePlayerStats(state) {
  const p = state.players.find(x => x.player_id === viewingPlayerId) || state.players[0];
  if (!p) return;
  const sections = [];
  const equip = [
    ...p.helmets.map(i    => renderItemRow(i)),
    ...p.chest_armor.map(i => renderItemRow(i)),
    ...p.leg_armor.map(i  => renderItemRow(i)),
    ...p.weapons.map(i    => renderItemRow(i)),
  ];
  if (equip.length) sections.push(statGroup('Equipped', equip.join('')));
  const isCurrentViewing = p.player_id === state.current_player_id && state.game_status === 'IN_PROGRESS' && !state.has_pending_offer;
  const canUseOverworld = isCurrentViewing && !state.has_pending_combat;
  const packRows = [
    ...p.pack.map((item, idx)    => renderPackItemRow(item, idx, isCurrentViewing, canUseOverworld)),
    ...p.consumables.map((c, i) => {
      const imgAttr = c.card_image ? ` data-card-image="/games/werblers/images/${c.card_image}"` : '';
      // Left-click on any consumable when it's the current player's overworld turn
      const clickAttr = canUseOverworld ? ` onclick="promptUseConsumable(${i})" title="Click to use"` : '';
      const clickCls  = canUseOverworld ? ' consumable-clickable' : '';
      return `<div class="stat-item has-card-preview${clickCls}"${imgAttr}${clickAttr}>🧪 ${c.name}</div>`;
    }),
    ...p.captured_monsters.map((m, i) => {
      const clickAttr = canUseOverworld ? ` onclick="summonCapturedMonster(${i})" title="Click to summon and fight"` : '';
      const clickCls  = canUseOverworld ? ' consumable-clickable' : '';
      return `<div class="stat-item has-card-preview${clickCls}" data-card-image="/games/werblers/images/${m.card_image}"${clickAttr}>🐾 ${m.name} (captured)</div>`;
    }),
  ];
  const used = p.pack.length + p.consumables.length + p.captured_monsters.length;
  if (used > 0) sections.push(statGroup(`Pack (${used}/${p.pack_size})`, packRows.join('')));
  if (p.traits.length) {
    sections.push(statGroup('Traits', p.traits.map(t => renderTraitRow(t)).join(''), 'trait-title'));
  }
  if (p.curses.length) {
    sections.push(statGroup('Curses', p.curses.map(c => renderCurseRow(c)).join(''), 'curse-title'));
  }
  const bosses = [
    p.miniboss1_defeated ? '<span class="boss-done">MB1 done</span>' : '',
    p.miniboss2_defeated ? '<span class="boss-done">MB2 done</span>' : '',
  ].filter(Boolean).join(' ');
  document.getElementById('player-stats').innerHTML = `
    <div class="player-header">
      <div class="player-name-str">
        <span class="player-name">${p.name}</span>
        <span class="player-str" title="${_playerStrBreakdown(p).replace(/"/g, '&quot;')}" style="cursor:help">STR ${p.strength}</span>
      </div>
      <div class="player-pos">Tile ${p.position}</div>
      ${bosses ? `<div class="boss-status">${bosses}</div>` : ''}
    </div>
    <div class="stats-body">
      ${sections.join('') || '<div class="stat-empty">No items yet.</div>'}
    </div>`;
  attachCardClickZoom(document.getElementById('player-stats'));
}
function statGroup(title, rowsHtml, titleClass = '') {
  return `<div class="stat-group">
    <div class="stat-group-title ${titleClass}">${title}</div>
    ${rowsHtml}
  </div>`;
}
// ================================================================ EQUIP FROM PACK
let _occupiedSlotPackIndex = -1;

async function equipFromPack(packIndex) {
  const resp = await fetch('/games/werblers/api/equip_from_pack', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pack_index: packIndex }),
  });
  const data = await resp.json();
  if (data.error) {
    if (data.error === 'multi_displace' && data.displaced_items) {
      _showMultiDisplaceModal(packIndex, data.displaced_items, data.pack_slots_free);
      return;
    }
    if (data.error.includes('no free slot') && gameState) {
      const p = gameState.players.find(pl => pl.is_current);
      const item = p && p.pack[packIndex];
      if (item) {
        const slotMap = { helmet: p.helmets, chest: p.chest_armor, legs: p.leg_armor, weapon: p.weapons };
        const equipped = slotMap[item.slot] || [];
        const equippedItem = equipped[0] || null;
        _showOccupiedSlotModal(packIndex, item, equippedItem, p.pack_slots_free);
        return;
      }
    }
    alert(data.error);
    return;
  }
  applyState(data.state);
}

function _showOccupiedSlotModal(packIndex, newItem, equippedItem, packSlotsFree) {
  _occupiedSlotPackIndex = packIndex;
  const modal = document.getElementById('occupied-slot-modal');
  const desc  = modal.querySelector('.modal-desc');
  const cardOf = (item, label) => {
    if (!item) return '';
    const src = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
    const img = src ? `<img class="occupied-slot-card-img" src="${src}" onclick="zoomCard(this.src)" onerror="this.style.display='none'">` : '';
    return `<div class="occupied-slot-card-wrap">
      <div class="occupied-slot-card-label">${label}</div>
      ${img || `<div class="no-card-placeholder">${item.name}</div>`}
    </div>`;
  };
  desc.innerHTML = `
    <div class="occupied-slot-cards">
      ${cardOf(equippedItem, 'Currently Equipped')}
      <div class="occupied-slot-arrow">&rarr;</div>
      ${cardOf(newItem, 'Replacing With')}
    </div>`;
  const toPackBtn = modal.querySelector('button[onclick="_occupiedSlotAction(\'to_pack\')"]');
  if (toPackBtn && packSlotsFree <= 0) toPackBtn.textContent = 'Move to Pack (full — choose discard)';
  modal.classList.remove('hidden');
}

async function _occupiedSlotAction(action, extraParams) {
  document.getElementById('occupied-slot-modal').classList.add('hidden');
  if (action === 'cancel' || _occupiedSlotPackIndex < 0) return;
  const body = { pack_index: _occupiedSlotPackIndex, force: action !== 'cancel', to_pack: action === 'to_pack' };
  if (extraParams) Object.assign(body, extraParams);
  const savedPackIndex = _occupiedSlotPackIndex;
  _occupiedSlotPackIndex = -1;
  const resp = await fetch('/games/werblers/api/equip_from_pack', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (data.error === 'multi_displace' && data.displaced_items) {
    // 2H weapon needs multiple displacements — switch to the multi-modal flow
    _showMultiDisplaceModal(savedPackIndex, data.displaced_items, data.pack_slots_free);
    return;
  }
  if (data.error === 'pack_full' && data.pack) {
    // Show pack discard choice, then retry with discard_pack_index
    _showEquipPackDiscardChoice(data.pack, savedPackIndex);
    return;
  }
  if (data.error) { alert(data.error); return; }
  applyState(data.state);
}

function _showEquipPackDiscardChoice(packItems, origPackIndex) {
  const overlay = document.createElement('div');
  overlay.id = 'equip-pack-discard-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:2000;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center';
  const box = document.createElement('div');
  box.style.cssText = 'background:var(--card-bg,#1a1a2e);border:1px solid var(--border,#333);border-radius:12px;padding:20px 24px;max-width:480px;text-align:center';
  box.innerHTML = `<div style="font-family:'Cinzel',serif;font-size:14px;color:var(--gold,#c9a84c);margin-bottom:12px">Pack Full</div>
    <div style="font-size:12px;color:var(--text,#e0e0e0);margin-bottom:16px">Choose an item to discard from your pack to make room:</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center">${packItems.map((p, i) => {
      const img = p.card_image ? `<img src="/games/werblers/images/${p.card_image}" style="width:70px;border-radius:4px;display:block">` : '';
      return `<div class="rake-equip-btn" style="cursor:pointer" onclick="window._confirmEquipPackDiscard(${i})">
        ${img}
        <div style="font-size:10px;color:var(--text,#e0e0e0);margin-top:4px;max-width:80px;word-break:break-word">${p.name}</div>
      </div>`;
    }).join('')}</div>
    <div style="margin-top:16px"><button class="btn-secondary" onclick="window._cancelEquipPackDiscard()">Cancel</button></div>`;
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  window._confirmEquipPackDiscard = async (dpi) => {
    overlay.remove();
    _occupiedSlotPackIndex = origPackIndex;
    await _occupiedSlotAction('to_pack', { discard_pack_index: dpi });
  };
  window._cancelEquipPackDiscard = () => overlay.remove();
}

// Multi-displace modal (for 2H weapons replacing multiple equipped items)
async function _showMultiDisplaceModal(packIndex, displacedItems, packSlotsFree) {
  const actions = [];
  let slotsAvailable = packSlotsFree;

  for (let i = 0; i < displacedItems.length; i++) {
    const item = displacedItems[i];
    const result = await new Promise(resolve => {
      const overlay = document.createElement('div');
      overlay.style.cssText = 'position:fixed;inset:0;z-index:2000;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center';
      const box = document.createElement('div');
      box.style.cssText = 'background:var(--card-bg,#1a1a2e);border:1px solid var(--border,#333);border-radius:12px;padding:20px 24px;max-width:400px;text-align:center';
      const img = item.card_image ? `<img src="/games/werblers/images/${item.card_image}" style="width:100px;border-radius:6px;display:block;margin:8px auto">` : '';
      const canPack = slotsAvailable > 0;
      box.innerHTML = `
        <div style="font-family:'Cinzel',serif;font-size:14px;color:var(--gold,#c9a84c);margin-bottom:8px">Displaced Item (${i+1}/${displacedItems.length})</div>
        <div style="font-size:12px;color:var(--text,#e0e0e0);margin-bottom:12px">${item.name} (+${item.strength_bonus} Str) must be removed to make room.</div>
        ${img}
        <div style="display:flex;gap:8px;justify-content:center;margin-top:16px">
          ${canPack ? `<button class="btn-secondary" id="md-pack-btn">Move to Pack</button>` : ''}
          <button class="btn-danger" id="md-discard-btn">Discard</button>
          <button class="btn-secondary" id="md-cancel-btn">Cancel</button>
        </div>`;
      overlay.appendChild(box);
      document.body.appendChild(overlay);
      const packBtn = box.querySelector('#md-pack-btn');
      if (packBtn) packBtn.addEventListener('click', () => { overlay.remove(); resolve({ action: 'to_pack' }); });
      box.querySelector('#md-discard-btn').addEventListener('click', () => { overlay.remove(); resolve({ action: 'discard' }); });
      box.querySelector('#md-cancel-btn').addEventListener('click', () => { overlay.remove(); resolve(null); });
    });

    if (result === null) return; // cancelled
    actions.push(result);
    if (result.action === 'to_pack') slotsAvailable--;
  }

  // Send all decisions to the server
  const resp = await fetch('/games/werblers/api/equip_from_pack', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pack_index: packIndex, force: true, displaced_actions: actions }),
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) { gameState = data.state; applyState(data.state); renderPlayerSheetFull(data.state); }
}

// ================================================================ ABILITIES
let _availableAbilities = [];
async function loadAndRenderAbilities() {
  if (!gameState || gameState.game_status !== 'IN_PROGRESS') return;
  const resp = await fetch('/games/werblers/api/get_abilities');
  const data = await resp.json();
  _availableAbilities = data.abilities || [];
  abilityChoices = {};
  renderAbilityPanel();
}
function renderAbilityPanel() {
  const section = document.getElementById('abilities-section');
  const isCurrentViewing = gameState && viewingPlayerId === gameState.current_player_id;
  if (!_availableAbilities.length || !isCurrentViewing) {
    section.classList.add('hidden');
    return;
  }
  section.classList.remove('hidden');
  const container = document.getElementById('abilities-list');
  container.innerHTML = '';
  for (const ab of _availableAbilities) {
    const timing = ab.timing === 'post_card' ? ' <span class="ability-timing">(auto after card)</span>' : '';
    const row = document.createElement('div');
    row.className = 'ability-row';
    const buildCheckRow = (inputExtra) => `
      <label class="ability-toggle">
        <input type="checkbox" class="ability-chk" data-id="${ab.id}" onchange="onAbilityCheck(this)">
        <span class="ability-label">${ab.label}${timing}</span>
      </label>
      <div class="ability-desc">${ab.description}</div>
      ${inputExtra}`;
    if (ab.type === 'toggle') {
      row.innerHTML = buildCheckRow('');
    } else if (ab.type === 'select_trait') {
      const opts = ab.traits.map((t, i) => `<option value="${i}">${t}</option>`).join('');
      row.innerHTML = buildCheckRow(`<select class="ability-select" data-id="${ab.id}" data-field="trait_index" onchange="onAbilitySelectField(this)">${opts}</select>`);
    } else if (ab.type === 'select_equip') {
      const opts = ab.equips.map((e, i) => `<option value="${i}">${e}</option>`).join('');
      row.innerHTML = buildCheckRow(`<select class="ability-select" data-id="${ab.id}" data-field="equip_index" onchange="onAbilitySelectField(this)">${opts}</select>`);
    } else if (ab.type === 'select_number') {
      const opts = ab.options.map(n => `<option value="${n}">Reduce by ${n}</option>`).join('');
      row.innerHTML = buildCheckRow(`<select class="ability-select" data-id="${ab.id}" data-field="reduction" data-int="1" onchange="onAbilitySelectField(this)">${opts}</select>`);
    } else if (ab.type === 'select_player_minion') {
      const opts = ab.targets.map(t => `<option value="${t.player_id}">${t.name}</option>`).join('');
      row.innerHTML = buildCheckRow(`<select class="ability-select" data-id="${ab.id}" data-field="target_player_id" onchange="onAbilitySelectField(this)">${opts}</select>`);
    } else if (ab.type === 'instant_select_curse') {
      const curses = ab.curses || [];
      if (curses.length === 1) {
        row.innerHTML = `
          <div class="ability-desc">${ab.description}</div>
          <button class="btn-primary ability-instant-btn" onclick="useEightLives(0)">Use: Remove "${curses[0]}"</button>`;
      } else {
        const opts = curses.map((c, i) => `<option value="${i}">${c}</option>`).join('');
        row.innerHTML = `
          <div class="ability-desc">${ab.description}</div>
          <div class="ability-instant-row">
            <select class="ability-select" id="eight-lives-curse-select">${opts}</select>
            <button class="btn-primary ability-instant-btn" onclick="useEightLives(parseInt(document.getElementById('eight-lives-curse-select').value))">Use Eight Lives</button>
          </div>`;
      }
    } else if (ab.type === 'activate') {
      const rawVal = ab.value || 0;
      row.innerHTML = `
        <div class="ability-desc">${ab.description}</div>
        <button class="btn-primary ability-activate-btn" onclick="activateWheelies(${rawVal})">&#x1F6FC; Use Wheelies!</button>`;
    }
    container.appendChild(row);
  }
}
function onAbilityCheck(el) {
  const id = el.dataset.id;
  const ab = _availableAbilities.find(a => a.id === id);
  if (!el.checked) { delete abilityChoices[id]; return; }
  if (ab && ab.type === 'toggle') {
    abilityChoices[id] = true;
  } else {
    // Initialise with current select value
    abilityChoices[id] = abilityChoices[id] || {};
    const sel = document.querySelector(`.ability-select[data-id="${id}"]`);
    if (sel) {
      const field = sel.dataset.field;
      const val = sel.dataset.int ? parseInt(sel.value) : sel.value;
      abilityChoices[id][field] = val;
    }
  }
}
function onAbilitySelectField(el) {
  const id    = el.dataset.id;
  const field = el.dataset.field;
  const val   = el.dataset.int ? parseInt(el.value) : el.value;
  if (abilityChoices[id] && typeof abilityChoices[id] === 'object') {
    abilityChoices[id][field] = val;
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
async function useEightLives(curseIndex) {
  const resp = await fetch('/games/werblers/api/use_eight_lives', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ curse_index: curseIndex }),
  });
  const data = await resp.json();
  if (data.state) { gameState = data.state; applyState(data.state); }
  await loadAndRenderAbilities();
}
// ================================================================ MOVEMENT SECTION
function updateMovementSection(state) {
  updateMovementHand(state);
  renderAbilityPanel();
}
function updateMovementHand(state) {
  const handDiv = document.getElementById('movement-hand');
  handDiv.innerHTML = '';
  const currentPlayer = state.players.find(p => p.is_current);
  const viewingCurrent = viewingPlayerId === state.current_player_id;
  // Flee (Fly, you dummy!) is now handled in the pre-fight battle scene.
  const fleeLbl = document.getElementById('flee-label');
  if (fleeLbl) {
    fleeLbl.classList.add('hidden');
    const tog = document.getElementById('flee-toggle');
    if (tog) tog.checked = false;
  }
  if (state.game_status !== 'IN_PROGRESS' || state.has_pending_offer) {
    handDiv.innerHTML = '<div class="hand-empty">Resolve the encounter first.</div>';
    return;
  }
  if (!viewingCurrent) {
    const name = currentPlayer ? currentPlayer.name : '?';
    handDiv.innerHTML = `<div class="hand-empty">It\'s ${name}\'s turn.</div>`;
    return;
  }
  const hand = currentPlayer ? currentPlayer.movement_hand : [];
  const heroBonus = currentPlayer ? (currentPlayer.movement_card_bonus || 0) : 0;
  if (!hand.length) {
    handDiv.innerHTML = '<div class="hand-empty">No cards in hand.</div>';
    return;
  }
  const hasYerAHare = currentPlayer && currentPlayer.curses &&
      currentPlayer.curses.some(c => c.effect_id === 'yer_a_hare');
  const hasBotched = currentPlayer && currentPlayer.curses &&
      currentPlayer.curses.some(c => c.effect_id === 'botched_circumcision');
  hand.forEach((val, idx) => {
    const dispVal = val + heroBonus;
    const imgVal = Math.min(Math.max(dispVal, 1), 5);
    const card = document.createElement('div');
    card.className = 'mv-card';
    card.title = `Move ${dispVal} tile${dispVal !== 1 ? 's' : ''} forward or backward`;
    card.innerHTML = `<img class="mv-card-img" src="/games/werblers/images/Movement/Movement Card ${imgVal}.png" alt="${dispVal}">`;
    // Botched Circumcision per-card banner
    if (hasBotched) {
      const banner = document.createElement('span');
      banner.className = 'mv-card-curse-banner';
      banner.textContent = '−1';
      banner.title = 'Botched Circumcision: −1 movement';
      banner.addEventListener('click', (e) => { e.stopPropagation(); alert('−1 movement from Botched Circumcision'); });
      card.appendChild(banner);
    }
    // Yer a Hare asterisk on 5s
    if (hasYerAHare && val === 5) {
      const ast = document.createElement('span');
      ast.className = 'mv-hare-asterisk';
      ast.textContent = '*';
      ast.title = "Yer a Hare, Wizard!: treated as 1";
      card.appendChild(ast);
    }
    card.addEventListener('click', () => promptDirection(idx, dispVal));
    handDiv.appendChild(card);
  });
  // Yer a Hare indicator
  if (hasYerAHare) {
    const hareNote = document.createElement('div');
    hareNote.className = 'mv-curse-badge mv-hare-note';
    hareNote.title = "Yer a Hare, Wizard!: 5 movement cards are treated as 1";
    hareNote.innerHTML = "*5's treated as 1's <span style=\"font-size:9px\">(Yer a Hare, Wizard)</span>";
    handDiv.prepend(hareNote);
  }
  // Botched Circumcision indicator
  if (currentPlayer && currentPlayer.curses &&
      currentPlayer.curses.some(c => c.effect_id === 'botched_circumcision')) {
    const badge = document.createElement('div');
    badge.className = 'mv-curse-badge';
    badge.title = 'Botched Circumcision: all movement cards −1';
    badge.textContent = '−1';
    handDiv.prepend(badge);
  }
}
// ================================================================ LOG
function updateLog(log) {
  const logDiv = document.getElementById('turn-log');
  logDiv.innerHTML = '';
  if (!log || !log.length) return;
  for (const line of log) {
    const div = document.createElement('div');
    div.className = 'log-line';
    if (line.startsWith('['))                      div.classList.add('log-header');
    else if (/win|defeat|victory|\uD83C\uDF89/i.test(line)) div.classList.add('log-win');
    else if (/lose|Curse|curse/i.test(line))       div.classList.add('log-lose');
    else if (line.startsWith('  '))                div.classList.add('log-indent');
    div.textContent = line;
    logDiv.appendChild(div);
  }
  logDiv.scrollTop = logDiv.scrollHeight;
}
// ================================================================ INTERACTIVE TURN FLOW
let _pendingCardIndex = null;
let _moveInFlight = false;

function promptDirection(cardIndex, cardValue) {
  // cardValue here is already the display value (raw + hero movement bonus)
  if (_moveInFlight) return;
  if (!gameState || gameState.game_status !== 'IN_PROGRESS') return;
  const p = gameState.players.find(x => x.is_current);
  if (!p) return;
  const fwdTile = Math.min(p.position + cardValue, 90);
  const bwdTile = Math.max(p.position - cardValue, 1);
  _pendingCardIndex = cardIndex;
  document.getElementById('direction-desc').textContent =
    `Card ${cardValue}: Forward to tile ${fwdTile} or Backward to tile ${bwdTile}?`;
  document.getElementById('direction-modal').classList.remove('hidden');
}

function confirmDirection(dir) {
  document.getElementById('direction-modal').classList.add('hidden');
  if (_pendingCardIndex === null) return;
  const idx = _pendingCardIndex;
  _pendingCardIndex = null;
  beginMove(idx, dir);
}

function cancelDirection() {
  document.getElementById('direction-modal').classList.add('hidden');
  _pendingCardIndex = null;
}

async function beginMove(cardIndex, direction = 'forward') {
  if (_moveInFlight) return;
  if (!gameState || gameState.game_status !== 'IN_PROGRESS') return;
  _moveInFlight = true;
  try {
    const activated = Object.assign({}, abilityChoices);
    const resp = await fetch('/games/werblers/api/begin_move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_index: cardIndex, flee: false, activated, direction }),
    });
    if (!resp.ok) { console.error('begin_move failed', resp.status); return; }
    const data = await resp.json();
    if (!data.state) { console.error('begin_move: no state returned'); return; }
    viewingPlayerId = data.state.current_player_id;
    applyState(data.state);
    if (data.phase === 'combat') {
      playMusic('Battle Music.wav');
      showPreFightScene(data.combat_info, data.state);
      return;
    }
    if (data.combat_info) {
      playMusic('Battle Music.wav');
      showBattleScene(data.combat_info, data.state);
      return;
    }
    if (data.phase === 'charlie_work') {
      _showCharlieWorkDecision(data.level);
      return;
    }
    const ts = data.tile_scene || {};
    if (data.phase === 'done') {
      document.getElementById('battle-overlay').classList.add('hidden');
      _resumeTierMusic(data.state);
      if (ts.tile_type === 'BLANK') {
        showTileScene(ts, () => loadAndRenderAbilities());
      } else {
        await loadAndRenderAbilities();
      }
    } else if (data.phase === 'offer_chest') {
      _pendingOfferData = data.offer;
      showChestModal(data.offer, ts);
    } else if (data.phase === 'offer_shop') {
      _pendingOfferData = data.offer;
      showShopModal(data.offer, data.state, ts);
    } else if (data.phase === 'mystery') {
      showMysteryEventModal(data.mystery_event, data.state);
    }
  } catch (err) {
    console.error('beginMove error:', err);
  } finally {
    _moveInFlight = false;
  }
}
// ================================================================ CHEST MODAL
let _pendingOfferData = null;
function _setOfferBackground(tileScene) {
  const modal = document.getElementById('offer-modal');
  if (tileScene && tileScene.background) {
    modal.style.background = `linear-gradient(rgba(0,0,0,0.78), rgba(0,0,0,0.78)), url('/games/werblers/images/${tileScene.background}') center/cover`;
  } else {
    modal.style.background = '';
  }
}
function showChestModal(offer, tileScene) {
  playMusic('Chest Music.wav');
  const modal = document.getElementById('offer-modal');
  const body  = document.getElementById('offer-modal-body');
  const item  = offer.items[0];
  _setOfferBackground(tileScene);
  const scavengerBtn = offer.has_scavenger
    ? `<button class="btn-secondary" onclick="scavengerSwap()">🔄 Scavenger: Swap</button>`
    : '';
  body.innerHTML = `
    <h2 class="offer-title">Found Chest</h2>
    <div class="offer-items">${renderOfferItemCard(item, 0, true)}</div>
    <div class="offer-actions">
      ${scavengerBtn}
      <button class="btn-primary" onclick="confirmChestTake()">Take It</button>
      <button class="btn-secondary" onclick="resolveOffer({take: false})">Leave It</button>
    </div>`;
  modal.classList.remove('hidden');
}
function confirmChestTake() {
  document.getElementById('offer-modal').classList.add('hidden');
  const item = _pendingOfferData.items[0];
  showInventoryPopup(item, (placement) => {
    if (placement.discard) { resolveOffer({ take: false }); }
    else { resolveOffer({ take: true, ...placement }); }
  });
}
let _shopSelectedIndex = 0;
function showShopModal(offer, state, tileScene) {
  playMusic('Shop Music.wav');
  _shopSelectedIndex = -1;
  const modal = document.getElementById('offer-modal');
  const body  = document.getElementById('offer-modal-body');
  _setOfferBackground(tileScene);
  body.innerHTML = `
    <h2 class="offer-title">Shop</h2>
    <p class="offer-sub">Choose one item to take — it's free!</p>
    <div class="offer-items shop-row">
      ${offer.items.map((it, i) => renderOfferItemCard(it, i, false)).join('')}
    </div>
    <div class="offer-actions">
      <button class="btn-primary" id="shop-confirm-btn" onclick="confirmShopTake()" disabled>
        Take It
      </button>
      <button class="btn-secondary" onclick="resolveOffer({take: false})">Leave Shop</button>
    </div>`;
  body.querySelectorAll('.offer-item-card').forEach(card => {
    card.addEventListener('click', () => {
      body.querySelectorAll('.offer-item-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      _shopSelectedIndex = parseInt(card.dataset.index);
      document.getElementById('shop-confirm-btn').disabled = false;
    });
  });
  modal.classList.remove('hidden');
}
function confirmShopTake() {
  if (_shopSelectedIndex < 0) return;
  const modal = document.getElementById('offer-modal');
  modal.classList.add('hidden');
  modal.style.background = '';
  const item = _pendingOfferData.items[_shopSelectedIndex];
  showInventoryPopup(item, (placement) => {
    if (placement.discard) { resolveOffer({ take: false, chosen_index: _shopSelectedIndex }); }
    else { resolveOffer({ chosen_index: _shopSelectedIndex, ...placement }); }
  });
}
function renderOfferItemCard(item, index, autoSelected) {
  const strSign = item.strength_bonus >= 0 ? '+' : '';
  const strText = item.strength_bonus !== 0 ? `${strSign}${item.strength_bonus} Str` : '';
  const imgHtml = item.card_image
    ? `<img class="offer-item-img" src="/games/werblers/images/${item.card_image}" alt="${item.name}" onclick="event.stopPropagation();zoomCard(this.src)">`
    : '';
  return `
    <div class="offer-item-card ${autoSelected ? 'selected' : ''}" data-index="${index}">
      ${imgHtml}
      <div class="offer-item-slot">${item.slot}</div>
      <div class="offer-item-name">${item.name}</div>
      <div class="offer-item-str">${strText}</div>
      ${item.tokens ? `<div class="offer-item-tokens">${tokenBadges(item.tokens)}</div>` : ''}
    </div>`;
}
// ================================================================ INVENTORY POPUP (player-sheet placement mode)
let _invState  = {};
let _invOnConfirm = null;
let _invPlacementItem = null;  // item currently being placed

function showInventoryPopup(item, onConfirm) {
  _invState          = {};
  _invOnConfirm      = onConfirm;
  _invPlacementItem  = item;
  // Open the player sheet in placement mode
  _playerSheetOpen   = true;
  if (gameState) renderPlayerSheetFull(gameState);
  document.getElementById('player-sheet-overlay').classList.remove('hidden');
}

function _finishPlacement(choices) {
  _invPlacementItem = null;
  _playerSheetOpen  = false;
  document.getElementById('player-sheet-overlay').classList.add('hidden');
  const cb = _invOnConfirm;
  _invOnConfirm = null;
  if (cb) cb(choices);
}

// Called when the player clicks an equip slot during placement mode.
function _psPlaceEquip() {
  _finishPlacement({ placement: 'equip' });
}

// Called when clicking on an occupied equip slot — show options modal.
function _psPlaceEquipDiscard(slotKey, idx) {
  const p = gameState.players.find(pl => pl.is_current);
  // Special case: placing a 2H weapon when both weapon slots are occupied
  if (slotKey === 'equip_weapon' && _invPlacementItem && _invPlacementItem.hands === 2 && (p.weapons || []).length >= 2) {
    _handle2HFullEquip(p.weapons[0], p.weapons[1], p);
    return;
  }
  const slotDataMap = { equip_helmet: p.helmets, equip_chest: p.chest_armor, equip_leg: p.leg_armor, equip_weapon: p.weapons };
  const existing = (slotDataMap[slotKey] || [])[idx];
  const name = existing ? existing.name : 'the current item';
  _showOccupiedSlotModal(name, slotKey, idx);
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

// Show a single "what to do with THIS weapon?" modal. Calls onChoice(action, packDiscardIdx, packFreeAfter).
function _show2HDisplaceModal(weapon, packFree, onChoice) {
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;z-index:2010;background:rgba(0,0,0,0.75);display:flex;align-items:center;justify-content:center';
  const box = document.createElement('div');
  box.style.cssText = 'background:var(--card-bg,#1a1a2e);border:1px solid var(--border,#444);border-radius:12px;padding:22px 26px;max-width:380px;text-align:center';
  const imgHtml = weapon.card_image
    ? `<img src="/games/werblers/images/${weapon.card_image}" style="width:90px;border-radius:6px;margin:0 auto 12px;display:block" onclick="event.stopPropagation();zoomCard(this.src)">`
    : '';
  box.innerHTML = `
    <div style="font-family:'Cinzel',serif;font-size:14px;color:var(--gold,#c9a84c);margin-bottom:10px">Equipping 2-Handed Weapon</div>
    ${imgHtml}
    <div style="font-size:13px;color:var(--text,#e0e0e0);margin-bottom:18px">What should happen to <b>${weapon.name}</b>?</div>
    <div style="display:flex;gap:10px;justify-content:center">
      <button class="btn-primary" id="btn-2h-pack">${packFree > 0 ? 'Move to Pack' : 'Move to Pack (full)'}</button>
      <button class="btn-secondary btn-danger-hover" id="btn-2h-discard">Discard</button>
    </div>`;
  overlay.appendChild(box);
  document.body.appendChild(overlay);

  box.querySelector('#btn-2h-discard').onclick = () => {
    overlay.remove();
    onChoice('discard', -1, packFree);
  };
  box.querySelector('#btn-2h-pack').onclick = () => {
    if (packFree > 0) {
      overlay.remove();
      onChoice('swap', -1, packFree - 1);
    } else {
      // Pack is full — pick which pack item to discard to make room
      overlay.remove();
      _show2HPackDiscardChoice(weapon, (pdi) => onChoice('swap', pdi, 0));
    }
  };
}

// Show pack-item-to-discard picker when pack is full during 2H displacement.
function _show2HPackDiscardChoice(weapon, onChoice) {
  const p = gameState.players.find(pl => pl.is_current);
  const packItems = [
    ...(p.pack || []).map((item, i) => ({ name: item.name, card_image: item.card_image, idx: i })),
    ...(p.consumables || []).map((item, i) => ({ name: item.name, card_image: item.card_image, idx: (p.pack || []).length + i })),
    ...(p.captured_monsters || []).map((item, i) => ({ name: item.name, card_image: item.card_image, idx: (p.pack || []).length + (p.consumables || []).length + i })),
  ];
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;z-index:2011;background:rgba(0,0,0,0.75);display:flex;align-items:center;justify-content:center';
  const box = document.createElement('div');
  box.style.cssText = 'background:var(--card-bg,#1a1a2e);border:1px solid var(--border,#444);border-radius:12px;padding:20px 24px;max-width:480px;text-align:center';
  box.innerHTML = `
    <div style="font-family:'Cinzel',serif;font-size:14px;color:var(--gold,#c9a84c);margin-bottom:10px">Pack Full</div>
    <div style="font-size:12px;color:var(--text,#e0e0e0);margin-bottom:14px">Discard a pack item to make room for <b>${weapon.name}</b>:</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center">${packItems.map(pi => {
      const img = pi.card_image ? `<img src="/games/werblers/images/${pi.card_image}" style="width:70px;border-radius:4px;display:block">` : '';
      return `<div class="rake-equip-btn" style="cursor:pointer" data-pack-idx="${pi.idx}">${img}<div style="font-size:10px;color:var(--text,#e0e0e0);margin-top:4px;max-width:80px;word-break:break-word">${pi.name}</div></div>`;
    }).join('')}</div>`;
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  box.querySelectorAll('[data-pack-idx]').forEach(el => {
    el.addEventListener('click', () => {
      overlay.remove();
      onChoice(parseInt(el.dataset.packIdx));
    });
  });
}

// Called when clicking a pack slot during placement mode.
function _psPlacePack(existingIdx) {
  if (existingIdx >= 0) {
    const p = gameState.players.find(pl => pl.is_current);
    const allPack = [
      ...(p.pack || []),
      ...(p.consumables || []),
      ...(p.captured_monsters || []),
    ];
    const name = allPack[existingIdx]?.name || 'item in slot';
    if (!confirm(`Discard ${name}?`)) return;
    _finishPlacement({ placement: 'pack', pack_discard_index: existingIdx });
  } else {
    _finishPlacement({ placement: 'pack', pack_discard_index: -1 });
  }
}

// Discard the offered item and close placement mode.
function _psDiscardPlacement() {
  const cb = _invOnConfirm;
  _invPlacementItem = null;
  _playerSheetOpen  = false;
  _invOnConfirm     = null;
  document.getElementById('player-sheet-overlay').classList.add('hidden');
  if (cb) cb({ discard: true });
}

// Go back to the offer modal without discarding the pending item.
function _psBackToOffer() {
  _invPlacementItem = null;
  _playerSheetOpen  = false;
  _invOnConfirm     = null;
  document.getElementById('player-sheet-overlay').classList.add('hidden');
  document.getElementById('offer-modal').classList.remove('hidden');
}

// ---- Context menu ----
const _ctxMenu = (() => {
  const el = document.createElement('div');
  el.id = 'card-context-menu';
  el.className = 'hidden';
  document.body.appendChild(el);
  return el;
})();

function _showCtxMenu(x, y, entries) {
  _ctxMenu.innerHTML = entries.map(e =>
    `<div class="ctx-menu-item${e.danger ? ' ctx-danger' : ''}" onclick="${e.action}">${e.label}</div>`
  ).join('');
  const margin = 8;
  _ctxMenu.classList.remove('hidden');
  const w = _ctxMenu.offsetWidth || 160;
  const h = _ctxMenu.offsetHeight || 100;
  _ctxMenu.style.left = Math.min(x, window.innerWidth - w - margin) + 'px';
  _ctxMenu.style.top  = Math.min(y, window.innerHeight - h - margin) + 'px';
}

function _closeCtxMenu() { _ctxMenu.classList.add('hidden'); }

document.addEventListener('click', () => _closeCtxMenu(), true);
document.addEventListener('keydown', e => { if (e.key === 'Escape') _closeCtxMenu(); });

function _attachCtxMenus(container) {
  const _jsEsc = s => s.replace(/'/g, "\\'");
  const _isMyTurn = () => gameState && viewingPlayerId === gameState.current_player_id;
  container.querySelectorAll('[data-ctx="equip"]').forEach(el => {
    el.addEventListener('contextmenu', e => {
      e.preventDefault();
      const slotKey  = el.dataset.slotKey;
      const slotIdx  = el.dataset.slotIdx;
      const name     = el.dataset.itemName || 'item';
      const imgSrc   = el.dataset.itemImage;
      const entries = [];
      if (imgSrc) entries.push({ label: 'View Card', action: `zoomCard('${_jsEsc(imgSrc)}');_closeCtxMenu()` });
      if (_isMyTurn()) {
        entries.push({ label: 'Move to Pack', action: `manageItem('to_pack','${slotKey}',${slotIdx});_closeCtxMenu()` });
        entries.push({ label: `Discard ${name}`, action: `if(confirm('Discard ${name.replace(/'/g, "\\'")}?')){manageItem('discard','${slotKey}',${slotIdx})}_closeCtxMenu()`, danger: true });
      } else {
        entries.push({ label: 'Not your turn', action: `_closeCtxMenu()` });
      }
      _showCtxMenu(e.clientX, e.clientY, entries);
    });
  });
  container.querySelectorAll('[data-ctx="captured_monster"]').forEach(el => {
    el.addEventListener('contextmenu', e => {
      e.preventDefault();
      const idx     = el.dataset.capturedIdx;
      const name    = el.dataset.itemName || 'monster';
      const imgSrc  = el.dataset.itemImage;
      const devImg  = el.dataset.deviceImage;
      const entries = [];
      if (imgSrc) entries.push({ label: 'View Monster Card', action: `zoomCard('${_jsEsc(imgSrc)}');_closeCtxMenu()` });
      if (devImg) entries.push({ label: 'View Capture Device Card', action: `zoomCard('${_jsEsc(devImg)}');_closeCtxMenu()` });
      if (_isMyTurn()) {
        entries.push({ label: `Summon ${name}`, action: `summonCapturedMonster(${idx});_closeCtxMenu()` });
        entries.push({ label: `Release ${name}`, action: `releaseCapturedMonster(${idx});_closeCtxMenu()`, danger: true });
      } else {
        entries.push({ label: 'Not your turn', action: `_closeCtxMenu()` });
      }
      _showCtxMenu(e.clientX, e.clientY, entries);
    });
  });
  container.querySelectorAll('[data-ctx="pack"]').forEach(el => {
    el.addEventListener('contextmenu', e => {
      e.preventDefault();
      const packIdx = el.dataset.packIdx;
      const name    = el.dataset.itemName || 'item';
      const imgSrc  = el.dataset.itemImage;
      const isConsumable = el.dataset.isConsumable === 'true';
      const consumableIdx = parseInt(el.dataset.consumableIdx ?? '-1', 10);
      const entries = [];
      if (imgSrc) entries.push({ label: 'View Card', action: `zoomCard('${_jsEsc(imgSrc)}');_closeCtxMenu()` });
      if (_isMyTurn()) {
        if (!isConsumable) entries.push({ label: 'Equip', action: `manageItem('to_equip','pack',${packIdx});_closeCtxMenu()` });
        if (isConsumable && consumableIdx >= 0) {
          const canUseNow = gameState && !gameState.has_pending_combat;
          if (canUseNow) entries.push({ label: `Use ${name}`, action: `_closeCtxMenu();promptUseConsumable(${consumableIdx})` });
          entries.push({ label: `Discard ${name}`, action: `if(confirm('Discard ${name.replace(/'/g, "\\'")}?')){_discardConsumable(${consumableIdx})}_closeCtxMenu()`, danger: true });
        } else {
          entries.push({ label: `Discard ${name}`, action: `if(confirm('Discard ${name.replace(/'/g, "\\'")}?')){manageItem('discard','pack',${packIdx})}_closeCtxMenu()`, danger: true });
        }
      } else {
        entries.push({ label: 'Not your turn', action: `_closeCtxMenu()` });
      }
      _showCtxMenu(e.clientX, e.clientY, entries);
    });
  });
}

/* ---------- Drag & Drop for player sheet ---------- */
function _attachDragDrop(container) {
  const _isMyTurn = () => gameState && viewingPlayerId === gameState.current_player_id;
  if (!_isMyTurn()) return;

  const _slotTypeMap = { equip_helmet: 'helmet', equip_chest: 'chest', equip_leg: 'legs', equip_weapon: 'weapon' };

  // Make filled equip & pack slots draggable
  container.querySelectorAll('.ps-slot.ps-slot-card, .ps-slot.ps-slot-filled').forEach(el => {
    if (el.classList.contains('ps-slot-ghost') || el.classList.contains('ps-slot-disabled')) return;
    const ctx = el.dataset.ctx;
    if (!ctx || (ctx !== 'equip' && ctx !== 'pack')) return;
    el.setAttribute('draggable', 'true');
    el.addEventListener('dragstart', e => {
      const info = { ctx };
      if (ctx === 'equip') { info.slotKey = el.dataset.slotKey; info.slotIdx = el.dataset.slotIdx; }
      else { info.packIdx = el.dataset.packIdx; info.isConsumable = el.dataset.isConsumable === 'true'; }
      e.dataTransfer.setData('text/plain', JSON.stringify(info));
      e.dataTransfer.effectAllowed = 'move';
      el.classList.add('ps-dragging');
    });
    el.addEventListener('dragend', () => {
      el.classList.remove('ps-dragging');
      container.querySelectorAll('.ps-drag-over').forEach(t => t.classList.remove('ps-drag-over'));
    });
  });

  // Equip slots (filled or empty) as drop targets for pack items
  container.querySelectorAll('[data-slot-key]').forEach(el => {
    el.addEventListener('dragover', e => {
      try {
        // Only allow pack→equip drops
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        el.classList.add('ps-drag-over');
      } catch (_) {}
    });
    el.addEventListener('dragleave', () => el.classList.remove('ps-drag-over'));
    el.addEventListener('drop', async e => {
      e.preventDefault();
      el.classList.remove('ps-drag-over');
      let info;
      try { info = JSON.parse(e.dataTransfer.getData('text/plain')); } catch (_) { return; }
      if (info.ctx !== 'pack' || info.isConsumable) return;
      const packIdx = parseInt(info.packIdx, 10);
      // Use equip_from_pack endpoint (supports displacement via to_pack)
      const resp = await fetch('/games/werblers/api/equip_from_pack', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pack_index: packIdx, to_pack: true }),
      });
      const data = await resp.json();
      if (data.error === 'multi_displace' && data.displaced_items) {
        _showMultiDisplaceModal(packIdx, data.displaced_items, data.pack_slots_free);
        return;
      }
      if (data.error === 'pack_full' && data.pack) {
        _showEquipFromPackFullModal(packIdx, data.pack, data.displaced_name || '');
        return;
      }
      if (data.ok) { gameState = data.state; applyState(data.state); renderPlayerSheetFull(data.state); }
      else { console.warn(data.error || 'Cannot equip here'); }
    });
  });

  // Individual pack slots as drop targets for equipped items (equip→pack)
  container.querySelectorAll('.ps-pack-grid .ps-slot').forEach(slotEl => {
    slotEl.addEventListener('dragover', e => {
      // Accept drops from equip slots only
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      slotEl.classList.add('ps-drag-over');
    });
    slotEl.addEventListener('dragleave', () => slotEl.classList.remove('ps-drag-over'));
    slotEl.addEventListener('drop', async e => {
      e.preventDefault();
      slotEl.classList.remove('ps-drag-over');
      let info;
      try { info = JSON.parse(e.dataTransfer.getData('text/plain')); } catch (_) { return; }
      if (info.ctx !== 'equip') return;
      // If dropping onto a filled pack slot, ask what to do with the pack item
      const targetPackIdx = slotEl.dataset.packIdx;
      if (targetPackIdx !== undefined && targetPackIdx !== '' && parseInt(targetPackIdx, 10) >= 0) {
        const dpi = parseInt(targetPackIdx, 10);
        const packItemName = slotEl.dataset.itemName || 'this item';
        const isConsumable = slotEl.dataset.isConsumable === 'true';
        // Show equip/drop prompt for the existing pack item
        _showPackSwapPrompt(packItemName, isConsumable, info.slotKey, parseInt(info.slotIdx, 10), dpi);
      } else {
        await manageItem('to_pack', info.slotKey, parseInt(info.slotIdx, 10), {});
      }
    });
  });
}

async function manageItem(action, source, idx, extraParams) {
  const body = { action, source, index: idx };
  if (extraParams) Object.assign(body, extraParams);
  const resp = await fetch('/games/werblers/api/manage_item', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (data.error === 'pack_full' && data.pack) {
    _showPackDiscardChoice(data.pack, action, source, idx);
    return;
  }
  if (data.ok && data.state) {
    gameState = data.state;
    applyState(data.state);
    renderPlayerSheetFull(gameState);
    await loadAndRenderAbilities();
  } else if (data.error) {
    alert(data.error);
  }
}

function _showPackDiscardChoice(packItems, origAction, origSource, origIdx) {
  const overlay = document.createElement('div');
  overlay.id = 'pack-discard-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:2000;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center';
  const box = document.createElement('div');
  box.style.cssText = 'background:var(--card-bg,#1a1a2e);border:1px solid var(--border,#333);border-radius:12px;padding:20px 24px;max-width:480px;text-align:center';
  box.innerHTML = `<div style="font-family:'Cinzel',serif;font-size:14px;color:var(--gold,#c9a84c);margin-bottom:12px">Pack Full</div>
    <div style="font-size:12px;color:var(--text,#e0e0e0);margin-bottom:16px">Choose an item to discard from your pack:</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center">${packItems.map((p, i) => {
      const img = p.card_image ? `<img src="/games/werblers/images/${p.card_image}" style="width:70px;border-radius:4px;display:block">` : '';
      return `<div class="rake-equip-btn" style="cursor:pointer" onclick="window._confirmPackDiscard(${i})">
        ${img}
        <div style="font-size:10px;color:var(--text,#e0e0e0);margin-top:4px;max-width:80px;word-break:break-word">${p.name}</div>
      </div>`;
    }).join('')}</div>
    <div style="margin-top:16px"><button class="btn-secondary" onclick="window._cancelPackDiscard()">Cancel</button></div>`;
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  window._confirmPackDiscard = async (dpi) => {
    overlay.remove();
    await manageItem(origAction, origSource, origIdx, { discard_pack_index: dpi });
  };
  window._cancelPackDiscard = () => overlay.remove();
}

function _showPackSwapPrompt(packItemName, isConsumable, slotKey, slotIdx, discardPackIdx) {
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;z-index:2000;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center';
  const box = document.createElement('div');
  box.style.cssText = 'background:var(--card-bg,#1a1a2e);border:1px solid var(--border,#333);border-radius:12px;padding:20px 28px;max-width:420px;text-align:center';
  box.innerHTML = `
    <div style="font-family:'Cinzel',serif;font-size:14px;color:var(--gold,#c9a84c);margin-bottom:12px">Pack Item</div>
    <div style="font-size:12px;color:var(--text,#e0e0e0);margin-bottom:20px">What would you like to do with <strong>${packItemName}</strong>?</div>
    <div style="display:flex;gap:12px;justify-content:center">
      ${!isConsumable ? `<button class="btn-secondary" id="pack-swap-equip">Equip</button>` : ''}
      <button class="btn-danger" id="pack-swap-drop">Drop</button>
      <button class="btn-secondary" id="pack-swap-cancel">Cancel</button>
    </div>`;
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  const equipBtn = box.querySelector('#pack-swap-equip');
  if (equipBtn) {
    equipBtn.addEventListener('click', async () => {
      overlay.remove();
      await manageItem('to_pack', slotKey, slotIdx, { discard_pack_index: discardPackIdx, swap_to_equip: true });
    });
  }
  box.querySelector('#pack-swap-drop').addEventListener('click', async () => {
    overlay.remove();
    await manageItem('to_pack', slotKey, slotIdx, { discard_pack_index: discardPackIdx });
  });
  box.querySelector('#pack-swap-cancel').addEventListener('click', () => overlay.remove());
}

function _showEquipFromPackFullModal(packIndex, packItems, displacedName) {
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;z-index:2000;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center';
  const box = document.createElement('div');
  box.style.cssText = 'background:var(--card-bg,#1a1a2e);border:1px solid var(--border,#333);border-radius:12px;padding:20px 24px;max-width:540px;text-align:center';
  const dispText = displacedName ? ` to make room for <strong>${displacedName}</strong>` : '';
  box.innerHTML = `
    <div style="font-family:'Cinzel',serif;font-size:14px;color:var(--gold,#c9a84c);margin-bottom:8px">Pack Full</div>
    <div style="font-size:12px;color:var(--text,#e0e0e0);margin-bottom:16px">Choose a pack item to remove${dispText}:</div>
    <div id="efp-items" style="display:flex;flex-wrap:wrap;gap:10px;justify-content:center"></div>
    <div style="margin-top:16px"><button class="btn-secondary" id="efp-cancel">Cancel</button></div>`;
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  const itemsDiv = box.querySelector('#efp-items');
  packItems.forEach((item, i) => {
    const cell = document.createElement('div');
    cell.style.cssText = 'text-align:center;width:96px;';
    const img = item.card_image ? `<img src="/games/werblers/images/${item.card_image}" style="width:72px;border-radius:4px;display:block;margin:0 auto">` : '';
    cell.innerHTML = `${img}<div style="font-size:10px;color:var(--text,#e0e0e0);margin-top:4px;word-break:break-word">${item.name}</div>`;
    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'display:flex;gap:4px;justify-content:center;margin-top:5px;';
    const discardBtn = document.createElement('button');
    discardBtn.className = 'btn-danger';
    discardBtn.style.cssText = 'font-size:10px;padding:3px 7px;';
    discardBtn.textContent = 'Discard';
    discardBtn.addEventListener('click', async () => {
      overlay.remove();
      const r = await fetch('/games/werblers/api/equip_from_pack', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pack_index: packIndex, to_pack: true, discard_pack_index: i }) });
      const d = await r.json();
      if (d.ok) { gameState = d.state; applyState(d.state); renderPlayerSheetFull(d.state); }
      else { alert(d.error || 'Cannot equip here'); }
    });
    btnRow.appendChild(discardBtn);
    if (!item.is_consumable) {
      const equipBtn = document.createElement('button');
      equipBtn.className = 'btn-secondary';
      equipBtn.style.cssText = 'font-size:10px;padding:3px 7px;';
      equipBtn.textContent = 'Equip';
      equipBtn.addEventListener('click', async () => {
        overlay.remove();
        const r = await fetch('/games/werblers/api/equip_from_pack', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pack_index: packIndex, to_pack: true, discard_pack_index: i, equip_displaced: true }) });
        const d = await r.json();
        if (d.ok) { gameState = d.state; applyState(d.state); renderPlayerSheetFull(d.state); }
        else { alert(d.error || 'Cannot equip here'); }
      });
      btnRow.appendChild(equipBtn);
    }
    cell.appendChild(btnRow);
    itemsDiv.appendChild(cell);
  });
  box.querySelector('#efp-cancel').addEventListener('click', () => overlay.remove());
}

async function _discardConsumable(consumableIdx) {
  const resp = await fetch('/games/werblers/api/discard_consumable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ consumable_index: consumableIdx }),
  });
  const data = await resp.json();
  if (data.ok && data.state) {
    gameState = data.state;
    renderPlayerSheetFull(gameState);
  } else if (data.error) {
    alert(data.error);
  }
}

// Use a consumable Item that's sitting in player.pack (is_consumable=true)
async function usePackConsumable(packIndex) {
  if (!gameState) return;
  const p = gameState.players.find(x => x.player_id === viewingPlayerId);
  if (!p) return;
  const item = p.pack[packIndex];
  if (!item) return;

  // Build a fake consumable-like object so we can reuse the same confirm/target flow
  const fakeConsumable = { name: item.name, effect_id: item.effect_id || '', card_image: item.card_image };
  const imgHtml = item.card_image
    ? `<img class="consumable-modal-card-img" src="/games/werblers/images/${item.card_image}" alt="${item.name}" onclick="zoomCard(this.src)">`
    : '';
  _showConsumableModal(fakeConsumable, `<div class="consumable-modal-card-wrap">${imgHtml}</div>`, [
    { label: `Use ${item.name}`, action: () => { _closeConsumableModal(); _doUsePackConsumableConfirmed(packIndex, fakeConsumable); } },
    { label: 'Cancel', action: () => _closeConsumableModal() },
  ]);
}

async function _doUsePackConsumableConfirmed(packIndex, consumable) {
  if (consumable.effect_id === 'give_curse') {
    const allPlayers = gameState.players;
    if (allPlayers.length === 1) {
      await _callUsePackConsumable(packIndex, allPlayers[0].player_id);
    } else {
      // Reuse player picker — show all players
      _showPlayerPickerModal(packIndex, consumable, allPlayers, true);
    }
    return;
  }
  await _callUsePackConsumable(packIndex, null);
}

async function _callUsePackConsumable(packIndex, targetPlayerId) {
  try {
    const body = { pack_index: packIndex };
    if (targetPlayerId !== null && targetPlayerId !== undefined) body.target_player_id = targetPlayerId;
    const resp = await fetch('/games/werblers/api/use_pack_consumable', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    let data;
    try { data = await resp.json(); } catch(e) { alert('Server error. Please try again.'); return; }
    if (!data.ok) { alert(data.error || 'Failed to use consumable'); return; }
    if (data.state) {
      gameState = data.state;
      // Don't reset viewingPlayerId yet — the result modal animation
      // needs to show the affected player, not the next-turn player.
      applyState(gameState);
    }
    if (data.phase === 'trait_gained') {
      _showConsumableResultModal({
        title: '✨ Trait Gained!',
        monsterName: data.monster_name, monsterImg: data.monster_card_image ? `/games/werblers/images/${data.monster_card_image}` : '',
        resultName: data.trait_name, resultDesc: data.trait_desc || '', resultClass: 'result-trait',
        onClose: () => { viewingPlayerId = gameState.current_player_id; applyState(gameState); },
      });
    } else if (data.phase === 'curse_given') {
      _showConsumableResultModal({
        title: `💀 Curse Given to ${data.target_name}!`,
        monsterName: data.monster_name, monsterImg: data.monster_card_image ? `/games/werblers/images/${data.monster_card_image}` : '',
        resultName: data.curse_name, resultDesc: data.curse_desc || '', resultClass: 'result-curse',
        affectedPlayerId: data.target_player_id,
        onClose: () => { viewingPlayerId = gameState.current_player_id; applyState(gameState); },
      });
    } else {
      // No modal to show — safe to advance viewingPlayerId now
      viewingPlayerId = gameState.current_player_id;
      applyState(gameState);
    }
    await loadAndRenderAbilities();
  } catch(e) {
    alert('Network error: ' + e.message);
  }
}

async function releaseCapturedMonster(idx) {
  const resp = await fetch('/games/werblers/api/release_monster', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ index: idx }),
  });
  const data = await resp.json();
  if (data.ok && data.state) {
    gameState = data.state;
    renderPlayerSheetFull(gameState);
  } else if (data.error) {
    alert(data.error);
  }
}

async function summonCapturedMonster(idx) {
  if (!confirm('Summon this monster as an enemy to fight? This cannot be undone.')) return;
  const resp = await fetch('/games/werblers/api/summon_monster', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ index: idx }),
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) {
    gameState = data.state;
    viewingPlayerId = data.state.current_player_id;
    applyState(data.state);
  }
  if (data.phase === 'combat' && data.combat_info) {
    // Close the player sheet if open, then show the battle scene
    closePlayerSheet();
    playMusic('Battle Music.wav');
    showPreFightScene(data.combat_info, gameState);
  }
}

function invSelectPlace(type, packIdx) {
  _invState = { type, packIdx: packIdx ?? -1 };
  document.querySelectorAll('.inv-slot').forEach(el => el.classList.remove('inv-selected'));
  if (type === 'equip') {
    document.getElementById('inv-equip-slot')?.classList.add('inv-selected');
  } else if ((packIdx ?? -1) >= 0) {
    document.querySelectorAll(`.inv-pack-slot[data-pack-idx="${packIdx}"]`)
      .forEach(el => el.classList.add('inv-selected'));
  } else {
    document.getElementById('inv-pack-free')?.classList.add('inv-selected');
  }
  document.getElementById('inv-confirm-btn').disabled = false;
}
function invEquipSwap(equipIdx) {
  _invState = { type: 'equip', equipAction: 'swap', equipItemIdx: equipIdx };
  document.querySelectorAll('.inv-slot').forEach(el => el.classList.remove('inv-selected'));
  document.querySelectorAll(`.inv-equipped[data-equip-idx="${equipIdx}"]`)
    .forEach(el => el.classList.add('inv-selected'));
  document.getElementById('inv-equip-slot')?.classList.add('inv-selected');
  document.getElementById('inv-confirm-btn').disabled = false;
}
function invEquipDiscard(equipIdx) {
  _invState = { type: 'equip', equipAction: 'discard', equipItemIdx: equipIdx };
  document.querySelectorAll('.inv-slot').forEach(el => el.classList.remove('inv-selected'));
  document.querySelectorAll(`.inv-equipped[data-equip-idx="${equipIdx}"]`)
    .forEach(el => el.classList.add('inv-selected'));
  document.getElementById('inv-equip-slot')?.classList.add('inv-selected');
  document.getElementById('inv-confirm-btn').disabled = false;
}
function invConfirm() {
  document.getElementById('inventory-modal').classList.add('hidden');
  const choices = { placement: _invState.type === 'equip' ? 'equip' : 'pack' };
  if (_invState.equipAction)  choices.equip_action     = _invState.equipAction;
  if (_invState.equipItemIdx !== undefined) choices.equip_item_index = _invState.equipItemIdx;
  if (_invState.packIdx !== undefined && _invState.packIdx >= 0)
    choices.pack_discard_index = _invState.packIdx;
  if (_invOnConfirm) _invOnConfirm(choices);
}
function invCancel() {
  document.getElementById('inventory-modal').classList.add('hidden');
  // Discard the item — resolve with placement=discard (server treats as pack full discard)
  if (_invOnConfirm) _invOnConfirm({ placement: 'pack', pack_discard_index: -999 });
}
// ================================================================ RESOLVE OFFER
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
  const modal = document.getElementById('offer-modal');
  modal.style.background = '';
  modal.classList.add('hidden');
  document.getElementById('inventory-modal').classList.add('hidden');
  const resp = await fetch('/games/werblers/api/resolve_offer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(choices),
  });
  const data = await resp.json();
  if (data.state) { gameState = data.state; applyState(data.state); }
  if (data.phase === 'rake_it_in') {
    showRakeItInModal(data);
    return;
  }
  // If there's a pending mystery farewell (item prize from Wheel/Box), show it now
  if (_pendingMysteryFarewell) {
    const fw = _pendingMysteryFarewell;
    _pendingMysteryFarewell = null;
    if (data.state) { gameState = data.state; }
    await _showCharacterFarewell(fw.event, fw.quote, () => {
      document.getElementById('battle-overlay').classList.add('hidden');
      if (gameState) {
        viewingPlayerId = gameState.current_player_id;
        applyState(gameState);
      }
      _resumeTierMusic(gameState);
      loadAndRenderAbilities();
    });
    return;
  }
  viewingPlayerId = data.state.current_player_id;
  applyState(data.state);
  _resumeTierMusic(data.state);
  await loadAndRenderAbilities();
}

// ================================================================ RAKE IT IN

let _rakeItInData = null;
let _rakeSelectedDiscardSlot = null;
let _rakeSelectedDiscardIdx = -1;
let _rakeSelectedShopItem = -1;

function showRakeItInModal(data) {
  _rakeItInData = data;
  _rakeSelectedDiscardSlot = null;
  _rakeSelectedDiscardIdx = -1;
  _rakeSelectedShopItem = -1;

  const modal = document.getElementById('rake-it-in-modal');
  if (!modal) return;

  const subType = data.sub_type || 'chest';
  const equips = data.equips || [];
  const packItems = data.pack_items || [];
  const consumableItems = data.consumable_items || [];
  const shopRemaining = data.shop_remaining || [];

  const equipsHtml = equips.map((e, i) => {
    const img = e.card_image ? `<img class="rake-item-thumb" src="/games/werblers/images/${e.card_image}" alt="${e.name}">` : '';
    const slot = e.slot === 'helmet' ? 'equip_helmet' : e.slot === 'chest' ? 'equip_chest' : e.slot === 'legs' ? 'equip_leg' : 'equip_weapon';
    const slotIdx = e.slot_index !== undefined ? e.slot_index : i;
    return `<div class="rake-equip-btn" data-slot="${slot}" data-idx="${slotIdx}" onclick="rakeSelectDiscard('${slot}',${slotIdx},this)">
      ${img}
      <div class="rake-item-name">${e.name}</div>
    </div>`;
  }).join('');

  const packHtml = packItems.length > 0 ? `<div class="rake-section-label">Or discard from pack:</div>
    <div class="rake-items-row">${packItems.map((p, i) => {
      const img = p.card_image ? `<img class="rake-item-thumb" src="/games/werblers/images/${p.card_image}" alt="${p.name}">` : '';
      return `<div class="rake-equip-btn" data-slot="pack" data-idx="${i}" onclick="rakeSelectDiscard('pack',${i},this)">
        ${img}
        <div class="rake-item-name">${p.name}</div>
      </div>`;
    }).join('')}</div>` : '';

  const consumableHtml = consumableItems.length > 0 ? `<div class="rake-section-label">Or discard a consumable:</div>
    <div class="rake-items-row">${consumableItems.map((c, i) => {
      const img = c.card_image ? `<img class="rake-item-thumb" src="/games/werblers/images/${c.card_image}" alt="${c.name}">` : '';
      return `<div class="rake-equip-btn" data-slot="consumable" data-idx="${i}" onclick="rakeSelectDiscard('consumable',${i},this)">
        ${img}
        <div class="rake-item-name">${c.name}</div>
      </div>`;
    }).join('')}</div>` : '';

  let shopHtml = '';
  if (subType === 'shop' && shopRemaining.length > 0) {
    shopHtml = `<div class="rake-section-label">Choose a 2nd item from the shop:</div>
    <div class="rake-items-row">${shopRemaining.map((it, i) => {
      const img = it.card_image ? `<img class="rake-item-thumb" src="/games/werblers/images/${it.card_image}" alt="${it.name}">` : '';
      return `<div class="rake-equip-btn" data-shop-idx="${i}" onclick="rakeSelectShopItem(${i},this)">
        ${img}
        <div class="rake-item-name">${it.name}</div>
      </div>`;
    }).join('')}</div>`;
  } else if (subType === 'chest') {
    shopHtml = `<div class="rake-section-label">Bonus:</div>
    <div class="rake-items-row">
      <div class="rake-equip-btn rake-draw-item rake-selected" data-shop-idx="0" onclick="rakeSelectShopItem(0,this)">
        <img class="rake-item-thumb" src="/games/werblers/images/Cards/Card back brown.png" alt="Draw Item" style="image-rendering:smooth">
        <div class="rake-item-name">Draw Item</div>
      </div>
    </div>`;
  }

  const descText = subType === 'shop'
    ? 'Discard an equipped or packed item to take a second item from the shop!'
    : 'Discard an equipped or packed item to draw a bonus item from the deck!';

  modal.querySelector('.rake-desc').textContent = descText;
  modal.querySelector('.rake-equips-row').innerHTML = equipsHtml;
  modal.querySelector('.rake-shop-section').innerHTML = packHtml + consumableHtml + shopHtml;
  modal.classList.remove('hidden');
}

function rakeSelectDiscard(slot, idx, el) {
  _rakeSelectedDiscardSlot = slot;
  _rakeSelectedDiscardIdx = idx;
  document.querySelectorAll('.rake-equip-btn[data-slot]').forEach(b => b.classList.remove('rake-selected'));
  if (el) el.classList.add('rake-selected');
  _updateRakeConfirmBtn();
}

function rakeSelectShopItem(idx, el) {
  _rakeSelectedShopItem = idx;
  document.querySelectorAll('.rake-equip-btn[data-shop-idx]').forEach(b => b.classList.remove('rake-selected'));
  if (el) el.classList.add('rake-selected');
  _updateRakeConfirmBtn();
}

function _updateRakeConfirmBtn() {
  const btn = document.getElementById('rake-confirm-btn');
  if (!btn || !_rakeItInData) return;
  const subType = _rakeItInData.sub_type || 'chest';
  const discardOk = _rakeSelectedDiscardSlot !== null && _rakeSelectedDiscardIdx >= 0;
  const shopOk = subType !== 'shop' || _rakeSelectedShopItem >= 0;
  btn.disabled = !(discardOk && shopOk);
}

async function resolveRakeItIn(useIt) {
  const modal = document.getElementById('rake-it-in-modal');
  if (modal) modal.classList.add('hidden');

  const body = { use_it: useIt };
  if (useIt) {
    body.discard_slot = _rakeSelectedDiscardSlot;
    body.discard_idx  = _rakeSelectedDiscardIdx;
    if (_rakeItInData && _rakeItInData.sub_type === 'shop') {
      body.second_item_choice = _rakeSelectedShopItem;
    }
  }

  const resp = await fetch('/games/werblers/api/resolve_rake_it_in', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  _rakeItInData = null;
  // Save the current player before state update (turn may advance)
  const rakePlayerId = gameState ? gameState.current_player_id : viewingPlayerId;
  if (data.state) {
    gameState = data.state;
    // Keep viewingPlayerId on the raking player during item placement
    applyState(data.state);
    _resumeTierMusic(data.state);
  }
  if (data.bonus_item) {
    // Show "Received" card notification + placement prompt (same as normal item receipt)
    await _placePendingTraitItems(rakePlayerId);
  }
  // Now that all modals/placements are done, advance to current player
  viewingPlayerId = gameState.current_player_id;
  applyState(gameState);
  await loadAndRenderAbilities();
}

// ================================================================ APPLY STATE
function applyState(state) {
  gameState = state;
  document.getElementById('turn-number').textContent = `Turn ${state.turn_number}`;
  const cur = state.players.find(p => p.is_current);
  document.getElementById('active-player-name').textContent = cur ? `${cur.name}'s Turn` : '';
  // Update main hero card display
  const mainHeroCard = document.getElementById('main-hero-card');
  if (mainHeroCard) {
    if (cur && cur.hero_card_image) {
      mainHeroCard.innerHTML = `<img src="/games/werblers/images/${cur.hero_card_image}" alt="${cur.name}" onclick="zoomCard(this.src)" title="${cur.name} — click to zoom">`;
    } else {
      mainHeroCard.innerHTML = '';
    }
  }
  updateBoard(state);
  updatePlayerTabs(state);
  updatePlayerStats(state);
  updateMovementSection(state);
  updateLog(state.log);
  renderPlayerSheet(state);
  if (state.game_status === 'WON' && state.winner !== null) {
    const winner = state.players.find(p => p.player_id === state.winner);
    document.getElementById('winner-text').textContent =
      `${winner ? winner.name : 'A player'} has defeated The Werbler!`;
    document.getElementById('winner-modal').classList.remove('hidden');
    // Achievement: Victory (defeat the Werbler)
    _checkAchievement('victory');
    // Achievement: multiplayer wins
    if (state.players.length > 1) {
      _checkAchievement('champion');
    }
  }
  // Achievement: miniboss1 defeated
  const curP = state.players.find(p => p.is_current);
  if (curP && curP.miniboss1_defeated) _checkAchievement('a_strong_start');
  if (curP && curP.miniboss2_defeated) _checkAchievement('getting_closer');
}
// ================================================================ CARD PREVIEW TOOLTIP
let _previewEl = null;
function _getPreviewEl() {
  if (!_previewEl) {
    _previewEl = document.createElement('div');
    _previewEl.id = 'card-preview-tooltip';
    _previewEl.className = 'hidden';
    document.body.appendChild(_previewEl);
  }
  return _previewEl;
}
function attachCardPreviews(container) {
  container.querySelectorAll('.has-card-preview').forEach(el => {
    const src = el.dataset.cardImage;
    if (!src) return;
    el.addEventListener('mouseenter', (e) => {
      const tip = _getPreviewEl();
      tip.innerHTML = `<img src="${src}" alt="Card preview">`;
      tip.classList.remove('hidden');
      _positionPreview(e);
    });
    el.addEventListener('mousemove', _positionPreview);
    el.addEventListener('mouseleave', () => _getPreviewEl().classList.add('hidden'));
  });
}
function attachCardClickZoom(container) {
  container.querySelectorAll('.has-card-preview').forEach(el => {
    const src = el.dataset.cardImage;
    if (!src) return;
    el.style.cursor = 'pointer';
    el.addEventListener('click', () => zoomCard(src));
  });
}
function _positionPreview(e) {
  const tip = _getPreviewEl();
  const tipW = tip.offsetWidth || 340;
  const tipH = tip.offsetHeight || 490;
  const margin = 16;
  let x, y;
  if (e.clientX > window.innerWidth / 2) {
    // Right side of screen → preview appears to the LEFT of cursor
    x = e.clientX - tipW - margin;
  } else {
    // Left side of screen → preview appears to the RIGHT of cursor
    x = e.clientX + margin;
  }
  x = Math.max(8, Math.min(x, window.innerWidth - tipW - 8));
  y = Math.max(8, Math.min(e.clientY - 10, window.innerHeight - tipH - 8));
  tip.style.left = x + 'px';
  tip.style.top  = y + 'px';
}
// ================================================================ BATTLE SCENE
function showTileScene(tileScene, onContinue) {
  const overlay = document.getElementById('battle-overlay');
  const bg = tileScene.background ? `/games/werblers/images/${tileScene.background}` : '';
  overlay.innerHTML = `
    <div class="battle-bg" style="background-image: url('${bg}')"></div>
    <div class="battle-content">
      <div class="battle-title">TILE ${tileScene.moved_to || ''}</div>
      <div class="battle-result" style="font-size:22px;color:var(--text-dim);letter-spacing:1px;">Nothing here&hellip;</div>
      <div class="battle-actions">
        <button class="btn-primary" onclick="closeTileScene()">Continue</button>
      </div>
    </div>`;
  overlay.classList.remove('hidden');
  _tileSceneCallback = onContinue;
}
let _tileSceneCallback = null;
async function closeTileScene() {
  document.getElementById('battle-overlay').classList.add('hidden');
  if (_tileSceneCallback) { const cb = _tileSceneCallback; _tileSceneCallback = null; await cb(); }
}
function _heroIdFromImageSrc(src) {
  for (const h of heroData) {
    if (src && h.card_image && src.includes(h.card_image)) return h.id;
  }
  // Also check current game state players
  if (gameState) {
    for (const p of gameState.players) {
      if (p.hero_card_image && src && src.includes(p.hero_card_image)) return p.hero_id;
    }
  }
  return null;
}
function zoomCard(src) {
  // If this is a hero portrait, show the animation instead of the zoom modal
  const heroId = _heroIdFromImageSrc(src);
  if (heroId) {
    _showHeroAnimation(heroId, 'general');
    return;
  }
  const modal = document.getElementById('card-zoom-modal');
  modal.querySelector('img').src = src;
  modal.classList.remove('hidden');
}
// ================================================================ PRE-FIGHT SCENE
let _preFightCombat = null;

function showPreFightScene(combat, state) {
  _preFightCombat = combat;
  // Show cinematic intro first, then proceed to bystanders or pre-fight
  _showFightIntro(combat, state, () => {
    const queue = combat.nearby_queue || [];
    if (queue.length > 0) {
      _renderBystanderScreen(queue[0], combat, state);
    } else {
      _renderPreFightScene(combat, state);
    }
  });
}

// ---------------------------------------------------------------- CINEMATIC FIGHT INTRO

function _showFightIntro(combat, state, onContinue) {
  const overlay = document.getElementById('battle-overlay');
  const p = state.players.find(x => x.player_id === combat.player_id) || state.players[0];
  const heroImg = combat.hero_card_image ? `/games/werblers/images/${combat.hero_card_image}` : (p && p.hero_card_image ? `/games/werblers/images/${p.hero_card_image}` : '');
  const playerName = combat.player_name || (p ? p.name : '');
  const monsterImg = combat.card_image ? `/games/werblers/images/${combat.card_image}` : '';
  const bg = combat.background ? `/games/werblers/images/${combat.background}` : '';

  // Use hero animation video for the versus intro if available
  const heroAnims = combat.hero_animations || (p && p.hero_animations) || {};
  const generalAnimSrc = heroAnims.general ? `/games/werblers/videos/${heroAnims.general}` : '';
  const heroVisual = generalAnimSrc
    ? `<video class="fight-intro-card" src="${generalAnimSrc}" autoplay muted playsinline style="border-radius:10px"></video>`
    : (heroImg ? `<img class="fight-intro-card" src="${heroImg}" alt="${playerName}">` : '');

  overlay.innerHTML = `
    <div class="battle-bg" style="background-image: url('${bg}')"></div>
    <div class="fight-intro-content">
      <div class="fight-intro-hero fight-intro-offscreen-left">
        <div class="fight-intro-name fight-intro-hero-name">${playerName}</div>
        ${heroVisual}
      </div>
      <div class="fight-intro-vs fight-intro-offscreen-top">VS</div>
      <div class="fight-intro-monster fight-intro-offscreen-right">
        <div class="fight-intro-name fight-intro-monster-name">${combat.monster_name}</div>
        ${monsterImg ? `<img class="fight-intro-card" src="${monsterImg}" alt="${combat.monster_name}">` : ''}
      </div>
      <div class="fight-intro-continue" id="fight-intro-continue">
        <button class="btn-primary" id="fight-intro-btn">Continue</button>
      </div>
    </div>`;
  overlay.classList.remove('hidden');

  const heroEl = overlay.querySelector('.fight-intro-hero');
  const vsEl = overlay.querySelector('.fight-intro-vs');
  const monsterEl = overlay.querySelector('.fight-intro-monster');
  const continueBtn = overlay.querySelector('#fight-intro-btn');

  // Beat 1: Hero flies in from bottom-left
  requestAnimationFrame(() => {
    heroEl.classList.remove('fight-intro-offscreen-left');
    heroEl.classList.add('fight-intro-animate-in');
  });

  // Beat 2: VS flies in from top
  setTimeout(() => {
    vsEl.classList.remove('fight-intro-offscreen-top');
    vsEl.classList.add('fight-intro-animate-in');
  }, 1300);

  // Beat 3: Monster flies in from bottom-right
  setTimeout(() => {
    monsterEl.classList.remove('fight-intro-offscreen-right');
    monsterEl.classList.add('fight-intro-animate-in');
  }, 2600);

  continueBtn.addEventListener('click', () => {
    onContinue();
  });
}

// ---------------------------------------------------------------- BYSTANDER CONSUMABLE SCREEN

function _renderBystanderScreen(bystander, combat, state) {
  const overlay = document.getElementById('battle-overlay');
  const bg = combat.background ? `/games/werblers/images/${combat.background}` : '';
  const fightingPlayer = state.players.find(x => x.player_id === combat.player_id) || state.players[0];
  const monsterImg = combat.card_image ? `/games/werblers/images/${combat.card_image}` : '';

  const tokenSrc = bystander.token_image ? `/games/werblers/images/${bystander.token_image}` : '';
  const consumables = bystander.consumables || [];

  const consumableHtml = consumables.length === 0
    ? '<div class="prefight-no-consumables">No applicable consumables</div>'
    : consumables.map((c, i) => {
        const sign = c.effect_value >= 0 ? '+' : '';
        const bonusText = c.effect_id === 'monster_str_mod'
          ? `${sign}${c.effect_value} Monster STR`
          : c.name;
        return `<div class="prefight-consumable">
          ${c.card_image ? `<img class="prefight-consumable-img" src="/games/werblers/images/${c.card_image}" alt="${c.name}" onclick="zoomCard(this.src)">` : ''}
          <div class="prefight-consumable-info">
            <div class="prefight-consumable-name">${c.name}</div>
            <div class="prefight-consumable-bonus">${bonusText}</div>
          </div>
          <button class="btn-use-consumable" onclick="doBystanderUse(${bystander.player_id}, ${i})">Use</button>
        </div>`;
      }).join('');

  overlay.innerHTML = `
    <div class="battle-bg" style="background-image: url('${bg}')"></div>
    <div class="battle-content">
      <div class="battle-main">
        <div class="battle-title" style="font-size:1rem;letter-spacing:2px;color:var(--gold-dim)">BEFORE THE FIGHT…</div>
        <div class="bystander-banner">
          ${tokenSrc ? `<img class="bystander-token" src="${tokenSrc}" alt="${bystander.name}">` : ''}
          <span class="bystander-name">${bystander.name}'s Turn</span>
        </div>
        <div class="bystander-subtitle">
          Use a consumable on <strong>${combat.monster_name}</strong>
          (STR ${combat.monster_strength}) or skip.
        </div>
        ${monsterImg ? `<div style="text-align:center;margin:8px 0">
          <img class="battle-card-img" src="${monsterImg}" alt="${combat.monster_name}" style="max-height:160px;width:auto" onclick="zoomCard(this.src)">
        </div>` : ''}
        <div class="prefight-consumables-section">
          <div class="prefight-consumables-title">${bystander.name}'s Consumables</div>
          <div class="prefight-consumables-list">${consumableHtml}</div>
        </div>
        <div class="battle-actions">
          <button class="btn-secondary" onclick="doBystanderSkip(${bystander.player_id})">Skip</button>
        </div>
      </div>
    </div>`;
  overlay.classList.remove('hidden');
  attachCardPreviews(overlay);
}

async function doBystanderUse(bystanderId, consumableIndex) {
  const resp = await fetch('/games/werblers/api/bystander_consumable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_id: bystanderId, consumable_index: consumableIndex, skip: false }),
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) gameState = data.state;
  const updatedCombat = data.combat_info || _preFightCombat;
  _preFightCombat = updatedCombat;
  _advanceBystanderQueue(updatedCombat);
}

async function doBystanderSkip(bystanderId) {
  const resp = await fetch('/games/werblers/api/bystander_consumable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_id: bystanderId, skip: true }),
  });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) gameState = data.state;
  const updatedCombat = data.combat_info || _preFightCombat;
  _preFightCombat = updatedCombat;
  _advanceBystanderQueue(updatedCombat);
}

function _advanceBystanderQueue(combat) {
  const queue = combat.nearby_queue || [];
  if (queue.length > 0) {
    _renderBystanderScreen(queue[0], combat, gameState);
  } else {
    _renderPreFightScene(combat, gameState);
  }
}

// ---------------------------------------------------------------- NORMAL PRE-FIGHT SCREEN

function _renderPreFightScene(combat, state) {
  const overlay = document.getElementById('battle-overlay');
  const p = state.players.find(x => x.player_id === combat.player_id) || state.players[0];
  const heroImg = combat.hero_card_image ? `/games/werblers/images/${combat.hero_card_image}` : (p && p.hero_card_image ? `/games/werblers/images/${p.hero_card_image}` : '');
  const playerName = combat.player_name || (p ? p.name : '');
  const monsterImg = combat.card_image ? `/games/werblers/images/${combat.card_image}` : '';
  const bg = combat.background ? `/games/werblers/images/${combat.background}` : '';
  const consumables = p ? (p.consumables || []) : [];
  const effectiveStr = Math.max(0, combat.player_strength);

  let consumableHtml = '';
  if (consumables.length === 0) {
    consumableHtml = '<div class="prefight-no-consumables">No consumables available</div>';
  } else {
    // Only show combat-relevant consumables in pre-fight (not gain_trait / give_curse — those are for overworld use)
    const combatConsumables = consumables.map((c, i) => ({c, i}))
      .filter(({c}) => c.strength_bonus > 0 || c.effect_id === 'monster_str_mod' || c.effect_id === 'capture_monster');
    if (combatConsumables.length === 0) {
      consumableHtml = '<div class="prefight-no-consumables">No combat consumables available</div>';
    } else {
    consumableHtml = combatConsumables.map(({c, i}) => {
      let bonusText = '';
      if (c.strength_bonus > 0) bonusText = `+${c.strength_bonus} STR`;
      else if (c.effect_id === 'monster_str_mod') bonusText = c.effect_value > 0 ? `+${c.effect_value} Monster STR` : `${c.effect_value} Monster STR`;
      else if (c.effect_id === 'capture_monster') bonusText = `Captures Monster (Tier ${c.effect_tier || '?'})`;
      return `<div class="prefight-consumable">
        ${c.card_image ? `<img class="prefight-consumable-img" src="/games/werblers/images/${c.card_image}" alt="${c.name}" onclick="zoomCard(this.src)">` : ''}
        <div class="prefight-consumable-info">
          <div class="prefight-consumable-name">${c.name}</div>
          ${bonusText ? `<div class="prefight-consumable-bonus">${bonusText}</div>` : ''}
        </div>
        <button class="btn-use-consumable" onclick="useConsumable(${i})">Use</button>
      </div>`;
    }).join('');
    }
  }

  const gearPanelHtml = _buildBattleGearSection(combat);
  const strTitle = _strBreakdownTitle(combat);

  // Billfold: "Fly, you dummy!" flee button (monsters & minibosses only)
  const canFlee = (combat.category === 'monster' || combat.category === 'miniboss')
    && combat.hero_id === 'BILLFOLD';
  const fleeTokenSrc = p && p.token_image ? `/games/werblers/images/${p.token_image}` : '';
  const fleeBtnHtml = canFlee ? `<div class="billfold-flee-box" title="From: Fly, You Dummy!" onclick="doFlee()">
    ${fleeTokenSrc ? `<img class="flee-token-img" src="${fleeTokenSrc}" alt="Billfold">` : ''}
    <button type="button" class="btn-flee">Flee back 13 spaces?</button>
  </div>` : '';

  // Swiftness trait: flee at no cost
  const canSwiftnessFlee = (combat.category === 'monster' || combat.category === 'miniboss')
    && combat.has_swiftness;
  const swiftnessFleeBtnHtml = canSwiftnessFlee
    ? `<button type="button" class="btn-flee btn-flee-swiftness" onclick="doSwiftnessFlee()">Flee? [Swiftness]</button>`
    : '';

  overlay.innerHTML = `
    <div class="battle-bg" style="background-image: url('${bg}')"></div>
    <div class="battle-content">
      ${gearPanelHtml ? `<div class="battle-left-panel">${gearPanelHtml}</div>` : ''}
      <div class="battle-main">
        <div class="battle-title">${combat.category === 'werbler' ? 'THE WERBLER' : combat.category === 'miniboss' ? 'MINIBOSS ENCOUNTER' : 'MONSTER ENCOUNTER'}</div>
        ${combat.description ? `<div class="battle-boss-desc">${combat.description}</div>` : ''}
        <div class="battle-arena">
          <div class="battle-side">
            ${heroImg ? `<img class="battle-card-img" src="${heroImg}" alt="${playerName}" onclick="zoomCard(this.src)" onerror="this.style.display='none'">` : ''}
            <div class="battle-name">${playerName}</div>
            <div class="battle-str" id="prefight-player-str" title="${strTitle}" style="cursor:help">STR ${effectiveStr}</div>
          </div>
          <div class="battle-vs">VS</div>
          <div class="battle-side">
            ${monsterImg ? `<img class="battle-card-img" src="${monsterImg}" alt="${combat.monster_name}" onclick="zoomCard(this.src)" onerror="this.style.display='none'">` : ''}
            <div class="battle-name">${combat.monster_name}</div>
            <div class="battle-str" title="${_monsterStrBreakdownTitle(combat)}" style="cursor:help">STR ${combat.monster_strength}</div>
          </div>
        </div>
        <div class="prefight-consumables-section">
          <div class="prefight-consumables-title">Consumables</div>
          <div class="prefight-consumables-list" id="prefight-consumables-list">
            ${consumableHtml}
          </div>
        </div>
        ${combat.ill_come_in_again_available ? `<div class="ill-come-in-again-section">
          <button class="btn-secondary" onclick="useIllComeInAgain()" title="Send this monster back and draw a new one">
            &#x21BA; ${_rerollTraitLabel(p)}
          </button>
        </div>` : ''}
        <div class="battle-actions">
          <button class="btn-primary btn-fight" onclick="doFight()">&#x2694; Fight!</button>
          ${swiftnessFleeBtnHtml}
          ${fleeBtnHtml}
        </div>
      </div>
    </div>`;
  overlay.classList.remove('hidden');
  attachCardPreviews(overlay);
}

let _pendingFleeState = null;

async function doFlee() {
  try {
    const resp = await fetch('/games/werblers/api/flee', { method: 'POST' });
    let rawText, data;
    try { rawText = await resp.text(); } catch(e) { alert('Network error during flee: ' + e.message); return; }
    try {
      data = JSON.parse(rawText);
    } catch(e) {
      alert('Server error during flee:\n' + rawText.substring(0, 400));
      return;
    }
    if (data.error) { alert(data.error); return; }
    _pendingFleeState = data.state || null;
    _showFledScreen(_preFightCombat ? `/games/werblers/images/${_preFightCombat.background}` : '');
  } catch(e) {
    alert('Network error during flee: ' + e.message);
  }
}

async function doSwiftnessFlee() {
  try {
    const resp = await fetch('/games/werblers/api/swiftness_flee', { method: 'POST' });
    let data;
    try { data = await resp.json(); } catch(e) { alert('Network error'); return; }
    if (data.error) { alert(data.error); return; }
    _pendingFleeState = data.state || null;
    _showFledScreen(_preFightCombat ? `/games/werblers/images/${_preFightCombat.background}` : '');
  } catch(e) {
    alert('Network error during flee: ' + e.message);
  }
}

function _showFledScreen(bg) {
  const overlay = document.getElementById('battle-overlay');
  overlay.classList.remove('hidden');
  overlay.innerHTML = `
    <div class="battle-bg" style="background-image: url('${bg}')"></div>
    <div style="position:relative;z-index:2;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:24px;">
      <div style="font-family:'Cinzel',serif;font-size:48px;color:var(--gold,#c9a84c);text-shadow:0 2px 20px #000,0 0 40px rgba(0,0,0,0.8);">You Fled</div>
      <button class="btn-primary" onclick="_finishFlee()">Continue</button>
    </div>`;
}

function _finishFlee() {
  const overlay = document.getElementById('battle-overlay');
  overlay.classList.add('hidden');
  overlay.innerHTML = '';  // reset for next battle render
  if (_pendingFleeState) {
    const prev = gameState?.players?.find(x => x.is_current);
    const next = _pendingFleeState?.players?.find(x => x.is_current);
    gameState = _pendingFleeState;
    viewingPlayerId = gameState.current_player_id;
    applyState(gameState);
    _resumeTierMusic();
    loadAndRenderAbilities();
    // Show "moved back" notification
    if (prev && next && prev.position !== next.position) {
      const moved = prev.position - next.position;
      if (moved > 0) {
        setTimeout(() => {
          const msg = document.createElement('div');
          msg.className = 'flee-move-notice';
          msg.innerHTML = `
            <div class="flee-move-box">
              <div class="flee-move-title">Moved back ${moved} space${moved !== 1 ? 's' : ''}!</div>
              <div class="flee-move-sub">Tile ${prev.position} → Tile ${next.position}</div>
              <button class="btn-primary" onclick="this.closest('.flee-move-notice').remove()">Continue</button>
            </div>`;
          document.body.appendChild(msg);
        }, 300);
      }
    }
    _pendingFleeState = null;
  }
}

function _rerollTraitLabel(player) {
  if (!player) return "I'll Come In Again!";
  const traits = (player.traits || []).filter(t =>
    t.effect_id === 'i_see_everything' || t.effect_id === 'ill_come_in_again'
  );
  if (traits.length === 0) return "Reroll Monster";
  // Show the first matching trait's name; if multiple, show both
  if (traits.length === 1) return traits[0].name;
  return traits.map(t => t.name).join(' / ');
}

async function useIllComeInAgain() {
  const resp = await fetch('/games/werblers/api/use_ill_come_in_again', { method: 'POST' });
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }
  if (data.state) gameState = data.state;
  if (data.phase === 'combat' && data.combat_info) {
    _preFightCombat = data.combat_info;
    _renderPreFightScene(data.combat_info, gameState);
  }
}

async function useConsumable(idx) {
  const resp = await fetch('/games/werblers/api/use_consumable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ consumable_index: idx }),
  });
  const data = await resp.json();
  if (!data.ok) {
    alert(data.error || 'Failed to use consumable');
    return;
  }
  if (data.phase === 'captured') {
    document.getElementById('battle-overlay').classList.add('hidden');
    gameState = data.state;
    viewingPlayerId = gameState.current_player_id;
    applyState(gameState);
    _resumeTierMusic();
    await loadAndRenderAbilities();
    return;
  }
  if (data.state) {
    gameState = data.state;
    _preFightCombat = data.combat_info;
    _renderPreFightScene(data.combat_info, data.state);
  }
}

// ================================================================ CONSUMABLE USE (OVERWORLD)
// promptUseConsumable: left-click handler — shows confirm then routes by type

function promptUseConsumable(idx) {
  if (!gameState) return;
  const p = gameState.players.find(x => x.player_id === viewingPlayerId);
  if (!p) return;
  const c = p.consumables[idx];
  if (!c) return;

  // Combat-only consumables can't be used from the pack outside of combat
  const combatOnly = c.effect_id === 'monster_str_mod' || c.effect_id === 'capture_monster'
    || (c.effect_id === '' && c.strength_bonus > 0);
  if (combatOnly) {
    _showConsumableModal(c, '<p class="consumable-modal-msg">This consumable can only be used during combat.</p>',
      [{label: 'OK', action: () => _closeConsumableModal()}]);
    return;
  }

  // Confirm use
  const imgHtml = c.card_image
    ? `<img class="consumable-modal-card-img" src="/games/werblers/images/${c.card_image}" alt="${c.name}" onclick="zoomCard(this.src)">`
    : '';
  _showConsumableModal(c, `<div class="consumable-modal-card-wrap">${imgHtml}</div>`, [
    { label: `Use ${c.name}`, action: () => { _closeConsumableModal(); _doUseConsumableConfirmed(idx, c); } },
    { label: 'Cancel', action: () => _closeConsumableModal() },
  ]);
}

async function _doUseConsumableConfirmed(idx, consumable) {
  if (consumable.effect_id === 'give_curse') {
    // Need a player target — show all players (including self as option)
    const allPlayers = gameState.players;
    if (allPlayers.length === 0) {
      alert('No players available!');
      return;
    }
    if (allPlayers.length === 1) {
      // Only self — use on self
      await _callUseConsumableOverworld(idx, allPlayers[0].player_id);
    } else {
      _showPlayerPickerModal(idx, consumable, allPlayers);
    }
    return;
  }
  // gain_trait (Blessings/Nectar) and anything else: call directly
  await _callUseConsumableOverworld(idx, null);
}

async function _callUseConsumableOverworld(idx, targetPlayerId) {
  try {
    const body = { consumable_index: idx };
    if (targetPlayerId !== null && targetPlayerId !== undefined) body.target_player_id = targetPlayerId;
    const resp = await fetch('/games/werblers/api/use_consumable', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    let data;
    try { data = await resp.json(); } catch(e) { alert('Server error. Please try again.'); return; }
    if (!data.ok) { alert(data.error || 'Failed to use consumable'); return; }
    if (data.state) {
      gameState = data.state;
      // Don't reset viewingPlayerId yet — result modal animation needs correct player
      applyState(gameState);
    }
    if (data.phase === 'trait_gained') {
      _showConsumableResultModal({
        title: '✨ Trait Gained!',
        monsterName:  data.monster_name,
        monsterImg:   data.monster_card_image ? `/games/werblers/images/${data.monster_card_image}` : '',
        resultName:   data.trait_name,
        resultDesc:   data.trait_desc || '',
        resultClass:  'result-trait',
        onClose: () => { viewingPlayerId = gameState.current_player_id; applyState(gameState); },
      });
    } else if (data.phase === 'curse_given') {
      _showConsumableResultModal({
        title: `💀 Curse Given to ${data.target_name}!`,
        monsterName: data.monster_name,
        monsterImg:  data.monster_card_image ? `/games/werblers/images/${data.monster_card_image}` : '',
        resultName:  data.curse_name,
        resultDesc:  data.curse_desc || '',
        resultClass: 'result-curse',
        affectedPlayerId: data.target_player_id,
        onClose: () => { viewingPlayerId = gameState.current_player_id; applyState(gameState); },
      });
    } else {
      viewingPlayerId = gameState.current_player_id;
      applyState(gameState);
    }
    await loadAndRenderAbilities();
  } catch(e) {
    alert('Network error: ' + e.message);
  }
}

// Legacy alias used in pre-fight screen - now routed through confirmDialog
async function useConsumableOverworld(idx) {
  await _callUseConsumableOverworld(idx, null);
}

// ---------------------------------------------------------------- CONSUMABLE MODALS

let _consumableModalEl = null;
function _getConsumableModal() {
  if (!_consumableModalEl) {
    _consumableModalEl = document.createElement('div');
    _consumableModalEl.id = 'consumable-modal';
    _consumableModalEl.className = 'consumable-modal-overlay hidden';
    document.body.appendChild(_consumableModalEl);
  }
  return _consumableModalEl;
}

function _showConsumableModal(consumable, bodyHtml, buttons) {
  const el = _getConsumableModal();
  const btnHtml = buttons.map((b, i) =>
    `<button class="btn-${i === 0 ? 'primary' : 'secondary'}" onclick="_consumableModalBtns[${i}]()">${b.label}</button>`
  ).join('');
  el.innerHTML = `<div class="consumable-modal-box">
    <h3 class="consumable-modal-title">${consumable.name}</h3>
    ${bodyHtml}
    <div class="consumable-modal-actions">${btnHtml}</div>
  </div>`;
  window._consumableModalBtns = buttons.map(b => b.action);
  el.classList.remove('hidden');
}

let _consumableModalOnClose = null;

function _closeConsumableModal() {
  const el = _getConsumableModal();
  // Stop embedded video if playing
  const vid = el.querySelector('video');
  if (vid) { vid.pause(); }
  // Remove floating anim panel too
  const panel = document.getElementById('hero-anim-panel');
  if (panel) panel.remove();
  el.classList.add('hidden');
  if (_consumableModalOnClose) {
    const cb = _consumableModalOnClose;
    _consumableModalOnClose = null;
    cb();
  }
}

function _showConsumableResultModal({ title, monsterName, monsterImg, resultName, resultDesc, resultClass, onClose, heroId, affectedPlayerId }) {
  _consumableModalOnClose = onClose || null;
  // Build video for trait (victory) or curse (defeat)
  // Use the AFFECTED player's animation, not necessarily the current-turn player
  let videoHtml = '';
  if (gameState) {
    const animType = resultClass === 'result-trait' ? 'victory' : resultClass === 'result-curse' ? 'defeat' : null;
    if (animType) {
      const p = affectedPlayerId != null
        ? (gameState.players.find(x => x.player_id === affectedPlayerId) || gameState.players.find(x => x.is_current) || gameState.players[0])
        : heroId
          ? (gameState.players.find(x => x.hero_id === heroId) || gameState.players.find(x => x.is_current) || gameState.players[0])
          : (gameState.players.find(x => x.is_current) || gameState.players[0]);
      if (p && p.hero_id && heroAnimMap[p.hero_id] && heroAnimMap[p.hero_id][animType]) {
        const vsrc = `/games/werblers/videos/${heroAnimMap[p.hero_id][animType]}`;
        videoHtml = `<video src="${vsrc}" autoplay muted playsinline style="max-width:220px;width:100%;border-radius:10px;box-shadow:0 0 20px rgba(0,0,0,0.7);"></video>`;
      }
    }
  }
  const el = _getConsumableModal();
  const mImg = monsterImg ? `<img class="consumable-modal-card-img" src="${monsterImg}" alt="${monsterName}" onclick="zoomCard(this.src)">` : '';
  // Side-by-side: animation left, card+text right
  const hasSideContent = videoHtml || mImg;
  const leftCol = videoHtml ? `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center">${videoHtml}</div>` : '';
  const mImgHtml = mImg ? `<div style="margin-bottom:6px">${mImg}</div>` : '';
  const rightCol = `<div style="display:flex;flex-direction:column;align-items:center;gap:8px">
    ${monsterName ? `<div class="consumable-result-from">Drew: <strong>${monsterName}</strong></div>` : ''}
    ${mImgHtml}
    <div class="consumable-result-name ${resultClass}">${resultName}</div>
    ${resultDesc ? `<div class="consumable-result-desc">${resultDesc}</div>` : ''}
  </div>`;
  const bodyHtml = hasSideContent
    ? `<div style="display:flex;gap:20px;align-items:center;justify-content:center;flex-wrap:wrap">${leftCol}${rightCol}</div>`
    : rightCol;
  el.innerHTML = `<div class="consumable-modal-box">
    <h3 class="consumable-modal-title">${title}</h3>
    ${bodyHtml}
    <div class="consumable-modal-actions">
      <button class="btn-primary" onclick="_closeConsumableModal()">OK</button>
    </div>
  </div>`;
  window._consumableModalBtns = [];
  el.classList.remove('hidden');
}

function _showPlayerPickerModal(consumableIdx, consumable, players, isPackItem) {
  const el = _getConsumableModal();
  const btns = players.map((pl) => {
    const label = pl.player_id === viewingPlayerId ? `${pl.name} (You)` : pl.name;
    const onclick = isPackItem
      ? `_pickPlayerForPackCurse(${consumableIdx}, ${pl.player_id})`
      : `_pickPlayerForCurse(${consumableIdx}, ${pl.player_id})`;
    return `<button class="btn-secondary player-pick-btn" onclick="${onclick}">${label}</button>`;
  }).join('');
  el.innerHTML = `<div class="consumable-modal-box">
    <h3 class="consumable-modal-title">${consumable.name}</h3>
    <p class="consumable-modal-msg">Choose a player to receive the curse:</p>
    <div class="consumable-modal-actions">${btns}</div>
    <div class="consumable-modal-actions" style="margin-top:8px">
      <button class="btn-secondary" onclick="_closeConsumableModal()">Cancel</button>
    </div>
  </div>`;
  window._consumableModalBtns = [];
  el.classList.remove('hidden');
}

async function _pickPlayerForCurse(consumableIdx, targetPlayerId) {
  _closeConsumableModal();
  await _callUseConsumableOverworld(consumableIdx, targetPlayerId);
}

async function _pickPlayerForPackCurse(packIndex, targetPlayerId) {
  _closeConsumableModal();
  await _callUsePackConsumable(packIndex, targetPlayerId);
}

let _lastFightWasSummon = false;
let _lastFightFromMystery = false;
async function doFight() {
  try {
    const resp = await fetch('/games/werblers/api/fight', { method: 'POST' });
    if (!resp.ok) {
      let errMsg = `HTTP ${resp.status}`;
      try {
        const errData = await resp.json();
        errMsg = errData.error || errMsg;
      } catch (_) {
        const rawText = await resp.text().catch(() => '');
        if (rawText) errMsg += '\n\n' + rawText.substring(0, 800);
      }
      console.error('fight failed:', errMsg);
      alert(`Fight error:\n${errMsg}`);
      return;
    }
    const data = await resp.json();
    if (data.state) gameState = data.state;
    _lastFightWasSummon = data.phase === 'summoned_done';
    _lastFightFromMystery = !!(data.combat_info && data.combat_info.from_mystery);
    if (data.combat_info) {
      showBattleScene(data.combat_info, data.state);
    } else {
      document.getElementById('battle-overlay').classList.add('hidden');
      if (gameState) {
        viewingPlayerId = gameState.current_player_id;
        applyState(gameState);
        _resumeTierMusic();
        await loadAndRenderAbilities();
      }
    }
  } catch (err) {
    console.error('doFight error:', err);
    alert(`Fight error: ${err.message || err}`);
  }
}
// ================================================================ BATTLE SCENE
let _lastCombatResult = null;
function showBattleScene(combat, state) {
  _lastCombatResult = combat;
  const overlay = document.getElementById('battle-overlay');
  const p = state.players.find(x => x.player_id === combat.player_id) || state.players.find(x => x.is_current) || state.players[0];
  const heroImg = combat.hero_card_image ? `/games/werblers/images/${combat.hero_card_image}` : (p && p.hero_card_image ? `/games/werblers/images/${p.hero_card_image}` : '');
  const playerName = combat.player_name || (p ? p.name : '');
  const monsterImg = combat.card_image ? `/games/werblers/images/${combat.card_image}` : '';
  const bg = combat.background ? `/games/werblers/images/${combat.background}` : '';
  const resultText = combat.result === 'WIN' ? 'VICTORY!'
    : combat.result === 'LOSE' ? 'DEFEAT'
    : combat.result === 'TIE' ? 'TIE' : '';
  const resultClass = combat.result === 'WIN' ? 'won' : combat.result === 'LOSE' ? 'lost' : '';
  const catLabel = combat.category === 'werbler' ? 'THE WERBLER'
    : combat.category === 'miniboss' ? 'MINIBOSS' : 'MONSTER';

  const gearPanelHtml = _buildBattleGearSection(combat);
  const strTitle = _strBreakdownTitle(combat);

  overlay.innerHTML = `
    <div class="battle-bg" style="background-image: url('${bg}')"></div>
    <div class="battle-content">
      ${gearPanelHtml ? `<div class="battle-left-panel">${gearPanelHtml}</div>` : ''}
      <div class="battle-main">
        <div class="battle-title">${catLabel} ENCOUNTER</div>
        <div class="battle-arena">
          <div class="battle-side">
            ${heroImg ? `<img class="battle-card-img" src="${heroImg}" alt="${playerName}" onclick="zoomCard(this.src)" onerror="this.style.display='none'">` : ''}
            <div class="battle-name">${playerName}</div>
            <div class="battle-str" title="${strTitle}" style="cursor:help">STR ${Math.max(0, combat.player_strength)}</div>
          </div>
          <div class="battle-vs">VS</div>
          <div class="battle-side">
            ${monsterImg ? `<img class="battle-card-img" src="${monsterImg}" alt="${combat.monster_name}" onclick="zoomCard(this.src)" onerror="this.style.display='none'">` : ''}
            <div class="battle-name">${combat.monster_name}</div>
            <div class="battle-str" title="${_monsterStrBreakdownTitle(combat)}" style="cursor:help">STR ${combat.monster_strength}</div>
          </div>
        </div>
        ${resultText ? `<div class="battle-result ${resultClass}">${resultText}</div>` : ''}
        <div class="battle-actions">
          <button class="btn-primary" onclick="closeBattleScene()">Continue</button>
        </div>
      </div>
    </div>`;
  overlay.classList.remove('hidden');
  attachCardPreviews(overlay);
}

async function closeBattleScene() {
  if (_lastCombatResult && (_lastCombatResult.trait_gained || _lastCombatResult.curse_gained)) {
    const gains = _lastCombatResult;
    _lastCombatResult = null;
    showGainModal(gains);
    return;
  }
  await _finishBattleContinue();
}

function showGainModal(combat) {
  let html = '';
  const animType = combat.trait_gained ? 'victory' : combat.curse_gained ? 'defeat' : null;
  // Build video element inline if we have an animation
  let videoHtml = '';
  let heroId = null;
  if (animType && gameState) {
    const fightPlayer = gameState.players.find(x => x.player_id === combat.player_id) || gameState.players.find(x => x.is_current);
    if (fightPlayer) heroId = fightPlayer.hero_id;
  }
  if (heroId && heroAnimMap[heroId] && heroAnimMap[heroId][animType]) {
    const vsrc = `/games/werblers/videos/${heroAnimMap[heroId][animType]}`;
    videoHtml = `<video id="gain-modal-video" src="${vsrc}" autoplay muted playsinline></video>`;
  }
  // Monster card
  const monsterCardEl = document.getElementById('gain-modal-monster-card');
  if (monsterCardEl) {
    monsterCardEl.innerHTML = combat.card_image
      ? `<img src="/games/werblers/images/${combat.card_image}" style="max-width:130px;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,0.5);display:block;">`
      : '';
  }
  if (combat.trait_gained) {
    html += `<div class="gain-modal-item is-trait">
      <div class="gain-modal-type">Trait Gained</div>
      <div class="gain-modal-name">${combat.trait_gained}</div>
      ${combat.trait_gained_desc ? `<div class="gain-modal-desc">${combat.trait_gained_desc}</div>` : ''}
    </div>`;
  }
  if (combat.curse_gained) {
    html += `<div class="gain-modal-item is-curse">
      <div class="gain-modal-type">Curse Gained</div>
      <div class="gain-modal-name">${combat.curse_gained}</div>
      ${combat.curse_gained_desc ? `<div class="gain-modal-desc">${combat.curse_gained_desc}</div>` : ''}
    </div>`;
  }
  document.getElementById('gain-modal-body').innerHTML = html;
  // Inject video into first grid cell (top-left)
  const gainContent = document.getElementById('gain-modal-content');
  const existingVideo = document.getElementById('gain-modal-video');
  if (existingVideo) existingVideo.remove();
  if (videoHtml) {
    gainContent.insertAdjacentHTML('afterbegin', videoHtml);
  }
  document.getElementById('gain-modal').classList.remove('hidden');
}

async function closeGainModal() {
  // Stop the embedded animation video if playing
  const vid = document.getElementById('gain-modal-video');
  if (vid) { vid.pause(); vid.remove(); }
  // Remove any stray floating animation panel too
  const panel = document.getElementById('hero-anim-panel');
  if (panel) panel.remove();
  document.getElementById('gain-modal').classList.add('hidden');
  // Check for pending trait items (items received from traits that need placement)
  await _placePendingTraitItems();
  // Check for pending minions that need placement (when at cap)
  await _placePendingMinions();
  await _finishBattleContinue();
}

async function _placePendingMinions() {
  if (!gameState) return;
  const p = gameState.players.find(x => x.player_id === viewingPlayerId);
  if (!p || !p.pending_trait_minions || !p.pending_trait_minions.length) return;
  // Show replacement modal and wait for user to resolve each pending minion
  await new Promise(resolve => {
    function checkDone() {
      const latest = gameState.players.find(x => x.player_id === viewingPlayerId);
      if (!latest || !latest.pending_trait_minions || latest.pending_trait_minions.length === 0) {
        resolve();
      }
    }
    _showMinionReplacementModal(p, checkDone);
  });
}

async function _placePendingTraitItems(forPlayerId) {
  if (!gameState) return;
  const pid = forPlayerId || viewingPlayerId;
  const p = gameState.players.find(x => x.player_id === pid);
  if (!p || !p.pending_trait_items || !p.pending_trait_items.length) return;
  for (let i = 0; i < p.pending_trait_items.length; i++) {
    const item = p.pending_trait_items[i];
    // Show "Received" popup
    await new Promise(resolve => {
      const playerHeroId = p?.hero_id;
      _showConsumableResultModal({
        title: 'Received!',
        monsterName: '',
        monsterImg: item.card_image ? `/games/werblers/images/${item.card_image}` : '',
        resultName: item.name,
        resultDesc: item.strength_bonus !== 0 ? `+${item.strength_bonus} Str (${item.slot})` : `(${item.slot})`,
        resultClass: 'result-trait',
        heroId: playerHeroId,
        onClose: resolve,
      });
    });
    // Open placement screen
    await new Promise(resolve => {
      showInventoryPopup(item, async (choices) => {
        const body = { placement_choices: choices };
        if (forPlayerId) body.player_id = forPlayerId;
        const resp = await fetch('/games/werblers/api/place_trait_item', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await resp.json();
        if (data.state) {
          gameState = data.state;
          // Keep viewingPlayerId on the placing player during the loop;
          // the caller (_finishBattleContinue / resolveRakeItIn) will
          // advance it to current_player_id when everything is done.
          applyState(data.state);
        }
        resolve();
      });
    });
  }
}

async function _finishBattleContinue() {
  // If the fight came from a mystery event (e.g., Wheel or Mystery Box prize),
  // show the character farewell screen before returning to the overworld.
  if (_lastFightFromMystery && _pendingMysteryEvent) {
    _lastFightFromMystery = false;
    const ev = _pendingMysteryEvent;
    _pendingMysteryEvent = null;
    const quote = ev.event_id === 'the_wheel'
      ? '"Congratulations or sorry that happened! Remember to spay and neuter your minions!"'
      : ev.event_id === 'mystery_box'
      ? '"Wow, I\'m envious\u2026"'
      : '"The outcome has been decided."';
    await _showCharacterFarewell(ev, quote, () => {});
  }
  _lastFightFromMystery = false;
  // If there's a pending mystery farewell (from item prize placement), show it now
  if (_pendingMysteryFarewell) {
    const fw = _pendingMysteryFarewell;
    _pendingMysteryFarewell = null;
    await _showCharacterFarewell(fw.event, fw.quote, () => {});
  }
  document.getElementById('battle-overlay').classList.add('hidden');
  if (gameState) {
    viewingPlayerId = gameState.current_player_id;
    applyState(gameState);
    _resumeTierMusic();
    _lastFightWasSummon = false;
    await loadAndRenderAbilities();
  }
}
// ================================================================ PLAYER SHEET
let _playerSheetOpen = false;

function openPlayerSheet() {
  _playerSheetOpen = true;
  if (gameState) renderPlayerSheetFull(gameState);
  document.getElementById('player-sheet-overlay').classList.remove('hidden');
}

function closePlayerSheet() {
  _playerSheetOpen = false;
  document.getElementById('player-sheet-overlay').classList.add('hidden');
}

function renderPlayerSheet(state) {
  if (_playerSheetOpen) renderPlayerSheetFull(state);
}

function _playerStrBreakdown(p) {
  const lines = [];
  if (p.base_strength !== undefined) lines.push(`Base: ${p.base_strength}`);
  const gear = [...(p.helmets||[]), ...(p.chest_armor||[]), ...(p.leg_armor||[]), ...(p.weapons||[])];
  for (const item of gear) {
    if (item.strength_bonus) lines.push(`${item.name}: ${item.strength_bonus >= 0 ? '+' : ''}${item.strength_bonus}`);
    if (item.tokens) lines.push(`  ${item.name} (effect): +${item.tokens}`);
  }
  // Hero abilities: Brunhilde's Luscious Locks & Skimpy Armour, Rizzt's Night Stalker
  if (p.hero_id === 'BRUNHILDE') {
    if (!(p.helmets && p.helmets.length)) {
      lines.push('Luscious Locks (no helmet): +5');
    }
    for (const item of (p.chest_armor || [])) {
      const skimpyBonus = Math.max(0, 8 - item.strength_bonus);
      if (skimpyBonus > 0) {
        lines.push(`Skimpy Armour (${item.name}): +${skimpyBonus} extra`);
      }
    }
  }
  if (p.hero_id === 'RIZZT' && gameState && gameState.is_night) {
    lines.push('Night Stalker (night): +3');
  }
  for (const t of (p.traits||[])) {
    if (t.strength_bonus) lines.push(`${t.name}: ${t.strength_bonus >= 0 ? '+' : ''}${t.strength_bonus}`);
    if (t.tokens) lines.push(`${t.name} (effect): +${t.tokens}`);
  }
  for (const m of (p.minions||[])) {
    if (m.strength_bonus) lines.push(`${m.name} (minion): +${m.strength_bonus}`);
  }
  for (const c of (p.curses||[])) {
    if (c.strength_bonus) lines.push(`${c.name}: ${c.strength_bonus >= 0 ? '+' : ''}${c.strength_bonus}`);
    if (c.tokens) lines.push(`${c.name} (effect): ${c.tokens >= 0 ? '+' : ''}${c.tokens}`);
  }
  lines.push(`Total: ${p.strength}`);
  return lines.join('\n');
}

function renderPlayerSheetMini(p) {
  const mini = document.getElementById('player-sheet-mini');
  if (!mini) return;
  const imgHtml = p.hero_card_image
    ? `<img class="ps-mini-hero-thumb" src="/games/werblers/images/${p.hero_card_image}" alt="${p.name}">`
    : '';
  const strBreak = _playerStrBreakdown(p).replace(/"/g, '&quot;');
  mini.innerHTML = `
    <div class="ps-mini-content" onclick="openPlayerSheet()" title="Open player sheet">
      ${imgHtml}
      <div class="ps-mini-info">
        <div class="ps-mini-name">${p.name}</div>
        <div class="ps-mini-str" title="${strBreak}" style="cursor:help">STR ${p.strength}</div>
        <div class="ps-mini-hint">View Sheet</div>
      </div>
    </div>`;
}

function renderPlayerSheetFull(state) {
  const p = state.players.find(x => x.player_id === viewingPlayerId) || state.players[0];
  if (!p) return;
  const overlay = document.getElementById('player-sheet-overlay');

  // ---- Movement piles ----
  const hasDiscard = p.movement_discard_top !== null && p.movement_discard_top !== undefined;
  const deckCount = p.movement_deck_cards ? p.movement_deck_cards.length : '?';
  const deckHtml = `
    <div class="ps-pile-stack" onclick="openDeckViewer('deck')" title="View remaining cards" style="cursor:pointer">
      <div class="ps-pile-card ps-pile-facedown"><img class="ps-pile-img" src="/games/werblers/images/Cards/Card back brown.png" alt="deck" onerror="this.style.display='none'"></div>
      <div class="ps-pile-label">Deck (${deckCount})</div>
    </div>
    <div class="ps-pile-stack" onclick="openDeckViewer('discard')" title="View discard pile" style="cursor:pointer">
      <div class="ps-pile-card ${hasDiscard ? '' : 'ps-pile-empty'}">
        ${hasDiscard ? `<img class="ps-pile-img" src="/games/werblers/images/Movement/Movement Card ${p.movement_discard_top}.png" alt="${p.movement_discard_top}">` : '—'}
      </div>
      <div class="ps-pile-label">Discard${p.movement_discard_count ? ' (' + p.movement_discard_count + ')' : ''}</div>
    </div>`;

  // ---- Pack slots ----
  const packItems = [
    ...p.pack.map((i, realIdx) => ({ label: i.name, sub: i.strength_bonus !== 0 ? ((i.strength_bonus >= 0 ? '+' : '') + i.strength_bonus + ' Str') : '', card_image: i.card_image, realPackIdx: realIdx, isConsumable: i.is_consumable || false, isCapturedMonster: false })),
    ...(p.consumables || []).map((c, ci) => ({ label: c.name, sub: 'Consumable', card_image: c.card_image, realPackIdx: -1, isConsumable: true, isCapturedMonster: false, consumableIdx: ci, effectId: c.effect_id })),
    ...(p.captured_monsters || []).map((m, ci) => ({ label: m.name, sub: 'Captured Monster', card_image: m.card_image, realPackIdx: -1, isConsumable: false, isCapturedMonster: true, capturedMonsterIdx: ci, level: m.level || 1 })),
  ];
  const totalPackSlots = Math.max(p.pack_size || 3, packItems.length);
  const inPlacement = _invPlacementItem !== null;
  let packHtml = '';
  for (let i = 0; i < totalPackSlots; i++) {
    const item = packItems[i];
    const placementClass = inPlacement ? ' ps-slot-placement-target' : '';
    if (item && item.isCapturedMonster) {
      // Captured monster: red border, special context menu
      const deviceMark = item.level === 3 ? 'III' : item.level === 2 ? 'II' : 'I';
      const deviceImg = `Items/Consumables/Consumable Finished Cards/Monster Capture Device Mark ${deviceMark} Card.png`;
      packHtml += `<div class="ps-slot ps-slot-card ps-captured-monster${placementClass} has-card-preview" data-card-image="/games/werblers/images/${item.card_image}"
        data-ctx="captured_monster" data-captured-idx="${item.capturedMonsterIdx}" data-item-name="${(item.label || '').replace(/"/g, '&quot;')}" data-item-image="/games/werblers/images/${item.card_image}" data-device-image="/games/werblers/images/${deviceImg}"
        style="border-color:var(--curse)">
        <div class="ps-slot-label" style="color:var(--curse)">Captured</div>
        <img class="ps-slot-card-img" src="/games/werblers/images/${item.card_image}" alt="${item.label}">
      </div>`;
    } else if (item && item.card_image) {
      const previewClass = inPlacement ? '' : ' has-card-preview';
      const previewData = inPlacement ? '' : `data-card-image="/games/werblers/images/${item.card_image}"`;
      const isMyTurn = gameState && p.player_id === gameState.current_player_id;
      const canUseConsumable = !inPlacement && isMyTurn && item.isConsumable && (item.consumableIdx ?? -1) >= 0 && gameState && !gameState.has_pending_combat;
      const consumableClickAttr = canUseConsumable ? ` onclick="promptUseConsumable(${item.consumableIdx})" title="Click to use ${(item.label||'').replace(/"/g,'&quot;')}" style="cursor:pointer"` : '';
      const ctxAttr = inPlacement
        ? `onclick="_psPlacePack(${i})" title="Pack here — discard ${(item.label || '').replace(/"/g, '&quot;')}"`
        : `data-ctx="pack" data-pack-idx="${item.realPackIdx >= 0 ? item.realPackIdx : i}" data-item-name="${(item.label || '').replace(/"/g, '&quot;')}" data-item-image="/games/werblers/images/${item.card_image}" data-is-consumable="${item.isConsumable}" data-consumable-idx="${item.consumableIdx ?? -1}" data-effect-id="${item.effectId || ''}"`;
      packHtml += `<div class="ps-slot ps-slot-card${placementClass}${previewClass}" ${previewData} ${ctxAttr}${consumableClickAttr}>
        <div class="ps-slot-label">Pack</div>
        <img class="ps-slot-card-img" src="/games/werblers/images/${item.card_image}" alt="${item.label}">
      </div>`;
    } else if (item) {
      const ctxAttr = inPlacement
        ? `onclick="_psPlacePack(${i})" title="Pack here — discard ${(item.label || '').replace(/"/g, '&quot;')}"`
        : `data-ctx="pack" data-pack-idx="${item.realPackIdx >= 0 ? item.realPackIdx : i}" data-item-name="${(item.label || '').replace(/"/g, '&quot;')}" data-item-image="" data-is-consumable="${item.isConsumable}" data-consumable-idx="${item.consumableIdx ?? -1}" data-effect-id="${item.effectId || ''}"`;
      packHtml += `<div class="ps-slot ps-slot-filled${placementClass}" ${ctxAttr}>
        <div class="ps-slot-label">Pack</div>
        <div class="ps-slot-divider"></div>
        <div class="ps-slot-name">${item.label}</div>
        <div class="ps-slot-sub">${item.sub}</div>
      </div>`;
    } else {
      const clickAttr = inPlacement ? `onclick="_psPlacePack(-1)" title="Pack here"` : '';
      packHtml += `<div class="ps-slot ps-slot-empty${placementClass}" ${clickAttr}><div class="ps-slot-label">Pack</div></div>`;
    }
  }

  // ---- Hero card ----
  const heroClickAttr = p.hero_card_image ? `onclick="zoomCard('/games/werblers/images/${p.hero_card_image}')" style="cursor:zoom-in" title="Click to zoom"` : '';
  const heroHtml = p.hero_card_image
    ? `<img class="ps-hero-card-img" src="/games/werblers/images/${p.hero_card_image}" alt="${p.name}" ${heroClickAttr}>`
    : `<div class="ps-hero-card-placeholder">${p.name}</div>`;

  // ---- Equipment grid ----
  const equipHtml = _buildEquipGrid(p);

  // ---- Traits / Curses (split into left and right columns) ----
  let traitsHtml = '';
  let cursesHtml = '';
  if (p.traits && p.traits.length) {
    const traitCards = p.traits.map(t => {
      const badges = t.tokens ? ' ' + tokenBadges(t.tokens) : '';
      const desc = t.description ? ` data-tc-desc="${t.description.replace(/"/g, '&quot;')}"` : '';
      return `<div class="ps-tc-card is-trait tc-hoverable" data-tc-name="${t.name}"${desc} onclick="this.classList.toggle('ps-tc-expanded')">${t.name}${badges}</div>`;
    }).join('');
    traitsHtml = `<div class="ps-tc-label ps-tc-label-trait">Traits</div><div class="ps-tc-stack">${traitCards}</div>`;
  }
  if (p.curses && p.curses.length) {
    const curseCards = p.curses.map(c => {
      const badges = c.tokens ? ' ' + tokenBadges(c.tokens) : '';
      const desc = c.description ? ` data-tc-desc="${c.description.replace(/"/g, '&quot;')}"` : '';
      return `<div class="ps-tc-card is-curse tc-hoverable" data-tc-name="${c.name}"${desc} onclick="this.classList.toggle('ps-tc-expanded')">${c.name}${badges}</div>`;
    }).join('');
    cursesHtml = `<div class="ps-tc-label ps-tc-label-curse">Curses</div><div class="ps-tc-stack">${curseCards}</div>`;
  }
  const tcRowHtml = (traitsHtml || cursesHtml) ? `
    <div id="ps-traits-curses-row">
      <div id="ps-traits-col">${traitsHtml || '<div class="ps-area-label" style="color:var(--text-dim)">No Traits</div>'}</div>
      <div id="ps-curses-col">${cursesHtml || '<div class="ps-area-label" style="color:var(--text-dim)">No Curses</div>'}</div>
    </div>` : '';

  // ---- Minion pool ----
  const minions = p.minions || [];
  const maxMinions = p.max_minions || 6;
  const minionSlots = Array.from({length: maxMinions}, (_, i) => {
    const m = minions[i];
    if (m && m.card_image) {
      return `<div class="ps-minion-slot ps-minion-filled has-card-preview" data-card-image="/games/werblers/images/${m.card_image}">
          <div class="ps-slot-label">Minion</div>
          <img class="ps-slot-card-img" src="/games/werblers/images/${m.card_image}" alt="${m.name}" onerror="this.style.display='none'">
        </div>`;
    }
    return m
      ? `<div class="ps-minion-slot ps-minion-filled">
          <div class="ps-slot-label">Minion</div>
          <div class="ps-slot-divider"></div>
          <div class="ps-minion-slot-name">${m.name}</div>
          <div class="ps-minion-slot-str">+${m.strength_bonus} Str</div>
        </div>`
      : `<div class="ps-minion-slot ps-minion-empty"><div class="ps-slot-label">Minion</div></div>`;
  }).join('');
  const minionHtml = `
    <div id="ps-minion-area">
      <div class="ps-area-label">Minions</div>
      <div class="ps-minion-pool">${minionSlots}</div>
    </div>`;

  overlay.innerHTML = `
    <div id="player-sheet-panel">
      ${inPlacement ? `<div id="ps-placement-banner">
        <span>Placing: <strong>${_invPlacementItem.name}</strong> — click a slot to equip or pack it</span>
        <button class="btn-secondary ps-discard-btn" onclick="_psDiscardPlacement()">Discard Item</button>
        <button class="btn-secondary" onclick="_psBackToOffer()" style="margin-left:6px">&#x2190; Back</button>
      </div>` : ''}
      ${inPlacement ? '' : '<button class="ps-close-btn" onclick="closePlayerSheet()">&#x2715; Close</button>'}
      <div class="ps-sheet-name">${p.name}</div>
      <div id="ps-layout">
        <div id="ps-left">
          <div id="ps-movement-area">
            <div class="ps-area-label">Movement</div>
            <div class="ps-piles-row">${deckHtml}</div>
          </div>
          <div id="ps-pack-area">
            <div class="ps-area-label">Pack</div>
            <div class="ps-pack-grid">${packHtml}</div>
          </div>
          ${minionHtml}
        </div>
        <div id="ps-center">
          <div class="ps-center-str" title="${_playerStrBreakdown(p).replace(/"/g, '&quot;')}" style="cursor:help">STR ${p.strength}</div>
          <div id="ps-hero-area">${heroHtml}</div>
          ${tcRowHtml}
        </div>
        <div id="ps-right">${equipHtml}</div>
      </div>
    </div>`;
  attachCardPreviews(overlay);
  if (!inPlacement) {
    _attachCtxMenus(overlay);
    _attachDragDrop(overlay);
  }
}

function _psSlotCell(label, item, slotKey, slotIdx) {
  const inPlacement = _invPlacementItem !== null;
  // Determine if this slot type matches the item being placed
  const _slotTypeMap = { equip_helmet: 'helmet', equip_chest: 'chest', equip_leg: 'legs', equip_weapon: 'weapon' };
  const thisSlotType = _slotTypeMap[slotKey] || '';
  const itemSlot = _invPlacementItem ? _invPlacementItem.slot : null;
  const slotMatch = inPlacement && itemSlot === thisSlotType;
  if (item) {
    const imgSrc = item.card_image ? `/games/werblers/images/${item.card_image}` : null;
    const safeName = (item.name || '').replace(/"/g, '&quot;');
    const placementClass = slotMatch ? ' ps-slot-placement-target' : '';
    const placementAttr  = slotMatch
      ? `onclick="_psPlaceEquipDiscard('${slotKey}', ${slotIdx})" title="Equip here — replace ${safeName}"`
      : (inPlacement ? '' : `data-ctx="equip" data-slot-key="${slotKey}" data-slot-idx="${slotIdx}" data-item-name="${safeName}" data-item-image="${imgSrc || ''}"`);
    // Show card preview even in placement mode so user can check Str of existing items
  const previewAttrs = imgSrc
      ? `class="ps-slot ps-slot-card${placementClass} has-card-preview" data-card-image="${imgSrc}"` : null;
    if (imgSrc) {
      const cls = previewAttrs
        ? previewAttrs
        : `class="ps-slot ps-slot-card${placementClass}"`;
      return `<div class="ps-equip-cell">
        <div class="ps-slot-title-above">${label}</div>
        <div ${cls} ${placementAttr}>
          <img class="ps-slot-card-img" src="${imgSrc}" alt="${item.name}">
        </div></div>`;
    }
    const strSign = item.strength_bonus >= 0 ? '+' : '';
    const strSub = item.strength_bonus !== 0 ? `${strSign}${item.strength_bonus} Str` : '';
    const badges = item.tokens ? ' ' + tokenBadges(item.tokens) : '';
    return `<div class="ps-equip-cell">
      <div class="ps-slot-title-above">${label}</div>
      <div class="ps-slot ps-slot-filled${placementClass}" ${placementAttr}>
        <div class="ps-slot-divider"></div>
        <div class="ps-slot-name">${item.name}${badges}</div>
        ${strSub ? `<div class="ps-slot-sub">${strSub}</div>` : ''}
      </div></div>`;
  }
  // Empty slot
  if (slotMatch) {
    return `<div class="ps-equip-cell">
      <div class="ps-slot-title-above">${label}</div>
      <div class="ps-slot ps-slot-empty ps-slot-placement-target" onclick="_psPlaceEquip()" title="Equip here"></div>
    </div>`;
  }
  return `<div class="ps-equip-cell">
    <div class="ps-slot-title-above">${label}</div>
    <div class="ps-slot ps-slot-empty" data-slot-key="${slotKey}"></div>
  </div>`;
}

const _psEmptyCell = '<div class="ps-equip-cell"></div>';

function _ps2HGhostSlot(weapon) {
  return _ps2HGhostSlot_labeled(weapon, 'L. Hand');
}

function _ps2HGhostSlot_labeled(weapon, label) {
  const imgSrc = weapon && weapon.card_image ? `/games/werblers/images/${weapon.card_image}` : null;
  if (imgSrc) {
    return `<div class="ps-equip-cell">
      <div class="ps-slot-title-above">${label}</div>
      <div class="ps-slot ps-slot-card ps-slot-ghost">
        <img class="ps-slot-card-img" src="${imgSrc}" alt="${weapon.name} (2H)">
      </div></div>`;
  }
  return `<div class="ps-equip-cell">
    <div class="ps-slot-title-above">${label} (2H)</div>
    <div class="ps-slot ps-slot-ghost"></div>
  </div>`;
}

function _psDisabledChestCell() {
  return `<div class="ps-equip-cell">
    <div class="ps-slot-title-above">Chest</div>
    <div class="ps-slot ps-slot-disabled"></div>
  </div>`;
}

function _buildEquipGrid(p) {
  const helmetSlots = p.helmet_slots || 1;
  const chestSlots  = p.chest_slots  || 0;
  const legSlots    = p.legs_slots != null ? p.legs_slots : 1;
  const weaponHands = p.weapon_hands || 2;
  const handRows    = Math.ceil(weaponHands / 2);
  const extraRows   = Math.max(Math.max(chestSlots, 1) - 1, handRows - 1);

  const rows = [];

  // Extra head slots — shown ABOVE the main head (in reverse so closest extra is just above)
  for (let i = helmetSlots - 1; i >= 1; i--) {
    rows.push(`<div class="ps-equip-row">${_psEmptyCell}${_psSlotCell('Head', p.helmets[i] || null, 'equip_helmet', i)}${_psEmptyCell}</div>`);
  }

  // Main head row
  rows.push(`<div class="ps-equip-row">${_psEmptyCell}${_psSlotCell('Head', p.helmets[0] || null, 'equip_helmet', 0)}${_psEmptyCell}</div>`);

  // Main hand/chest row (R.Hand | Chest | L.Hand)
  const mainWeapon = p.weapons[0] || null;
  const r0 = 0 < weaponHands ? _psSlotCell('R. Hand', mainWeapon, 'equip_weapon', 0) : _psEmptyCell;
  // L.Hand: if main weapon is 2H, show a ghost copy (display only, no interaction)
  let l0;
  if (1 < weaponHands) {
    l0 = (mainWeapon && mainWeapon.hands === 2) ? _ps2HGhostSlot(mainWeapon) : _psSlotCell('L. Hand', p.weapons[1] || null, 'equip_weapon', 1);
  } else {
    l0 = _psEmptyCell;
  }
  // Chest: show disabled (crossed out) when player has no chest slots
  const chestCell0 = chestSlots === 0 ? _psDisabledChestCell() : _psSlotCell('Chest', p.chest_armor[0] || null, 'equip_chest', 0);
  rows.push(`<div class="ps-equip-row">${r0}${chestCell0}${l0}</div>`);

  // Extra rows — blend extra hand pairs with extra chest slots
  // Apply 2H ghost logic: if a right-hand weapon uses 2 hands, show ghost in left-hand slot
  for (let i = 0; i < extraRows; i++) {
    const rIdx    = (i + 1) * 2;
    const lIdx    = (i + 1) * 2 + 1;
    const cIdx    = i + 1;
    const rLabel  = `Hand ${rIdx + 1}`;
    const lLabel  = `Hand ${lIdx + 1}`;
    const rWeapon = rIdx < weaponHands ? (p.weapons[rIdx] || null) : null;
    const rCell   = rIdx < weaponHands ? _psSlotCell(rLabel, rWeapon, 'equip_weapon', rIdx) : _psEmptyCell;
    const cCell   = cIdx < chestSlots  ? _psSlotCell('Chest', p.chest_armor[cIdx] || null, 'equip_chest', cIdx) : _psEmptyCell;
    let lCell;
    if (lIdx < weaponHands) {
      // Show ghost if right-hand weapon in this row is 2H
      lCell = (rWeapon && rWeapon.hands === 2)
        ? _ps2HGhostSlot_labeled(rWeapon, lLabel)
        : _psSlotCell(lLabel, p.weapons[lIdx] || null, 'equip_weapon', lIdx);
    } else {
      lCell = _psEmptyCell;
    }
    rows.push(`<div class="ps-equip-row">${rCell}${cCell}${lCell}</div>`);
  }

  // Main feet row (only if leg slot exists)
  if (legSlots > 0) {
    rows.push(`<div class="ps-equip-row">${_psEmptyCell}${_psSlotCell('Feet', p.leg_armor[0] || null, 'equip_leg', 0)}${_psEmptyCell}</div>`);
  }

  // Extra feet slots — below main feet
  for (let i = 1; i < legSlots; i++) {
    rows.push(`<div class="ps-equip-row">${_psEmptyCell}${_psSlotCell('Feet', p.leg_armor[i] || null, 'equip_leg', i)}${_psEmptyCell}</div>`);
  }

  return `<div class="ps-equip-grid">${rows.join('')}</div>`;
}

// ================================================================ TRAIT/CURSE TOOLTIPS
const _tcTooltip = (() => {
  const el = document.createElement('div');
  el.id = 'tc-tooltip';
  el.className = 'tc-tooltip hidden';
  document.body.appendChild(el);
  return el;
})();

document.addEventListener('mouseover', (e) => {
  const target = e.target.closest('.tc-hoverable');
  if (!target) return;
  const name = target.dataset.tcName || '';
  const desc = target.dataset.tcDesc || '';
  if (!name) return;
  _tcTooltip.innerHTML = `<div class="tc-tooltip-name">${name}</div>${desc ? `<div class="tc-tooltip-desc">${desc}</div>` : ''}`;
  _tcTooltip.classList.remove('hidden');
});
document.addEventListener('mousemove', (e) => {
  if (_tcTooltip.classList.contains('hidden')) return;
  const gap = 16;
  const tw = _tcTooltip.offsetWidth;
  const th = _tcTooltip.offsetHeight;
  let x = e.clientX + gap;
  let y = e.clientY + gap;
  if (x + tw > window.innerWidth - 8) x = e.clientX - tw - gap;
  if (y + th > window.innerHeight - 8) y = e.clientY - th - gap;
  _tcTooltip.style.left = x + 'px';
  _tcTooltip.style.top  = y + 'px';
});
document.addEventListener('mouseout', (e) => {
  if (!e.target.closest('.tc-hoverable')) return;
  if (!e.relatedTarget || !e.relatedTarget.closest('.tc-hoverable')) {
    _tcTooltip.classList.add('hidden');
  }
});

// ================================================================ MOVEMENT DECK VIEWER
function openDeckViewer(pile) {
  if (!gameState) return;
  const p = gameState.players.find(x => x.player_id === viewingPlayerId) || gameState.players[0];
  if (!p) return;
  let cards = [];
  let title = '';
  if (pile === 'deck') {
    cards = p.movement_deck_cards || [];
    title = `Movement Deck (${cards.length} remaining)`;
  } else {
    cards = p.movement_discard_list || [];
    title = `Movement Discard (${cards.length} cards)`;
  }
  const grid = cards.map(v => {
    const imgVal = Math.min(Math.max(v, 1), 5);
    return `<div class="mv-card mv-card-small"><img class="mv-card-img" src="/games/werblers/images/Movement/Movement Card ${imgVal}.png" alt="${v}"></div>`;
  }).join('') || '<div class="dv-empty">Empty</div>';
  document.getElementById('deck-viewer-title').textContent = title;
  document.getElementById('deck-viewer-grid').innerHTML = grid;
  document.getElementById('deck-viewer-modal').classList.remove('hidden');
}
function closeDeckViewer() {
  document.getElementById('deck-viewer-modal').classList.add('hidden');
}

// ================================================================ CHARLIE WORK DECISION
let _charlieWorkLevel = null;

function _showCharlieWorkDecision(level) {
  _charlieWorkLevel = level;
  const modal = document.getElementById('charlie-work-modal');
  if (!modal) return;
  modal.querySelector('.modal-desc').textContent =
    `You have "No More Charlie Work". Fight a harder Tier ${level + 1} monster for better rewards, or fight a normal Tier ${level} monster?`;
  modal.classList.remove('hidden');
}

async function resolveCharlieWork(useIt) {
  const modal = document.getElementById('charlie-work-modal');
  if (modal) modal.classList.add('hidden');
  const resp = await fetch('/games/werblers/api/resolve_charlie_work', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ use_it: useIt }),
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

// ================================================================ OCCUPIED SLOT MODAL
let _occupiedSlotKey = null;
let _occupiedSlotIdx = null;

function _showOccupiedSlotModal(existingName, slotKey, idx) {
  _occupiedSlotKey = slotKey;
  _occupiedSlotIdx = idx;
  const modal = document.getElementById('occupied-slot-modal');
  if (!modal) return;
  modal.querySelector('.modal-desc').textContent =
    `"${existingName}" is already equipped here. What would you like to do?`;
  modal.classList.remove('hidden');
}

function _occupiedSlotAction(action) {
  const modal = document.getElementById('occupied-slot-modal');
  if (modal) modal.classList.add('hidden');
  if (action === 'discard') {
    _finishPlacement({ placement: 'equip', equip_action: 'discard', equip_item_index: _occupiedSlotIdx });
  } else if (action === 'to_pack') {
    // Check if pack is full — if so, player must choose which pack item to discard
    const p = gameState && gameState.players.find(pl => pl.is_current);
    if (p && p.pack_slots_free <= 0) {
      _showPlacementPackDiscardChoice(_occupiedSlotIdx);
    } else {
      _finishPlacement({ placement: 'equip', equip_action: 'swap', equip_item_index: _occupiedSlotIdx });
    }
  }
  // 'cancel' → do nothing, placement stays open
}

function _showPlacementPackDiscardChoice(equipItemIdx) {
  const p = gameState && gameState.players.find(pl => pl.is_current);
  if (!p) return;
  const packItems = [
    ...(p.pack || []).map((item, i) => ({ name: item.name, card_image: item.card_image, idx: i })),
    ...(p.consumables || []).map((item, i) => ({ name: item.name, card_image: item.card_image, idx: p.pack.length + i })),
    ...(p.captured_monsters || []).map((item, i) => ({ name: item.name, card_image: item.card_image, idx: p.pack.length + (p.consumables || []).length + i })),
  ];
  const overlay = document.createElement('div');
  overlay.id = 'placement-pack-discard-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:2000;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center';
  const box = document.createElement('div');
  box.style.cssText = 'background:var(--card-bg,#1a1a2e);border:1px solid var(--border,#333);border-radius:12px;padding:20px 24px;max-width:480px;text-align:center';
  box.innerHTML = `<div style="font-family:'Cinzel',serif;font-size:14px;color:var(--gold,#c9a84c);margin-bottom:12px">Pack Full</div>
    <div style="font-size:12px;color:var(--text,#e0e0e0);margin-bottom:16px">Choose an item to discard from your pack to make room for the displaced item:</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center">${packItems.map(p => {
      const img = p.card_image ? `<img src="/games/werblers/images/${p.card_image}" style="width:70px;border-radius:4px;display:block">` : '';
      return `<div class="rake-equip-btn" style="cursor:pointer" onclick="window._confirmPlacementPackDiscard(${p.idx})">
        ${img}
        <div style="font-size:10px;color:var(--text,#e0e0e0);margin-top:4px;max-width:80px;word-break:break-word">${p.name}</div>
      </div>`;
    }).join('')}</div>
    <div style="margin-top:16px"><button class="btn-secondary" onclick="window._cancelPlacementPackDiscard()">Cancel</button></div>`;
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  window._confirmPlacementPackDiscard = (dpi) => {
    overlay.remove();
    _finishPlacement({ placement: 'equip', equip_action: 'swap', equip_item_index: equipItemIdx, pack_discard_index: dpi });
  };
  window._cancelPlacementPackDiscard = () => overlay.remove();
}

// ================================================================ BATTLE GEAR SECTION BUILDER
function _buildBattleGearSection(combat) {
  const gear   = combat.player_gear   || [];
  const traits = combat.player_traits || [];
  const curses = combat.player_curses || [];
  const minions = combat.player_minions || [];
  if (!gear.length && !traits.length && !curses.length && !minions.length) return '';

  // Categorize gear by slot
  const helmets = gear.filter(i => i.slot === 'helmet');
  const chests  = gear.filter(i => i.slot === 'chest');
  const legs    = gear.filter(i => i.slot === 'legs');
  const weapons = gear.filter(i => i.slot === 'weapon');

  // Slot capacities from enriched combat info
  const helmetSlots = combat.player_helmet_slots || 1;
  const chestSlots  = combat.player_chest_slots  || 1;
  const legSlots    = combat.player_legs_slots   || 1;
  const weaponHands = combat.player_weapon_hands || 2;

  function equipSlot(item, label) {
    if (item) {
      const img = item.card_image ? `/games/werblers/images/${item.card_image}` : '';
      const bonus = item.strength_bonus >= 0 ? `+${item.strength_bonus}` : `${item.strength_bonus}`;
      if (img) {
        return `<div class="battle-equip-slot has-card-preview" data-card-image="${img}" title="${item.name} (${bonus} Str)">
          <img src="${img}" alt="${item.name}" onerror="this.parentElement.classList.add('is-empty')">
        </div>`;
      }
      return `<div class="battle-equip-slot" title="${item.name} (${bonus})" style="display:flex;align-items:center;justify-content:center;font-size:7px;text-align:center;padding:2px">${item.name}</div>`;
    }
    return `<div class="battle-equip-slot is-empty" title="${label}"></div>`;
  }

  const handRows = Math.ceil(weaponHands / 2);
  const extraRows = Math.max(chestSlots - 1, handRows - 1);
  const rows = [];

  // Extra head rows above main
  for (let i = helmetSlots - 1; i >= 1; i--) {
    rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell"></div><div class="battle-equip-cell">${equipSlot(helmets[i] || null, 'Head')}</div><div class="battle-equip-cell"></div></div>`);
  }

  // Main head row
  rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell"></div><div class="battle-equip-cell">${equipSlot(helmets[0] || null, 'Head')}</div><div class="battle-equip-cell"></div></div>`);

  // Main chest / weapon row
  const rw0 = weaponHands >= 1 ? equipSlot(weapons[0] || null, 'R.Hand') : '';
  const lw0 = weaponHands >= 2 ? equipSlot(weapons[1] || null, 'L.Hand') : '';
  rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell">${rw0}</div><div class="battle-equip-cell">${equipSlot(chests[0] || null, 'Chest')}</div><div class="battle-equip-cell">${lw0}</div></div>`);

  // Extra hand/chest rows
  for (let i = 0; i < extraRows; i++) {
    const rIdx = (i + 1) * 2;
    const lIdx = (i + 1) * 2 + 1;
    const cIdx = i + 1;
    const rCell = rIdx < weaponHands ? equipSlot(weapons[rIdx] || null, `Hand ${rIdx + 1}`) : '';
    const lCell = lIdx < weaponHands ? equipSlot(weapons[lIdx] || null, `Hand ${lIdx + 1}`) : '';
    const cCell = cIdx < chestSlots ? equipSlot(chests[cIdx] || null, 'Chest') : '';
    rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell">${rCell}</div><div class="battle-equip-cell">${cCell}</div><div class="battle-equip-cell">${lCell}</div></div>`);
  }

  // Main leg row
  rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell"></div><div class="battle-equip-cell">${equipSlot(legs[0] || null, 'Feet')}</div><div class="battle-equip-cell"></div></div>`);

  // Extra leg rows
  for (let i = 1; i < legSlots; i++) {
    rows.push(`<div class="battle-equip-row"><div class="battle-equip-cell"></div><div class="battle-equip-cell">${equipSlot(legs[i] || null, 'Feet')}</div><div class="battle-equip-cell"></div></div>`);
  }

  let html = `<div class="battle-equip-grid">${rows.join('')}</div>`;

  if (minions.length) {
    html += `<div class="battle-left-section-label" style="margin-top:6px">Minions</div>`;
    for (const m of minions) {
      if (m.card_image) {
        html += `<div class="battle-equip-slot has-card-preview" data-card-image="/games/werblers/images/${m.card_image}" title="${m.name} (+${m.strength_bonus} Str)" style="width:56px;height:80px;margin:2px 0">
          <img src="/games/werblers/images/${m.card_image}" alt="${m.name}" onerror="this.parentElement.classList.add('is-empty')">
        </div>`;
      } else {
        html += `<div class="battle-left-tag" style="background:var(--surface2);border:1px solid var(--border);color:var(--gold)">${m.name} (+${m.strength_bonus})</div>`;
      }
    }
  }
  if (traits.length) {
    html += `<div class="battle-left-section-label" style="margin-top:6px">Traits</div>`;
    for (const t of traits) {
      html += `<div class="battle-left-tag is-trait tc-hoverable" data-tc-name="${t.name}" data-tc-desc="${(t.description||'').replace(/"/g,'&quot;')}">${t.name}</div>`;
    }
  }
  if (curses.length) {
    html += `<div class="battle-left-section-label" style="margin-top:6px">Curses</div>`;
    for (const c of curses) {
      html += `<div class="battle-left-tag is-curse tc-hoverable" data-tc-name="${c.name}" data-tc-desc="${(c.description||'').replace(/"/g,'&quot;')}">${c.name}</div>`;
    }
  }
  return html;
}

function _monsterStrBreakdownTitle(combat) {
  const lines = [];
  // Derive base from total minus modifiers
  const abilityMod = combat.ability_monster_mod || 0;
  const niceHat = combat.nice_hat_bonus || 0;
  const maleBon = combat.monster_bonus_vs_male || 0;
  const baseSt = (combat.monster_strength || 0) - abilityMod - niceHat - maleBon;
  lines.push(`Base: ${baseSt}`);
  if (maleBon) lines.push(`+${maleBon} vs Men`);
  for (const line of (combat.ability_breakdown || [])) {
    const t = line.trim();
    if (t) lines.push(t);
  }
  lines.push(`Total: ${combat.monster_strength}`);
  return lines.join('\n');
}

function _strBreakdownTitle(combat) {
  const lines = [];
  const base = combat.player_base_strength;
  if (base !== undefined) lines.push(`Base: ${base}`);
  for (const item of (combat.player_gear || [])) {
    const parts = [];
    if (item.strength_bonus) {
      const s = item.strength_bonus >= 0 ? `+${item.strength_bonus}` : `${item.strength_bonus}`;
      parts.push(s);
    }
    if (item.tokens) {
      parts.push(`+${item.tokens} ability`);
    }
    if (parts.length) lines.push(`${item.name}: ${parts.join(', ')}`);
  }
  for (const t of (combat.player_traits || [])) {
    if (t.tokens) lines.push(`${t.name}: +${t.tokens}`);
  }
  for (const m of (combat.player_minions || [])) {
    lines.push(`${m.name} (minion): +${m.strength_bonus}`);
  }
  for (const c of (combat.player_curses || [])) {
    if (c.tokens) lines.push(`${c.name}: ${c.tokens >= 0 ? '+' : ''}${c.tokens}`);
  }
  if (combat.prefight_str_bonus) lines.push(`Consumable bonus: +${combat.prefight_str_bonus}`);
  for (const line of (combat.ability_breakdown || [])) {
    lines.push(line.trim());
  }
  lines.push(`Total: ${Math.max(0, combat.player_strength)}`);
  return lines.join('\n');
}

// ================================================================ MYSTERY EVENT MODAL

let _pendingMysteryEvent = null;
let _mysterySelectedIdx = -1;

function showMysteryEventModal(event, state) {
  _pendingMysteryEvent = event;
  _mysterySelectedIdx = -1;
  const overlay = document.getElementById('battle-overlay');
  // Use the event's own character image as the full-screen background
  const bg = event.image ? `/games/werblers/images/${event.image}` : '';
  const player = state.players.find(p => p.is_current) || state.players[0];

  let bodyHtml = '';
  if (event.event_id === 'mystery_box') {
    // Step 1: intro — "Hey, wanna know what's in this box?"
    bodyHtml = `<div class="mystery-speech-bubble">
      <p>"Hey, wanna know what's in this box?"</p>
    </div>
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

  // Wheel renders its own image in the body; all others show description only
  const showDesc = event.event_id !== 'the_wheel';

  overlay.innerHTML = `
    <div class="battle-bg" style="background-image:url('${bg}')"></div>
    <div class="battle-content mystery-fullscreen">
      <div class="mystery-fs-inner">
        <h2 class="mystery-fs-title">${event.name}</h2>
        ${showDesc ? `<p class="mystery-fs-desc">${event.description || ''}</p>` : ''}
        <div class="mystery-fs-body">${bodyHtml}</div>
      </div>
    </div>`;
  overlay.classList.remove('hidden');
}

// Called when the player clicks Yes on the Mystery Box intro screen.
function _showMysteryBoxWager() {
  const player = gameState?.players?.find(p => p.is_current) || gameState?.players?.[0];
  const bodyEl = document.querySelector('.mystery-fs-body');
  if (!bodyEl) return;
  bodyEl.innerHTML = _renderMysteryBox(_pendingMysteryEvent, player);
}

async function _mysteryBoxDecline() {
  // "A pity…"
  await _showCharacterFarewell(
    _pendingMysteryEvent,
    '"A pity\u2026"',
    () => {}
  );
  await _postResolveMystery({action: 'skip'});
}

function _renderMysteryBox(event, player) {
  const packItems = _getUnifiedPack(player);
  const equipped = _getAllEquipped(player);
  if (packItems.length === 0 && equipped.length === 0) {
    return `<p class="mystery-info">You have nothing to wager!</p>
            <button class="btn-primary" onclick="_resolveMysterySkip()">Continue</button>`;
  }
  function _makeMysteryBtn(item, idx) {
    const img = item.img ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.img}" onerror="this.style.display='none'">` : '';
    return `<div class="mystery-selectable-item" data-idx="${idx}" onclick="_selectMysteryItem(${idx}, this)">
      ${img}<div class="mystery-item-label">${item.name}</div>
    </div>`;
  }
  let html = '<p class="mystery-info">Choose an item to discard:</p>';
  if (packItems.length > 0) {
    html += `<div class="mystery-section-label">Pack</div><div class="mystery-item-grid">${
      packItems.map((item, i) => _makeMysteryBtn({name: item.name, img: item.card_image}, i)).join('')
    }</div>`;
  }
  if (equipped.length > 0) {
    html += `<div class="mystery-section-label">Equipped</div><div class="mystery-item-grid">${
      equipped.map((item, i) => _makeMysteryBtn({name: item.name, img: item.card_image}, packItems.length + i)).join('')
    }</div>`;
  }
  html += `<div class="mystery-btn-row">
    <button class="btn-secondary" onclick="_mysteryBoxBack()">Back</button>
    <button class="btn-primary" id="mystery-confirm-btn" onclick="_resolveMysteryBox(_mysterySelectedIdx)" disabled>Discard &amp; Open</button>
  </div>`;
  return html;
}

function _mysteryBoxBack() {
  // Return to the initial mystery event screen (yes/decline prompt)
  const bodyEl = document.querySelector('.mystery-fs-body');
  if (!bodyEl) return;
  const event = _pendingMysteryEvent;
  if (!event) return;
  bodyEl.innerHTML = `
    <p class="mystery-info">Discard an item to open?</p>
    <div class="mystery-btn-row">
      <button class="btn-primary" onclick="_showMysteryBoxWager()">Yes (discard one item)</button>
      <button class="btn-secondary" onclick="_mysteryBoxDecline()">Decline</button>
    </div>`;
}

function _renderTheWheel(event) {
  const tier = event.tier || 1;
  const imgSrc = `/games/werblers/images/Events/Wheel Tier ${tier}.png`;
  return `<div class="mystery-speech-bubble">
            <p>"Step right up! Spin the wheel! Win a prize <span style="font-size:0.75em;opacity:0.7">(or something else)</span>!"</p>
          </div>
          <img class="mystery-fs-img" src="${imgSrc}" alt="The Wheel" onerror="this.style.display='none'" style="margin:12px auto;display:block">
          <div class="mystery-btn-row">
            <button class="btn-primary mystery-spin-btn" onclick="_resolveMysteryWheel()">Spin</button>
            <button class="btn-secondary" onclick="_wheelDecline()">Decline</button>
          </div>`;
}

async function _wheelDecline() {
  // "Well, coward, don't forget to have your minions spayed and neutered."
  await _showCharacterFarewell(
    _pendingMysteryEvent,
    '"Well, coward, don\'t forget to have your minions spayed and neutered."',
    () => {}
  );
  await _postResolveMystery({action: 'skip'});
}

function _renderTheSmith(event, player) {
  const packItems = _getUnifiedPack(player);
  if (event.tier < 3) {
    const equipped = _getAllEquipped(player);
    const allItems = [...packItems.map((item, i) => ({name: item.name, img: item.card_image, idx: i})),
                      ...equipped.map((item, i) => ({name: item.name, img: item.card_image, idx: packItems.length + i}))];
    if (allItems.length < 3) {
      return `<p class="mystery-info">You need at least 3 items to trade. You have ${allItems.length}.</p>
              <button class="btn-primary" onclick="_resolveMysterySkip()">Leave</button>`;
    }
    const itemBtns = allItems.map(item => {
      const img = item.img ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.img}" onerror="this.style.display='none'">` : '';
      return `<div class="mystery-selectable-item smith-item" data-idx="${item.idx}" onclick="_toggleSmithItem(this)">
        ${img}<div class="mystery-item-label">${item.name}</div>
      </div>`;
    }).join('');
    return `<p class="mystery-info">Select 3 items to trade for a Tier ${Math.min(event.tier + 1, 3)} item:</p>
            <div class="mystery-item-grid" id="smith-grid">${itemBtns}</div>
            <div class="mystery-btn-row">
              <button class="btn-primary" id="smith-confirm-btn" onclick="_resolveMysterySmith()" disabled>Trade (select 3)</button>
              <button class="btn-secondary" onclick="_resolveMysterySkip()">Decline</button>
            </div>`;
  } else {
    // Tier 3: trade 3 pack items AND enhance an equipped item
    const equipped = _getAllEquipped(player);
    if (packItems.length < 3) {
      return `<p class="mystery-info">You need at least 3 pack items to trade. You have ${packItems.length}.</p>
              <button class="btn-primary" onclick="_resolveMysterySkip()">Leave</button>`;
    }
    if (equipped.length === 0) {
      return `<p class="mystery-info">You have no equipped items to enhance.</p>
              <button class="btn-primary" onclick="_resolveMysterySkip()">Leave</button>`;
    }
    _smithSelected3.clear();
    const wagerBtns = packItems.map((item, i) => {
      const img = item.card_image ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.card_image}" onerror="this.style.display='none'">` : '';
      return `<div class="mystery-selectable-item smith3-wager" data-idx="${i}" onclick="_toggleSmithT3Item(this)">
        ${img}<div class="mystery-item-label">${item.name}</div>
      </div>`;
    }).join('');
    const enhanceBtns = equipped.map((item, i) => {
      const img = item.card_image ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.card_image}" onerror="this.style.display='none'">` : '';
      return `<div class="mystery-selectable-item" data-idx="${i}" onclick="_selectMysteryItem(${i}, this)">
        ${img}<div class="mystery-item-label">${item.name} (+${item.strength_bonus})</div>
      </div>`;
    }).join('');
    return `<p class="mystery-info">Select 3 items from your pack to trade:</p>
            <div class="mystery-item-grid" id="smith3-wager-grid">${wagerBtns}</div>
            <p class="mystery-info" style="margin-top:12px">Choose an equipped item to receive +3 Str:</p>
            <div class="mystery-item-grid" id="smith3-enhance-grid">${enhanceBtns}</div>
            <div class="mystery-btn-row">
              <button class="btn-primary" id="smith3-confirm-btn" onclick="_resolveSmithT3()" disabled>Trade &amp; Enhance</button>
              <button class="btn-secondary" onclick="_resolveMysterySkip()">Decline</button>
            </div>`;
  }
}

function _renderBandits(event) {
  return `<p class="mystery-info">Bandits ambush you and steal one of your equipped items!</p>
          <div class="mystery-btn-row">
            <button class="btn-primary" onclick="_resolveMysteryAuto('bandits')">Face the Bandits</button>
          </div>`;
}

function _renderThief(event) {
  return `<p class="mystery-info">A thief sneaks up and steals everything from your pack!</p>
          <div class="mystery-btn-row">
            <button class="btn-primary" onclick="_resolveMysteryAuto('thief')">Encounter the Thief</button>
          </div>`;
}

function _renderBeggar(event, player) {
  // When beggar_completed=true the beggar is filtered from the event pool, so this is a safety fallback only.
  const beggarDone = player.beggar_completed || false;
  if (beggarDone) {
    return `<div class="mystery-speech-bubble"><p>"I have nothing more for you. Good luck."</p></div>
            <div class="mystery-btn-row">
              <button class="btn-primary" onclick="_resolveMysterySkip()">Continue</button>
            </div>`;
  }
  const packItems = _getUnifiedPack(player);
  const equipped = _getAllEquipped(player);
  if (packItems.length + equipped.length === 0) {
    return `<div class="mystery-speech-bubble"><p>"Do you have anything to spare for an old man?"</p></div>
            <p class="mystery-info">You have nothing to give.</p>
            <div class="mystery-btn-row">
              <button class="btn-primary" onclick="_resolveMysterySkip()">Continue</button>
            </div>`;
  }
  return `<div class="mystery-speech-bubble"><p>"Do you have anything to spare for an old man?"</p></div>
          <div class="mystery-btn-row">
            <button class="btn-primary" onclick="_beggarShowItemPicker()">Yes</button>
            <button class="btn-secondary" onclick="_beggarSayNo()">No</button>
          </div>`;
}

function _beggarSayNo() {
  const bodyEl = document.querySelector('.mystery-fs-body');
  if (!bodyEl) return;
  bodyEl.innerHTML = `
    <div class="mystery-speech-bubble"><p>"Thank you anyway..."</p></div>
    <div class="mystery-btn-row">
      <button class="btn-primary" onclick="_resolveMysterySkip()">Continue</button>
    </div>`;
}

function _beggarShowItemPicker() {
  const player = gameState?.players?.find(p => p.is_current) || gameState?.players?.[0];
  if (!player) return;
  const packItems = _getUnifiedPack(player);
  const equipped = _getAllEquipped(player);
  _mysterySelectedIdx = -1;
  function _makeBeggarBtn(item, idx) {
    const img = item.img ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.img}" onerror="this.style.display='none'">` : '';
    return `<div class="mystery-selectable-item" data-idx="${idx}" onclick="_selectMysteryItem(${idx}, this)">
      ${img}<div class="mystery-item-label">${item.name}</div>
    </div>`;
  }
  const bodyEl = document.querySelector('.mystery-fs-body');
  if (!bodyEl) return;
  let html = '<p class="mystery-info">Choose an item to give:</p>';
  if (packItems.length > 0) {
    html += `<div class="mystery-section-label">Pack</div><div class="mystery-item-grid">${
      packItems.map((item, i) => _makeBeggarBtn({name: item.name, img: item.card_image}, i)).join('')
    }</div>`;
  }
  if (equipped.length > 0) {
    html += `<div class="mystery-section-label">Equipped</div><div class="mystery-item-grid">${
      equipped.map((item, i) => _makeBeggarBtn({name: item.name, img: item.card_image}, packItems.length + i)).join('')
    }</div>`;
  }
  html += `<div class="mystery-btn-row">
    <button class="btn-primary" id="mystery-confirm-btn" onclick="_resolveBeggarGive(_mysterySelectedIdx)" disabled>Give Item</button>
  </div>`;
  bodyEl.innerHTML = html;
}

// Shared item selection for events that need select-then-confirm
function _selectMysteryItem(idx, el) {
  _mysterySelectedIdx = idx;
  document.querySelectorAll('.mystery-selectable-item').forEach(b => b.classList.remove('selected'));
  if (el) el.classList.add('selected');
  const btn = document.getElementById('mystery-confirm-btn');
  if (btn) btn.disabled = false;
  // Also refresh smith3 confirm button if we're in that mode
  const smith3Btn = document.getElementById('smith3-confirm-btn');
  if (smith3Btn) {
    smith3Btn.disabled = !(_smithSelected3.size === 3 && _mysterySelectedIdx >= 0);
  }
}

// Helper: get unified pack items
function _getUnifiedPack(player) {
  const items = [];
  for (const p of (player.pack || [])) items.push(p);
  for (const c of (player.consumables || [])) items.push(c);
  for (const m of (player.captured_monsters || [])) items.push(m);
  return items;
}

// Helper: get all equipped items (flat list)
function _getAllEquipped(player) {
  return [...(player.helmets || []), ...(player.chest_armor || []),
          ...(player.leg_armor || []), ...(player.weapons || [])];
}

// Smith: toggle item selection (exactly 3)
let _smithSelected = new Set();
let _smithSelected3 = new Set();
function _toggleSmithItem(el) {
  const idx = parseInt(el.dataset.idx);
  if (_smithSelected.has(idx)) {
    _smithSelected.delete(idx);
    el.classList.remove('selected');
  } else {
    if (_smithSelected.size >= 3) return;
    _smithSelected.add(idx);
    el.classList.add('selected');
  }
  const confirmBtn = document.getElementById('smith-confirm-btn');
  if (confirmBtn) {
    confirmBtn.disabled = _smithSelected.size !== 3;
    confirmBtn.textContent = _smithSelected.size === 3 ? 'Trade!' : `Trade (select ${3 - _smithSelected.size} more)`;
  }
}

// --- Resolution handlers ---

async function _resolveMysteryBox(wagerIndex) {
  if (wagerIndex < 0) return;
  await _postResolveMystery({action: 'open', wager_index: wagerIndex});
}

async function _resolveMysteryWheel() {
  await _postResolveMystery({action: 'spin'});
}

async function _resolveMysterySmith() {
  const indices = Array.from(_smithSelected).sort((a,b) => b - a);
  _smithSelected.clear();
  await _postResolveMystery({action: 'smith', smith_indices: indices});
}

async function _resolveSmithEnhance(equipIndex) {
  if (equipIndex < 0) return;
  await _postResolveMystery({action: 'smith', smith_equip_index: equipIndex, smith_indices: []});
}

// Smith Tier 3: toggle wager item
function _toggleSmithT3Item(el) {
  const idx = parseInt(el.dataset.idx);
  if (_smithSelected3.has(idx)) {
    _smithSelected3.delete(idx);
    el.classList.remove('selected');
  } else {
    if (_smithSelected3.size >= 3) return;
    _smithSelected3.add(idx);
    el.classList.add('selected');
  }
  const btn = document.getElementById('smith3-confirm-btn');
  if (btn) {
    const ready = _smithSelected3.size === 3 && _mysterySelectedIdx >= 0;
    btn.disabled = !ready;
    btn.textContent = _smithSelected3.size < 3
      ? `Trade & Enhance (select ${3 - _smithSelected3.size} more)`
      : 'Trade & Enhance';
  }
}



async function _resolveSmithT3() {
  if (_smithSelected3.size < 3 || _mysterySelectedIdx < 0) return;
  const indices = Array.from(_smithSelected3).sort((a, b) => b - a);
  const enhanceIdx = _mysterySelectedIdx;
  _smithSelected3.clear();
  _mysterySelectedIdx = -1;
  await _postResolveMystery({action: 'smith', smith_indices: indices, smith_equip_index: enhanceIdx});
}

async function _resolveMysteryAuto(eventType) {
  await _postResolveMystery({action: 'accept'});
}

async function _resolveBeggarGive(giveIndex) {
  if (giveIndex < 0) return;
  await _postResolveMystery({action: 'give', wager_index: giveIndex});
}

async function _resolveMysterySkip() {
  await _postResolveMystery({action: 'skip'});
}

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
      try {
        errData = await resp.json();
        errMsg = errData.error || errMsg;
      } catch (_) {
        const rawText = await resp.text().catch(() => '');
        if (rawText) errMsg += '\n\n' + rawText.substring(0, 800);
      }
      // Update state if provided (keeps game consistent)
      if (errData.state) { gameState = errData.state; applyState(errData.state); }
      console.error('resolve_mystery failed', resp.status, errMsg);
      // For mystery box wager validation failure, stay on the wager screen so player can retry
      const isWagerError = _pendingMysteryEvent?.event_id === 'mystery_box' && errMsg.includes('Invalid');
      if (isWagerError) {
        alert('Please select a valid item to wager.');
        _showMysteryBoxWager();
      } else {
        alert(`Mystery event error:\n${errMsg}`);
        _closeMysteryResult();
      }
      return;
    }
    const data = await resp.json();
    // Save the player who encountered this event BEFORE the turn advances in the state
    const mysteryPlayer = gameState?.players?.find(x => x.is_current) || null;
    if (data.state) { gameState = data.state; applyState(data.state); }

    const isWheel = _pendingMysteryEvent && _pendingMysteryEvent.event_id === 'the_wheel';
    const isBandits = _pendingMysteryEvent && _pendingMysteryEvent.event_id === 'bandits';
    const isMysteryBox = _pendingMysteryEvent && _pendingMysteryEvent.event_id === 'mystery_box';

    // Determine the farewell quote for this event
    const _wheelFarewell = '"Congratulations or sorry that happened! Remember to spay and neuter your minions!"';
    const _boxFarewell = '"Wow, I\'m envious\u2026"';

    if (data.phase === 'offer_chest') {
      // Item prize — show announcement, then item placement, then farewell
      const farewellQuote = isWheel ? _wheelFarewell : isMysteryBox ? _boxFarewell : null;
      await _showMysteryOutcome(data, () => {
        // Stash farewell info so we show it after chest resolution
        if (farewellQuote) {
          _pendingMysteryFarewell = { event: _pendingMysteryEvent, quote: farewellQuote };
        }
        _pendingMysteryEvent = null;
        _pendingOfferData = data.offer;
        // IMPORTANT: hide the battle-overlay so the player-sheet placement overlay
        // (z-index 250) is not blocked behind it (z-index 400).
        document.getElementById('battle-overlay').classList.add('hidden');
        showChestModal(data.offer, {});
      }, mysteryPlayer);
    } else if (data.phase === 'beggar_thank') {
      _showBeggarThankYou(data, mysteryPlayer);
    } else if (data.phase === 'fairy_king_reveal') {
      _showFairyKingReveal(data);
    } else {
      // done — show outcome screen then farewell
      if (data.prize_type === 'skip') {
        _closeMysteryResult();
      } else if (isWheel) {
        // Wheel: nothing / trait / etc → announcement, then farewell
        await _showMysteryOutcome(data, async () => {
          await _showCharacterFarewell(
            _pendingMysteryEvent,
            _wheelFarewell,
            () => _closeMysteryResult()
          );
        }, mysteryPlayer);
      } else if (isMysteryBox) {
        // Mystery Box: nothing / trait → announcement, then farewell
        await _showMysteryOutcome(data, async () => {
          await _showCharacterFarewell(
            _pendingMysteryEvent,
            _boxFarewell,
            () => _closeMysteryResult()
          );
        }, mysteryPlayer);
      } else if (isBandits && data.prize_type === 'stolen') {
        await _showMysteryOutcome(data, async () => {
          await _showCharacterFarewell(
            _pendingMysteryEvent,
            '"Thank you for your\u2026 heh\u2026 generosity."',
            () => _closeMysteryResult()
          );
        }, mysteryPlayer);
      } else {
        await _showMysteryOutcome(data, () => _closeMysteryResult(), mysteryPlayer);
      }
    }
  } catch (err) {
    console.error('resolve_mystery error:', err);
  }
}

// Pending farewell info for events that need to show a farewell AFTER item placement
let _pendingMysteryFarewell = null;

// Show a character farewell/quote screen using the event's own image as background.
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
        <div class="mystery-btn-row">
          <button class="btn-primary" id="mystery-farewell-btn">Continue</button>
        </div>
      </div>
    </div>`;
  overlay.classList.remove('hidden');

  return new Promise(resolve => {
    document.getElementById('mystery-farewell-btn').onclick = () => {
      if (typeof onContinue === 'function') onContinue();
      resolve();
    };
  });
}

// ------ Outcome screen shown after resolving any mystery event ------
function _getMysteryOutcomeContent(data) {
  const eventId = data.event_id || (_pendingMysteryEvent && _pendingMysteryEvent.event_id) || '';
  const prizeType = data.prize_type || '';
  const label = data.mystery_result || '';

  const itemName = data.offer?.items?.[0]?.name || '';

  let title = '';
  let outcomeText = '';
  let quoteText = '';

  switch (eventId) {
    case 'mystery_box':
      title = 'Mystery Box';
      if (prizeType === 'nothing') {
        outcomeText = 'You got nothing! Good day sir!';
      } else if (prizeType === 'trait') {
        const monsterNameBox = data.monster_name || '';
        const traitNameBox = data.trait_name || 'a mysterious trait';
        const traitDescBox = data.trait_description ? `<br><span style="font-size:0.85em;color:var(--text-dim);font-style:italic">${data.trait_description}</span>` : '';
        outcomeText = monsterNameBox
          ? `The box contained\u2026 a dead <strong>${monsterNameBox}</strong>! Its trait is now yours: <strong>${traitNameBox}</strong>!${traitDescBox}`
          : `The box contained\u2026 a trait: <strong>${traitNameBox}</strong>!${traitDescBox}`;
      } else if (prizeType === 'item' || prizeType === 'item_up' || prizeType === 'item_t3') {
        outcomeText = `The box contained\u2026 <strong>${itemName || 'an item'}</strong>!`;
      } else if (prizeType === 'curse') {
        const curseMonsterBox = data.monster_name || '';
        const curseDescBox = data.curse_description ? `<br><span style="font-size:0.85em;color:var(--text-dim);font-style:italic">${data.curse_description}</span>` : '';
        outcomeText = curseMonsterBox
          ? `The box contained\u2026 <strong>${curseMonsterBox}</strong>! And with it comes a curse: <strong>${data.curse_name || 'a curse'}</strong>!${curseDescBox}`
          : `The box contained\u2026 <strong>A CURSE!</strong> You received: <strong>${data.curse_name || 'a curse'}</strong>!${curseDescBox}`;
      } else {
        outcomeText = label || 'The mystery has been resolved.';
      }
      break;
    case 'the_wheel':
      title = 'The Wheel';
      if (prizeType === 'nothing') {
        outcomeText = 'You got nothing! Good day sir!';
      } else if (prizeType === 'trait') {
        const monsterName = data.monster_name || '';
        const traitNameW = data.trait_name || 'a mysterious trait';
        const traitDescW = data.trait_description ? `<br><span style="font-size:0.85em;color:var(--text-dim);font-style:italic">${data.trait_description}</span>` : '';
        outcomeText = monsterName
          ? `You got a dead <strong>${monsterName}</strong>! Its trait is now yours: <strong>${traitNameW}</strong>!${traitDescW}`
          : `You got a mysterious trait: <strong>${traitNameW}</strong>!${traitDescW}`;
      } else if (prizeType === 'item' || prizeType === 'item_up' || prizeType === 'item_t3') {
        outcomeText = `You got <strong>${itemName || 'an item'}</strong>!`;
      } else if (prizeType === 'curse') {
        const curseMonsterW = data.monster_name || '';
        const curseDescW = data.curse_description ? `<br><span style="font-size:0.85em;color:var(--text-dim);font-style:italic">${data.curse_description}</span>` : '';
        outcomeText = curseMonsterW
          ? `You spun\u2026 <strong>${curseMonsterW}</strong>! And with it comes a curse: <strong>${data.curse_name || 'a curse'}</strong>!${curseDescW}`
          : `You got\u2026 <strong>A CURSE!</strong> You received: <strong>${data.curse_name || 'a curse'}</strong>!${curseDescW}`;
      } else {
        outcomeText = label || 'The wheel has spoken.';
      }
      // No quoteText here — goblin farewell is shown in a separate screen after the outcome
      break;
    case 'the_smith':
      title = 'The Smith';
      if (prizeType === 'smith_enhance') {
        outcomeText = `The Smith enhanced <strong>${data.item_name || 'your item'}</strong> with +3 Str!`;
        quoteText = '"Fine work, if I do say so myself."';
      } else if (prizeType === 'item') {
        outcomeText = `The Smith forged you: <strong>${itemName || 'a new item'}</strong>!`;
        quoteText = '"A fair trade. Use it well."';
      } else {
        outcomeText = label || 'The Smith nods and returns to work.';
      }
      break;
    case 'bandits':
      title = 'Bandits';
      if (prizeType === 'stolen' && data.item_name) {
        outcomeText = `The bandits stole your <strong>${data.item_name}</strong>!`;
      } else if (prizeType === 'skip') {
        outcomeText = 'The bandits find nothing worth stealing and leave you alone.';
      } else {
        outcomeText = label || 'The bandits vanish into the shadows.';
      }
      // No quoteText here — bandit farewell is shown in a separate screen
      break;
    case 'thief':
      title = 'Thief';
      if (prizeType === 'stolen' && data.stolen_items && data.stolen_items.length > 0) {
        outcomeText = `The thief stole: <strong>${data.stolen_items.join(', ')}</strong>!`;
      } else if (prizeType === 'skip') {
        outcomeText = 'Your pack is empty — the thief slinks away with nothing.';
      } else {
        outcomeText = label || 'The thief disappears into the darkness.';
      }
      quoteText = '"Nothing personal, mate."';
      break;
    case 'beggar':
      title = 'Beggar';
      outcomeText = '';
      quoteText = '"Thank you for your generosity."';
      break;
    default:
      title = _pendingMysteryEvent?.name || 'Mystery';
      outcomeText = label || 'The mystery has been resolved.';
      break;
  }
  return { title, outcomeText, quoteText };
}

async function _showMysteryOutcome(data, onContinue, overrideAnimPlayer = null) {
  const { title, outcomeText, quoteText } = _getMysteryOutcomeContent(data);
  const eventId = data.event_id || (_pendingMysteryEvent && _pendingMysteryEvent.event_id) || '';
  const tier = _pendingMysteryEvent?.tier || 1;
  const imgName = _pendingMysteryEvent?.image_name || _pendingMysteryEvent?.name || title;
  // Use event character image as full-screen background
  const bg = `/games/werblers/images/Events/${imgName} Tier ${tier}.png`;
  // Show a specific card (stolen item, monster card) if provided
  const featuredCard = data.card_image || data.combat_info?.card_image || null;

  // Determine animation type
  let animVideoHtml = '';
  if (gameState) {
    const prizeType = data.prize_type || '';
    let animType = null;
    if ((eventId === 'thief' || eventId === 'bandits') && prizeType === 'stolen') animType = 'defeat';
    else if (prizeType === 'trait') animType = 'victory';
    else if (prizeType === 'curse') animType = 'defeat';
    if (animType) {
      const p = overrideAnimPlayer || gameState.players.find(x => x.is_current) || gameState.players[0];
      if (p && p.hero_id && heroAnimMap[p.hero_id] && heroAnimMap[p.hero_id][animType]) {
        const vsrc = `/games/werblers/videos/${heroAnimMap[p.hero_id][animType]}`;
        animVideoHtml = `<video id="mystery-anim-video" src="${vsrc}" autoplay muted playsinline
          style="position:absolute;bottom:20px;right:20px;max-width:300px;width:28vw;border-radius:12px;box-shadow:0 0 30px rgba(0,0,0,0.8);z-index:10;pointer-events:none;"></video>`;
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
        <div class="mystery-btn-row">
          <button class="btn-primary" id="mystery-outcome-btn">Continue</button>
        </div>
      </div>
    </div>
    ${animVideoHtml}`;
  overlay.classList.remove('hidden');

  return new Promise(resolve => {
    document.getElementById('mystery-outcome-btn').onclick = () => {
      // Stop embedded video on continue
      const vid = overlay.querySelector('#mystery-anim-video');
      if (vid) { vid.pause(); vid.remove(); }
      if (onContinue) onContinue();
      resolve();
    };
  });
}

function _showBeggarThankYou(data, mysteryPlayer) {
  _showMysteryOutcome(data, () => _closeMysteryResult(), mysteryPlayer || null);
}

function _showFairyKingReveal(data) {
  const overlay = document.getElementById('battle-overlay');
  const tier = _pendingMysteryEvent?.tier || 1;
  const beggarImg = `/games/werblers/images/Events/Beggar Tier ${tier}.png`;
  const fkImg = `/games/werblers/images/Events/Fairy King Tier ${tier}.png`;

  // Step 1: Beggar says thank you
  overlay.innerHTML = `
    <div class="battle-bg" style="background-image:url('${beggarImg}')"></div>
    <div class="battle-content mystery-fullscreen">
      <div class="mystery-fs-inner">
        <h2 class="mystery-fs-title">The Beggar</h2>
        <div class="mystery-speech-bubble"><p>"Thank you. Now you will see my true form…"</p></div>
        <div class="mystery-btn-row">
          <button class="btn-primary" id="fk-huh-btn">Huh?</button>
        </div>
      </div>
    </div>`;
  overlay.classList.remove('hidden');

  document.getElementById('fk-huh-btn').onclick = () => {
    // Step 2: Beggar transforms into the Fairy King
    const bgEl = overlay.querySelector('.battle-bg');
    if (bgEl) { bgEl.classList.add('fk-reveal-flash'); bgEl.style.backgroundImage = `url('${fkImg}')`; }
    overlay.querySelector('.mystery-fs-inner').innerHTML = `
      <h2 class="mystery-fs-title">The Fairy King</h2>
      <div class="mystery-speech-bubble"><p style="font-style:italic">"You are very kind. Your generosity shall be rewarded."</p></div>
      <div class="mystery-btn-row">
        <button class="btn-primary" id="fk-reward-prompt-btn">Reward?</button>
      </div>`;

    document.getElementById('fk-reward-prompt-btn').onclick = () => {
      // Step 3: Show item choices
      const items = data.reward_items || [];
      if (items.length === 0) {
        overlay.querySelector('.mystery-fs-inner').innerHTML = `
          <h2 class="mystery-fs-title">The Fairy King</h2>
          <p class="mystery-info">No items available.</p>
          <div class="mystery-btn-row"><button class="btn-primary" onclick="_closeMysteryResult()">Continue</button></div>`;
        return;
      }
      const itemsHtml = items.map((item, i) => {
        const img = item.card_image ? `<img class="mystery-item-thumb" src="/games/werblers/images/${item.card_image}" onerror="this.style.display='none'">` : '';
        return `<div class="mystery-selectable-item" data-idx="${i}" onclick="_selectFairyKingReward(${i}, this)">
          ${img}<div class="mystery-item-label">${item.name} (+${item.strength_bonus})</div>
        </div>`;
      }).join('');
      overlay.querySelector('.mystery-fs-inner').innerHTML = `
        <h2 class="mystery-fs-title">The Fairy King</h2>
        <p class="mystery-info" style="margin-top:16px">Choose your reward:</p>
        <div class="mystery-item-grid">${itemsHtml}</div>
        <div class="mystery-btn-row">
          <button class="btn-primary" id="fk-reward-btn" onclick="_resolveFairyKingReward()" disabled>Take Item</button>
        </div>`;
    };
  };
}

let _fkRewardIdx = -1;
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
    // Show "Goodbye, and good luck." farewell before proceeding
    const tier = _pendingMysteryEvent?.tier || 1;
    const fkImg = `/games/werblers/images/Events/Fairy King Tier ${tier}.png`;
    const overlay = document.getElementById('battle-overlay');
    overlay.innerHTML = `
      <div class="battle-bg" style="background-image:url('${fkImg}')"></div>
      <div class="battle-content mystery-fullscreen">
        <div class="mystery-fs-inner">
          <h2 class="mystery-fs-title">The Fairy King</h2>
          <div class="mystery-speech-bubble"><p>"Goodbye, and good luck."</p></div>
          <div class="mystery-btn-row">
            <button class="btn-primary" id="fk-farewell-btn">Continue</button>
          </div>
        </div>
      </div>`;
    overlay.classList.remove('hidden');
    await new Promise(resolve => {
      document.getElementById('fk-farewell-btn').onclick = () => resolve();
    });
    // Hide the battle-overlay BEFORE showing the chest modal so the inventory
    // placement popup (z-index 250) is not blocked behind it (z-index 400).
    overlay.classList.add('hidden');
    _pendingMysteryEvent = null;
    if (data.phase === 'offer_chest') {
      _pendingOfferData = data.offer;
      showChestModal(data.offer, {});
    } else {
      _closeMysteryResult();
    }
  } catch(e) { console.error('fairy king reward error:', e); }
}

async function _closeMysteryResult() {
  document.getElementById('battle-overlay').classList.add('hidden');
  _pendingMysteryEvent = null;
  if (gameState) {
    viewingPlayerId = gameState.current_player_id;
    applyState(gameState);
  }
  _resumeTierMusic(gameState);
  loadAndRenderAbilities();
  await _placePendingTraitItems();
  _checkPendingMinions(gameState);
}

// ================================================================ MINION REPLACEMENT MODAL

let _minionReplaceDone = null;

function _checkPendingMinions(state) {
  if (!state) return;
  const player = state.players.find(p => p.is_current) || state.players[0];
  if (player.pending_trait_minions && player.pending_trait_minions.length > 0) {
    _showMinionReplacementModal(player);
  }
}

function _showMinionReplacementModal(player, onDone) {
  if (onDone) _minionReplaceDone = onDone;
  const pending = player.pending_trait_minions[0];
  const overlay = document.getElementById('battle-overlay');
  const currentMinions = player.minions || [];
  const slots = currentMinions.map((m, i) => {
    const img = m.card_image ? `<img class="ps-slot-card-img" src="/games/werblers/images/${m.card_image}" alt="${m.name}" style="width:80px;height:auto;border-radius:6px;margin-bottom:4px" onerror="this.style.display='none'">` : '';
    return `<button class="btn-secondary mystery-item-btn" onclick="_resolveMinion(${i})">
      ${img}<div>${m.name}</div><div style="font-size:0.85em;color:var(--text-dim)">+${m.strength_bonus} Str</div>
    </button>`;
  }).join('');

  const pendingImg = pending.card_image ? `<img src="/games/werblers/images/${pending.card_image}" alt="${pending.name}" style="width:120px;height:auto;border-radius:8px;margin:8px auto;display:block" onerror="this.style.display='none'">` : '';

  overlay.innerHTML = `
    <div class="mystery-modal">
      <h2 class="mystery-title">Minion Slots Full!</h2>
      <p class="mystery-info">${pending.name} (+${pending.strength_bonus} Str) wants to join your party, but you have no room.</p>
      ${pendingImg}
      <p class="mystery-info">Choose a minion to replace:</p>
      <div class="mystery-item-grid">${slots}</div>
      <button class="btn-secondary" onclick="_resolveMinion(-1)" style="margin-top:10px">Discard ${pending.name}</button>
    </div>`;
  overlay.classList.remove('hidden');
}

async function _resolveMinion(replaceIndex) {
  try {
    const body = replaceIndex < 0
      ? {discard: true}
      : {replace_index: replaceIndex};
    const resp = await fetch('/games/werblers/api/resolve_minion', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    if (!resp.ok) { console.error('resolve_minion failed', resp.status); return; }
    const data = await resp.json();
    if (data.state) {
      gameState = data.state;
      applyState(data.state);
    }
    // Check if more pending minions remain
    const player = data.state?.players?.find(p => p.is_current);
    if (player && player.pending_trait_minions && player.pending_trait_minions.length > 0) {
      _showMinionReplacementModal(player);
    } else {
      document.getElementById('battle-overlay').classList.add('hidden');
      if (_minionReplaceDone) {
        const cb = _minionReplaceDone;
        _minionReplaceDone = null;
        cb();
      }
    }
  } catch (err) {
    console.error('resolveMinion error:', err);
  }
}


// ================================================================ HERO ANIMATION SYSTEM
// Displays hero animation videos in a panel to the right of the screen.
// Position is configurable via the _heroAnimPosition object.

const _heroAnimPosition = { top: '50%', right: '40px', transform: 'translateY(-50%)', maxWidth: '380px' };

function _showHeroAnimation(heroId, animType, onEnd) {
  const anims = heroAnimMap[heroId];
  if (!anims || !anims[animType]) { if (onEnd) onEnd(); return; }
  const src = `/games/werblers/videos/${anims[animType]}`;
  // Remove any existing animation panel
  const existing = document.getElementById('hero-anim-panel');
  if (existing) existing.remove();

  const panel = document.createElement('div');
  panel.id = 'hero-anim-panel';
  panel.style.cssText = `position:fixed;top:${_heroAnimPosition.top};right:${_heroAnimPosition.right};transform:${_heroAnimPosition.transform};max-width:${_heroAnimPosition.maxWidth};z-index:500;pointer-events:none;`;

  const video = document.createElement('video');
  video.src = src;
  video.autoplay = true;
  video.muted = true;
  video.playsInline = true;
  video.style.cssText = 'width:100%;border-radius:12px;box-shadow:0 0 30px rgba(0,0,0,0.7);';
  video.addEventListener('ended', () => {
    panel.remove();
    if (onEnd) onEnd();
  });
  video.addEventListener('error', () => {
    panel.remove();
    if (onEnd) onEnd();
  });
  panel.appendChild(video);
  document.body.appendChild(panel);
}

function _showHeroAnimationForPlayer(state, animType, onEnd) {
  const p = state.players.find(x => x.is_current) || state.players[0];
  if (!p || !p.hero_id) { if (onEnd) onEnd(); return; }
  _showHeroAnimation(p.hero_id, animType, onEnd);
}

// ================================================================ INIT
window.addEventListener('DOMContentLoaded', initSetup);

// ================================================================ DEVICE ID
function _initDeviceId() {
  let id = localStorage.getItem('werblers_device_id');
  if (!id) {
    id = 'dev_' + crypto.randomUUID();
    localStorage.setItem('werblers_device_id', id);
  }
  _deviceId = id;
}

// ================================================================ PROFILE SCREEN
async function _loadProfileScreen() {
  const resp = await fetch('/games/werblers/api/profiles?device_id=' + encodeURIComponent(_deviceId));
  const data = await resp.json();
  const profiles = data.profiles || [];
  if (profiles.length === 0) {
    // Show create section
    document.getElementById('profile-create-section').classList.remove('hidden');
    document.getElementById('profile-select-section').classList.add('hidden');
  } else {
    // Show select section
    _renderProfileList(profiles);
    document.getElementById('profile-create-section').classList.add('hidden');
    document.getElementById('profile-select-section').classList.remove('hidden');
  }
  document.getElementById('profile-screen').classList.remove('hidden');
  document.getElementById('main-menu-screen').classList.add('hidden');
  document.getElementById('setup-screen').classList.add('hidden');
  document.getElementById('game-screen').classList.add('hidden');
  document.getElementById('game-side-buttons').classList.add('hidden');
}

function _renderProfileList(profiles) {
  const list = document.getElementById('profile-list');
  list.innerHTML = '';
  for (const p of profiles) {
    const btn = document.createElement('button');
    btn.className = 'btn-profile';
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
  // Go to main menu
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
  // Return to profile selection
  _profileId = null;
  _profileName = '';
  _loadProfileScreen();
}

// ================================================================ MAIN MENU
function goToNewGame() {
  document.getElementById('main-menu-screen').classList.add('hidden');
  document.getElementById('setup-screen').classList.remove('hidden');
  setNumPlayers(1);
}

// ================================================================ SAVE / LOAD MODAL
function openSaveLoadModal() {
  _saveLoadMode = 'save';
  _selectedSlot = null;
  document.getElementById('saveload-modal').classList.remove('hidden');
  _refreshSaveSlots();
}

function closeSaveLoadModal() {
  document.getElementById('saveload-modal').classList.add('hidden');
}

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
        <span class="slot-info">${save.hero_names} &bull; ${save.num_players}P &bull; Turn ${save.turn_number}</span>
        <span class="slot-time">${timeStr}</span>`;
    } else {
      slot.innerHTML = `<span class="slot-label">Slot ${i}</span><span class="slot-info slot-empty">— Empty —</span>`;
    }
    slot.addEventListener('click', () => {
      _selectedSlot = i;
      const btnId = isMenuLoad ? 'menu-load-btn' : 'saveload-confirm-btn';
      const btn = document.getElementById(btnId);
      // For load mode, only enable if slot has data
      if ((_saveLoadMode === 'load' || isMenuLoad) && !save) {
        btn.disabled = true;
      } else {
        btn.disabled = false;
      }
      container.querySelectorAll('.save-slot').forEach(s => s.classList.remove('selected'));
      slot.classList.add('selected');
    });
    container.appendChild(slot);
  }
}

async function confirmSaveLoad() {
  if (_selectedSlot === null) return;
  if (_saveLoadMode === 'save') {
    // Check if slot is occupied
    const existing = _savesData.find(s => s.slot_number === _selectedSlot);
    if (existing) {
      // Show overwrite confirmation
      document.getElementById('overwrite-modal').classList.remove('hidden');
      return;
    }
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
  if (data.ok) {
    closeSaveLoadModal();
  }
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
    // Make sure game screen is visible
    document.getElementById('setup-screen').classList.add('hidden');
    document.getElementById('main-menu-screen').classList.add('hidden');
    document.getElementById('profile-screen').classList.add('hidden');
    document.getElementById('game-screen').classList.remove('hidden');
    document.getElementById('game-side-buttons').classList.remove('hidden');
    _boardBuilt = false;
    viewingPlayerId = data.state.current_player_id;
    applyState(data.state);
    _resumeTierMusic(data.state);
    await loadAndRenderAbilities();
  }
}

// ================================================================ LOAD FROM MAIN MENU
async function openLoadFromMenu() {
  _selectedSlot = null;
  _saveLoadMode = 'load';
  const resp = await fetch('/games/werblers/api/saves?profile_id=' + _profileId);
  const data = await resp.json();
  _savesData = data.saves || [];
  _renderSaveSlots('menu-load-slots');
  document.getElementById('menu-load-modal').classList.remove('hidden');
}

function closeMenuLoadModal() {
  document.getElementById('menu-load-modal').classList.add('hidden');
}

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
    document.getElementById('game-side-buttons').classList.remove('hidden');
    _boardBuilt = false;
    viewingPlayerId = data.state.current_player_id;
    applyState(data.state);
    _resumeTierMusic(data.state);
    await loadAndRenderAbilities();
  }
}

// ================================================================ ACHIEVEMENTS
async function openAchievementsModal() {
  if (!_profileId) return;
  const resp = await fetch('/games/werblers/api/achievements?profile_id=' + _profileId);
  const data = await resp.json();
  const list = document.getElementById('achievements-list');
  list.innerHTML = '';
  for (const a of (data.achievements || [])) {
    const row = document.createElement('div');
    row.className = 'achievement-row' + (a.achieved ? ' achieved' : '');
    row.innerHTML = `<span class="achievement-check">${a.achieved ? '✅' : '⬜'}</span>
                     <span class="achievement-desc">${a.description}</span>`;
    list.appendChild(row);
  }
  document.getElementById('achievements-modal').classList.remove('hidden');
}

function closeAchievementsModal() {
  document.getElementById('achievements-modal').classList.add('hidden');
}

// Track which achievements we've already triggered this session to avoid duplicates
let _achievementsTriggeredThisSession = new Set();

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
    // Find the description
    const ach = (data.achievements || []).find(a => a.key === key);
    const desc = ach ? ach.description : key;
    _pendingAchievements.push(desc);
    _showNextAchievementPopup();
    // Check if total_victory was also just granted
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
  // Show next if queued
  _showNextAchievementPopup();
}
