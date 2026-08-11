// ============================================================
//  Bootstrap da interface: liga WebSocket -> módulos -> estado global.
// ============================================================
import { byId } from './dom.js';
import { State, STATUS_LABEL } from './state.js';
import { connectWS, wsSend } from './ws.js';
import * as chat from './chat.js';
import * as sidebar from './sidebar.js';
import * as avatar from './avatar.js';
import * as voice from './voice.js';
import { initSettings, openSettings, closeSettings, settingsTab, loadStatus, setLlm } from './settings.js';
import { ingest } from './core/events.js';
import { humanizeTool } from './core/humanize.js';
import { initDirector } from './core/director.js';
import { initTopbar, refreshStatus } from './shell/topbar.js';
import { initInspector } from './shell/inspector.js';
import { initDrawer } from './shell/drawer.js';
import { initHud } from './shell/hud.js';

/* ---------- abas ---------- */
function showTab(t) {
  ['avatar', 'chat'].forEach((x) => {
    byId('pane-' + x).classList.toggle('active', x === t);
    byId('tab-' + x).classList.toggle('active', x === t);
  });
}

/* ---------- permissão ---------- */
let permId = null;
function showPerm(m) {
  permId = m.id;
  const risk = (m.risk || 'review').toLowerCase();
  byId('perm-human').textContent = humanizeTool(m.action, m.params);
  byId('perm-action').textContent = m.action;
  const hasParams = m.params && Object.keys(m.params).length;
  byId('perm-params').textContent = hasParams ? JSON.stringify(m.params, null, 2) : '';
  const badge = byId('perm-risk');
  badge.textContent = risk === 'danger' ? 'RISCO ALTO' : 'REVISÃO';
  badge.dataset.risk = risk;
  byId('perm-modal').dataset.risk = risk;
  byId('perm-allow').className = 'btn ' + (risk === 'danger' ? 'danger' : 'accent');
  byId('perm-overlay').classList.add('show');
}
function respondPerm(ok) {
  wsSend({ type: 'permission.response', id: permId, approved: ok });
  byId('perm-overlay').classList.remove('show');
  State.set({ pendingPermission: null });   // sai do estado WAITING_PERMISSION
}

/* ---------- roteamento dos eventos do backend ---------- */
function route(m) {
  switch (m.type) {
    case 'assistant.token': chat.onToken(m); break;
    case 'assistant.message': chat.onMessage(m); sidebar.loadSessions(); break;
    // agent.invoked / agent.result / memory.recalled NÃO poluem mais o chat —
    // vivem no Activity drawer (via core/events.js:ingest). O chat fica só com a conversa.
    case 'avatar.state': State.set({ emotion: m.emotion }); avatar.avatarEmotion(m.emotion, m.animation, m.gesture); break;
    case 'avatar.behavior': State.set({ emotion: m.emotion }); avatar.avatarBehavior(m); break;
    case 'avatar.gesture': avatar.avatarGesture(m.value); break;
    case 'aila.state': State.set({ status: m.status, tool: m.tool || null }); avatar.avatarStatus(m.status); break;
    case 'permission.request': showPerm(m); break;
    case 'session.loaded': chat.renderMessages(m.messages); State.set({ activeSession: m.id }); sidebar.loadSessions(); break;
    case 'session.changed': chat.clearChat(); State.set({ activeSession: m.id }); sidebar.loadSessions(); break;
    case 'error': chat.onSys('erro: ' + m.message); break;
  }
}

/* ---------- estado global -> topbar (emoção/estado) ---------- */
State.on((s) => {
  document.body.dataset.status = s.status;
  const chip = byId('emochip');
  chip.textContent = s.status !== 'IDLE' ? (STATUS_LABEL[s.status] || s.status) : s.emotion;
});

/* ---------- wiring da UI ---------- */
function wireUI() {
  byId('btn-settings').onclick = openSettings;
  byId('btn-settings-close').onclick = closeSettings;
  byId('settings-nav').querySelectorAll('.snav').forEach((b) => b.onclick = () => settingsTab(b.dataset.p));
  byId('btn-new').onclick = () => { sidebar.newSession(); chat.clearChat(); showTab('chat'); };
  byId('search').oninput = sidebar.renderSessions;
  byId('btn-hamb').onclick = () => setDrawer(byId('drawer').classList.contains('collapsed'));
  byId('tab-avatar').onclick = () => showTab('avatar');
  byId('tab-chat').onclick = () => showTab('chat');
  byId('btn-send').onclick = chat.send;
  byId('mic').onclick = voice.toggleMic;
  byId('attach').onclick = () => byId('attachfile').click();
  byId('attachfile').onchange = (e) => chat.attachFiles(e.target.files, () => { showTab('chat'); e.target.value = ''; });
  byId('perm-deny').onclick = () => respondPerm(false);
  byId('perm-allow').onclick = () => respondPerm(true);

  const input = byId('input');
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); chat.send(); } });
  input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = input.scrollHeight + 'px'; });

  voice.setTranscriptHandler((text, err) => {
    if (err) return chat.onSys(err);
    if (text) { showTab('chat'); chat.sendUserText(text); }
  });

  // ---- responsividade: gaveta (sidebar) no mobile ----
  byId('scrim').onclick = () => setDrawer(false);                                    // toca no fundo -> fecha
  byId('sessions').addEventListener('click', () => { if (isMobile()) setDrawer(false); });  // escolheu conversa -> fecha
  let wasMobile = null;
  const applyResponsive = () => { const m = isMobile(); if (m !== wasMobile) { setDrawer(!m); wasMobile = m; } };
  applyResponsive();
  addEventListener('resize', applyResponsive);
}

/* ---------- gaveta (sidebar) + scrim ---------- */
const isMobile = () => window.innerWidth <= 860;
function setDrawer(open) {
  byId('drawer').classList.toggle('collapsed', !open);
  byId('scrim').classList.toggle('show', open && isMobile());   // scrim só no mobile
}

/* ---------- start ---------- */
initSettings();
initDirector();     // camada adaptativa: Agent State → data-mode no shell
initTopbar();
initInspector();
initDrawer();       // inspector como drawer retrátil (abre em WORKING)
initHud();          // telemetria HUD sobre o palco (dono do poll de /api/metrics)
wireUI();
connectWS({
  onMessage: (m) => { ingest(m); route(m); },   // ingest = estado/atividade; route = UI (chat/avatar)
  onOpen: () => { State.set({ connection: 'online' }); refreshStatus(); },
  onClose: () => { State.set({ connection: 'offline', llmOnline: false }); setLlm(false); },
});
sidebar.loadSessions();
loadStatus();   // status de voz (uma vez); a topbar cuida do poll de /api/status
