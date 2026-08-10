// ============================================================
//  Model Center — gerência de provedores de LLM (local + nuvem).
//  Colar a API key, ativar/desativar, escolher o modelo preferido.
//  As chaves NUNCA voltam do backend (só has_key); o input só ENVIA.
// ============================================================
import { byId, el } from '../dom.js';
import { api } from '../core/api.js';

// marcas com a cor de cada empresa (não são os logos oficiais — evita marca
// registrada e funciona offline). glyph curto e reconhecível pela cor.
const BRAND = {
  local: { color: 'var(--accent)', glyph: '💻' },
  openai: { color: '#10a37f', glyph: 'O' },
  gemini: { color: '#4285f4', glyph: '✦' },
  grok: { color: '#111827', glyph: 'x' },
  deepseek: { color: '#4d6bfe', glyph: 'D' },
};

let busy = false;

export async function renderProviders() {
  const box = byId('providers-list');
  if (!box) return;
  box.textContent = 'carregando…';
  try {
    const data = await api.providers();
    box.innerHTML = '';
    data.providers.forEach((p) => box.append(card(p)));
  } catch (e) {
    box.textContent = 'não foi possível carregar os provedores.';
  }
}

function card(p) {
  const b = BRAND[p.name] || BRAND.local;
  const mark = el('div', { class: 'prov-mark', style: `background:${b.color}` }, b.glyph);

  const badge = p.preferred
    ? el('span', { class: 'prov-badge on' }, p.kind === 'local' ? 'Preferido' : 'Ativo · preferido')
    : (p.kind === 'cloud' && p.enabled ? el('span', { class: 'prov-badge' }, 'Configurado') : null);

  const sub = p.kind === 'local'
    ? 'Ollama · grátis · offline'
    : `${p.model || ''}${p.vision ? ' · visão' : ''}`;

  const info = el('div', { class: 'prov-info' },
    el('div', { class: 'prov-name' }, p.label, badge),
    el('div', { class: 'prov-sub muted' }, sub),
  );

  const actions = el('div', { class: 'prov-actions' });
  if (p.kind === 'local') {
    if (!p.preferred) actions.append(btn('Usar local', 'ghost', () => apply({ name: 'local' })));
  } else {
    const input = el('input', {
      class: 'prov-key', type: 'password', autocomplete: 'off',
      placeholder: p.has_key ? '•••••••• salva — cole outra p/ trocar' : 'Cole a API key…',
    });
    const applyBtn = btn(p.enabled ? 'Reaplicar' : 'Aplicar', 'accent', () => {
      const key = input.value.trim();
      if (!key && !p.has_key) { flash('Cole a chave de API primeiro.'); input.focus(); return; }
      apply({ name: p.name, api_key: key || null, enabled: true, preferred: true });
    });
    const row = el('div', { class: 'prov-keyrow' }, input, applyBtn);
    actions.append(row);
    const sub2 = el('div', { class: 'prov-subactions' });
    if (p.enabled) sub2.append(btn('Desativar', 'ghost', () => apply({ name: p.name, enabled: false, preferred: false })));
    if (p.has_key) sub2.append(btn('Remover chave', 'link', () => apply({ name: p.name, clear_key: true, enabled: false, preferred: false })));
    if (sub2.children.length) actions.append(sub2);
  }

  return el('div', { class: 'prov', 'data-pref': p.preferred ? '1' : '0' },
    el('div', { class: 'prov-head' }, mark, info), actions);
}

async function apply(body) {
  if (busy) return;
  busy = true;
  try {
    const r = await api.setProvider(body);
    if (body.name !== 'local' && body.enabled && !body.clear_key) {
      if (r.verified === true) flash(`✓ ${label(body.name)} ativado e verificado.`);
      else if (r.verified === false) flash(`⚠ ${label(body.name)} salvo, mas a chave não verificou (rede offline ou chave inválida).`);
    } else if (body.name === 'local') {
      flash('Usando o modelo local.');
    } else if (body.clear_key) {
      flash('Chave removida.');
    } else {
      flash('Provedor desativado.');
    }
    await renderProviders();
  } catch (e) {
    flash('Falha ao aplicar. Tente de novo.');
  } finally {
    busy = false;
  }
}

/* ---------- helpers ---------- */
function btn(text, kind, onClick) {
  const cls = kind === 'accent' ? 'btn accent' : kind === 'ghost' ? 'btn ghost' : 'prov-linkbtn';
  return el('button', { class: cls, onclick: onClick }, text);
}
function label(name) { return { openai: 'OpenAI', gemini: 'Gemini', grok: 'Grok', deepseek: 'DeepSeek' }[name] || name; }
function flash(msg) {
  const h = byId('prov-help');
  if (!h) return;
  h.textContent = msg;
  h.classList.add('flash');
  setTimeout(() => h.classList.remove('flash'), 1800);
}
