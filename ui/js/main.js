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
  permId = m.id; byId('perm-action').textContent = m.action;
  byId('perm-params').textContent = JSON.stringify(m.params, null, 2);
  byId('perm-overlay').classList.add('show');
}
function respondPerm(ok) { wsSend({ type: 'permission.response', id: permId, approved: ok }); byId('perm-overlay').classList.remove('show'); }

/* ---------- roteamento dos eventos do backend ---------- */
function route(m) {
  switch (m.type) {
    case 'assistant.token': chat.onToken(m); break;
    case 'assistant.message': chat.onMessage(m); sidebar.loadSessions(); break;
    case 'agent.invoked': chat.onTool(`↳ ${m.tool}(${JSON.stringify(m.args)})`); break;
    case 'agent.result': chat.onTool(`✓ ${m.tool}: ${m.content}`); break;
    case 'avatar.state': State.set({ emotion: m.emotion }); avatar.avatarEmotion(m.emotion, m.animation, m.gesture); break;
    case 'avatar.gesture': avatar.avatarGesture(m.value); break;
    case 'aila.state': State.set({ status: m.status, tool: m.tool || null }); break;
    case 'memory.recalled': chat.onTool(`🧠 lembrei de ${m.items.length} memória(s)`); break;
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
  byId('btn-hamb').onclick = () => byId('drawer').classList.toggle('collapsed');
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
}

/* ---------- start ---------- */
initSettings();
wireUI();
connectWS({ onMessage: route, onClose: () => setLlm(false) });
sidebar.loadSessions();
loadStatus();
setInterval(loadStatus, 8000);
