/* Private guest rooms. Both desktop and mobile use this interface and API. */
window.WerblersOnline = (() => {
  const API = '/games/werblers/api';
  const STORE = 'werblers-online-seats-v1';
  let screen, room = null, heroes = [], timer = null, busy = false, active = false;
  let code = '', token = '', revision = -1;
  let tokens = {};
  try { tokens = JSON.parse(localStorage.getItem(STORE) || '{}'); } catch (_) {}
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const button = (label, action, payload = {}, disabled = false) => `<button type="button" data-op="${esc(action)}" data-payload="${esc(JSON.stringify(payload))}" ${disabled ? 'disabled' : ''}>${esc(label)}</button>`;
  const options = (values, selected) => values.map(([value, text]) => `<option value="${esc(value)}" ${String(value) === String(selected) ? 'selected' : ''}>${esc(text)}</option>`).join('');
  const select = (label, name, values, selected) => `<label>${esc(label)}<select name="${esc(name)}">${options(values, selected)}</select></label>`;
  const card = item => `<div class="wo-card">${item.card_image ? `<a href="/games/werblers/images/${esc(item.card_image)}" target="_blank" rel="noopener" aria-label="View ${esc(item.name)} card"><img loading="lazy" src="/games/werblers/images/${esc(item.card_image)}" alt="${esc(item.name)}"></a>` : ''}<span>${esc(item.name)}${item.strength_bonus !== undefined ? ` (${item.strength_bonus >= 0 ? '+' : ''}${item.strength_bonus} Str)` : ''}</span></div>`;

  function error(message) {
    const el = screen.querySelector('#wo-error');
    el.textContent = message || '';
    el.hidden = !message;
  }
  function remember() {
    tokens[code] = token;
    try { localStorage.setItem(STORE, JSON.stringify(tokens)); } catch (_) {
      error('This browser cannot remember your seat. Keep this page open to stay in the room.');
    }
  }
  async function request(path, body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    let response, data;
    try {
    response = await fetch(API + path, {
      signal: controller.signal,
      method: body === undefined ? 'GET' : 'POST',
      headers: {'Content-Type': 'application/json', 'X-Werblers-Token': token},
      ...(body === undefined ? {} : {body: JSON.stringify(body)}),
    });
    data = await response.json();
    } finally { clearTimeout(timeout); }
    if (!response.ok) throw Object.assign(new Error(data.error || 'Could not update the room.'), {status: response.status});
    return data;
  }
  function accept(next, force = false) {
    if (!active || next.code !== code || next.version < revision) return;
    const changed = force || revision !== next.version;
    room = next;
    revision = room.version;
    if (changed) renderRoom();
    else updatePresence();
  }
  async function poll() {
    if (!active || !code || !token || busy) return;
    const requestedCode = code;
    try {
      const data = await request(`/rooms/${requestedCode}`);
      if (code !== requestedCode || !room || busy || !active) return;
      accept(data.room);
      screen.querySelector('#wo-connection').textContent = 'Connected · saved automatically';
    } catch (e) {
      const status = screen.querySelector('#wo-connection');
      if (status && code === requestedCode && room) status.textContent = 'Reconnecting… Your seat is reserved.';
    }
  }
  function schedule() {
    clearInterval(timer);
    // No turn timeout in either mode. Async sessions can resume on another day.
    timer = setInterval(poll, room?.mode === 'async' ? 8000 : 2000);
  }
  async function act(action, payload = {}) {
    if (busy || !room) return;
    busy = true; error('');
    const body = {...payload, _version: room.version, _request_id: crypto.randomUUID()};
    screen.querySelectorAll('button, input, select').forEach(el => { el.disabled = true; });
    try {
      let data;
      try { data = await request(`/rooms/${code}/actions/${action}`, body); }
      catch (e) {
        if (e.status) throw e;
        // Lost response: retry the same identifier, never replay the move.
        data = await request(`/rooms/${code}/actions/${action}`, body);
      }
      busy = false;
      accept(data.room, true);
    } catch (e) {
      busy = false;
      try { accept((await request(`/rooms/${code}`)).room, true); } catch (_) { renderRoom(); }
      error(e.message);
    }
  }
  function shell(content) {
    screen.innerHTML = `<div class="wo-wrap"><header class="wo-top"><div><h1>Werblers Online</h1><span id="wo-connection" class="wo-muted">Private rooms · guests welcome</span></div>${button('Back to local game', 'close')}</header><div id="wo-error" role="alert" hidden></div>${content}</div>`;
  }
  function landing() {
    room = null; revision = -1;
    const invited = new URLSearchParams(location.search).get('room') || code;
    shell(`<div class="wo-grid"><section class="wo-panel"><h2>Gather your party</h2><p>Up to four players. Phones and PCs play together.</p><form data-form="create"><label>Your name<input name="name" maxlength="24" required autocomplete="nickname"></label>${select('Game pace', 'mode', [['live', 'Live session'], ['async', 'Play at your own pace']])}<p class="wo-muted">Both modes save every action. Live sessions show connection status and wait for absent players; asynchronous games wait for each person’s next visit. There are no turn timers.</p><button>Create private room</button></form></section><section class="wo-panel"><h2>Join your friends</h2><form data-form="join"><label>Your name<input name="name" maxlength="24" required autocomplete="nickname"></label><label>Room code<input name="code" minlength="6" maxlength="6" value="${esc(invited)}" required autocapitalize="characters" autocomplete="off"></label><button>Join room</button></form>${Object.keys(tokens).length ? `<h3 style="margin-top:24px">Return to a room</h3><div class="wo-row">${Object.keys(tokens).slice(-8).reverse().map(c => button(c, 'reconnect', {code: c})).join('')}</div><p class="wo-muted">Your seat is remembered in this browser. Return here to resume.</p>` : ''}</section></div>`);
  }
  function seatsHtml() {
    return room.seats.map(s => `<div class="wo-seat ${s.player_id === room.you ? 'is-you' : ''}"><strong>${s.player_id + 1}. ${esc(s.name)}${s.player_id === 0 ? ' · Host' : ''}${s.player_id === room.you ? ' · You' : ''}</strong><p>${esc(heroes.find(h => h.id === s.hero)?.name || 'Choosing a hero')}</p><span class="wo-pill">${s.ai ? 'AI' : s.online ? 'Connected' : 'Away · seat reserved'}</span>${s.skip_next ? '<p class="wo-muted">Next turn will be skipped</p>' : ''}</div>`).join('');
  }
  function updatePresence() {
    const seats = screen.querySelector('#wo-seats');
    if (seats) seats.innerHTML = seatsHtml();
    const waiting = screen.querySelector('#wo-waiting');
    if (waiting && room.decision?.player_id != null) {
      const s = room.seats[room.decision.player_id];
      waiting.textContent = room.paused ? 'The host paused the room.' : room.waiting_for_connection && room.mode === 'live'
        ? `Paused for ${s.name} to reconnect. The host can skip or use AI.`
        : `Waiting for ${s.name}${s.ai ? ' (AI)' : ''}: ${room.decision.phase.replaceAll('_', ' ')}.`;
    }
  }
  function hostControls() {
    if (!room.host || room.phase !== 'playing') return '';
    return `<details class="wo-panel wo-host"><summary>Host controls</summary><p class="wo-muted">Skipping ends an unfinished turn or passes a pending decision. Completed actions stay. Skipping someone whose turn is later marks their next turn. AI continues their current situation; you can restore human control anytime.</p><div class="wo-row">${button(room.paused ? 'Resume room' : 'Pause room', room.paused ? 'resume' : 'pause')}</div>${room.seats.map(s => `<div class="wo-item"><strong>${esc(s.name)}</strong><div class="wo-row">${button('Skip turn / decision', 'skip', {player_id: s.player_id})}${button(s.ai ? 'Return to human' : 'Replace with AI', s.ai ? 'human' : 'ai', {player_id: s.player_id})}</div></div>`).join('')}</details>`;
  }
  function boardHtml(state) {
    return `<section class="wo-panel"><h2>The board <span class="wo-pill">${state.is_night ? 'Night' : 'Day'}</span></h2><div class="wo-board">${state.board.map(t => {
      const row = Math.floor((t.index - 1) / 10), column = (t.index - 1) % 10;
      return `<div class="wo-tile" style="grid-row:${9 - row};grid-column:${row % 2 ? 10 - column : column + 1}" title="Tile ${t.index}: ${esc(t.tile_type)}"><img loading="lazy" src="/games/werblers/images/${esc(t.image)}" alt="${esc(t.tile_type === 'HIDDEN' ? 'Unrevealed tile' : t.tile_type)}"><span>${t.index}</span><div class="wo-tokens">${state.players.filter(p => p.position === t.index).map(p => `<b class="wo-token" title="${esc(p.name)}">${p.player_id + 1}</b>`).join('')}</div></div>`;
    }).join('')}</div></section>`;
  }
  const myPlayer = () => room.state.players.find(p => p.player_id === room.you);
  const canAct = () => room.phase === 'playing' && !room.paused && !room.seats[room.you].ai && room.decision.player_id === room.you;
  function placementFields(p) {
    const pack = [...p.pack, ...p.consumables, ...p.captured_monsters];
    return `<details><summary>Placement and replacement options</summary><div class="wo-form-grid">${select('Place reward', 'placement', [['pack', 'Pack'], ['equip', 'Equip']])}${select('When equipment slots are full', 'equip_action', [['swap', 'Move old equipment to pack'], ['discard', 'Discard old equipment']])}${select('Equipment to replace (within its slot)', 'equip_item_index', [[0,'First item'],[1,'Second item'],[2,'Third item']])}${select('Second weapon, if replacing two', 'equip_action_2', [['discard','Discard'],['swap','Move to pack']])}${select('If pack is full, replace', 'pack_discard_index', pack.map((i,n) => [n, `${n+1}. ${i.name}`]))}${select('Second pack replacement, if needed', 'pack_discard_index_2', pack.map((i,n) => [n, `${n+1}. ${i.name}`]))}</div></details>`;
  }
  function abilityFields(d) {
    return (d.abilities || []).map(a => {
      if (a.type === 'instant_select_curse') return `<div class="wo-item"><p>${esc(a.description)}</p>${a.curses.map((c,i) => button(`Eight Lives: remove ${c}`, 'use_eight_lives', {curse_index:i})).join('')}</div>`;
      let fields = '';
      if (a.type === 'select_number') fields = select('Reduction', `ability.${a.id}.reduction`, a.options.map(v => [v,v]));
      if (a.type === 'select_equip') fields = select('Equipment to discard', `ability.${a.id}.equip_index`, a.equips.map((v,i) => [i,v]));
      if (a.type === 'select_player_minion') {
        fields = select('Opponent’s minion', 'ability.meat_on_menu.target', a.targets.flatMap(t => t.minions.map((m,i) => [`${t.player_id}:${i}`, `${t.name}: ${m}`])));
      }
      return `<div class="wo-item"><label><input type="checkbox" name="ability.${esc(a.id)}"> ${esc(a.label)}</label><p class="wo-muted">${esc(a.description)}</p>${fields}</div>`;
    }).join('');
  }
  function decisionHtml() {
    const d = room.decision, p = myPlayer();
    let html = '<section class="wo-panel"><h2>Your next move</h2>';
    if (room.phase === 'finished') return `<section class="wo-panel"><h2>${esc(room.state.players.find(p => p.player_id === room.state.winner)?.name || 'A player')} wins!</h2><p>This adventure is saved. Create another room to play again.</p></section>`;
    if (!canAct()) return html + `<p id="wo-waiting"></p>${d.combat ? card({name:d.combat.monster_name,card_image:d.combat.card_image}) : ''}</section>`;
    if (d.phase === 'move') {
      html += `<p>Tile ${p.position} · ${p.strength} strength</p><form data-form="begin_move">${select('Movement card', 'card_index', p.movement_hand.map((v,i) => [i, `${v + p.movement_card_bonus} spaces${p.movement_card_bonus ? ` (card ${v})` : ''}`]))}${select('Direction', 'direction', [['forward','Forward'],['backward','Backward']])}${d.abilities.length ? `<details><summary>Abilities</summary>${abilityFields(d)}</details>` : ''}<button>Play movement card</button></form>`;
    } else if (d.phase === 'trait_loss') {
      html += `<h3>Slurp!</h3><p>Joh’Neil defeated you. Choose ${d.choice.count} traits to lose.</p><form data-form="resolve_trait_loss">${p.traits.map((t,i) => `<label><input type="checkbox" name="trait_indices" value="${i}"> ${esc(t.name)}</label>`).join('')}<button disabled>Discard selected traits</button></form>`;
    } else if (d.phase === 'me_too') {
      html += `<h3>Me Too!</h3><p>Another player discarded a curse. You may discard one of yours.</p><div class="wo-row">${p.curses.map((c,i) => button(`Discard ${c.name}`, 'resolve_me_too', {choice_id:d.choice.id,curse_index:i})).join('')}${button('Keep my curses','resolve_me_too',{choice_id:d.choice.id,curse_index:null})}</div>`;
    } else if (d.phase === 'bystander') {
      html += `<h3>Nearby battle</h3><p>You may use a consumable on ${esc(d.combat.monster_name)}, or pass.</p>${p.consumables.filter(c=>c.effect_id==='monster_str_mod').map((c,i)=>button(`Use ${c.name}`, 'bystander_consumable', {player_id:room.you,consumable_index:i})).join('')}${button('Pass', 'bystander_consumable', {player_id:room.you,skip:true})}`;
    } else if (d.phase === 'combat') {
      const c = d.combat;
      html += `${card({name:c.monster_name,card_image:c.card_image})}<p>You: ${c.player_strength} strength · Opponent: ${c.monster_strength}</p><p>${esc(c.description || '')}</p><div class="wo-row">${button('Fight','fight')}${d.can_flee ? button('Flee','flee') : ''}${p.traits.some(t=>t.effect_id==='swiftness') && c.category!=='werbler' ? button('Use Swiftness','swiftness_flee') : ''}${c.ill_come_in_again_available ? button('Draw another monster','use_ill_come_in_again') : ''}</div><p class="wo-muted">Use your inventory below to equip items${d.consumables_allowed ? ' or use consumables' : '. This opponent forbids consumables'} before fighting.</p>`;
      if (c.effect_id === 'crossroads_demon') html += `<form data-form="crossroads_discard"><h3>Fair Exchange</h3>${equipped(p).map(e=>`<label><input type="checkbox" name="equip_sources" value="${esc(JSON.stringify({source:e.source,index:e.index}))}" ${isLocked(e.item,p)?'disabled':''}> ${esc(e.item.name)}${isLocked(e.item,p)?' (curse-locked)':''}</label>`).join('')}<button>Discard selected equipment</button></form>`;
    } else if (d.phase === 'charlie_work') {
      html += `<p>Fight a tier ${d.level + 1} monster instead?</p>${button('Fight higher tier','resolve_charlie_work',{use_it:true})}${button('Keep current tier','resolve_charlie_work',{use_it:false})}`;
    } else if (['chest','shop','item'].includes(d.phase)) {
      html += `<h3>${d.phase === 'item' ? 'Place your reward' : d.phase === 'chest' ? 'Treasure chest' : 'Shop'}</h3><form data-form="${d.phase === 'item' ? 'place_trait_item' : 'resolve_offer'}"><div class="wo-cards">${d.items.map((i,n)=>`<label><input type="radio" name="chosen_index" value="${n}" ${n===0?'checked':''}>${card(i)}</label>`).join('')}</div>${placementFields(p)}<button>Take item</button></form><div class="wo-row">${d.phase==='item' ? button('Discard reward','place_trait_item',{player_id:room.you,placement_choices:{discard:true}}) : button('Leave item','resolve_offer',{take:false})}${d.scavenger ? button('Replace selected item (Scavenger)','scavenger_swap') : ''}</div>`;
    } else if (d.phase === 'minion') {
      html += `<h3>${esc(d.minion.name)} wants to join (+${d.minion.strength_bonus} Str)</h3>${p.minions.length < p.max_minions ? button('Add minion','resolve_minion',{player_id:room.you,replace_index:-1}) : ''}${p.minions.map((m,i)=>button(`Replace ${m.name}`, 'resolve_minion',{player_id:room.you,replace_index:i})).join('')}${button('Decline','resolve_minion',{player_id:room.you,discard:true})}`;
    } else if (d.phase === 'rake_it_in') {
      const sacrifices = [...equipped(p).map(e=>[`${e.source}:${e.index}`,e.item.name]), ...p.pack.map((i,n)=>[`pack:${n}`,i.name]), ...p.consumables.map((i,n)=>[`consumable:${n}`,i.name])];
      html += `<h3>Rake It In!</h3><form data-form="resolve_rake_it_in">${select('Discard an item for a bonus reward','sacrifice',sacrifices)}${d.sub_type==='shop' ? `${select('Bonus item','second_item_choice',d.items.map((i,n)=>[n,i.name]))}${placementFields(p)}` : ''}<button>Trade for bonus item</button></form>${button('Pass','resolve_rake_it_in',{use_it:false})}`;
    } else if (d.phase === 'mystery') {
      const e=d.event;
      html += `<h3>${esc(e.name)} · Tier ${e.tier}</h3><p>${esc(e.description)}</p><form data-form="resolve_mystery">`;
      if (['mystery_box','beggar'].includes(e.event_id)) html += select('Pack item to give','wager_index',p.pack.map((i,n)=>[n,i.name]));
      if (e.event_id==='the_smith') html += `<p>Choose items for the smith’s trade:</p>${p.pack.map((i,n)=>`<label><input type="checkbox" name="smith_indices" value="${n}"> ${esc(i.name)}</label>`).join('')}${select('Equipped item to enhance (tier 3)','smith_equip_index',equipped(p).map((e,n)=>[n,e.item.name]))}`;
      html += `<button>Accept / continue</button></form>${button('Decline event','resolve_mystery',{action:'skip'})}`;
    } else if (d.phase==='fairy_king_reward') {
      html += `<h3>Choose the Fairy King’s reward</h3>${d.items.map((i,n)=>`<div class="wo-item">${card(i)}${button('Choose this item','resolve_fairy_king_reward',{choice_index:n})}</div>`).join('')}`;
    }
    return html+'</section>';
  }
  function equipped(p) {
    return [['helmets','equip_helmet'],['chest_armor','equip_chest'],['leg_armor','equip_leg'],['weapons','equip_weapon']].flatMap(([key,source])=>p[key].map((item,index)=>({item,index,source})));
  }
  function isLocked(item, player) {
    return item.locked_by_curse_id && player.curses.some(c => c.effect_id === item.locked_by_curse_id);
  }
  function inventoryHtml() {
    return room.state.players.map(p=>{
      const own=p.player_id===room.you, editable=own && canAct() && ['move','combat'].includes(room.decision.phase);
      const use=editable && (room.decision.phase!=='combat' || room.decision.consumables_allowed);
      let html=`<details class="wo-panel" ${own?'open':''}><summary>${esc(p.name)} · Tile ${p.position} · ${p.strength} Str${own?' · Your inventory':''}</summary><h3>Equipment</h3>`;
      html+=equipped(p).map(e=>`<div class="wo-item">${card(e.item)}${editable?`<div class="wo-row">${button('Move to pack','manage_item',{source:e.source,index:e.index,action:'to_pack'})}${button('Discard','manage_item',{source:e.source,index:e.index,action:'discard'})}</div>`:''}</div>`).join('') || '<p class="wo-muted">No equipment.</p>';
      html+=`<h3>Pack (${p.pack_size-p.pack_slots_free}/${p.pack_size})</h3>`;
      html+=p.pack.map((i,n)=>`<div class="wo-item">${card(i)}${editable?`<div class="wo-row">${i.is_consumable ? use?button('Use','use_pack_consumable',{pack_index:n}):'' : button('Equip; keep replaced items','equip_from_pack',{pack_index:n,to_pack:true,displaced_actions:p.weapons.map(()=>({action:'to_pack'}))})+button('Equip; discard replaced items','equip_from_pack',{pack_index:n,force:true,displaced_actions:p.weapons.map(()=>({action:'discard'}))})}${button('Discard','manage_item',{source:'pack',index:n,action:'discard'})}</div>`:''}</div>`).join('');
      if (use && p.consumables.some(c=>c.effect_id==='give_curse')) html+=select('Curse target','curse_target',room.seats.filter(s=>s.player_id!==room.you).map(s=>[s.player_id,s.name]));
      html+=p.consumables.map((c,i)=>`<div class="wo-item">${card(c)}${use?button('Use consumable','use_consumable',{consumable_index:i}):''}${editable?button('Discard','discard_consumable',{index:i}):''}</div>`).join('');
      html+=p.captured_monsters.map((m,i)=>`<div class="wo-item">${card(m)}${editable && room.decision.phase==='move'?button('Summon to fight','summon_monster',{index:i}):''}${editable?button('Release','release_monster',{index:i}):''}</div>`).join('');
      html+=`<h3>Traits</h3>${p.traits.map((t,i)=>`<div class="wo-item"><strong>${esc(t.name)}</strong> ${esc(t.description||'')}${editable && room.decision.phase==='move' && p.weapons.some(w=>w.effect_id==='mages_gauntlet')?button('Sacrifice to Mage’s Gauntlet','use_mages_gauntlet',{trait_index:i}):''}</div>`).join('')||'<p>None</p>'}<h3>Curses</h3>${p.curses.map(c=>`<p>${esc(c.name)} ${esc(c.description||'')}</p>`).join('')||'<p>None</p>'}<h3>Minions</h3>${p.minions.map(m=>`<p>${esc(m.name)} (+${m.strength_bonus} Str)</p>`).join('')||'<p>None</p>'}`;
      if (editable && room.decision.phase==='move' && p.hero_id==='GREGORY' && p.curses.length) html+=`<form data-form="mutagen"><h3>Contagious Mutagen</h3>${select('Curse to transfer','curse_index',p.curses.map((c,i)=>[i,c.name]))}${select('Opponent','target_player_id',room.seats.filter(s=>s.player_id!==room.you).map(s=>[s.player_id,s.name]))}<button>Transfer curse (once per game)</button></form>`;
      return html+'</details>';
    }).join('');
  }
  function renderRoom() {
    if (!room) return landing();
    const roomDetails=`<section class="wo-panel"><div class="wo-top"><div><span class="wo-muted">PRIVATE ROOM</span><div class="wo-code">${esc(code)}</div></div><span class="wo-pill">${room.mode==='live'?'Live session':'Play at your own pace'}</span>${button('Copy invitation','invite')}</div><label class="wo-muted">Invitation link<input readonly value="${esc(location.origin+'/games/werblers?room='+code)}" aria-label="Invitation link"></label><div id="wo-seats" class="wo-seats">${seatsHtml()}</div><p class="wo-muted">Progress saves automatically. Your seat is kept when you close the page; return using this browser.</p>${room.notice?`<p>${esc(room.notice)}</p>`:''}</section>`;
    let content = '';
    if (room.phase==='lobby') {
      content = `<div class="wo-row">${button('Other rooms', 'rooms')}</div>` + roomDetails;
      const taken=room.seats.filter(s=>s.player_id!==room.you).map(s=>s.hero);
      content+=`<section class="wo-panel"><h2>Choose your hero</h2><div class="wo-cards">${heroes.map(h=>`<div class="wo-item">${card({name:h.name,card_image:h.card_image})}<p>${esc(h.title)}</p>${button(room.seats[room.you].hero===h.id?'Selected':`Choose ${h.name}`,'hero',{hero:h.id},taken.includes(h.id))}</div>`).join('')}</div>${room.host?button('Start adventure','start',{},room.seats.length<2||room.seats.some(s=>!s.hero)):'<p>The host will start once everyone chooses a hero.</p>'}</section>`;
    } else {
      content = `<div class="wo-grid"><div>${decisionHtml()}${boardHtml(room.state)}</div><div>${inventoryHtml()}<section class="wo-panel"><h2>Turn ${room.state.turn_number} - Recent events</h2><div class="wo-log">${room.state.log.map(line=>`<p>${esc(line)}</p>`).join('')}</div></section></div></div><details class="wo-room-details wo-panel"><summary>Room ${esc(code)} - ${room.seats.length} players - Invitations and connection status</summary>${roomDetails}<div class="wo-row">${button('Other rooms', 'rooms')}</div></details>${hostControls()}`;
    }
    const detailsOpen = screen.querySelector('.wo-room-details')?.open;
    const hostOpen = screen.querySelector('.wo-host')?.open;
    shell(content); updatePresence();
    if (detailsOpen && screen.querySelector('.wo-room-details')) screen.querySelector('.wo-room-details').open = true;
    if (hostOpen && screen.querySelector('.wo-host')) screen.querySelector('.wo-host').open = true;
    screen.querySelector('#wo-connection').textContent='Connected · saved automatically';
  }
  function formPayload(form) {
    const data=new FormData(form), action=form.dataset.form;
    const number = name => Number(data.get(name) || 0);
    const placement={placement:data.get('placement')||'pack', equip_action:data.get('equip_action')||'swap',equip_action_2:data.get('equip_action_2')||'discard',equip_item_index:number('equip_item_index'),pack_discard_index:number('pack_discard_index'),pack_discard_index_2:number('pack_discard_index_2')};
    if (action==='begin_move') {
      const activated={};
      for (const a of room.decision.abilities) if (data.has('ability.'+a.id)) {
        activated[a.id]=true;
        if(a.id==='fancy_footwork') activated[a.id]={reduction:number('ability.fancy_footwork.reduction')};
        if(a.id==='phase_shift') activated[a.id]={equip_index:number('ability.phase_shift.equip_index')};
        if(a.id==='meat_on_menu') {const [target_player_id,minion_index]=data.get('ability.meat_on_menu.target').split(':').map(Number);activated[a.id]={target_player_id,minion_index};}
      }
      return {card_index:number('card_index'),direction:data.get('direction'),activated};
    }
    if(action==='resolve_offer') return {take:true,chosen_index:number('chosen_index'),...placement};
    if(action==='place_trait_item') return {player_id:room.you,placement_choices:placement};
    if(action==='resolve_rake_it_in') { const [discard_slot,idx]=data.get('sacrifice').split(':');return {use_it:true,discard_slot,discard_idx:Number(idx),second_item_choice:number('second_item_choice'),...placement}; }
    if(action==='resolve_mystery') return {action:'accept',wager_index:number('wager_index'),smith_indices:data.getAll('smith_indices').map(Number),smith_equip_index:number('smith_equip_index')};
    if(action==='resolve_trait_loss') return {choice_id:room.decision.choice.id,trait_indices:data.getAll('trait_indices').map(Number)};
    if(action==='crossroads_discard') return {equip_sources:data.getAll('equip_sources').map(JSON.parse)};
    if(action==='mutagen') return {curse_index:number('curse_index'),target_player_id:number('target_player_id')};
    return Object.fromEntries(data);
  }
  async function connect(target) {
    clearInterval(timer); room=null; revision=-1;
    code=target.toUpperCase().trim(); token=tokens[code]||'';
    if (!token) {landing(); return;}
    try { accept((await request(`/rooms/${code}`)).room,true);schedule(); }
    catch(e) {landing();error(e.message);}
  }
  async function open() {
    active=true; document.body.classList.add('wo-open');screen.hidden=false;
    if (!heroes.length) {
      try { heroes=await (await fetch(API+'/heroes')).json(); } catch (_) {}
    }
    const invited=new URLSearchParams(location.search).get('room');
    if (room) {renderRoom();schedule();poll();}
    else if(invited && tokens[invited.toUpperCase()]) await connect(invited);
    else landing();
  }
  function init() {
    screen=document.createElement('section');screen.id='wo-screen';screen.hidden=true;document.body.appendChild(screen);
    for(const id of ['profile-screen','main-menu-screen']) {
      const parent=document.getElementById(id); if(!parent)continue;
      const b=document.createElement('button');b.className='btn-primary wo-launch';b.textContent='Play Online';b.onclick=open;
      (parent.querySelector('.setup-box')||parent).appendChild(b);
    }
    screen.addEventListener('click',async event=>{
      const b=event.target.closest('[data-op]');if(!b||busy)return;
      const action=b.dataset.op,payload=JSON.parse(b.dataset.payload||'{}');
      if(action==='close'){active=false;clearInterval(timer);screen.hidden=true;document.body.classList.remove('wo-open');return;}
      if(action==='rooms'){clearInterval(timer);room=null;code='';token='';landing();return;}
      if(action==='reconnect'){await connect(payload.code);return;}
      if(action==='invite'){try{await navigator.clipboard.writeText(location.origin+'/games/werblers?room='+code);}catch(_){screen.querySelector('[aria-label="Invitation link"]').select();}return;}
      if(action==='scavenger_swap') payload.item_index=Number(screen.querySelector('[name=chosen_index]:checked')?.value || 0);
      if(action==='use_consumable') {const target=screen.querySelector('[name="curse_target"]');if(target)payload.target_player_id=Number(target.value);}
      await act(action,payload);
    });
    screen.addEventListener('change', event => {
      const form = event.target.closest('form[data-form=resolve_trait_loss]');
      if (form) form.querySelector('button').disabled = form.querySelectorAll('input:checked').length !== room.decision.choice.count;
    });
    screen.addEventListener('submit',async event=>{
      event.preventDefault();if(busy)return;
      const form=event.target, action=form.dataset.form, payload=formPayload(form);
      if(action==='create'||action==='join') {
        busy=true;error('');
        try{
          if(action==='join'){code=payload.code.trim().toUpperCase();token=tokens[code]||'';}else token='';
          const data=await request(action==='create'?'/rooms':`/rooms/${encodeURIComponent(code)}/join`,payload);
          code=data.room.code;token=data.token;remember();accept(data.room,true);schedule();
        }catch(e){error(e.message);}finally{busy=false;}
      } else await act(action,payload);
    });
    window.addEventListener('online',poll);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
    if(new URLSearchParams(location.search).has('room'))open();
  }
  document.addEventListener('DOMContentLoaded',init);
  return {open};
})();
