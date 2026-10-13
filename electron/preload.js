import { contextBridge, ipcRenderer } from 'electron';

const listen = (channel, callback) => {
  const handler = (_event, data) => callback(data);
  ipcRenderer.on(channel, handler);
  return () => ipcRenderer.removeListener(channel, handler);
};

contextBridge.exposeInMainWorld('nexusNative', {
  isElectron: true,
  platform: process.platform,
  // NOTE: internalToken is strictly omitted from the contextBridge boundary.
  // The renderer NEVER receives the application's reusable internal secret.

  // The browser: the main process owns tabs and groups; the interface renders its state and sends commands.
  browser: {
    getState: () => ipcRenderer.invoke('browser-state'),
    onState: (callback) => listen('browser-state', callback),
    command: (cmd) => ipcRenderer.invoke('browser-command', cmd),
    onUiCommand: (callback) => listen('ui-command', callback),
    setBounds: (bounds) => ipcRenderer.send('tabs-set-bounds', bounds),
    testSendKey: (args) => ipcRenderer.invoke('test-send-key', args), // only answers with COMEX_TEST_HOOKS=1
    popup: {
      show: (payload) => ipcRenderer.send('popup-show', payload),
      hide: () => ipcRenderer.send('popup-hide'),
      onEvent: (callback) => listen('popup-event', callback),
    },
  },

  // Used by the agent backend (through this page) and by the chat: agent tabs and their status.
  tabs: {
    setBounds: (bounds) => ipcRenderer.send('tabs-set-bounds', bounds),
    openAgentTab: (tabId, url, label, groupId) => ipcRenderer.invoke('tabs-open-agent', { tabId, url, label, groupId }),
    getTabInfo: (tabId) => ipcRenderer.invoke('tabs-get-info', tabId),
    requestActivate: (tabId) => ipcRenderer.send('tabs-request-activate', tabId),
    getActiveTarget: () => ipcRenderer.invoke('tabs-get-active-target'),
    setAgentStatus: (tabId, status, step) => ipcRenderer.send('tabs-set-agent-status', tabId, status, step),
    setAgentStep: (tabId, step) => ipcRenderer.send('tabs-set-agent-step', tabId, step),
  },
  cursor: {
    animate: (data) => ipcRenderer.send('cursor-animate', data),
    reset: () => ipcRenderer.send('cursor-reset'),
  },
  agent: {
    run: (payload) => ipcRenderer.invoke('agent-run', payload),
    stop: (taskId) => ipcRenderer.invoke('agent-stop', taskId),
    stream: (payload, onChunk, onError, onEnd) => {
      const streamId = 'stream_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
      const chunkChannel = `agent-stream-chunk:${streamId}`;
      const errorChannel = `agent-stream-error:${streamId}`;
      const endChannel = `agent-stream-end:${streamId}`;

      const handleChunk = (_event, chunk) => onChunk?.(chunk);
      const handleError = (_event, err) => { cleanup(); onError?.(err); };
      const handleEnd = () => { cleanup(); onEnd?.(); };

      const cleanup = () => {
        ipcRenderer.removeListener(chunkChannel, handleChunk);
        ipcRenderer.removeListener(errorChannel, handleError);
        ipcRenderer.removeListener(endChannel, handleEnd);
      };

      ipcRenderer.on(chunkChannel, handleChunk);
      ipcRenderer.on(errorChannel, handleError);
      ipcRenderer.on(endChannel, handleEnd);

      ipcRenderer.invoke('agent-stream-start', { streamId, payload }).catch((err) => {
        cleanup();
        onError?.(err?.message || String(err));
      });

      return () => {
        cleanup();
        ipcRenderer.send('agent-stream-abort', streamId);
      };
    },
  }
});
