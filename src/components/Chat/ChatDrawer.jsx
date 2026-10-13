import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  X, ArrowUp, Square, Copy, Check, ChevronRight, ChevronDown, Brain, ArrowLeft,
  SquarePen, RefreshCw, Trash2, Plus, Circle, Minus, ExternalLink, Users, User, CornerDownLeft, Plane, Search, FileText, Scale, Newspaper, History
} from 'lucide-react';
import MarkdownRenderer, { hasMarkdownTable } from './MarkdownRenderer';
import { OrbitMark, ShimmerLabel, SwarmOrbit, SwarmStage } from './LiveStage';
import { runSwarm, stopSwarmRun, respondToSwarmApproval } from '../../agents/orchestratorClient';
import './ChatDrawer.css';
import { AGENT_SERVICE } from '../../config';

function formatDuration(durationMs) {
  const totalSeconds = Math.max(0, durationMs) / 1000;
  if (totalSeconds < 10) return `${totalSeconds.toFixed(1)}s`;
  if (totalSeconds < 60) return `${Math.round(totalSeconds)}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.round(totalSeconds % 60);
  return `${minutes}m ${seconds}s`;
}

function nowTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Re-renders every second while `active`, for live elapsed timers.
function useNow(active) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

export const DRAWER_WIDTH = 440;
const DRAWER_MIN = 360;
// Wide enough for a 4-5 column comparison table, while leaving the page usable.
const wideDrawerWidth = () => Math.min(760, Math.round(window.innerWidth * 0.55));
const maxDrawerWidth = () => Math.max(DRAWER_MIN, Math.min(1000, window.innerWidth - 420));

// Tab markers: the page overlay and the tab-strip card follow these. No-ops outside Electron.
const tabsBridge = () => (typeof window !== 'undefined' ? window.nexusNative?.tabs : undefined);
const markAgentStep = (tabId, step) => { if (tabId && step) tabsBridge()?.setAgentStep?.(tabId, step); };
const markAgentTab = (tabId, status, step) => { if (tabId) tabsBridge()?.setAgentStatus?.(tabId, status, step); };

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled', 'blocked']);

// How a multi-agent run shows its progress; chosen in the Memory view, kept per person.
const SWARM_ANIMATION_KEY = 'comex.swarmAnimation';
const SWARM_ANIMATIONS = [
  { key: 'orbit', label: 'Orbit', hint: 'One dot per agent. It circles while the agent works and settles when it finishes.' },
  { key: 'scene', label: 'Scene', hint: 'A planner, one window per agent and a result node, drawn out in full.' },
];
const readSwarmAnimation = () => {
  try { return localStorage.getItem(SWARM_ANIMATION_KEY) === 'scene' ? 'scene' : 'orbit'; } catch { return 'orbit'; }
};
// Two agents working and one finished, for the previews in the Memory view
const DEMO_AGENTS = [
  { status: 'completed', stepCount: 4 }, { status: 'running', stepCount: 2 }, { status: 'running', stepCount: 1 },
];

function StatusIcon({ status, live = false }) {
  if (status === 'running') return <span className={`status-dot status-running${live ? ' is-live' : ''}`} role="img" aria-label="Running" />;
  if (status === 'completed') return <Check size={14} className="status-icon status-ok" aria-label="Done" />;
  if (status === 'failed' || status === 'blocked') return <X size={14} className="status-icon status-err" aria-label="Failed" />;
  if (status === 'cancelled') return <Minus size={14} className="status-icon status-muted" aria-label="Stopped" />;
  return <Circle size={14} strokeWidth={1.75} className="status-icon status-muted" aria-label="Queued" />;
}

const RUN_PHASE_LABEL = {
  planning: 'Splitting the task between agents',
  working: 'Agents are working',
  comparing: 'Combining the results',
  approval: 'Waiting for your approval',
  acting: 'Carrying out the approved step',
  done: 'Done',
  failed: "The run didn't finish",
  stopped: 'Stopped',
};

// What an agent row says when the agent has not reported a step of its own yet.
function agentStepText(agent) {
  if (agent.status === 'queued') return 'Waiting for a free slot';
  if (agent.status === 'running') return agent.currentStep || 'Opening its tab';
  return null;
}

// Placeholder rows shaped like the agent list, shown while the plan is being made.
function SkeletonRows({ count = 2 }) {
  return (
    <ol className="run-agents" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <li key={i} className="run-agent skeleton-row">
          <span className="skeleton skeleton-dot" />
          <span className="skeleton-lines">
            <span className="skeleton skeleton-line" style={{ width: `${78 - i * 14}%` }} />
            <span className="skeleton skeleton-line skeleton-line-sm" style={{ width: `${46 - i * 8}%` }} />
          </span>
        </li>
      ))}
    </ol>
  );
}

function RunPanel({ run, onOpenTab, animation = 'orbit' }) {
  const isLive = !['done', 'failed', 'stopped'].includes(run.phase);
  const now = useNow(isLive);
  const [expanded, setExpanded] = useState(true);
  const elapsed = (run.endedAt || now) - run.startedAt;
  const working = run.agents.filter((a) => a.status === 'running').length;
  const finished = run.agents.filter((a) => a.status === 'completed').length;
  const n = run.agents.length;
  let headline = RUN_PHASE_LABEL[run.phase];
  if (run.phase === 'working' && n > 0) {
    // between the last agent finishing and the results being combined nobody is working, so say what has happened
    headline = working === 0 && finished > 0 ? `${finished} of ${n} agents finished` : n === 1 ? 'Agent is working' : `${working} of ${n} agents working`;
  }
  if (run.phase === 'done' && n > 0) {
    headline = n === 1
      ? (finished ? 'Agent finished' : 'Agent stopped')
      : finished === n ? `${n} agents finished` : `${finished} of ${n} agents finished`;
  }

  const [settling, setSettling] = useState(false); // the stage stays up briefly after the last agent so the result node settles
  useEffect(() => {
    if (run.phase !== 'done') return undefined;
    setExpanded(false);
    setSettling(true);
    const t = setTimeout(() => setSettling(false), 1700);
    return () => clearTimeout(t);
  }, [run.phase]);

  return (
    <section className={`run-panel run-${run.phase}`} aria-label="Multi-agent run" aria-live="polite">
      {animation === 'scene' && (isLive || settling) && <SwarmStage agents={run.agents} phase={run.phase} />}
      <button type="button" className="run-header" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
        {animation === 'orbit' && (isLive || settling)
          ? <SwarmOrbit agents={run.agents} phase={run.phase} />
          : <StatusIcon status={isLive ? 'running' : run.phase === 'done' ? 'completed' : run.phase === 'stopped' ? 'cancelled' : 'failed'} />}
        {animation === 'orbit' && isLive
          ? <ShimmerLabel className="run-headline" text={headline} />
          : <span className="run-headline">{headline}</span>}
        <span className="run-elapsed">{formatDuration(elapsed)}</span>
        {expanded ? <ChevronDown size={14} className="run-chevron" /> : <ChevronRight size={14} className="run-chevron" />}
      </button>

      {expanded && run.phase === 'planning' && run.agents.length === 0 && <SkeletonRows />}

      {expanded && run.agents.length > 0 && (
        <ol className="run-agents">
          {run.agents.map((agent) => {
            const agentElapsed = agent.startedAt ? (agent.endedAt || now) - agent.startedAt : null;
            const canOpen = Boolean(agent.tabId && onOpenTab);
            return (
              <li key={agent.taskId} className={`run-agent agent-${agent.status}`}>
                <StatusIcon status={agent.status} />
                <div className="run-agent-body">
                  <span className="run-agent-task">{agent.description}</span>
                  {agentStepText(agent) && (
                    <span className="run-agent-step" key={agentStepText(agent)}>{agentStepText(agent)}</span>
                  )}
                  {agent.error && <span className="run-agent-error">{agent.error}</span>}
                </div>
                {agentElapsed != null && <span className="run-agent-time">{formatDuration(agentElapsed)}</span>}
                {canOpen && (
                  <button
                    type="button"
                    className="run-agent-open"
                    onClick={() => onOpenTab(agent.tabId)}
                    aria-label={`Watch this agent's tab: ${agent.description}`}
                    title="Watch this agent's tab"
                  >
                    <ExternalLink size={13} />
                  </button>
                )}
              </li>
            );
          })}
          {run.phase === 'comparing' && (
            <li className="run-agent agent-running">
              <StatusIcon status="running" />
              <div className="run-agent-body">
                <span className="run-agent-task">Comparing findings</span>
                <span className="run-agent-step">Removing duplicates and writing one answer</span>
              </div>
            </li>
          )}
        </ol>
      )}
    </section>
  );
}

