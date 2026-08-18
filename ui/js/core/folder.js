// Seleção de pasta pelo picker NATIVO (Electron → backend tkinter). Só cai no
// prompt de caminho se NENHUM picker nativo estiver disponível. Se o usuário
// CANCELAR o picker nativo, devolve null — e NÃO abre o prompt (era o bug: cancelar
// mostrava o "caminho da pasta" mesmo assim).
import { api } from './api.js';

export async function pickFolderPath() {
  // 1) Electron (.exe): diálogo nativo
  if (window.aila && window.aila.pickFolder) {
    try { const p = await window.aila.pickFolder(); return (p || '').trim() || null; }
    catch (e) { /* sem bridge → tenta o backend */ }
  }
  // 2) do FONTE: o backend abre o explorador nativo (tkinter). Se rodou (mesmo
  //    cancelado), o resultado é FINAL — não cai no prompt.
  try {
    const r = await api.pickFolder();
    if (r && r.native !== false) return (r.path || '').trim() || null;
  } catch (e) { /* endpoint indisponível → prompt */ }
  // 3) nenhum picker nativo → pede o caminho
  const p = window.prompt('Caminho da pasta (a Aila lê direto do disco):');
  return (p || '').trim() || null;
}
