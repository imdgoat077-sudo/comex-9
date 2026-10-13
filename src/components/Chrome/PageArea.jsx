import React, { useEffect, useRef } from 'react';
import { AlertTriangle, RotateCw, ShieldAlert, WifiOff } from 'lucide-react';
import Launchpad from '../Apps/Launchpad';
import { isInternalUrl } from '../../shell/omnibox';
import { MACOS_TITLEBAR_OFFSET } from '../../shell/geometry';
import './Chrome.css';

// What a failed load means, in plain words (Chromium net error codes).
function describeError(error) {
  const code = error?.code;
  if (code === 'crashed') return { icon: AlertTriangle, title: 'This page crashed', text: 'Reload to try again.' };
  if (code === -106) return { icon: WifiOff, title: "You're offline", text: 'Check your internet connection, then try again.' };
  if (code === -105 || code === -137) return { icon: AlertTriangle, title: "This site can't be found", text: 'Check the address for typos. The site may also be down.' };
  if (code === -102 || code === -109 || code === -118 || code === -7 || code === -21) return { icon: AlertTriangle, title: "This site can't be reached", text: 'It refused the connection or took too long to respond.' };
  if (typeof code === 'number' && code <= -200 && code > -300) {
    return { icon: ShieldAlert, title: "This connection isn't private", text: "The site's security certificate is not valid, so Comex did not open it. Your information was not sent." };
  }
  return { icon: AlertTriangle, title: "This page couldn't be loaded", text: error?.description || 'Something went wrong while loading it.' };
}

function ErrorPage({ tab, onRetry }) {
  const { icon: Icon, title, text } = describeError(tab.error);
  return (
    <div className="error-page" role="alert">
      <Icon size={28} className="error-page-icon" />
      <h1>{title}</h1>
      <p>{text}</p>
      {tab.error?.url && <p className="error-page-url">{tab.error.url}</p>}
      <button type="button" className="error-page-retry" onClick={onRetry} autoFocus>
        <RotateCw size={14} /> Try again
      </button>
      {typeof tab.error?.code === 'number' && <p className="error-page-code">Error {tab.error.code}</p>}
    </div>
  );
}

/**
 * The page area. Real pages are native views placed over this box by the main process; this component tells it where
 * the box is (CLAUDE.md §3.1: measured from .browser-body-layout plus the title-bar offset, never from innerHeight).
 * It draws the Launchpad and error pages itself, and then the native view is hidden.
 */
export default function PageArea({ tab, isChatOpen, covered = false, command, onOpenChat, onSubmitLandingPrompt }) {
  const isElectron = typeof window !== 'undefined' && window.nexusNative?.isElectron;
  const ref = useRef(null);
  const ownPage = !tab || isInternalUrl(tab.url) || Boolean(tab.error);

  useEffect(() => {
    if (!isElectron) return undefined;
    const send = () => {
      const body = document.querySelector('.browser-body-layout');
      const drawer = document.querySelector('.chat-drawer');
      if (!body) return;
      const rect = body.getBoundingClientRect();
      const drawerWidth = isChatOpen && drawer ? Math.round(drawer.getBoundingClientRect().width) : 0;
      window.nexusNative.browser.setBounds({
        x: 0,
        y: Math.round(rect.top + MACOS_TITLEBAR_OFFSET),
        width: Math.max(0, Math.round(rect.width - drawerWidth)),
        height: Math.max(0, Math.min(Math.round(rect.height), window.innerHeight - Math.round(rect.top))),
        isHidden: ownPage || covered, // a dialog over the page area: pages draw above the interface, so hide it
      });
    };
    const raf = requestAnimationFrame(send);
    const ro = new ResizeObserver(send);
    if (ref.current) ro.observe(ref.current);
    const body = document.querySelector('.browser-body-layout');
    if (body) ro.observe(body);
    window.addEventListener('resize', send);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); window.removeEventListener('resize', send); };
  }, [isElectron, tab?.id, ownPage, covered, isChatOpen]);

  let content = null;
  if (!tab || isInternalUrl(tab.url)) {
    content = <Launchpad onNavigate={(url) => command({ type: 'navigate', url })} onOpenChat={onOpenChat} onSubmitPrompt={onSubmitLandingPrompt} history={[]} />;
  } else if (tab.error) {
    content = <ErrorPage tab={tab} onRetry={() => command({ type: 'reload', tabId: tab.id })} />;
  } else if (!isElectron) {
    content = <div className="preview-page"><p>{tab.title || tab.url}</p><p className="preview-page-url">{tab.url}</p><p>Websites open in the Comex app.</p></div>;
  }

  return (
    <main ref={ref} className={`browser-canvas-area ${isChatOpen ? 'with-drawer' : ''}`}>
      {content}
    </main>
  );
}
