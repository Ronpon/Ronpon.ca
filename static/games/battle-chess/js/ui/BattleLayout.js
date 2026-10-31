import { playerEmblemMarkup } from '../PlayerEmblems.js';

const escapeHtml = text => {
    const element = document.createElement('span');
    element.textContent = text ?? '';
    return element.innerHTML;
};

/** Shared player panels and arena for local and online battles. */
export function createBattleLayout({ players, attackerColor, advantage, gameEntry, controls }) {
    const panel = document.createElement('div');
    panel.className = 'mg-screen';
    const sidebar = (player, index) => {
        const role = attackerColor === (index === 0 ? 'w' : 'b') ? 'Attacker' : 'Defender';
        return `
            <div class="mg-sidebar mg-sidebar-${index === 0 ? 'left' : 'right'}">
                <div class="mg-player-icon">${playerEmblemMarkup(player.icon || (index === 0 ? '⚔️' : '🛡️'))}</div>
                <div class="mg-player-name">${escapeHtml(player.name)}</div>
                <div class="mg-player-role mg-role-${role.toLowerCase()}">${role}</div>
                ${advantage === role.toLowerCase() ? '<div class="mg-advantage-badge">★ Advantage</div>' : ''}
                <div class="mg-controls-hint">${escapeHtml(controls?.[index] ?? gameEntry.controls?.[index === 0 ? 'player1' : 'player2'])}</div>
            </div>`;
    };
    panel.innerHTML = sidebar(players[0], 0)
        + `<div class="mg-center"><h2 class="mg-title">${escapeHtml(gameEntry.name)}</h2><div class="mg-arena" id="mg-arena"></div></div>`
        + sidebar(players[1], 1);
    return panel;
}

export function captureConsequence(attackerWins, isKing, attackerLosesPiece) {
    return attackerWins ? 'The capture succeeds. The defending piece is taken.'
        : isKing ? 'The capture fails. The king and defending piece stay on the board.'
        : attackerLosesPiece ? 'The attacking piece is removed. The defending piece stays.'
        : 'The capture fails. Both pieces stay on the board.';
}

export function createBattleResult({ result, players, attackerColor, consequence = '', buttonText, onContinue }) {
    const attackerIndex = attackerColor === 'w' ? 0 : 1;
    const winnerIndex = result.attackerWins ? attackerIndex : 1 - attackerIndex;
    const winner = players[winnerIndex];
    const overlay = document.createElement('div');
    overlay.className = 'mg-result-overlay';
    overlay.innerHTML = `
        <div class="mg-result-panel">
            <div class="mg-result-icon">${result.tie ? '😮' : playerEmblemMarkup(winner.icon || (winnerIndex === 0 ? '⚔️' : '🛡️'))}</div>
            <h3 class="mg-result-title">${result.tie ? "Whoa… it's a tie!" : result.attackerWins ? 'Attacker Wins!' : 'Defender Wins!'}</h3>
            ${result.tie ? '' : `<p class="mg-result-name">${escapeHtml(winner.name)}</p>`}
            <p class="mg-result-consequence">${escapeHtml(consequence)}</p>
            <button class="btn btn-primary mg-continue-btn">${escapeHtml(buttonText || (result.tie ? 'Here we go again' : 'Continue'))}</button>
        </div>`;
    overlay.querySelector('button').onclick = onContinue;
    return overlay;
}
