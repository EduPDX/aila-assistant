// Bridge mínima e segura entre a interface e o Electron.
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('aila', {
  desktop: true,
  version: process.env.npm_package_version || '0.1.0',
});
