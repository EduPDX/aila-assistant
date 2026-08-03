// Voz: saída (TTS + lip-sync no avatar) e entrada (microfone + STT).
import { byId } from './dom.js';
import { avatarMouth } from './avatar.js';

let ttsAudio, lipCtx, lipAnalyser, lipBuf;
let _onTranscript = () => {};
export function setTranscriptHandler(fn) { _onTranscript = fn; }

/** Fala um texto: baixa o áudio (Edge-TTS) e move a boca do avatar em sincronia. */
export async function speak(text) {
  try {
    const r = await fetch('/api/voice/speak', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }),
    });
    if (!r.ok) return;
    const blob = await r.blob();
    if (ttsAudio) { try { ttsAudio.pause(); } catch (e) {} }
    ttsAudio = new Audio(URL.createObjectURL(blob));
    lipCtx = lipCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (lipCtx.state === 'suspended') await lipCtx.resume();
    const src = lipCtx.createMediaElementSource(ttsAudio);
    lipAnalyser = lipCtx.createAnalyser(); lipAnalyser.fftSize = 1024;
    lipBuf = new Uint8Array(lipAnalyser.fftSize);
    src.connect(lipAnalyser); lipAnalyser.connect(lipCtx.destination);
    _driveMouth();
    ttsAudio.onended = () => { lipAnalyser = null; avatarMouth(0); };
    await ttsAudio.play();
  } catch (e) { /* voz indisponível: silencioso */ }
}
function _driveMouth() {
  if (!lipAnalyser) return;
  lipAnalyser.getByteTimeDomainData(lipBuf);
  let sum = 0;
  for (let i = 0; i < lipBuf.length; i++) { const v = (lipBuf[i] - 128) / 128; sum += v * v; }
  avatarMouth(Math.min(1, Math.sqrt(sum / lipBuf.length) * 4.5));
  requestAnimationFrame(_driveMouth);
}

// ---------- microfone (STT) ----------
let recording = false, mediaRec = null, micStream = null, audioCtx = null, chunks = [];
export function toggleMic() { recording ? stopRec() : startRec(); }
async function startRec() {
  try { micStream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch (e) { _onTranscript(null, 'sem acesso ao microfone'); return; }
  recording = true; byId('mic').classList.add('rec'); chunks = [];
  mediaRec = new MediaRecorder(micStream);
  mediaRec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  mediaRec.onstop = _onRecStop; mediaRec.start(); _detectSilence();
}
function stopRec() {
  recording = false; byId('mic').classList.remove('rec');
  try { mediaRec && mediaRec.state !== 'inactive' && mediaRec.stop(); } catch (e) {}
  if (audioCtx) { try { audioCtx.close(); } catch (e) {} audioCtx = null; }
  if (micStream) { micStream.getTracks().forEach((t) => t.stop()); micStream = null; }
}
function _detectSilence() {
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const an = audioCtx.createAnalyser(); an.fftSize = 2048;
  audioCtx.createMediaStreamSource(micStream).connect(an);
  const buf = new Uint8Array(an.fftSize); let spoke = false, last = Date.now(), start = Date.now();
  (function loop() {
    if (!recording) return;
    an.getByteTimeDomainData(buf);
    let s = 0; for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; s += v * v; }
    const rms = Math.sqrt(s / buf.length), now = Date.now();
    if (rms > 0.04) { spoke = true; last = now; }
    if ((spoke && now - last > 1200) || now - start > 15000 || (!spoke && now - start > 6000)) {
      if (mediaRec && mediaRec.state !== 'inactive') mediaRec.stop(); return;
    }
    requestAnimationFrame(loop);
  })();
}
async function _onRecStop() {
  if (audioCtx) { try { audioCtx.close(); } catch (e) {} audioCtx = null; }
  if (micStream) { micStream.getTracks().forEach((t) => t.stop()); micStream = null; }
  recording = false; byId('mic').classList.remove('rec');
  if (!chunks.length) return;
  const fd = new FormData(); fd.append('file', new Blob(chunks, { type: 'audio/webm' }), 'fala.webm');
  try {
    const j = await (await fetch('/api/voice/transcribe', { method: 'POST', body: fd })).json();
    if ((j.text || '').trim()) _onTranscript(j.text.trim());
  } catch (e) {}
}
