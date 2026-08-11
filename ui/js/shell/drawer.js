// ============================================================
//  Drawer — o Inspector (Atividade/Tarefas/Sistema) vira um painel
//  retrátil que desliza da direita. Fechado por padrão; abre pelo
//  botão da topbar e AUTOMATICAMENTE quando a Aila entra em "working"
//  (Focus Mode) — assim você vê o que ela está fazendo sem precisar abrir.
// ============================================================
import { byId } from '../dom.js';
import { State } from '../state.js';

const set = (open) => State.set({ drawerOpen: open });

export function initDrawer() {
  const toggle = byId('btn-drawer');
  if (toggle) toggle.onclick = () => set(!State.get('drawerOpen'));

  let lastMode = null;
  State.on((s, patch) => {
    document.body.dataset.drawer = s.drawerOpen ? 'open' : 'closed';
    if (toggle) toggle.classList.toggle('active', !!s.drawerOpen);
    // ao ENTRAR em working, revela a atividade (só na transição, não em loop)
    if (patch && patch.uiMode) {
      if (patch.uiMode === 'working' && lastMode !== 'working') set(true);
      lastMode = patch.uiMode;
    }
  });
  document.body.dataset.drawer = 'closed';
}

export function closeDrawer() { set(false); }
