// Conexão WebSocket com o backend da Aila (reconecta sozinha).
let ws = null;
let handlers = { onMessage: () => {}, onOpen: () => {}, onClose: () => {} };

export function connectWS(h) {
  handlers = { ...handlers, ...h };
  _open();
}
function _open() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => handlers.onOpen();
  ws.onmessage = (e) => { try { handlers.onMessage(JSON.parse(e.data)); } catch (err) { console.error(err); } };
  ws.onclose = () => { handlers.onClose(); setTimeout(_open, 2000); };
}
export function wsSend(obj) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); }
export const wsReady = () => !!ws && ws.readyState === 1;
