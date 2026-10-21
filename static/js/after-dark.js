/* Station controls; navigation and page content also work without JavaScript. */
(() => {
    'use strict';
    const body = document.body;
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    let saved = null;
    try { saved = localStorage.getItem('ronpon-reduced-motion'); } catch { /* Optional preference. */ }
    let paused = reduced.matches || saved === 'true';
    const motionButtons = document.querySelectorAll('[data-motion-toggle]');
    const television = document.querySelector('[data-television]');
    const cards = [...document.querySelectorAll('[data-scroll-card]')];
    let pendingFrame = false;
    function renderScroll() {
        pendingFrame = false;
        if (paused) return;
        if (television) {
            const distance = Math.max(0, -television.getBoundingClientRect().top);
            television.style.setProperty('--tv-tilt', `${Math.min(distance / 200, 2)}deg`);
        }
        cards.forEach((card, index) => {
            const progress = Math.max(0, Math.min(1, (innerHeight - card.getBoundingClientRect().top) / (innerHeight * .7)));
            card.style.setProperty('--tape-rotation', `${(index % 2 ? 3 : -3) * (1 - progress)}deg`);
        });
    }
    function queueScroll() {
        if (!paused && !pendingFrame && (television || cards.length)) {
            pendingFrame = true;
            requestAnimationFrame(renderScroll);
        }
    }
    function syncMotion() {
        body.classList.toggle('motion-paused', paused);
        motionButtons.forEach(button => {
            button.hidden = false;
            button.textContent = reduced.matches ? 'Motion reduced' : paused ? 'Motion paused' : 'Pause motion';
            button.disabled = reduced.matches;
            button.setAttribute('aria-pressed', String(paused));
        });
        if (paused) {
            television?.style.removeProperty('--tv-tilt');
            cards.forEach(card => card.style.removeProperty('--tape-rotation'));
        } else queueScroll();
    }
    motionButtons.forEach(button => button.addEventListener('click', () => {
        saved = String(!paused);
        paused = reduced.matches || saved === 'true';
        try { localStorage.setItem('ronpon-reduced-motion', saved); } catch { /* Optional preference. */ }
        syncMotion();
    }));
    reduced.addEventListener('change', event => { paused = event.matches || saved === 'true'; syncMotion(); });
    syncMotion();
    addEventListener('scroll', queueScroll, {passive: true});
    addEventListener('resize', queueScroll);

    const toggle = document.getElementById('nav-toggle');
    const menu = document.getElementById('nav-menu');
    const overlay = document.getElementById('nav-overlay');
    const mobile = matchMedia('(max-width: 1000px)');
    let open = false;
    function syncMenu() {
        const expanded = mobile.matches && open;
        menu.classList.toggle('open', expanded);
        menu.inert = mobile.matches && !expanded;
        toggle.classList.toggle('active', expanded);
        toggle.setAttribute('aria-expanded', String(expanded));
        toggle.setAttribute('aria-label', expanded ? 'Close navigation' : 'Open navigation');
        overlay.classList.toggle('visible', expanded);
        body.classList.toggle('nav-is-open', expanded);
    }
    if (toggle && menu && overlay) {
        body.classList.add('nav-enhanced');
        toggle.addEventListener('click', () => { open = !open; syncMenu(); });
        overlay.addEventListener('click', () => { open = false; syncMenu(); toggle.focus(); });
        menu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => { open = false; syncMenu(); }));
        document.addEventListener('keydown', event => {
            if (!open || !mobile.matches) return;
            if (event.key === 'Escape') { open = false; syncMenu(); toggle.focus(); }
            if (event.key === 'Tab') {
                const items = [toggle, ...menu.querySelectorAll('a, button:not([disabled])')];
                const first = items[0], last = items[items.length - 1];
                if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
                else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
            }
        });
        mobile.addEventListener('change', () => { open = false; syncMenu(); });
        syncMenu();
    }

    if (!television) return;
    const panels = [...television.querySelectorAll('[data-broadcast]')];
    const dial = television.querySelector('[data-dial]');
    const buttons = [...document.querySelectorAll('[data-channel]')];
    const status = document.querySelector('[data-channel-status]');
    let channel = 0;
    document.querySelectorAll('[data-tv-enhancement], [data-dial], [data-tune]').forEach(el => { el.hidden = false; });
    function tune(index, announce = true) {
        if (!panels[index]) return;
        channel = index;
        panels.forEach((panel, i) => { panel.hidden = i !== channel; });
        buttons.filter(b => !b.hasAttribute('data-tune')).forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.channel) === channel)));
        dial.style.setProperty('--dial-angle', `${channel * 90 - 30}deg`);
        const name = panels[channel].querySelector('.channel-ident').textContent.trim().replace(/\s+/g, ' ');
        dial.setAttribute('aria-label', `${name}. Tune to the next channel`);
        if (announce) status.textContent = `Tuned to ${name}`;
        if (!paused) panels[channel].animate([{opacity: .55}, {opacity: 1}], {duration: 180});
    }
    dial.addEventListener('click', () => tune((channel + 1) % panels.length));
    buttons.forEach(button => button.addEventListener('click', () => {
        tune(Number(button.dataset.channel));
        if (button.hasAttribute('data-tune')) {
            television.scrollIntoView({behavior: paused ? 'instant' : 'smooth', block: 'center'});
            dial.focus({preventScroll: true});
        }
    }));
    television.querySelector('.channel-buttons').addEventListener('keydown', event => {
        if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const index = event.key === 'Home' ? 0 : event.key === 'End' ? panels.length - 1 : (channel + (event.key === 'ArrowRight' ? 1 : panels.length - 1)) % panels.length;
        tune(index);
        television.querySelector(`[data-channel="${index}"]`).focus();
    });
    tune(0, false);
})();
