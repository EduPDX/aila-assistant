// ============================================================
//  Boot sequence — splash HUD de inicialização ("ligando a nave").
//  Puramente cosmético: revela os subsistemas em sequência e sai quando
//  o app conecta (ou por timeout de segurança). Respeita reduced-motion.
//  Rede de segurança extra em CSS (@keyframes bootFail) caso o JS falhe.
// ============================================================
import { byId } from '../dom.js';
import { State } from '../state.js';

const SUBS = ['NÚCLEO', 'MODELO', 'AVATAR', 'MEMÓRIA', 'REDE'];

export function initBoot() {
  const boot = byId('boot');
  if (!boot) return;
  const lines = byId('boot-lines');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const start = performance.now();
  let done = false, off = null;

  const finish = () => {
    if (done) return; done = true;
    if (off) off();
    boot.classList.add('done');
    setTimeout(() => boot.remove(), 600);   // remove após o fade
  };

  if (reduce) {
    lines.innerHTML = SUBS.map((s) => `<div class="boot-line ok"><span>${s}</span><b>OK</b></div>`).join('');
    setTimeout(finish, 350);
    return;
  }

  // revela cada subsistema em sequência, com "OK" logo depois
  SUBS.forEach((s, i) => {
    setTimeout(() => {
      if (done) return;
      const el = document.createElement('div');
      el.className = 'boot-line';
      el.innerHTML = `<span>${s}</span><b>··</b>`;
      lines.appendChild(el);
      setTimeout(() => { el.classList.add('ok'); const b = el.querySelector('b'); if (b) b.textContent = 'OK'; }, 170);
    }, 190 * i);
  });

  // saída: quando conectar (após tempo mínimo de exibição) ou por timeout
  const MIN = 1500, MAX = 3200;
  const maybe = () => { if (State.get('connection') === 'online' && performance.now() - start >= MIN) finish(); };
  off = State.on(maybe);
  setTimeout(maybe, MIN);
  setTimeout(finish, MAX);   // fallback: sai de qualquer jeito
}
