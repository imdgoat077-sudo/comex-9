// The agent service the interface talks to. An isolated test instance points this elsewhere (VITE_COMEX_AGENT_URL).
export const AGENT_SERVICE = (import.meta.env.VITE_COMEX_AGENT_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
