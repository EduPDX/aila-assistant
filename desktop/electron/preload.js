// Bridge mínima e segura entre a interface e o Electron.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('aila', {
  desktop: true,
  version: process.env.npm_package_version || '0.1.0',
  // seletor NATIVO de pasta → devolve o caminho absoluto (sem upload). A Aila lê
  // a pasta direto do disco (via file.list/read). Retorna null se cancelar.
  pickFolder: () => ipcRenderer.invoke('aila:pick-folder'),
  pickFile: () => ipcRenderer.invoke('aila:pick-file'),
});
