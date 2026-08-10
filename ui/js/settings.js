// Tela de Configurações (⚙️): tema, modelos VRM, voz, status.
import { byId, $$ } from './dom.js';
import { State } from './state.js';
import { avatarReload } from './avatar.js';
import { renderProviders } from './views/providers.js';

const THEMES = [
  { id: 'aqua', c: '#38e1d0' }, { id: 'cyber', c: '#c257ff' }, { id: 'rose', c: '#ff6fae' },
  { id: 'forest', c: '#43e08a' }, { id: 'light', c: '#0bb3a0' },
];

export function setTheme(id) {
  document.documentElement.setAttribute('data-theme', id);
  localStorage.setItem('aila-theme', id);
  $$('.swatch').forEach((s) => s.classList.toggle('active', s.dataset.id === id));
}

export const openSettings = () => byId('settings-overlay').classList.add('show');
export const closeSettings = () => byId('settings-overlay').classList.remove('show');
export function settingsTab(p) {
  $$('.snav').forEach((b) => b.classList.toggle('active', b.dataset.p === p));
  $$('.spane').forEach((s) => s.classList.toggle('active', s.id === 'sp-' + p));
  if (p === 'modelos') renderProviders();   // carrega o estado dos provedores ao abrir
}

export function setLlm(on) {
  byId('s-llm').innerHTML = `<span class="dot ${on ? 'on' : 'off'}"></span>${on ? 'online' : 'offline'}`;
}
// status de VOZ (a topbar cuida do /api/status → State; aqui só a voz).
export async function loadStatus() {
  try {
    const v = await (await fetch('/api/voice/status')).json();
    byId('s-voice').textContent = v.enabled ? (v.tts_engine + ' · ' + (v.tts_voice || '')) : 'off';
  } catch (e) { /* offline */ }
}

// espelha o estado global (modelo/llm/memória) nas linhas do painel de Status.
function bindStatusRows() {
  const paint = (s) => {
    setLlm(s.llmOnline);
    byId('s-model').textContent = s.model || '—';
    byId('s-mem').textContent = s.memoryCount ?? 0;
  };
  State.on(paint); paint(State.get());
}

export function initSettings() {
  // swatches de tema
  const box = byId('themes');
  THEMES.forEach((t) => {
    const s = document.createElement('div');
    s.className = 'swatch'; s.dataset.id = t.id; s.style.background = t.c; s.title = t.id;
    s.onclick = () => setTheme(t.id); box.appendChild(s);
  });
  setTheme(localStorage.getItem('aila-theme') || 'aqua');

  // fechar clicando fora
  byId('settings-overlay').addEventListener('click', (e) => { if (e.target.id === 'settings-overlay') closeSettings(); });

  // trocar VRM
  byId('pickvrm').onclick = () => byId('vrmfile').click();
  byId('vrmfile').onchange = async (ev) => {
    const f = ev.target.files[0]; if (!f) return;
    byId('vrmnote').textContent = 'enviando…';
    try {
      const fd = new FormData(); fd.append('file', f, f.name);
      const r = await fetch('/api/avatar/vrm', { method: 'POST', body: fd });
      byId('vrmnote').textContent = r.ok ? '✓ trocado' : 'falhou';
      if (r.ok) avatarReload();
    } catch (e) { byId('vrmnote').textContent = 'falhou'; }
    setTimeout(() => byId('vrmnote').textContent = '', 4000); ev.target.value = '';
  };

  // toggle de voz
  byId('tg-voice').onclick = () => {
    const on = !State.get('voiceOut'); State.set({ voiceOut: on });
    byId('tg-voice').classList.toggle('on', on);
  };

  bindStatusRows();   // linhas do painel de Status espelham o State global
}
