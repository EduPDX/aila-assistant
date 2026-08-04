// Componentes de UI reutilizáveis: menu de contexto e diálogos (confirm/prompt).
import { el } from './dom.js';

function closeMenu() { document.querySelector('.ctx-menu')?.remove(); }

/** Menu de contexto ancorado a um elemento. items: [{icon,label,danger,onClick}] */
export function contextMenu(anchor, items) {
  closeMenu();
  const menu = el('div', { class: 'ctx-menu' },
    ...items.map((it) => el('button',
      { class: it.danger ? 'danger' : '',
        onclick: (e) => { e.stopPropagation(); closeMenu(); it.onClick(); } },
      (it.icon ? it.icon + ' ' : '') + it.label)));
  document.body.append(menu);
  const r = anchor.getBoundingClientRect();
  menu.style.top = Math.min(r.bottom + 4, innerHeight - menu.offsetHeight - 8) + 'px';
  menu.style.left = Math.min(r.left, innerWidth - menu.offsetWidth - 8) + 'px';
  setTimeout(() => document.addEventListener('click', closeMenu, { once: true }), 0);
  document.addEventListener('keydown', function esc(e) {
    if (e.key === 'Escape') { closeMenu(); document.removeEventListener('keydown', esc); }
  });
}

function overlay(build) {
  return new Promise((resolve) => {
    const ov = el('div', { class: 'overlay show' });
    const done = (v) => { ov.remove(); resolve(v); };
    ov.append(build(done));
    ov.addEventListener('click', (e) => { if (e.target === ov) done(null); });
    document.body.append(ov);
    return ov;
  });
}

/** Confirmação. Resolve true/false. */
export function confirmDialog({ title = 'Confirmar', body = '', confirmLabel = 'Confirmar', danger = false } = {}) {
  return overlay((done) => el('div', { class: 'modal' },
    el('h3', danger ? { style: 'color:var(--danger)' } : {}, title),
    body ? el('p', { class: 'muted', style: 'margin-top:6px' }, body) : null,
    el('div', { class: 'modal-actions' },
      el('button', { class: 'btn', onclick: () => done(false) }, 'Cancelar'),
      el('button', { class: 'btn ' + (danger ? 'danger' : 'accent'), onclick: () => done(true) }, confirmLabel),
    ),
  )).then((v) => v === true);
}

/** Entrada de texto. Resolve o texto ou null. */
export function promptDialog({ title = 'Editar', value = '', placeholder = '' } = {}) {
  return overlay((done) => {
    const inp = el('input', { class: 'field', value, placeholder });
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') done(inp.value.trim() || null);
      if (e.key === 'Escape') done(null);
    });
    setTimeout(() => { inp.focus(); inp.select(); }, 0);
    return el('div', { class: 'modal' },
      el('h3', {}, title), inp,
      el('div', { class: 'modal-actions' },
        el('button', { class: 'btn', onclick: () => done(null) }, 'Cancelar'),
        el('button', { class: 'btn accent', onclick: () => done(inp.value.trim() || null) }, 'Salvar'),
      ));
  });
}
