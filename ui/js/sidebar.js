// Sidebar: histórico de conversas. (Fase 1 adiciona busca/renomear/apagar.)
import { byId } from './dom.js';
import { State } from './state.js';
import { wsSend, wsReady } from './ws.js';

export function newSession() { if (wsReady()) wsSend({ type: 'session.new' }); }
export function openSession(id) { if (wsReady()) wsSend({ type: 'session.load', id }); }

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export async function loadSessions() {
  try {
    const r = await (await fetch('/api/sessions')).json();
    if (r.current != null) State.set({ activeSession: r.current });
    const active = State.get('activeSession');
    const box = byId('sessions');
    const items = (r.sessions || []).map((s) =>
      `<div class="session-item ${s.id === active ? 'active' : ''}" data-id="${s.id}">
         <span class="title">💬 ${esc(s.title || ('conversa ' + s.id))}</span>
       </div>`).join('');
    box.innerHTML = items || '<div class="muted" style="padding:6px">nenhuma ainda</div>';
    box.querySelectorAll('.session-item').forEach((it) =>
      it.onclick = () => openSession(+it.dataset.id));
  } catch (e) { /* offline */ }
}
