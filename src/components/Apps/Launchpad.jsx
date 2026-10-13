import React, { useEffect, useRef, useState } from 'react';
import { ArrowUp, User, Users, Globe } from 'lucide-react';
import './Apps.css';

function normalizeWebUrl(value) {
  const trimmed = value.trim();
  if (!trimmed || /\s/.test(trimmed)) return null;

  const candidate = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    const url = new URL(candidate);
    return ['http:', 'https:'].includes(url.protocol) && url.hostname.includes('.') ? url.href : null;
  } catch {
    return null;
  }
}

const MODES = {
  single: {
    label: 'Single agent',
    icon: User,
    hint: 'One agent works in this tab: it reads, searches, clicks and fills in forms.',
    typed: [
      'Find the cheapest flight from Bengaluru to Delhi next Friday',
      'Summarize the reviews on this product page',
      'Book a table for two near Indiranagar tonight',
    ],
  },
  multi: {
    label: 'Multi-agent',
    icon: Users,
    hint: 'Up to four agents each open a tab, then Comex compares what they found.',
    typed: [
      'Compare noise-cancelling headphones on Amazon and Flipkart',
      'Find the most cited papers on multi-agent orchestration',
      'Research Rust vs Go for a web backend',
    ],
  },
};
const MODE_KEYS = Object.keys(MODES);

const EXAMPLES = [
  { mode: 'multi', text: 'Compare noise-cancelling headphones under ₹10,000 on Amazon and Flipkart' },
  { mode: 'multi', text: 'Find the most cited papers on multi-agent orchestration since 2023' },
  { mode: 'single', text: 'Find the cheapest flight from Bengaluru to Delhi next Friday' },
  { mode: 'single', text: 'Open YouTube and search for a lo-fi study playlist' },
];

const SHORTCUTS = [
  ['⌘', 'J', 'Assistant'],
  ['⌘', 'T', 'New tab'],
  ['⌘', 'L', 'Address bar'],
];

const HEADLINE = 'What do you want to get done?';

function todayLabel() {
  return new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
}

// Types example tasks into the empty prompt, one after another.
function useTypedPlaceholder(phrases, active) {
  const [text, setText] = useState('');
  useEffect(() => {
    if (!active) return undefined;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setText(phrases[0]);
      return undefined;
    }
    let phrase = 0;
    let chars = 0;
    let deleting = false;
    let timer;
    const tick = () => {
      const full = phrases[phrase];
      if (!deleting) {
        chars += 1;
        setText(full.slice(0, chars));
        if (chars >= full.length) { deleting = true; timer = setTimeout(tick, 1900); return; }
        timer = setTimeout(tick, 34 + Math.random() * 30);
      } else {
        chars -= 2;
        setText(full.slice(0, Math.max(0, chars)));
        if (chars <= 0) { deleting = false; phrase = (phrase + 1) % phrases.length; timer = setTimeout(tick, 380); return; }
        timer = setTimeout(tick, 16);
      }
    };
    timer = setTimeout(tick, 600);
    return () => clearTimeout(timer);
  }, [phrases, active]);
  return text;
}

/*
 * Background dot grid on a canvas. Dots near the cursor brighten and take the
 * accent colour, a slow diagonal wave keeps it alive, and dots around the prompt
 * light up while it has focus. Flat dots only, no gradients.
 */