// ── Chats per tab group ───────────────────────────────────────────────────────────────────────────
// Every tab belongs to a group (see App.jsx); a group has one chat, stored by the backend (SQLite), so it survives
// closing the drawer and restarting the app. The drawer shows the chat of the active tab's group.
const EMPTY_THREAD = { conversationId: null, messages: [], status: 'idle' };
const groupIdOf = (tab) => (tab ? tab.groupId || `grp-${tab.id}` : null);

async function postJson(path, body) {
  const r = await fetch(`${AGENT_SERVICE}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} answered ${r.status}`);
  return r.json();
}

function storedTime(seconds) {
  return seconds ? new Date(seconds * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
}

// A stored message (backend) as the drawer draws it
function toUiMessage(m) {
  if (m.role === 'user') return { id: m.id, sender: 'user', text: m.content, timestamp: storedTime(m.created_at), restored: true };
  const meta = m.meta || {};
  const status = meta.status || 'completed';
  const ui = {
    id: m.id,
    sender: 'assistant',
    text: m.content,
    content: m.content,
    status,
    failed: status === 'failed',
    statusLabel: status === 'failed' ? "Couldn't finish" : status === 'stopped' ? 'Stopped' : (meta.is_conversational ? '' : 'Done'),
    is_conversational: Boolean(meta.is_conversational),
    activity: (meta.activity || []).map((a, i) => ({ id: `${m.id}_${i}`, ...a })),
    task_outcome: meta.task_outcome || null,
    durationMs: meta.durationMs ?? meta.duration_ms ?? null,
    timestamp: storedTime(m.created_at),
    restored: true,
  };
  if (meta.helpers?.length) ui.helpers = meta.helpers;
  if (m.kind === 'run') {
    const startedAt = (m.created_at || 0) * 1000 - (meta.duration_ms || 0);
    ui.kind = 'run';
    ui.run = {
      phase: status === 'completed' ? 'done' : status === 'stopped' ? 'stopped' : 'failed',
      startedAt,
      endedAt: (m.created_at || 0) * 1000,
      agents: (meta.run?.agents || []).map((a) => ({ ...a, status: a.status === 'running' ? 'cancelled' : a.status })),
    };
  }
  return ui;
}

// An agent that was never reported finished must not be shown as working once the run is over. The single agent
// stops its helpers when it answers, so they settle as stopped; a swarm run only returns after every worker ended.
function settleAgents(agents, status = 'cancelled') {
  return agents?.map((a) => (a.status === 'running' || a.status === 'queued' ? { ...a, status, currentStep: null, endedAt: Date.now() } : a));
}

// Helper agents started by the single agent, shaped like a multi-agent run for RunPanel
function helperRun(helpers) {
  const running = helpers.some((h) => h.status === 'running' || h.status === 'queued');
  return {
    phase: running ? 'working' : 'done',
    startedAt: Math.min(...helpers.map((h) => h.startedAt || Date.now())),
    endedAt: running ? null : Math.max(...helpers.map((h) => h.endedAt || Date.now())),
    agents: helpers,
  };
}

const SUGGESTIONS = {
  single: [
    { icon: Plane, text: 'Find the cheapest direct flight from Bengaluru to Delhi next Friday' },
    { icon: Search, text: 'Check train tickets from Chennai to Bengaluru this weekend' },
    { icon: FileText, text: 'Summarize this page' },
  ],
  multi: [
    { icon: Plane, text: 'Compare flights from Bengaluru to Delhi on three booking sites' },
    { icon: Scale, text: 'Compare the best headphones under ₹3,000 on Amazon and Flipkart' },
    { icon: Newspaper, text: 'Research the pros and cons of Rust vs Go for a web backend' },
  ],
};

function EmptyState({ isMultiAgentMode, onPick }) {
  const items = isMultiAgentMode ? SUGGESTIONS.multi : SUGGESTIONS.single;
  return (
    <div className="chat-empty">
      <span className="chat-empty-mark" aria-hidden="true" />
      <h2 className="chat-empty-title">{isMultiAgentMode ? 'What should the agents work on?' : 'What should Comex do?'}</h2>
      <p className="chat-empty-text">
        {isMultiAgentMode
          ? 'Up to four agents each open a tab, work in parallel, and the results come back as one answer.'
          : 'Comex works in the tab you have open: it reads the page, searches, clicks and fills in forms. It asks before anything is booked or sent.'}
      </p>
      <ul className="chat-suggestions">
        {items.map(({ icon: Icon, text }) => (
          <li key={text}>
            <button type="button" className="chat-suggestion" onClick={() => onPick(text)}>
              <Icon size={15} className="chat-suggestion-icon" aria-hidden="true" />
              <span>{text}</span>
              <CornerDownLeft size={13} className="chat-suggestion-go" aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ChatDrawer({
  isOpen,
  onClose,
  activeTab,
  tabs = [],
  onSelectTab,
  onOpenLink,
  onCloseTabs,
  onGroupTitle,
  onGroupActivity,
  width = DRAWER_WIDTH,
  onWidthChange,
}) {
  const [isMultiAgentMode, setIsMultiAgentMode] = useState(false);
  // groupId -> { conversationId, messages, status }. The visible chat is the active tab's group's.
  const [threads, setThreads] = useState({});
  const threadsRef = useRef(threads);
  threadsRef.current = threads;
  const groupId = groupIdOf(activeTab);
  const thread = (groupId && threads[groupId]) || EMPTY_THREAD;
  const messages = thread.messages;
  const conversationId = thread.conversationId;
  // Updates one group's messages, whichever group is on screen: a run keeps writing into the chat it started in.
  const setMessagesFor = useCallback((gid) => (updater) => setThreads((prev) => {
    const t = prev[gid] || EMPTY_THREAD;
    const next = typeof updater === 'function' ? updater(t.messages) : updater;
    return { ...prev, [gid]: { ...t, messages: next } };
  }), []);
  const setMessages = setMessagesFor(groupId);
  // Runs are per tab group: each group can have one task running while other groups run theirs.
  const runsRef = useRef({}); // groupId -> live run { mode, taskId, controller, runId, messageId, tabId, stopping }
  const [runs, setRuns] = useState({}); // groupId -> { mode, startedAt }, what the interface draws
  const beginRun = (gid, run) => {
    runsRef.current[gid] = run;
    setRuns((prev) => ({ ...prev, [gid]: { mode: run.mode, startedAt: Date.now() } }));
    onGroupActivity?.(gid, { state: 'working', mode: run.mode, since: Date.now() });
  };
  const endRun = (gid, state) => {
    delete runsRef.current[gid];
    setRuns((prev) => { const next = { ...prev }; delete next[gid]; return next; });
    onGroupActivity?.(gid, { state, since: Date.now() });
  };
  const isTyping = Boolean(groupId && runs[groupId]); // a task is running in the chat on screen
  const [historyList, setHistoryList] = useState(null); // earlier conversations, for the history view
  const [input, setInput] = useState('');
  const [expandedActivity, setExpandedActivity] = useState({});
  const [copiedId, setCopiedId] = useState(null);
  const [activeDrawerTab, setActiveDrawerTab] = useState('chat'); // 'chat' | 'brain' | 'history'
  const [brainSection, setBrainSection] = useState('user_memory'); // 'user_memory' | 'skills' | 'reflections' | 'adapters' | 'settings'
  const [swarmAnimation, setSwarmAnimation] = useState(readSwarmAnimation);
  const chooseSwarmAnimation = (key) => {
    setSwarmAnimation(key);
    try { localStorage.setItem(SWARM_ANIMATION_KEY, key); } catch { /* the choice just will not be remembered */ }
  };
  const [userMemories, setUserMemories] = useState([]);
  const [skills, setSkills] = useState([]);
  const [reflections, setReflections] = useState([]);
  const [adapters, setAdapters] = useState([]);
  const [lessons, setLessons] = useState([]);
  const [memoryStats, setMemoryStats] = useState(null);
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [newCategory, setNewCategory] = useState('preference');
  const [isRefreshingBrain, setIsRefreshingBrain] = useState(false);
  const userSizedRef = useRef(false);
  const latestTabRef = useRef(activeTab);
  latestTabRef.current = activeTab;
  const messagesRef = useRef(null);
  const inputRef = useRef(null);

  // Load the active group's chat from the backend (once per group). The tab joins its group there, so the agent may
  // use it. If the backend is down the chat still works, it is just not stored.
  const loadThread = useCallback(async (gid, tab) => {
    if (!gid) return null;
    setThreads((prev) => ({ ...prev, [gid]: { ...(prev[gid] || EMPTY_THREAD), status: 'loading' } }));
    try {
      const data = await postJson('/chat/groups/ensure', {
        group_id: gid, tab_id: tab?.id || null, role: tab?.agentLabel ? 'agent' : 'main',
      });
      setThreads((prev) => {
        const local = prev[gid]?.messages || [];
        return {
          ...prev,
          [gid]: {
            conversationId: data.conversation_id,
            // stored turns first; anything sent before the load finished is newer and follows them
            messages: [...(data.messages || []).map(toUiMessage), ...local.filter((m) => !m.restored)],
            status: 'ready',
          },
        };
      });
      return data.conversation_id;
    } catch {
      setThreads((prev) => ({ ...prev, [gid]: { ...(prev[gid] || EMPTY_THREAD), status: 'offline' } }));
      return null;
    }
  }, []);

  useEffect(() => {
    if (!groupId) return;
    const t = threadsRef.current[groupId];
    if (!t || t.status === 'idle') loadThread(groupId, activeTab);
  }, [groupId, activeTab?.id, loadThread]);

  // The group's chip in the tab strip shows the chat's first request
  const firstUserText = messages.find((m) => m.sender === 'user')?.text;
  useEffect(() => {
    if (groupId && firstUserText) onGroupTitle?.(groupId, firstUserText.replace(/\s+/g, ' ').slice(0, 40));
  }, [groupId, firstUserText]);

  // Grow the composer with its content, up to the CSS max-height.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [input]);

  // Load Brain memory data from Python Agent service
  const fetchBrainData = async () => {
    setIsRefreshingBrain(true);
    try {
      const [ovRes, memRes, sklRes, refRes, adpRes, lesRes] = await Promise.all([
        fetch(`${AGENT_SERVICE}/agent/memory/overview`).then(r => r.ok ? r.json() : null),
        fetch(`${AGENT_SERVICE}/agent/user/memory`).then(r => r.ok ? r.json() : []),
        fetch(`${AGENT_SERVICE}/agent/skills?limit=30`).then(r => r.ok ? r.json() : []),
        fetch(`${AGENT_SERVICE}/agent/reflections?limit=20`).then(r => r.ok ? r.json() : []),
        fetch(`${AGENT_SERVICE}/agent/adapters`).then(r => r.ok ? r.json() : []),
        fetch(`${AGENT_SERVICE}/agent/lessons`).then(r => r.ok ? r.json() : []).catch(() => []),
      ]);
      if (ovRes) setMemoryStats(ovRes.stats);
      if (Array.isArray(memRes)) setUserMemories(memRes);
      if (Array.isArray(sklRes)) setSkills(sklRes);
      if (Array.isArray(refRes)) setReflections(refRes);
      if (Array.isArray(adpRes)) setAdapters(adpRes);
      if (Array.isArray(lesRes)) setLessons(lesRes);
    } catch (e) {
      console.warn('Could not fetch brain data:', e);
    } finally {
      setIsRefreshingBrain(false);
    }
  };

  useEffect(() => {
    if (activeDrawerTab === 'brain') {
      fetchBrainData();
    }
  }, [activeDrawerTab]);

  const handleDeleteMemory = async (key) => {
    try {
      await fetch(`${AGENT_SERVICE}/agent/user/memory/${encodeURIComponent(key)}`, { method: 'DELETE' });
      setUserMemories(prev => prev.filter(m => m.key !== key));
    } catch (e) {
      console.warn('Failed to delete memory:', e);
    }
  };

  const handleDeleteSkill = async (id) => {
    try {
      await fetch(`${AGENT_SERVICE}/agent/skills/${encodeURIComponent(id)}`, { method: 'DELETE' });
      setSkills(prev => prev.filter(s => s.id !== id));
    } catch (e) {
      console.warn('Failed to delete skill:', e);
    }
  };

  const handleDeleteLesson = async (id) => {
    try {
      await fetch(`${AGENT_SERVICE}/agent/lessons/${encodeURIComponent(id)}`, { method: 'DELETE' });
      setLessons(prev => prev.filter(l => l.id !== id));
    } catch (e) {
      console.warn('Failed to delete lesson:', e);
    }
  };

  const handleDeleteAdapter = async (id) => {
    try {
      await fetch(`${AGENT_SERVICE}/agent/adapters/${encodeURIComponent(id)}`, { method: 'DELETE' });
      setAdapters(prev => prev.filter(a => a.id !== id));
    } catch (e) {
      console.warn('Failed to delete adapter:', e);
    }
  };

  const handleConsolidateSkills = async () => {
    try {
      setIsRefreshingBrain(true);
      await fetch(`${AGENT_SERVICE}/agent/skills/consolidate`, { method: 'POST' });
      await fetchBrainData();
    } catch (e) {
      console.warn('Failed to consolidate skills:', e);
    } finally {
      setIsRefreshingBrain(false);
    }
  };

  const handleAddMemory = async (e) => {
    e.preventDefault();
    if (!newKey.trim() || !newValue.trim()) return;
    try {
      await fetch(`${AGENT_SERVICE}/agent/user/memory`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: newKey.trim(), value: newValue.trim(), category: newCategory })
      });
      setNewKey('');
      setNewValue('');
      fetchBrainData();
    } catch (e) {
      console.warn('Failed to add user memory:', e);
    }
  };

  // The Stop button on the page shield asks for the running agent(s) to stop, same as the drawer's Stop.
  const stopRequestRef = useRef(() => {});
  stopRequestRef.current = () => { const gid = groupIdOf(latestTabRef.current); if (runsRef.current[gid]) stopRun(gid); };
  useEffect(() => {
    const onStop = () => stopRequestRef.current();
    window.addEventListener('comex-agent-stop', onStop);
    return () => window.removeEventListener('comex-agent-stop', onStop);
  }, []);

  // While the single agent runs, mirror its current step onto the tab it is driving.
  useEffect(() => {
    Object.entries(runsRef.current).forEach(([gid, run]) => {
      if (run.mode !== 'single' || !run.tabId) return;
      const label = threads[gid]?.messages.find((m) => m.id === run.messageId)?.statusLabel;
      if (label && label !== run.lastLabel) { run.lastLabel = label; markAgentStep(run.tabId, label); }
    });
  }, [threads]);

  // Widen the drawer while the conversation holds a table; back to normal for a new chat.
  // A width the user dragged to always wins.
  const conversationHasTable = messages.some((m) => m.sender === 'assistant' && hasMarkdownTable(m.text || m.content));
  useEffect(() => {
    if (userSizedRef.current || !onWidthChange) return;
    onWidthChange(conversationHasTable ? Math.max(DRAWER_WIDTH, wideDrawerWidth()) : DRAWER_WIDTH);
  }, [conversationHasTable]);

  const startResize = (event) => {
    if (event.button !== 0 || !onWidthChange) return;
    event.preventDefault();
    const handle = event.currentTarget;
    handle.setPointerCapture(event.pointerId);
    document.body.classList.add('drawer-resizing');
    const onMove = (e) => {
      userSizedRef.current = true;
      onWidthChange(Math.round(Math.min(maxDrawerWidth(), Math.max(DRAWER_MIN, window.innerWidth - e.clientX))));
    };
    const onUp = () => {
      document.body.classList.remove('drawer-resizing');
      handle.removeEventListener('pointermove', onMove);
      handle.removeEventListener('pointerup', onUp);
      handle.removeEventListener('pointercancel', onUp);
    };
    handle.addEventListener('pointermove', onMove);
    handle.addEventListener('pointerup', onUp);
    handle.addEventListener('pointercancel', onUp);
  };

  const resetWidth = () => {
    userSizedRef.current = false;
    onWidthChange?.(conversationHasTable ? Math.max(DRAWER_WIDTH, wideDrawerWidth()) : DRAWER_WIDTH);
  };

  const nudgeWidth = (event) => {
    if (!onWidthChange || (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight')) return;
    event.preventDefault();
    userSizedRef.current = true;
    const step = event.key === 'ArrowLeft' ? 24 : -24;
    onWidthChange(Math.min(maxDrawerWidth(), Math.max(DRAWER_MIN, width + step)));
  };

  // Follow the conversation only when something new is there to read: a new message (the user's send and the
  // agent's reply card), an agent window joining the run (the card is still being set up), or the final answer.
  // Step progress rewrites `messages` constantly; scrolling on that dragged the view to the bottom while the
  // user was reading further up.
  const lastMessage = messages[messages.length - 1];
  const answerLength = lastMessage?.sender === 'assistant' ? (lastMessage.text || lastMessage.content || '').length : 0;
  const runAgentCount = lastMessage?.run?.agents?.length || 0;
  // Scroll the container to its end rather than scrolling a marker into view: the conversation has bottom padding
  // so the last lines can rise above the glass composer, and a marker would leave them underneath it.
  useEffect(() => {
    const el = messagesRef.current;
    el?.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [messages.length, runAgentCount, answerLength, activeDrawerTab]);

  // Receive prompts submitted from the Comet-style landing page.
  useEffect(() => {
    const handleLandingPrompt = (event) => {
      const prompt = event.detail?.prompt?.trim();
      const { intent, mode } = event.detail || {};
      if (mode) setIsMultiAgentMode(mode === 'multi');
      if (prompt) handleSend(prompt, intent, mode);
    };

    window.addEventListener('comex-landing-prompt', handleLandingPrompt);
    return () => window.removeEventListener('comex-landing-prompt', handleLandingPrompt);
  }, [activeTab?.id, activeTab?.url, isMultiAgentMode]);

  // Single Agent Direct Automation with Live Streaming Event Stream
  const executeSingleAgentAction = async (gid, text, taskId, controller, intent, messageId, conversationOptions = {}) => {
    const setMessages = setMessagesFor(gid);
    try {
      let buffer = '';
      let outcome = { status: 'completed', text: '', durationMs: null, task_outcome: null };

      const processChunk = (chunkText) => {
        buffer += chunkText;
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep partial line in buffer

        let currentEventType = 'message';

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i].trim();
          if (!line) continue;

          if (line.startsWith('event:')) {
            currentEventType = line.replace(/^event:\s*/, '');
          } else if (line.startsWith('data:')) {
            const dataStr = line.replace(/^data:\s*/, '');
            try {
              const data = JSON.parse(dataStr);

              // Synchronously update outcome outside React's batched state updater
              if (currentEventType === 'done' || currentEventType === 'completed' || data.type === 'result' || data.type === 'chat' || data.done) {
                const isFailed = data.stopped ? false : (data.success === false || Boolean(data.error));
                if (data.agent_tab_ids) { outcome.agentTabIds = data.agent_tab_ids; outcome.resultTabId = data.result_tab_id || null; }
                const isConv = Boolean(!isFailed && (data.is_conversational || data.type === 'chat'));
                const errorText = data.error || data.metadata?.error;
                const rawContent = data.content || data.text || data.result;
                const fallbackSuccessText = isConv ? 'Hi. What would you like to do?' : 'Done.';
                const finalContent = isFailed
                  ? (errorText || rawContent || outcome.content || outcome.text || 'The agent could not complete the task.')
                  : (rawContent || outcome.content || outcome.text || fallbackSuccessText);

                outcome = {
                  agentTabIds: outcome.agentTabIds,
                  resultTabId: outcome.resultTabId,
                  status: data.stopped ? 'stopped' : isFailed ? 'failed' : 'completed',
                  text: finalContent,
                  content: finalContent,
                  durationMs: data.durationMs || outcome.durationMs,
                  is_conversational: isConv,
                  fast_path: Boolean(!isFailed && (data.fast_path || outcome.fast_path)),
                  adapter_name: isFailed ? null : (data.adapter_name || outcome.adapter_name),
                  task_outcome: isFailed ? null : (data.metadata?.task_outcome || data.task_outcome || outcome.task_outcome || null)
                };
              }

              if (currentEventType === 'tab_switched' && data.tab_id && runsRef.current[gid]) {
                const run = runsRef.current[gid];
                if (run.tabId && run.tabId !== data.tab_id) markAgentTab(run.tabId, 'idle');
                run.tabId = data.tab_id;
                markAgentTab(data.tab_id, 'working', 'Working in this tab');
              }

              setMessages((prev) => prev.map((msg) => {
                if (msg.id !== messageId) return msg;

                const curActivity = [...(msg.activity || [])];

                if (currentEventType === 'thinking') {
                  return {
                    ...msg,
                    statusLabel: data.detail || 'Reading your request',
                    thinking: data.detail
                  };
                }

                if (currentEventType === 'planning') {
                  return {
                    ...msg,
                    statusLabel: data.detail || 'Working out the next step'
                  };
                }

                if (currentEventType.startsWith('helper_')) {
                  const helpers = [...(msg.helpers || [])];
                  const idx = helpers.findIndex((h) => h.taskId === data.agent_id);
                  const base = idx >= 0 ? helpers[idx] : {
                    taskId: data.agent_id, description: data.description, status: 'running', startedAt: Date.now(),
                  };
                  let next = { ...base, tabId: data.tab_id || base.tabId };
                  if (currentEventType === 'helper_progress') { next.currentStep = data.label; next.stepCount = (next.stepCount || 0) + 1; markAgentStep(data.tab_id || base.tabId, data.label); }
                  if (currentEventType === 'helper_finished') {
                    next = { ...next, status: data.status, endedAt: Date.now(), currentStep: null,
                      error: data.status === 'completed' ? null : data.error };
                  }
                  if (idx >= 0) helpers[idx] = next; else helpers.push(next);
                  return { ...msg, helpers };
                }

                if (currentEventType === 'step') {
                  const existingIdx = curActivity.findIndex(a => a.step === data.step);
                  if (existingIdx >= 0) {
                    curActivity[existingIdx] = { ...curActivity[existingIdx], ...data };
                  } else {
                    curActivity.push({
                      id: `step_${data.step}_${Date.now()}`,
                      step: data.step,
                      tool: data.tool,
                      label: data.label,
                      status: 'running',
                      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                    });
                  }
                  return {
                    ...msg,
                    activity: curActivity,
                    statusLabel: data.label
                  };
                }

                if (currentEventType === 'step_done') {
                  const existingIdx = curActivity.findIndex(a => a.step === data.step);
                  if (existingIdx >= 0) {
                    curActivity[existingIdx] = {
                      ...curActivity[existingIdx],
                      status: data.success ? 'done' : 'failed'
                    };
                  }
                  // The step is over; until the next one starts the model is choosing what to do.
                  return {
                    ...msg,
                    activity: curActivity,
                    statusLabel: 'Working out the next step'
                  };
                }

                if (currentEventType === 'done' || currentEventType === 'completed' || data.type === 'result' || data.type === 'chat' || data.done) {
                  const finalContent = outcome.content || outcome.text;
                  const isConv = outcome.is_conversational;
                  const statusLbl = outcome.status === 'failed'
                    ? "Couldn't finish"
                    : (outcome.status === 'stopped'
                      ? 'Stopped'
                      : (outcome.fast_path ? 'Used a saved shortcut' : (isConv ? '' : 'Done')));
                  return {
                    ...msg,
                    helpers: settleAgents(msg.helpers),
                    text: finalContent,
                    content: finalContent,
                    status: outcome.status,
                    statusLabel: statusLbl,
                    is_conversational: isConv,
                    fast_path: outcome.fast_path,
                    adapter_name: outcome.adapter_name,
                    task_outcome: outcome.task_outcome,
                    isStreaming: false
                  };
                }

                return msg;
              }));
            } catch (je) {
              console.warn('Error parsing SSE event:', je);
            }
          }
        }
      };

      if (window.nexusNative?.agent?.stream) {
        await new Promise((resolve, reject) => {
          const unsubscribe = window.nexusNative.agent.stream(
            {
              task: text,
              taskId,
              tabId: 'active_tab',
              url: activeTab?.url || '',
              conversation_id: conversationOptions?.conversation_id,
              group_id: conversationOptions?.group_id,
              ui_tab_id: conversationOptions?.ui_tab_id,
              messages: conversationOptions?.messages,
              task_context: conversationOptions?.task_context,
              ...(intent ? { intent } : {})
            },
            (chunk) => processChunk(chunk),
            (err) => reject(new Error(err)),
            () => resolve()
          );
          controller.signal.addEventListener('abort', () => {
            unsubscribe();
            resolve();
          });
        });
        return outcome;
      }

      // Non-electron web fallback
      const response = await fetch(`${AGENT_SERVICE}/agent/run/stream`, {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task: text,
          taskId,
          tabId: 'active_tab',
          url: activeTab?.url || '',
          conversation_id: conversationOptions?.conversation_id,
          group_id: conversationOptions?.group_id,
          ui_tab_id: conversationOptions?.ui_tab_id,
          messages: conversationOptions?.messages,
          task_context: conversationOptions?.task_context,
          ...(intent ? { intent } : {})
        })
      });

      if (!response.ok || !response.body) {
        throw new Error(`Agent service responded with status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        processChunk(decoder.decode(value, { stream: true }));
      }

      return outcome;
    } catch (err) {
      if (err.name === 'AbortError') return { status: 'stopped', text: 'The task was stopped by the user.' };
      return { status: 'failed', text: "Can't reach the Comex agent service at " + AGENT_SERVICE.replace(/^https?:\/\//, '') + ". Start it with `python agent_service.py`, then try again." };
    }
  };

  const stopRun = (gid) => (runsRef.current[gid]?.mode === 'multi' ? stopSwarm(gid) : stopSingleAgent(gid));

  const stopSingleAgent = async (gid) => {
    const active = runsRef.current[gid];
    if (!active || active.stopping) return;
    const setMessages = setMessagesFor(gid);

    active.stopping = true;
    setMessages((prev) => prev.map((message) => message.id === active.messageId ? {
      ...message,
      statusLabel: 'Stopping the agent',
    } : message));

    active.controller.abort();
    try {
      if (window.nexusNative?.agent?.stop) {
        await window.nexusNative.agent.stop(active.taskId);
      } else {
        await fetch(`${AGENT_SERVICE}/agent/stop`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ taskId: active.taskId }),
        });
      }
    } catch (err) {
      console.warn('Agent cancellation request failed:', err);
    }
  };

  const respondToApproval = async (messageId, runId, approved) => {
    setMessages((prev) => prev.map((m) => m.id === messageId && m.approval
      ? { ...m, approval: { ...m.approval, state: approved ? 'approved' : 'declined' } }
      : m));
    try {
      await respondToSwarmApproval(runId, approved);
    } catch (err) {
      console.warn('Approval response failed:', err);
    }
  };

  const stopSwarm = async (gid) => {
    const active = runsRef.current[gid];
    if (!active || active.stopping) return;

    active.stopping = true;
    active.controller.abort();
    try {
      await stopSwarmRun(active.runId);
    } catch (err) {
      console.warn('Swarm cancellation request failed:', err);
    }
  };

  // After a run: close the agent tabs that are no longer needed and show the one the answer points at.
  // Tabs stay open when the run failed or was stopped, so their pages can still be looked at.
  const tidyAgentTabs = (agentTabIds, resultTabId) => {
    if (!agentTabIds?.length && !resultTabId) return;
    setTimeout(() => onCloseTabs?.(agentTabIds || [], resultTabId || null), 1400);
  };

  const runMultiAgent = async (gid, text, conversation) => {
    const setMessages = setMessagesFor(gid);
    const controller = new AbortController();
    let finalState = 'done';
    beginRun(gid, { mode: 'multi', controller, runId: null, stopping: false });
    const messageId = `a_run_${Date.now()}`;
    setMessages((prev) => [...prev, {
      id: messageId,
      sender: 'assistant',
      kind: 'run',
      text: '',
      timestamp: nowTime(),
      run: { phase: 'planning', startedAt: Date.now(), endedAt: null, agents: [] },
    }]);

    const updateMessage = (fn) => setMessages((prev) => prev.map((m) => (m.id === messageId ? fn(m) : m)));
    const updateRun = (fn) => updateMessage((m) => ({ ...m, run: fn(m.run) }));

    const tabByTask = {};
    const liveAgentTabs = new Set(); // worker tabs currently lit; cleared as each worker ends
    const endAgentTab = (tabId, status) => {
      if (!tabId || !liveAgentTabs.delete(tabId)) return;
      markAgentTab(tabId, status);
      setTimeout(() => markAgentTab(tabId, 'idle'), 3200);
    };
    const handleTaskUpdate = (ev) => {
      switch (ev.eventType) {
        case 'run_started':
          if (runsRef.current[gid]) runsRef.current[gid].runId = ev.run_id;
          updateRun((run) => ({
            ...run,
            phase: 'working',
            agents: (ev.tasks || []).map((t) => ({ taskId: t.task_id, description: t.description, status: 'queued' })),
          }));
          return;
        case 'task_started':
          if (ev.tab_id) {
            tabByTask[ev.task_id] = ev.tab_id;
            liveAgentTabs.add(ev.tab_id);
            markAgentTab(ev.tab_id, 'working', ev.description);
          }
          updateRun((run) => {
            const started = { taskId: ev.task_id, description: ev.description, status: 'running', tabId: ev.tab_id, startedAt: Date.now() };
            const exists = run.agents.some((a) => a.taskId === ev.task_id);
            return {
              ...run,
              phase: ev.task_id === 'follow_up' ? 'acting' : run.phase,
              agents: exists ? run.agents.map((a) => (a.taskId === ev.task_id ? { ...a, ...started } : a)) : [...run.agents, started],
            };
          });
          return;
        case 'task_progress':
          markAgentStep(tabByTask[ev.task_id], ev.label);
          updateRun((run) => ({
            ...run,
            agents: run.agents.map((a) => (a.taskId === ev.task_id ? { ...a, currentStep: ev.label, stepCount: (a.stepCount || 0) + 1 } : a)),
          }));
          return;
        case 'synthesis_started':
          updateRun((run) => ({ ...run, phase: 'comparing' }));
          return;
        case 'approval_required':
          updateMessage((m) => ({
            ...m,
            text: ev.proposal,
            approval: { runId: ev.run_id, action: ev.action, state: 'pending' },
            run: { ...m.run, phase: 'approval' },
          }));
          return;
        default: {
          const status = ev.eventType?.startsWith('task_') ? ev.eventType.slice(5) : null;
          if (status && TERMINAL_STATUSES.has(status)) {
            endAgentTab(tabByTask[ev.task_id], ['completed', 'cancelled', 'blocked'].includes(status) ? status : 'failed');
            updateRun((run) => ({
              ...run,
              agents: run.agents.map((a) => (a.taskId === ev.task_id
                ? { ...a, status, endedAt: Date.now(), error: status === 'completed' ? null : ev.error }
                : a)),
            }));
          }
        }
      }
    };

    const expireApproval = (m) => (m.approval?.state === 'pending' ? { ...m.approval, state: 'expired' } : m.approval);

    try {
      const result = await runSwarm(text, { signal: controller.signal, onTaskUpdate: handleTaskUpdate, conversation });
      [...liveAgentTabs].forEach((tabId) => endAgentTab(tabId, 'completed')); // any worker that never reported an end
      updateMessage((m) => ({
        ...m,
        text: result.finalAnswer,
        approval: expireApproval(m),
        run: { ...m.run, phase: 'done', endedAt: Date.now(), agents: settleAgents(m.run.agents, 'completed') },
      }));
      tidyAgentTabs(result.agentTabIds, result.resultTabId);
    } catch (err) {
      const stopped = err.name === 'AbortError' || runsRef.current[gid]?.stopping;
      finalState = stopped ? 'stopped' : 'failed';
      [...liveAgentTabs].forEach((tabId) => endAgentTab(tabId, stopped ? 'cancelled' : 'failed'));
      updateMessage((m) => ({
        ...m,
        text: stopped
          ? 'Stopped. The agents’ tabs stay open if you want to look at what they found.'
          : `The run stopped with an error: ${err.message}`,
        failed: !stopped,
        approval: expireApproval(m),
        run: {
          ...m.run,
          phase: stopped ? 'stopped' : 'failed',
          endedAt: Date.now(),
          agents: settleAgents(m.run.agents),
        },
      }));
    } finally {
      endRun(gid, finalState);
    }
  };

  const runSingleAgent = async (gid, text, intent, conversation) => {
    const setMessages = setMessagesFor(gid);
    const messageId = `a_${Date.now()}`;
    const taskId = conversation?.taskId || `task-${Date.now()}`;
    const controller = new AbortController();
    let finalState = 'done';
    // Mark the tab the agent will drive (the active one) so it is visible in the tab strip and the page.
    beginRun(gid, { mode: 'single', taskId, controller, messageId, tabId: latestTabRef.current?.id || null, stopping: false });
    setMessages((prev) => [...prev, {
      id: messageId,
      sender: 'assistant',
      text: '',
      status: 'working',
      statusLabel: 'Reading your request',
      activity: [],
      startedAt: Date.now(),
      timestamp: nowTime()
    }]);
    markAgentTab(runsRef.current[gid]?.tabId, 'working', 'Reading your request');
    const endSingleTab = (status) => {
      const tabId = runsRef.current[gid]?.tabId;
      markAgentTab(tabId, status);
      // Your own tab goes back to normal a few seconds after the result is shown.
      if (tabId) setTimeout(() => markAgentTab(tabId, 'idle'), 3200);
    };

    try {

      const historyMessages = messages
        .filter(m => (m.sender === 'user' || m.sender === 'assistant') && (m.text || m.content) && m.status !== 'working')
        .slice(-10)
        .map(m => ({
          role: m.sender === 'user' ? 'user' : 'assistant',
          content: (m.text || m.content || '').slice(0, 2000),
          task_outcome: m.task_outcome || null,
        }));

      let lastTaskContext = null;
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].task_outcome) {
          lastTaskContext = messages[i].task_outcome;
          break;
        }
      }

      const outcome = await executeSingleAgentAction(gid, text, taskId, controller, intent, messageId, {
        ...conversation,
        messages: historyMessages,
        task_context: lastTaskContext,
      });
      if (outcome.status === 'completed') tidyAgentTabs(outcome.agentTabIds, outcome.resultTabId);
      const active = runsRef.current[gid];
      const terminalStatus = active?.stopping || outcome.status === 'stopped' ? 'stopped' : outcome.status;
      finalState = terminalStatus === 'completed' ? 'done' : terminalStatus === 'stopped' ? 'stopped' : 'failed';
      const isConv = Boolean(outcome.is_conversational);
      const defaultFallback = terminalStatus === 'failed'
        ? 'The agent could not complete the task.'
        : (isConv ? 'Hi. What would you like to do?' : 'Done.');
      const cleanText = terminalStatus === 'stopped'
        ? 'Stopped.'
        : (outcome.content || outcome.text || defaultFallback).replace(/^### (Agent Error|Connection Error|Browser-Use Result)\s*/, '');
      endSingleTab(terminalStatus === 'completed' ? 'completed' : terminalStatus === 'stopped' ? 'cancelled' : 'failed');
      const isFastPath = Boolean(outcome.fast_path);
      setMessages((prev) => prev.map((message) => message.id === messageId ? {
        ...message,
        helpers: settleAgents(message.helpers),
        text: cleanText,
        content: cleanText,
        status: terminalStatus,
        statusLabel: terminalStatus === 'stopped' ? 'Stopped' : terminalStatus === 'failed' ? "Couldn't finish" : (isConv ? '' : 'Done'),
        activity: message.activity || [],
        durationMs: outcome.durationMs ?? (Date.now() - message.startedAt),
        is_conversational: isConv,
        fast_path: isFastPath,
        adapter_name: outcome.adapter_name,
        task_outcome: outcome.task_outcome,
        completed: true,
        isStreaming: false,
      } : message));
    } catch (err) {
      const active = runsRef.current[gid];
      const stopped = active?.stopping || err.name === 'AbortError';
      finalState = stopped ? 'stopped' : 'failed';
      endSingleTab(stopped ? 'cancelled' : 'failed');
      setMessages((prev) => prev.map((message) => message.id === messageId ? {
        ...message,
        helpers: settleAgents(message.helpers),
        text: stopped ? 'Stopped.' : err.message || 'The agent could not complete the task.',
        status: stopped ? 'stopped' : 'failed',
        statusLabel: stopped ? 'Stopped' : "Couldn't finish",
        activity: message.activity || [],
        completed: true,
      } : message));
    } finally {
      endRun(gid, finalState);
    }
  };

  const handleSend = async (textToSend = input, intent = undefined, mode = undefined) => {
    const text = textToSend.trim();
    if (!text || !groupId || runsRef.current[groupId]) return;

    const gid = groupId;
    const tab = latestTabRef.current;
    runsRef.current[gid] = { mode: 'pending' }; // claimed at once, so a double send cannot start two runs here
    setMessagesFor(gid)((prev) => [...prev, { id: `u_${Date.now()}`, sender: 'user', text, timestamp: nowTime() }]);
    if (textToSend === input) setInput('');

    // The turn is stored in the group's conversation; if it was never loaded (backend was down), try once more now.
    let cid = threadsRef.current[gid]?.conversationId;
    if (!cid) cid = await loadThread(gid, tab);
    const conversation = { conversation_id: cid || undefined, group_id: gid, ui_tab_id: tab?.id, taskId: `task-${Date.now()}` };

    if (mode ? mode === 'multi' : isMultiAgentMode) {
      await runMultiAgent(gid, text, conversation);
    } else {
      await runSingleAgent(gid, text, intent, conversation);
    }
  };

  const handleComposerKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCopy = (id, text) => {
    navigator.clipboard.writeText(text || '');
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleNewChat = async () => {
    if (isTyping || !groupId) return;
    const gid = groupId;
    setThreads((prev) => ({ ...prev, [gid]: { conversationId: null, messages: [], status: 'loading' } }));
    setExpandedActivity({});
    userSizedRef.current = false;
    inputRef.current?.focus();
    try {
      const data = await postJson('/chat/groups/new', { group_id: gid });
      setThreads((prev) => ({ ...prev, [gid]: { ...(prev[gid] || EMPTY_THREAD), conversationId: data.conversation_id, status: 'ready' } }));
    } catch {
      setThreads((prev) => ({ ...prev, [gid]: { ...(prev[gid] || EMPTY_THREAD), status: 'offline' } }));
    }
  };

  // Earlier conversations, to reopen one in this tab
  const openHistory = async () => {
    setActiveDrawerTab('history');
    setHistoryList(null);
    try {
      const r = await fetch(`${AGENT_SERVICE}/chat/conversations?limit=30`);
      setHistoryList(r.ok ? await r.json() : []);
    } catch {
      setHistoryList([]);
    }
  };

  const reopenConversation = async (cid) => {
    if (isTyping || !groupId) return;
    const gid = groupId;
    try {
      const data = await postJson('/chat/groups/attach', { group_id: gid, conversation_id: cid });
      setThreads((prev) => ({ ...prev, [gid]: { conversationId: data.conversation_id, messages: (data.messages || []).map(toUiMessage), status: 'ready' } }));
      setExpandedActivity({});
      setActiveDrawerTab('chat');
    } catch (e) {
      console.warn('Could not reopen the conversation:', e);
    }
  };

  // Links in the chat open in a new tab of this chat's group
  const handleMessagesClick = (e) => {
    const a = e.target.closest?.('a[href]');
    if (!a) return;
    const href = a.getAttribute('href') || '';
    if (!/^https?:\/\//i.test(href)) return;
    e.preventDefault();
    onOpenLink?.(href, groupId);
  };

  if (!isOpen) return null;

  const tabTitle = activeTab?.url && !activeTab.url.startsWith('comex://') ? activeTab.title : null;
  const groupTabCount = tabs.filter((t) => groupIdOf(t) === groupId).length;
  const otherRunCount = Object.keys(runs).filter((g) => g !== groupId).length;

  const latestAssistantId = [...messages].reverse().find((m) => m.sender === 'assistant')?.id;

  const renderFooter = (msg) => (
    <div className="msg-footer">
      <span>{msg.timestamp}</span>
      {msg.durationMs != null && <span>{formatDuration(msg.durationMs)}</span>}
      {msg.fast_path && <span className="msg-tag">Fast path</span>}
      <button
        type="button"
        className="msg-copy"
        onClick={() => handleCopy(msg.id, msg.text)}
        aria-label={copiedId === msg.id ? 'Copied' : 'Copy reply'}
        title="Copy"
      >
        {copiedId === msg.id ? <Check size={13} /> : <Copy size={13} />}
      </button>
    </div>
  );

  const renderSingleAgentWorking = (msg) => (
    <div className="live-row" role="status" aria-live="polite">
      <OrbitMark />
      <ShimmerLabel className="live-label" text={msg.statusLabel || 'Reading your request'} />
      <ElapsedTime since={msg.startedAt} />
    </div>
  );

  const renderStepsToggle = (msg) => {
    const steps = msg.activity || [];
    if (steps.length === 0 || msg.is_conversational) return null;
    const open = Boolean(expandedActivity[msg.id]);
    return (
      <div className="steps-toggle-group">
        <button
          type="button"
          className="steps-toggle"
          onClick={() => setExpandedActivity((prev) => ({ ...prev, [msg.id]: !prev[msg.id] }))}
          aria-expanded={open}
        >
          <StatusIcon status={msg.status === 'completed' ? 'completed' : msg.status === 'stopped' ? 'cancelled' : 'failed'} />
          <span>{msg.statusLabel || 'Done'} in {steps.length} {steps.length === 1 ? 'step' : 'steps'}</span>
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        {open && (
          <ol className="agent-steps agent-steps-history">
            {steps.map((stepItem, idx) => (
              <li key={stepItem.id || idx} className="agent-step" title={stepItem.tool || undefined}>
                <span className="agent-step-label">{stepItem.label || stepItem.message}</span>
                {stepItem.status === 'failed' && <span className="agent-step-note">didn’t work</span>}
              </li>
            ))}
          </ol>
        )}
      </div>
    );
  };

  const renderApproval = (msg) => {
    const { approval } = msg;
    if (!approval) return null;
    return (
      <div className={`approval approval-${approval.state}`} role="group" aria-label="Approval needed">
        <p className="approval-question">Comex wants to: <strong>{approval.action}</strong></p>
        {approval.state === 'pending' ? (
          <div className="approval-actions">
            <button type="button" className="btn btn-primary" onClick={() => respondToApproval(msg.id, approval.runId, true)}>
              Approve
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => respondToApproval(msg.id, approval.runId, false)}>
              Decline
            </button>
            <span className="approval-note">Comex never checks out or pays.</span>
          </div>
        ) : (
          <p className="approval-state" role="status">
            {{ approved: 'Approved', declined: 'Declined', expired: 'No longer waiting for approval' }[approval.state]}
          </p>
        )}
      </div>
    );
  };

  const renderMessage = (msg) => {
    if (msg.sender === 'user') {
      return (
        <div key={msg.id} className="msg msg-user">
          <div className="msg-user-bubble">{msg.text}</div>
        </div>
      );
    }

    const isWorking = msg.status === 'working';
    return (
      <article key={msg.id} className={`msg msg-assistant ${msg.status === 'failed' || msg.failed ? 'msg-failed' : ''} ${isWorking ? 'msg-working' : ''}`}>
        {msg.kind === 'run' && <RunPanel run={msg.run} onOpenTab={onSelectTab} animation={swarmAnimation} />}
        {msg.helpers?.length > 0 && <RunPanel run={helperRun(msg.helpers)} onOpenTab={onSelectTab} animation={swarmAnimation} />}
        {isWorking ? renderSingleAgentWorking(msg) : renderStepsToggle(msg)}
        {(msg.text || msg.content) && (
          <div className="msg-body">
            <MarkdownRenderer content={msg.text || msg.content} animate={msg.id === latestAssistantId && !msg.restored} />
          </div>
        )}
        {renderApproval(msg)}
        {!isWorking && (msg.text || msg.content) && renderFooter(msg)}
      </article>
    );
  };

  return (
    <aside className="chat-drawer animate-slide-right" aria-label="Comex assistant">
      <div
        className="drawer-resize-handle"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize assistant"
        aria-valuenow={width}
        aria-valuemin={DRAWER_MIN}
        tabIndex={0}
        title="Drag to resize, double-click to reset"
        onPointerDown={startResize}
        onDoubleClick={resetWidth}
        onKeyDown={nudgeWidth}
      />
      <header className="drawer-header">
        {activeDrawerTab !== 'chat' ? (
          <>
            <button type="button" className="icon-btn" onClick={() => setActiveDrawerTab('chat')} aria-label="Back to chat" title="Back to chat">
              <ArrowLeft size={16} />
            </button>
            <h2 className="drawer-title">{activeDrawerTab === 'history' ? 'Chats' : 'Memory'}</h2>
            <div className="drawer-actions">
              {activeDrawerTab === 'brain' && (
                <button type="button" className="icon-btn" onClick={fetchBrainData} aria-label="Refresh memory" title="Refresh">
                  <RefreshCw size={15} className={isRefreshingBrain ? 'animate-spin' : ''} />
                </button>
              )}
              <button type="button" className="icon-btn" onClick={onClose} aria-label="Close assistant" title="Close (⌘J)">
                <X size={16} />
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="drawer-heading">
              <span className={`drawer-mark${isTyping ? ' is-working' : ''}`} aria-hidden="true" />
              <div className="drawer-heading-text">
                <h2 className="drawer-title">Comex</h2>
                <span className="drawer-context" title={tabTitle || ''}>
                  {isTyping ? (runs[groupId]?.mode === 'multi' ? 'Agents are working' : 'Working in this tab')
                    : otherRunCount > 0 ? `${otherRunCount} ${otherRunCount === 1 ? 'task is' : 'tasks are'} running in other tabs`
                    : groupTabCount > 1 ? `${groupTabCount} tabs share this chat`
                    : isMultiAgentMode ? 'Agents open their own tabs' : tabTitle ? `In ${tabTitle}` : 'Ready'}
                </span>
              </div>
            </div>
            <div className="drawer-actions">
              <button type="button" className="icon-btn" onClick={openHistory} aria-label="Earlier chats" title="Earlier chats">
                <History size={15} />
              </button>
              <button type="button" className="icon-btn" onClick={() => setActiveDrawerTab('brain')} aria-label="Memory" title="Memory">
                <Brain size={15} />
              </button>
              <button type="button" className="icon-btn" onClick={handleNewChat} disabled={isTyping} aria-label="New chat" title="New chat">
                <SquarePen size={15} />
              </button>
              <button type="button" className="icon-btn" onClick={onClose} aria-label="Close assistant" title="Close (⌘J)">
                <X size={16} />
              </button>
            </div>
          </>
        )}
      </header>

      {activeDrawerTab === 'chat' ? (
        <>
          <div className="chat-messages" ref={messagesRef} onClick={handleMessagesClick}>
            {messages.length === 0
              ? <EmptyState isMultiAgentMode={isMultiAgentMode} onPick={(text) => handleSend(text)} />
              : messages.map(renderMessage)}
          </div>

          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
          >
            <textarea
              ref={inputRef}
              rows={1}
              className="composer-input"
              placeholder={isMultiAgentMode ? 'Describe a task to split across agents' : 'Ask about this page, or tell Comex what to do'}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleComposerKeyDown}
              aria-label="Message"
            />
            <div className="composer-row">
              <div className="mode-switch" role="radiogroup" aria-label="Agent mode" style={{ '--idx': isMultiAgentMode ? 1 : 0 }}>
                <span className="mode-thumb" aria-hidden="true" />
                <button
                  type="button"
                  role="radio"
                  aria-checked={!isMultiAgentMode}
                  className={`mode-option ${!isMultiAgentMode ? 'selected' : ''}`}
                  onClick={() => setIsMultiAgentMode(false)}
                  disabled={isTyping}
                >
                  <User size={13} /> Single agent
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={isMultiAgentMode}
                  className={`mode-option ${isMultiAgentMode ? 'selected' : ''}`}
                  onClick={() => setIsMultiAgentMode(true)}
                  disabled={isTyping}
                >
                  <Users size={13} /> Multi-agent
                </button>
              </div>
              <button
                type={isTyping ? 'button' : 'submit'}
                className={`composer-send ${isTyping ? 'is-stop' : ''}`}
                disabled={isTyping ? Boolean(runsRef.current[groupId]?.stopping) : !input.trim()}
                onClick={isTyping ? () => stopRun(groupId) : undefined}
                aria-label={isTyping ? 'Stop' : 'Send'}
                title={isTyping ? 'Stop' : 'Send (Enter)'}
              >
                {isTyping ? <Square size={11} fill="currentColor" /> : <ArrowUp size={16} />}
              </button>
            </div>
          </form>
        </>
      ) : activeDrawerTab === 'history' ? (
        <div className="chat-history">
          {historyList === null ? (
            <p className="brain-empty">Loading earlier chats…</p>
          ) : historyList.length === 0 ? (
            <p className="brain-empty">No earlier chats yet. Chats are saved as you use them, and stay after you restart Comex.</p>
          ) : (
            <ul className="chat-history-list">
              {historyList.map((c) => (
                <li key={c.id}>
                  <button type="button" className={`chat-history-item${c.id === conversationId ? ' current' : ''}`}
                    onClick={() => reopenConversation(c.id)} disabled={isTyping || c.id === conversationId}>
                    <span className="chat-history-title">{c.title || 'Untitled chat'}</span>
                    <span className="chat-history-meta">
                      {c.message_count} {c.message_count === 1 ? 'message' : 'messages'} · {new Date(c.updated_at * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      {c.id === conversationId ? ' · open here' : c.status === 'open' ? ' · open in another tab' : ''}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="chat-history-note">Opening a chat here continues it in this tab.</p>
        </div>
      ) : (
        <div className="brain-inspector">
          {memoryStats && (
            <dl className="brain-stats">
              <div><dt>Facts</dt><dd>{memoryStats.usermemory_count || 0}</dd></div>
              <div><dt>Skills</dt><dd>{memoryStats.skill_count || 0}</dd></div>
              <div><dt>Reflections</dt><dd>{memoryStats.reflection_count || 0}</dd></div>
              <div><dt>Artifacts</dt><dd>{memoryStats.artifact_count || 0}</dd></div>
            </dl>
          )}

          <div className="brain-nav-tabs" role="tablist" aria-label="Memory sections">
            {[
              ['user_memory', `Facts (${userMemories.length})`],
              ['lessons', `Lessons (${lessons.length})`],
              ['adapters', `Adapters (${adapters.length})`],
              ['skills', `Skills (${skills.length})`],
              ['reflections', `Reflections (${reflections.length})`],
              ['settings', 'Settings'],
            ].map(([key, label]) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={brainSection === key}
                className={`brain-tab-btn ${brainSection === key ? 'active' : ''}`}
                onClick={() => setBrainSection(key)}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="brain-tab-content">
            {brainSection === 'user_memory' && (
              <>
                <form className="add-memory-form" onSubmit={handleAddMemory}>
                  <input type="text" className="brain-input" placeholder="Key, e.g. preferred_airline" value={newKey} onChange={e => setNewKey(e.target.value)} aria-label="Fact key" />
                  <input type="text" className="brain-input" placeholder="Value, e.g. IndiGo" value={newValue} onChange={e => setNewValue(e.target.value)} aria-label="Fact value" />
                  <div className="add-memory-row">
                    <select className="brain-select" value={newCategory} onChange={e => setNewCategory(e.target.value)} aria-label="Fact category">
                      <option value="preference">Preference</option>
                      <option value="constraint">Constraint</option>
                      <option value="profile">Profile</option>
                    </select>
                    <button type="submit" className="btn btn-primary" disabled={!newKey.trim() || !newValue.trim()}>
                      <Plus size={13} /> Save fact
                    </button>
                  </div>
                </form>
                <div className="brain-items-list">
                  {userMemories.length === 0 ? (
                    <p className="brain-empty">No saved facts yet. Comex learns them as you work, or you can add one above.</p>
                  ) : userMemories.map(m => (
                    <div key={m.id || m.key} className="brain-card">
                      <div className="card-header">
                        <span className="card-badge">{m.category}</span>
                        <span className="card-key">{m.key}</span>
                        <button type="button" className="icon-btn icon-btn-sm" onClick={() => handleDeleteMemory(m.key)} aria-label={`Delete ${m.key}`}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                      <div className="card-value">{m.value}</div>
                      {m.updated_at && <div className="card-time">{new Date(m.updated_at).toLocaleString()}</div>}
                    </div>
                  ))}
                </div>
              </>
            )}

            {brainSection === 'skills' && (
              <>
                <div className="brain-toolbar">
                  <button type="button" className="btn btn-secondary" onClick={handleConsolidateSkills} title="Merge duplicate and near-identical skills">
                    Merge duplicates
                  </button>
                </div>
                <div className="brain-items-list">
                  {skills.length === 0 ? (
                    <p className="brain-empty">No skills yet. Comex distills reusable skills after it handles something new.</p>
                  ) : skills.map(s => (
                    <div key={s.id} className={`brain-card ${s.status === 'demoted' ? 'card-demoted' : ''}`}>
                      <div className="card-header">
                        <span className="card-badge">{s.domain}</span>
                        <span className="card-key">{s.name}</span>
                        <button type="button" className="icon-btn icon-btn-sm" onClick={() => handleDeleteSkill(s.id)} aria-label={`Delete ${s.name}`}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                      <p className="card-text">{s.description}</p>
                      {s.kind === 'program' && (
                        <p className="card-text card-note">
                          {s.status === 'demoted' ? 'Not offered any more: it kept failing its checks.'
                            : s.status === 'probation' ? 'On probation: offered, and trusted after it passes another check.'
                              : 'Verified program.'}
                          {(() => { try { const c = JSON.parse(s.check_json || '{}'); return c.type ? ` Checked by ${c.type.replace('_', ' ')}.` : ''; } catch { return ''; } })()}
                          {s.task ? ` Learned from: “${s.task.slice(0, 90)}”.` : ''}
                        </p>
                      )}
                      {s.code_snippet && <pre className="card-code"><code>{s.code_snippet}</code></pre>}
                      <div className="card-metrics">
                        {s.kind === 'program' ? (
                          <>
                            <span>Passed {s.success_count || 0} of {s.usage_count || 0} checks</span>
                            {s.failure_count > 0 && <span>{s.failure_count} failed</span>}
                          </>
                        ) : (
                          <>
                            <span>Used {s.usage_count || 0} times</span>
                            <span>{s.success_count || 0} successes</span>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {brainSection === 'reflections' && (
              <div className="brain-items-list">
                {reflections.length === 0 ? (
                  <p className="brain-empty">No reflections yet. Comex reviews each task in the background after it finishes.</p>
                ) : reflections.map(r => (
                  <div key={r.id} className="brain-card">
                    <div className="card-header">
                      <span className={`card-badge ${r.is_novel ? 'card-badge-accent' : ''}`}>{r.is_novel ? 'New kind of task' : 'Routine'}</span>
                      <span className="card-time">{r.created_at}</span>
                    </div>
                    {r.critique && <p className="card-text">{r.critique}</p>}
                    {r.lesson_learned && (
                      <p className="card-lesson"><strong>Lesson:</strong> {r.lesson_learned}</p>
                    )}
                  </div>
                ))}
              </div>
            )}

            {brainSection === 'lessons' && (
              <div className="brain-items-list">
                {lessons.length === 0 ? (
                  <p className="brain-empty">No lessons yet. After a difficult task (failed steps, many steps, or several sites) Comex writes down what got it past the obstacle on that site, and offers it the next time it works there.</p>
                ) : lessons.map(l => (
                  <div key={l.id} className={`brain-card${l.status === 'demoted' ? ' card-dim' : ''}`}>
                    <div className="card-header">
                      <span className="card-badge">{l.domain}</span>
                      <span className="card-key">{l.obstacle}</span>
                      <button type="button" className="icon-btn icon-btn-sm" onClick={() => handleDeleteLesson(l.id)} aria-label="Delete lesson">
                        <Trash2 size={13} />
                      </button>
                    </div>
                    <p className="card-text"><strong>What worked:</strong> {l.approach}</p>
                    {l.avoid && <p className="card-text"><strong>Avoid:</strong> {l.avoid}</p>}
                    <div className="card-metrics">
                      <span>{l.uses ? `Helped ${l.successes} of ${l.uses} later runs` : 'Not used yet'}</span>
                      {l.status !== 'active' && <span>{l.status === 'demoted' ? 'No longer offered (kept failing)' : 'On probation'}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {brainSection === 'settings' && (
              <section className="setting-group" aria-labelledby="setting-swarm-title">
                <h3 className="setting-title" id="setting-swarm-title">Multi-agent animation</h3>
                <p className="setting-hint">How a multi-agent run shows its progress while it works.</p>
                <div className="setting-choices" role="radiogroup" aria-labelledby="setting-swarm-title">
                  {SWARM_ANIMATIONS.map(({ key, label, hint }) => (
                    <button
                      key={key}
                      type="button"
                      role="radio"
                      aria-checked={swarmAnimation === key}
                      className={`setting-choice${swarmAnimation === key ? ' selected' : ''}`}
                      onClick={() => chooseSwarmAnimation(key)}
                    >
                      <span className="setting-preview" aria-hidden="true">
                        {key === 'orbit' ? <SwarmOrbit agents={DEMO_AGENTS} phase="working" /> : <SwarmStage agents={DEMO_AGENTS} phase="working" />}
                      </span>
                      <span className="setting-choice-label">{label}</span>
                      <span className="setting-choice-hint">{hint}</span>
                    </button>
                  ))}
                </div>
              </section>
            )}

            {brainSection === 'adapters' && (
              <div className="brain-items-list">
                {adapters.length === 0 ? (
                  <p className="brain-empty">No adapters yet. Routine actions you repeat are compiled into fast adapters automatically.</p>
                ) : adapters.map(a => (
                  <div key={a.id} className="brain-card">
                    <div className="card-header">
                      <span className={`card-badge ${a.status === 'active' ? 'card-badge-accent' : ''}`}>{a.domain}</span>
                      <span className="card-key">{a.name}</span>
                      <button type="button" className="icon-btn icon-btn-sm" onClick={() => handleDeleteAdapter(a.id)} aria-label={`Delete ${a.name}`}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                    <p className="card-text">{a.action_intent}</p>
                    {a.code_template && <pre className="card-code"><code>{a.code_template}</code></pre>}
                    <div className="card-metrics">
                      <span>{a.status}</span>
                      <span>{a.success_count || 0} successes</span>
                      <span>{a.failure_count || 0} failures</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}

function ElapsedTime({ since }) {
  const now = useNow(Boolean(since));
  if (!since) return null;
  return <span className="elapsed">{formatDuration(now - since)}</span>;
}
