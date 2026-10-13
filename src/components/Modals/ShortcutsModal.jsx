import React, { useEffect } from 'react';
import { Command, X, Sparkles, Plus, RotateCw, Search } from 'lucide-react';
import './Modals.css';

export default function ShortcutsModal({ isOpen, onClose }) {
  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);
  if (!isOpen) return null;

  // Matches the shortcuts in electron/main.js; they work with the focus anywhere, including inside a web page.
  const shortcuts = [
    { key: '⌘T', desc: 'New tab', icon: Plus },
    { key: '⇧⌘T', desc: 'Reopen closed tab or group', icon: RotateCw },
    { key: '⌘W', desc: 'Close tab', icon: X },
    { key: '⌘L', desc: 'Address bar', icon: Search },
    { key: '⌘R', desc: 'Reload (⇧⌘R ignores the cache)', icon: RotateCw },
    { key: '⌘.', desc: 'Stop loading', icon: X },
    { key: '⌘[  ⌘]', desc: 'Back, forward', icon: Command },
    { key: '⌃Tab  ⌃⇧Tab', desc: 'Next, previous tab', icon: Command },
    { key: '⌘1 – ⌘8, ⌘9', desc: 'Go to tab, last tab', icon: Command },
    { key: '⌘J', desc: 'Assistant', icon: Sparkles },
    { key: '⌘=  ⌘-  ⌘0', desc: 'Zoom in, out, actual size', icon: Search },
  ];
  return (
    <div className="modal-backdrop animate-fade-in" onClick={onClose}>
      <div className="modal-content glass-panel-elevated" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <Command size={18} className="modal-icon text-accent" />
            <h3>Keyboard Shortcuts</h3>
          </div>
          <button className="chat-icon-btn" onClick={onClose} aria-label="Close" autoFocus><X size={16} /></button>
        </div>

        <div className="shortcuts-list">
          {shortcuts.map((sc, idx) => {
            const Icon = sc.icon;
            return (
              <div key={idx} className="shortcut-row">
                <div className="shortcut-desc">
                  <Icon size={14} className="sc-icon" />
                  <span>{sc.desc}</span>
                </div>
                <kbd className="shortcut-key">{sc.key}</kbd>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
