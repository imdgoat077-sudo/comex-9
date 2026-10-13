// Lets the shield page ask the main process to stop the agent (the only thing it can do).
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('comexShield', { stop: () => ipcRenderer.send('agent-shield-stop') });
