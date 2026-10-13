import React, { useCallback, useEffect, useRef, useState } from 'react';
import TabStrip from './components/Chrome/TabStrip';
import Toolbar from './components/Chrome/Toolbar';
import PageArea from './components/Chrome/PageArea';
import { BookmarkBar, ClosedToast, NoticeBar } from './components/Chrome/ChromeBars';
import ChatDrawer, { DRAWER_WIDTH } from './components/Chat/ChatDrawer';
import ShortcutsModal from './components/Modals/ShortcutsModal';
import { classifyIntent } from './agents/IntentClassifier';
import { useBrowser, useUiCommands } from './shell/useBrowser';
import { popupTheme, toNativeRect } from './shell/geometry';
import { toNavigableUrl } from './shell/omnibox';
import './App.css';
import './components/Chrome/Chrome.css';

const popupBridge = () => window.nexusNative?.browser?.popup;

function elapsedText(since) {
  if (!since) return '';
  const s = Math.max(0, Math.round((Date.now() - since) / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

const AGENT_TITLES = { working: 'Agent working in this tab', completed: 'Agent finished', failed: 'Agent failed', cancelled: 'Agent stopped', blocked: 'Agent blocked' };

/**
 * The browser window. Tabs and groups belong to the main process (TabManager); this renders its state and sends its
 * commands. Chat state per group, and what the AI is doing in each group, stay here: they are about the chat.
 */
export default function App() {
  const { state, command, isNative } = useBrowser();
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [drawerWidth, setDrawerWidth] = useState(DRAWER_WIDTH);
  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);
  const [renamingGroupId, setRenamingGroupId] = useState(null);
  const [groupTitles, setGroupTitles] = useState({}); // groupId -> the chat's title, a label for unnamed groups
  // groupId -> { state: working | done | failed | stopped, since }: what the AI is doing in each group. A finished
  // state stays until you have looked at that group, so a background group that finished is noticed.
  const [groupActivity, setGroupActivity] = useState({});
  const omniboxRef = useRef(null);

  const session = state?.session;
  const tabs = session?.tabs || [];
  const activeTab = tabs.find((t) => t.id === session?.activeTabId) || tabs[0] || null;
  const bookmarks = state?.bookmarks || [];

  const toggleChat = useCallback(() => setIsChatOpen((v) => !v), []);

  useUiCommands({
    'focus-omnibox': () => omniboxRef.current?.focus(),
    'toggle-assistant': toggleChat,
    'show-shortcuts': () => setIsShortcutsOpen(true),
    'rename-group': ({ groupId }) => setRenamingGroupId(groupId),
    'agent-stop': () => window.dispatchEvent(new CustomEvent('comex-agent-stop')),
  });

  // Without Electron (the preview) there is no main process to catch shortcuts; the page does it.
  useEffect(() => {
    if (isNative) return undefined;
    const onKey = (e) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      const k = e.key.toLowerCase();
      const run = { t: e.shiftKey ? { type: 'reopen-closed' } : { type: 'new-tab' }, w: { type: 'close-tab' } }[k];
      if (run) { e.preventDefault(); command(run); }
      if (k === 'l') { e.preventDefault(); omniboxRef.current?.focus(); }
      if (k === 'j') { e.preventDefault(); toggleChat(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isNative, command, toggleChat]);

  // A new, empty tab puts the cursor in the address bar
  const lastActive = useRef(null);
  useEffect(() => {
    if (!activeTab || activeTab.id === lastActive.current) return;
    const fresh = lastActive.current !== null && activeTab.url === 'comex://launchpad';
    lastActive.current = activeTab.id;
    if (fresh) omniboxRef.current?.focus();
  }, [activeTab]);

  // A finished group's mark clears a few seconds after you look at it
  const activeGroupId = activeTab?.groupId || null;
  const activeGroupState = activeGroupId ? groupActivity[activeGroupId]?.state : null;
  useEffect(() => {
    if (!activeGroupId || !activeGroupState || activeGroupState === 'working') return undefined;
    const t = setTimeout(() => setGroupActivity((prev) => {
      if (prev[activeGroupId]?.state === 'working') return prev;
      const next = { ...prev };
      delete next[activeGroupId];
      return next;
    }), 6000);
    return () => clearTimeout(t);
  }, [activeGroupId, activeGroupState]);

  // Hover card for agent tabs, drawn above the page by the popup layer
  const showCard = useCallback((tab, rect) => {
    const popup = popupBridge();
    if (!popup) return;
    const lines = [];
    if (tab.agentLabel) lines.push({ text: tab.agentLabel });
    if (tab.agentStatus === 'working') lines.push({ text: tab.agentStep || 'Starting' });
    try { lines.push({ text: new URL(tab.url).hostname.replace(/^www\./, ''), dim: true }); } catch { /* internal page */ }
    const width = 300;
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
    popup.show({
      kind: 'card',
      rect: toNativeRect({ left, top: rect.bottom + 6, width, height: 30 + lines.length * 22 }, { padX: 10, padBottom: 12 }),
      card: { status: tab.agentStatus, title: AGENT_TITLES[tab.agentStatus] || 'Agent', time: tab.agentStatus === 'working' ? elapsedText(tab.agentSince) : '', lines },
      theme: popupTheme(),
    });
  }, []);
  const hideCard = useCallback(() => popupBridge()?.hide(), []);

  // Launchpad prompt: multi-agent goes to the chat; a single-agent task that names a site opens it first.
  const handleLandingPrompt = async (prompt, mode = 'single') => {
    setIsChatOpen(true);
    if (mode === 'multi') {
      window.dispatchEvent(new CustomEvent('comex-landing-prompt', { detail: { prompt, mode } }));
      return;
    }
    let intent;
    try {
      const result = await classifyIntent(prompt);
      intent = result?.intent;
      if (intent === 'visible_browser_task' && result.confidence >= 0.6 && result.target) {
        const url = toNavigableUrl(result.target);
        if (url) await command({ type: 'navigate', url });
      }
    } catch (err) {
      console.error('Intent classification failed:', err);
    }
    requestAnimationFrame(() => window.dispatchEvent(new CustomEvent('comex-landing-prompt', { detail: { prompt, intent, mode } })));
  };

  if (!session) return <div className="nexus-app-container" />;

  return (
    <div className="nexus-app-container" style={{ '--drawer-w': `${drawerWidth}px` }}>
      <header className="browser-header">
        <div className="browser-topbar">
          <div className="traffic-spacer" aria-hidden="true" />
          <TabStrip
            session={session}
            groupActivity={groupActivity}
            groupTitles={groupTitles}
            command={command}
            renamingGroupId={renamingGroupId}
            setRenamingGroupId={setRenamingGroupId}
            onShowCard={showCard}
            onHideCard={hideCard}
          />
          <div className="topbar-end">
            <ClosedToast lastClosed={session.lastClosed} command={command} />
          </div>
        </div>
        <Toolbar
          ref={omniboxRef}
          tab={activeTab}
          tabs={tabs}
          bookmarks={bookmarks}
          command={command}
          isChatOpen={isChatOpen}
          onToggleChat={toggleChat}
          unreadCount={0}
        />
        <BookmarkBar bookmarks={bookmarks} command={command} />
        <NoticeBar tab={activeTab} command={command} />
      </header>

      <div className="browser-body-layout">
        <PageArea
          tab={activeTab}
          isChatOpen={isChatOpen}
          covered={isShortcutsOpen}
          command={command}
          onOpenChat={() => setIsChatOpen(true)}
          onSubmitLandingPrompt={handleLandingPrompt}
        />
        <ChatDrawer
          isOpen={isChatOpen}
          onClose={() => setIsChatOpen(false)}
          activeTab={activeTab}
          tabs={tabs}
          onSelectTab={(tabId) => command({ type: 'activate', tabId })}
          onOpenLink={(url, groupId) => { if (/^https?:\/\//i.test(url || '')) command({ type: 'new-tab', url, groupId }); }}
          onCloseTabs={(ids, focusId) => command({ type: 'close-tabs', tabIds: ids || [], focusId: focusId || null })}
          onGroupTitle={(groupId, title) => setGroupTitles((prev) => (prev[groupId] === title ? prev : { ...prev, [groupId]: title }))}
          onGroupActivity={(groupId, activity) => setGroupActivity((prev) => ({ ...prev, [groupId]: activity }))}
          width={drawerWidth}
          onWidthChange={setDrawerWidth}
        />
      </div>

      <ShortcutsModal isOpen={isShortcutsOpen} onClose={() => setIsShortcutsOpen(false)} />
    </div>
  );
}
