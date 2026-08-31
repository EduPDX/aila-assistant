const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', '..');
const read = (rel) => fs.readFileSync(path.join(root, rel), 'utf8');

test('Electron mantém isolamento e não atualiza código silenciosamente', () => {
  const src = read('desktop/electron/main.js');
  assert.match(src, /contextIsolation:\s*true/);
  assert.match(src, /nodeIntegration:\s*false/);
  assert.match(src, /sandbox:\s*true/);
  assert.match(src, /AILA_AUTO_UPDATE\s*===\s*'1'/);
});

test('ponte do avatar restringe origem e janela remetente', () => {
  const parent = read('ui/js/avatar.js');
  const frame = read('ui/avatar3d.html');
  assert.doesNotMatch(parent, /postMessage\(msg,\s*['"]\*['"]\)/);
  assert.match(parent, /e\.origin\s*!==\s*location\.origin/);
  assert.match(parent, /e\.source\s*!==\s*frame\.contentWindow/);
  assert.doesNotMatch(frame, /body\.report[^\n]+['"]\*['"]/);
  assert.match(frame, /e\.source\s*!==\s*parent/);
});
