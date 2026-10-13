// The popup layer (address-bar suggestions, agent tab cards) only receives what to draw and reports a pick.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('comexPopup', {
  onRender: (callback) => ipcRenderer.on('popup-render', (_event, payload) => callback(payload)),
  pick: (index) => ipcRenderer.send('popup-pick', index),
});