function DotField({ focused }) {
  const canvasRef = useRef(null);
  const focusRef = useRef(focused);
  focusRef.current = focused;

  useEffect(() => {
    const canvas = canvasRef.current;
    const host = canvas.parentElement;
    const ctx = canvas.getContext('2d');
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const GAP = 26;
    let width = 0;
    let height = 0;
    let raf = 0;
    let glow = 0;
    const mouse = { x: -9999, y: -9999, sx: -9999, sy: -9999 };
    const start = performance.now();

    const draw = (now) => {
      ctx.clearRect(0, 0, width, height);
      glow += ((focusRef.current ? 1 : 0) - glow) * 0.06;
      mouse.sx += (mouse.x - mouse.sx) * 0.18;
      mouse.sy += (mouse.y - mouse.sy) * 0.18;
      const t = reduce ? 0 : now - start;
      const intro = reduce ? 1 : Math.min(1, t / 900);
      const promptEl = host.querySelector('.landing-prompt');
      const hostRect = host.getBoundingClientRect();
      const pr = promptEl?.getBoundingClientRect();
      const px = pr ? pr.left - hostRect.left + pr.width / 2 : width / 2;
      const py = pr ? pr.top - hostRect.top + pr.height / 2 : height / 2;
      const pw = pr ? pr.width / 2 + 60 : 300;

      for (let y = GAP / 2; y < height; y += GAP) {
        for (let x = GAP / 2; x < width; x += GAP) {
          const near = Math.max(0, 1 - Math.hypot(x - mouse.sx, y - mouse.sy) / 170);
          const wave = (Math.sin(x * 0.011 + y * 0.007 - t * 0.0007) + 1) / 2;
          const prompt = Math.max(0, 1 - Math.hypot((x - px) / pw, (y - py) / 110)) * glow;
          const base = (0.05 + wave * 0.055) * intro;
          ctx.fillStyle = `rgba(236, 237, 239, ${base})`;
          ctx.fillRect(x - 0.75, y - 0.75, 1.5, 1.5);
          const lit = Math.max(near, prompt * 0.8);
          if (lit > 0.02) {
            const r = 0.8 + lit * 1.1;
            ctx.fillStyle = `rgba(124, 156, 255, ${lit * 0.6})`;
            ctx.beginPath();
            ctx.arc(x, y, r, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }
      if (!reduce && !document.hidden) raf = requestAnimationFrame(draw);
    };

    const resize = () => {
      const rect = host.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (reduce) draw(performance.now());
    };

    const onMove = (e) => {
      const rect = host.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
      if (mouse.sx < -999) { mouse.sx = mouse.x; mouse.sy = mouse.y; }
      if (reduce) draw(performance.now());
    };
    const onLeave = () => { mouse.x = -9999; mouse.y = -9999; };
    const onVisibility = () => {
      cancelAnimationFrame(raf);
      if (!document.hidden && !reduce) raf = requestAnimationFrame(draw);
    };

    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();
    host.addEventListener('pointermove', onMove);
    host.addEventListener('pointerleave', onLeave);
    document.addEventListener('visibilitychange', onVisibility);
    if (!reduce) raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      host.removeEventListener('pointermove', onMove);
      host.removeEventListener('pointerleave', onLeave);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  return <canvas ref={canvasRef} className="landing-field" aria-hidden="true" />;
}

export default function Launchpad({ onNavigate, onOpenChat, onSubmitPrompt, history = [] }) {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('single');
  const [focused, setFocused] = useState(false);
  const inputRef = useRef(null);
  const webUrl = normalizeWebUrl(query);
  const current = MODES[mode];
  const typed = useTypedPlaceholder(current.typed, !query);

  const handleSubmit = (event) => {
    event.preventDefault();
    const value = query.trim();
    if (!value) return;

    if (webUrl) {
      onNavigate(webUrl);
    } else if (onSubmitPrompt) {
      onSubmitPrompt(value, mode);
    } else {
      onOpenChat?.();
    }
    setQuery('');
  };

  const pickExample = (example) => {
    setMode(example.mode);
    setQuery(example.text);
    inputRef.current?.focus();
  };

  return (
    <main className="comet-landing">
      <DotField focused={focused} />

      <section className="comet-landing-content" aria-labelledby="landing-title">
        <p className="landing-greeting">{todayLabel()}</p>
        <h1 id="landing-title" className="landing-headline" aria-label={HEADLINE}>
          {HEADLINE.split(' ').map((word, i) => (
            <span key={i} className="landing-word" style={{ '--w': i }} aria-hidden="true">{word} </span>
          ))}
        </h1>

        <div className={`landing-shell ${focused ? 'is-focused' : ''}`}>
        <form className="landing-prompt" onSubmit={handleSubmit}>
          <div className="landing-input-wrap">
            <input
              ref={inputRef}
              id="landing-prompt"
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              aria-label="Ask Comex or enter a website"
              aria-describedby="landing-hint"
              autoComplete="off"
              autoFocus
            />
            {!query && (
              <span className="landing-typed" aria-hidden="true">
                {typed}<span className="landing-caret" />
              </span>
            )}
          </div>
          <div className="landing-prompt-bar">
            <div className="mode-switch" role="radiogroup" aria-label="Agent mode" style={{ '--idx': MODE_KEYS.indexOf(mode) }}>
              <span className="mode-thumb" aria-hidden="true" />
              {MODE_KEYS.map((key) => {
                const { label, icon: Icon } = MODES[key];
                return (
                  <button
                    key={key}
                    type="button"
                    role="radio"
                    aria-checked={mode === key}
                    className={`mode-option ${mode === key ? 'selected' : ''}`}
                    onClick={() => { setMode(key); inputRef.current?.focus(); }}
                  >
                    <Icon size={13} /> {label}
                  </button>
                );
              })}
            </div>
            <button type="submit" className="landing-submit" disabled={!query.trim()} aria-label={webUrl ? 'Open website' : 'Send to assistant'}>
              {webUrl ? <><Globe size={14} /> Open</> : <ArrowUp size={17} />}
            </button>
          </div>
        </form>
        </div>

        <p id="landing-hint" className="landing-hints" key={webUrl ? 'url' : mode}>
          {webUrl ? `Opens ${new URL(webUrl).hostname} in this tab.` : current.hint}
        </p>

        <ul className="landing-suggestions" aria-label="Example tasks">
          {EXAMPLES.map((example, i) => {
            const { icon: Icon, label } = MODES[example.mode];
            return (
              <li key={example.text} style={{ '--c': i }}>
                <button type="button" className="landing-suggest" onClick={() => pickExample(example)}>
                  <span className="landing-suggest-mode"><Icon size={12} aria-hidden="true" /> {label}</span>
                  <span className="landing-suggest-text">{example.text}</span>
                </button>
              </li>
            );
          })}
        </ul>

        {history.length > 0 && (
          <section className="landing-section" aria-labelledby="landing-history-title">
            <h2 id="landing-history-title" className="landing-section-title">Recent</h2>
            <div className="landing-history-list">
              {history.slice(0, 6).map((item) => (
                <div key={item.id} className={`landing-history-item landing-history-item--${item.status || 'done'}`}>
                  <div className="landing-history-item-header">
                    <span className="landing-history-item-title">{item.title}</span>
                    <span className="landing-history-item-time">{item.timestamp}</span>
                  </div>
                  {item.result && (
                    <pre className="landing-history-item-result">{item.result}</pre>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
      </section>

      <footer className="landing-shortcuts" aria-label="Keyboard shortcuts">
        {SHORTCUTS.map(([mod, key, label]) => (
          <span key={key} className="landing-shortcut">
            <kbd>{mod}</kbd><kbd>{key}</kbd> {label}
          </span>
        ))}
      </footer>
    </main>
  );
}
