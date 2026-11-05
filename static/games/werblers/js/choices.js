/* Shared saved decisions and recovery for desktop and mobile play. */
window.werblersChoices = (() => {
  let overlay = null;
  let submitting = false;
  let restoring = false;
  let resumeOverlay = null;

  function render(state) {
    if (submitting) return;
    if (['move', 'finished'].includes(state.decision?.phase)) restoring = false;
    if (overlay) overlay.remove();
    overlay = null;
    const loss = state.pending_trait_loss;
    const choice = loss || state.pending_me_too;
    if (!choice) return;
    const player = state.players.find(p => p.player_id === choice.player_id);
    const source = state.players.find(p => p.player_id === choice.source_player_id);
    if (!player) return;

    overlay = document.createElement('div');
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', loss ? 'Choose traits to lose' : 'Me Too!');
    Object.assign(overlay.style, {
      position: 'fixed', inset: '0', zIndex: '100000', background: '#000b',
      display: 'grid', placeItems: 'center', padding: '20px',
    });
    const panel = document.createElement('div');
    Object.assign(panel.style, {
      background: '#202b26', color: '#fff', padding: '24px', borderRadius: '12px',
      maxWidth: '420px', width: '100%', maxHeight: '85vh', overflowY: 'auto',
    });
    const heading = document.createElement('h2');
    heading.textContent = `${loss ? 'Slurp!' : 'Me Too!'} — ${player.name}`;
    const description = document.createElement('p');
    description.textContent = loss
      ? `Joh’Neil defeated you. Choose ${choice.count} traits to lose before continuing.`
      : `${source?.name || 'Another player'} discarded a curse. Choose one of your curses to discard, or keep them.`;
    panel.append(heading, description);
    const error = document.createElement('p');
    error.setAttribute('role', 'alert');

    async function submit(curseIndex) {
      if (submitting) return;
      submitting = true;
      panel.querySelectorAll('button').forEach(b => { b.disabled = true; });
      try {
        const response = await fetch('/games/werblers/api/' + (loss ? 'resolve_trait_loss' : 'resolve_me_too'), {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(loss ? {choice_id: choice.id, trait_indices: curseIndex}
                                   : {choice_id: choice.id, curse_index: curseIndex}),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Could not resolve Me Too!');
        submitting = false;
        applyState(data.state);
        if (restoring) resumeDecision(data.state.decision, data.state);
      } catch (e) {
        submitting = false;
        error.textContent = e.message;
        panel.querySelectorAll('button').forEach(b => { b.disabled = false; });
      }
    }
    function button(label, index) {
      const b = document.createElement('button');
      b.className = 'btn-secondary';
      b.textContent = label;
      Object.assign(b.style, {display: 'block', width: '100%', marginTop: '12px'});
      b.addEventListener('click', () => submit(index));
      panel.appendChild(b);
    }
    if (loss) {
      const selected = new Set();
      const confirm = document.createElement('button');
      confirm.className = 'btn-primary';
      confirm.textContent = `Discard ${choice.count} selected traits`;
      confirm.disabled = true;
      player.traits.forEach((trait, index) => {
        const label = document.createElement('label');
        Object.assign(label.style, {display: 'block', margin: '12px 0'});
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.addEventListener('change', () => {
          if (input.checked) selected.add(index); else selected.delete(index);
          confirm.disabled = selected.size !== choice.count;
        });
        const name = document.createElement('span');
        name.textContent = ` ${trait.name}`;
        label.append(input, name);
        panel.appendChild(label);
      });
      confirm.addEventListener('click', () => submit([...selected]));
      panel.appendChild(confirm);
    } else {
      player.curses.forEach((curse, index) => button(`Discard ${curse.name}`, index));
      button('Keep my curses', null);
    }
    panel.appendChild(error);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);
    const buttons = [...panel.querySelectorAll('input'), ...panel.querySelectorAll('button')];
    overlay.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const enabled = buttons.filter(b => !b.disabled);
      const index = enabled.indexOf(document.activeElement);
      event.preventDefault();
      enabled[(index + (event.shiftKey ? -1 : 1) + enabled.length) % enabled.length].focus();
    });
    buttons[0].focus();
  }
  function resumeGame(data) {
    restoring = true;
    if (typeof _invOnConfirm !== 'undefined') _invOnConfirm = null;
    if (typeof _invPlacementItem !== 'undefined') _invPlacementItem = null;
    if (typeof _playerSheetOpen !== 'undefined') _playerSheetOpen = false;
    if (typeof _pendingCombatInfo !== 'undefined') _pendingCombatInfo = null;
    resumeOverlay?.remove();
    resumeOverlay = null;
    for (const id of ['battle-overlay', 'offer-modal', 'inventory-modal', 'gain-modal', 'winner-modal', 'rake-it-in-modal', 'player-sheet-overlay', 'minion-replace-modal']) {
      if (id === 'winner-modal' && data.state?.game_status === 'WON') continue;
      document.getElementById(id)?.classList.add('hidden');
    }
    resumeDecision(data.resume || data.state?.decision, data.state);
  }

  function resumeDecision(decision, state) {
    if (!decision) return;
    const d = decision;
    if (d.phase === 'combat') {
      playMusic('Battle Music.wav');
      showPreFightScene(d.combat || d.combat_info, state);
    } else if (d.phase === 'charlie_work') {
      _showCharlieWorkDecision(d.level);
    } else if (d.phase === 'chest' || d.phase === 'shop') {
      _pendingOfferType = d.phase;
      _pendingOfferData = {items: d.items, has_scavenger: d.scavenger};
      if (d.phase === 'chest') showChestModal(_pendingOfferData, {});
      else showShopModal(_pendingOfferData, state, {});
    } else if (d.phase === 'mystery') {
      const event = {...d.event, image: `Events/${d.event.image_name || d.event.name} Tier ${d.event.tier}.png`};
      showMysteryEventModal(event, state);
    } else if (d.phase === 'rake_it_in') {
      const p = state.players.find(p => p.player_id === d.player_id);
      const equips = ['helmets', 'chest_armor', 'leg_armor', 'weapons'].flatMap(key =>
        p[key].map((item, index) => ({...item, slot_index: index}))).filter(item =>
          !item.locked_by_curse_id || !p.curses.some(c => c.effect_id === item.locked_by_curse_id));
      const data = {state, sub_type: d.sub_type, equips, pack_items: p.pack,
        consumable_items: p.consumables, shop_remaining: d.items};
      if (typeof showRakeItInModal === 'function') showRakeItInModal(data);
      else showRakeItIn(data);
    } else if (['item', 'minion', 'fairy_king_reward'].includes(d.phase)) {
      resumeReward(d, state);
    } else if (d.phase === 'me_too' || d.phase === 'trait_loss') {
      render(state);
    } else {
      restoring = false;
    }
  }

  function resumeReward(d, state) {
    resumeOverlay?.remove();
    const p = state.players.find(p => p.player_id === d.player_id);
    const dialog = document.createElement('div');
    dialog.className = 'werblers-recovery';
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-label', 'Finish your reward choice');
    const panel = document.createElement('div');
    panel.className = 'werblers-recovery-panel';
    const title = document.createElement('h2');
    title.textContent = `${p.name} — ${d.phase === 'minion' ? d.minion.name : 'Choose your reward'}`;
    const error = document.createElement('p');
    error.setAttribute('role', 'alert');
    panel.append(title, error);
    async function submit(action, body) {
      if (submitting) return;
      submitting = true;
      panel.querySelectorAll('button').forEach(b => { b.disabled = true; });
      try {
        const response = await fetch('/games/werblers/api/' + action, {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
        });
        const data = await response.json();
        if (!response.ok || data.error) throw new Error(data.error || 'Could not finish this choice.');
        submitting = false;
        dialog.remove(); resumeOverlay = null;
        applyState(data.state);
        resumeDecision(data.state.decision, data.state);
      } catch (e) {
        submitting = false; error.textContent = e.message;
        panel.querySelectorAll('button').forEach(b => { b.disabled = false; });
      }
    }
    function button(text, action, body) {
      const b = document.createElement('button');
      b.className = 'btn-secondary'; b.textContent = text;
      b.addEventListener('click', () => submit(action, typeof body === 'function' ? body() : body));
      panel.appendChild(b);
    }
    function select(label, entries) {
      const wrap = document.createElement('label');
      wrap.textContent = label;
      const input = document.createElement('select');
      entries.forEach(([value, name]) => {
        const option = document.createElement('option'); option.value = value; option.textContent = name;
        input.appendChild(option);
      });
      wrap.appendChild(input); panel.appendChild(wrap);
      return input;
    }
    if (d.phase === 'item') {
      const item = d.items[0];
      const name = document.createElement('p'); name.textContent = item.name; panel.appendChild(name);
      const slot = {helmet:'helmets', chest:'chest_armor', legs:'leg_armor', weapon:'weapons'}[item.slot];
      const old = select('Equipment to replace if needed', (p[slot] || []).map((i,n) => [n,i.name]));
      const action = select('Replaced equipment', [['swap','Keep in pack'],['discard','Discard']]);
      const second = select('Second replaced weapon', [['swap','Keep in pack'],['discard','Discard']]);
      const pack = [...p.pack, ...p.consumables, ...p.captured_monsters].map((i,n) => [n,i.name]);
      const replace = select('Pack item to replace if full', pack);
      const replace2 = select('Second pack replacement if needed', pack);
      const choices = placement => ({player_id:p.player_id, placement_choices:{placement,
        equip_item_index:Number(old.value || 0), equip_action:action.value, equip_action_2:second.value,
        pack_discard_index:Number(replace.value || 0), pack_discard_index_2:Number(replace2.value || 0)}});
      button('Keep in pack', 'place_trait_item', () => choices('pack'));
      if (!item.is_consumable) button('Equip', 'place_trait_item', () => choices('equip'));
      button('Discard reward', 'place_trait_item', {player_id:p.player_id, placement_choices:{discard:true}});
    } else if (d.phase === 'minion') {
      if (p.minions.length < p.max_minions) button('Add minion', 'resolve_minion', {player_id:p.player_id, replace_index:-1});
      p.minions.forEach((m,i) => button(`Replace ${m.name}`, 'resolve_minion', {player_id:p.player_id, replace_index:i}));
      button('Decline minion', 'resolve_minion', {player_id:p.player_id, discard:true});
    } else {
      d.items.forEach((item,i) => button(item.name, 'resolve_fairy_king_reward', {choice_index:i}));
    }
    dialog.appendChild(panel); document.body.appendChild(dialog); resumeOverlay = dialog;
    panel.querySelectorAll('button')[0]?.focus();
    dialog.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const inputs = [...panel.querySelectorAll('select'), ...panel.querySelectorAll('button')].filter(e => !e.disabled);
      const index = inputs.indexOf(document.activeElement);
      event.preventDefault(); inputs[(index + (event.shiftKey ? -1 : 1) + inputs.length) % inputs.length].focus();
    });
  }
  return {render, resumeGame, resumeLoadedCombat: resumeGame};
})();
