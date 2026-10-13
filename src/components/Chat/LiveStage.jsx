import React, { useEffect, useLayoutEffect, useRef } from 'react';
import gsap from 'gsap';
import { MotionPathPlugin } from 'gsap/MotionPathPlugin';

gsap.registerPlugin(MotionPathPlugin);

/*
 * Live work, shown quietly.
 *
 *  OrbitMark     (single agent): three dots circling on an orbit that tumbles slowly in 3D; size and brightness follow depth.
 *  ShimmerLabel  (single agent): the current step as one line of text, a soft light sweeping through it; a new step
 *                replaces the old one by rising into place.
 *  SwarmOrbit    (multi-agent, "Orbit" style): the same orbit with one dot per agent. A working agent circles; when it
 *                finishes its dot settles onto the outer ring, so the count is readable at a glance.
 *  SwarmStage    (multi-agent, "Scene" style): a planner dispatches pulses to one window per agent; each window fills
 *                as its agent works, finished agents send a pulse into the result node, whose ring fills as they land.
 *
 * Driven by GSAP; with prefers-reduced-motion everything renders still, in its current state.
 */

const reduceMotion = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const SVG_NS = 'http://www.w3.org/2000/svg';

// ── single agent ────────────────────────────────────────────────────────────────────────────────
const ORBIT_DOTS = 3;

// A point on a circle that tips and turns in 3D. Returns the screen offset, the depth z and depth 0 (far) .. 1 (near).
function orbitPoint(t, angle, R, focal) {
  const tilt = 1.05 + 0.4 * Math.sin(t * 0.55);
  const turn = t * 0.42;
  const x0 = R * Math.cos(angle), y0 = R * Math.sin(angle);
  const y1 = y0 * Math.cos(tilt), z1 = y0 * Math.sin(tilt);                            // tip about the x axis
  const x = x0 * Math.cos(turn) + z1 * Math.sin(turn), z = -x0 * Math.sin(turn) + z1 * Math.cos(turn);   // turn about the y axis
  const k = focal / (focal - z);
  return { x: x * k, y: y1 * k, z, depth: (z / R + 1) / 2 };
}

export function OrbitMark({ size = 24 }) {
  const svg = useRef(null);

  useLayoutEffect(() => {
    const dots = [...svg.current.children];
    const state = { t: 0 };
    const draw = () => {
      const pts = dots.map((dot, i) => {
        const p = orbitPoint(state.t, state.t * 3.3 + (i * 2 * Math.PI) / ORBIT_DOTS, 8, 30);
        return { dot, x: 12 + p.x, y: 12 + p.y, r: 1.3 + p.depth * 1.6, o: 0.3 + p.depth * 0.7, z: p.z };
      });
      pts.forEach(({ dot, x, y, r, o }) => {
        dot.setAttribute('cx', x.toFixed(2));
        dot.setAttribute('cy', y.toFixed(2));
        dot.setAttribute('r', r.toFixed(2));
        dot.style.opacity = o.toFixed(2);
      });
      [...pts].sort((p, q) => p.z - q.z).forEach(({ dot }) => svg.current.appendChild(dot));   // nearer dots on top
    };
    draw();
    if (reduceMotion()) return undefined;
    const tick = (_t, dt) => { state.t += dt / 1000; draw(); };
    gsap.ticker.add(tick);
    return () => gsap.ticker.remove(tick);
  }, []);

  return (
    <svg ref={svg} className="orbit-mark" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      {Array.from({ length: ORBIT_DOTS }, (_, i) => <circle key={i} cx="12" cy="12" r="2" />)}
    </svg>
  );
}

// ── multi-agent, orbit style ──────────────────────────────────────────────────────────────────────
const SO = { c: 24, orbit: 10.5, ring: 18.5, focal: 34, cap: 8 };
const SO_CLASS = { running: 'is-running', completed: 'is-ok', failed: 'is-err', blocked: 'is-err', cancelled: 'is-stop' };
const isSettled = (status) => status === 'completed' || status === 'failed' || status === 'blocked' || status === 'cancelled';
const lerp = (a, b, k) => a + (b - a) * k;
const smooth = (k) => k * k * (3 - 2 * k);

export function SwarmOrbit({ agents = [], phase = 'working', size = 44 }) {
  const planning = agents.length === 0;
  const list = planning ? [{ status: 'queued' }, { status: 'queued' }, { status: 'queued' }] : agents.slice(0, SO.cap);
  const svg = useRef(null);
  const live = useRef(null);
  const api = useRef(null);
  live.current = { list, phase };
  const stateKey = `${phase}|${list.map((a) => a.status).join(',')}`;

  useLayoutEffect(() => {
    const el = svg.current;
    const group = el.querySelector('.so-dots');
    const core = el.querySelector('.so-core');
    const check = el.querySelector('.so-check');
    const still = reduceMotion();
    const S = { t: 0, dots: [], core: 0, check: 0, born: false };

    const frame = (dt) => {
      const { list: agentList, phase: ph } = live.current;
      const n = agentList.length;
      const byIndex = {};
      [...group.children].forEach((c) => { byIndex[c.dataset.i] = c; });
      while (S.dots.length < n) {
        const i = S.dots.length;
        S.dots.push({ a: i * 2.4, w: 2.7 + (i % 3) * 0.28, settle: 0, appear: S.born ? 0 : 1, cls: '' });
      }
      S.t += dt;
      const rate = (r) => (still ? 1 : 1 - Math.exp(-dt * r));
      const placed = [];
      agentList.forEach((ag, i) => {
        const d = S.dots[i];
        const c = byIndex[i];
        if (!c) return;
        const done = isSettled(ag.status);
        const running = ag.status === 'running';
        if (!S.born) d.settle = done ? 1 : 0;                         // first paint shows the state, no flight
        d.settle += ((done ? 1 : 0) - d.settle) * rate(3.6);
        d.appear += (1 - d.appear) * rate(5);
        d.a += dt * (running ? d.w : 1.1) * (1 - d.settle);
        const p = orbitPoint(S.t, d.a, SO.orbit, SO.focal);
        const s = smooth(Math.min(1, d.settle));
        const slot = -Math.PI / 2 + (i * 2 * Math.PI) / n;
        const grow = smooth(d.appear);
        const x = lerp(SO.c, lerp(SO.c + p.x, SO.c + SO.ring * Math.cos(slot), s), grow);
        const y = lerp(SO.c, lerp(SO.c + p.y, SO.c + SO.ring * Math.sin(slot), s), grow);
        const orbitOpacity = running ? 0.4 + 0.6 * p.depth : 0.18 + 0.3 * p.depth;
        c.setAttribute('cx', x.toFixed(2));
        c.setAttribute('cy', y.toFixed(2));
        c.setAttribute('r', (lerp(1.7 + p.depth * 2.1, 2.8, s) * grow).toFixed(2));
        c.style.opacity = (lerp(orbitOpacity, ag.status === 'completed' ? 0.95 : 0.5, s) * grow).toFixed(2);
        const cls = `so-dot ${SO_CLASS[ag.status] || 'is-queued'}`;
        if (d.cls !== cls) { c.setAttribute('class', cls); d.cls = cls; }
        placed.push({ c, z: lerp(p.z, 0, s) });
      });
      S.born = true;
      placed.sort((a, b) => a.z - b.z).forEach(({ c }) => group.appendChild(c));   // nearer dots on top

      // once everyone has finished the results are combined (a pulsing core), then a check is drawn
      S.core += ((['comparing', 'approval', 'acting'].includes(ph) ? 1 : 0) - S.core) * rate(4);
      S.check += ((ph === 'done' ? 1 : 0) - S.check) * rate(3.5);
      const pulse = ph === 'comparing' && !still ? 1 + 0.28 * Math.sin(S.t * 6) : 1;
      core.setAttribute('r', (3.2 * smooth(S.core) * pulse).toFixed(2));
      core.style.opacity = smooth(S.core).toFixed(2);
      check.style.strokeDashoffset = (1 - smooth(S.check)).toFixed(3);
      check.style.opacity = Math.min(1, S.check * 2).toFixed(2);
    };

    frame(0);
    api.current = { still, frame };
    if (still) return () => { api.current = null; };
    const tick = (_t, ms) => frame(Math.min(0.05, ms / 1000));
    gsap.ticker.add(tick);
    return () => { gsap.ticker.remove(tick); api.current = null; };
  }, []);

  // reduced motion has no ticker: repaint when something changed
  useLayoutEffect(() => { if (api.current?.still) api.current.frame(0); }, [stateKey]);

  const working = list.filter((a) => a.status === 'running').length;
  return (
    <svg ref={svg} className="swarm-orbit" width={size} height={size} viewBox="0 0 48 48" role="img"
      aria-label={planning ? 'Splitting the task between agents' : `${working} of ${list.length} agents working`}>
      <circle className="so-ring" cx={SO.c} cy={SO.c} r={SO.ring} />
      <circle className="so-core" cx={SO.c} cy={SO.c} r="0" />
      <path className="so-check" d="M18 24.5 l4.2 4.2 l7.8 -9" pathLength="1" strokeDasharray="1" strokeDashoffset="1" />
      <g className="so-dots">
        {list.map((_, i) => <circle key={i} data-i={i} className="so-dot is-queued" cx={SO.c} cy={SO.c} r="0" />)}
      </g>
    </svg>
  );
}

// One line of text. The light moving through it is a CSS variable animated here; a changed text rises in as the old one lifts away.
export function ShimmerLabel({ text, className = '' }) {
  const box = useRef(null);

  useLayoutEffect(() => {
    if (reduceMotion()) return undefined;
    const sweep = gsap.fromTo(box.current, { '--shine': 100 }, { '--shine': 0, duration: 2.3, ease: 'none', repeat: -1, repeatDelay: 0.25 });
    return () => sweep.kill();
  }, []);

  useLayoutEffect(() => {
    const el = box.current;
    const current = el.lastElementChild;
    if (current && current.textContent === text) return;
    [...el.children].slice(0, -1).forEach((c) => { gsap.killTweensOf(c); c.remove(); });   // still leaving from an earlier change
    const next = document.createElement('span');
    next.textContent = text;
    el.appendChild(next);
    if (!current) return;
    if (reduceMotion()) { current.remove(); return; }
    current.setAttribute('aria-hidden', 'true');
    gsap.to(current, { opacity: 0, y: -7, filter: 'blur(3px)', duration: 0.22, ease: 'power2.in', onComplete: () => current.remove() });
    gsap.fromTo(next, { opacity: 0, y: 8, filter: 'blur(3px)' }, { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.5, ease: 'power3.out', delay: 0.12, clearProps: 'filter,transform' });
  }, [text]);

  return <span ref={box} className={`shimmer ${className}`} />;
}

// ── multi-agent ─────────────────────────────────────────────────────────────────────────────────
const HUB = { x: 24, y: 60 };
const RESULT = { x: 282, y: 60, r: 14 };
const WIN = { x: 108, w: 100 };
const RING = 2 * Math.PI * RESULT.r;

function layout(n) {
  const gap = 6;
  const h = Math.min(27, (112 - gap * (n - 1)) / n);
  const total = n * h + (n - 1) * gap;
  const y0 = 60 - total / 2;
  return Array.from({ length: n }, (_, i) => ({ y: y0 + i * (h + gap), h, cy: y0 + i * (h + gap) + h / 2 }));
}
const pathIn = (cy) => `M${HUB.x + 9} ${HUB.y} C ${HUB.x + 40} ${HUB.y}, ${WIN.x - 38} ${cy}, ${WIN.x} ${cy}`;
const pathOut = (cy) => `M${WIN.x + WIN.w} ${cy} C ${WIN.x + WIN.w + 32} ${cy}, ${RESULT.x - RESULT.r - 30} ${RESULT.y}, ${RESULT.x - RESULT.r} ${RESULT.y}`;

export function SwarmStage({ agents = [], phase = 'working' }) {
  const planning = agents.length === 0;
  const list = planning ? [{ status: 'queued', stepCount: 0 }, { status: 'queued', stepCount: 0 }, { status: 'queued', stepCount: 0 }] : agents.slice(0, 4);
  const n = list.length;
  const rows = layout(n);
  const root = useRef(null);
  const api = useRef(null);
  const prev = useRef(null);

  useLayoutEffect(() => {
    const el = root.current;
    const still = reduceMotion();
    const ctx = gsap.context(() => {
      if (!still) {
        // the planner breathes
        gsap.to(el.querySelector('.sw-hub-ring'), { scale: 1.5, opacity: 0, duration: 1.8, repeat: -1, ease: 'power1.out', transformOrigin: '50% 50%' });
      }
    }, el);
    api.current = { still, ctx, loops: {} };
    return () => { Object.values(api.current?.loops || {}).forEach((l) => l.forEach((t) => t.kill())); ctx.revert(); api.current = null; prev.current = null; };
  }, [n, planning]);

  // react to agents changing state: dispatch, steps, finishing, comparing
  useEffect(() => {
    const a = api.current;
    if (!a) return;
    const el = root.current;
    const pulse = (d, cls, dur = 0.75, r = 3) => {
      if (a.still) return;
      const c = document.createElementNS(SVG_NS, 'circle');
      c.setAttribute('r', String(r));
      c.setAttribute('class', `sw-pulse ${cls}`);
      el.appendChild(c);
      const p = document.createElementNS(SVG_NS, 'path');
      p.setAttribute('d', d);
      gsap.fromTo(c, { opacity: 0 }, { opacity: 1, duration: 0.15 });
      gsap.to(c, { duration: dur, ease: 'power2.inOut', motionPath: { path: p, align: p, alignOrigin: [0.5, 0.5] },
        onComplete: () => gsap.to(c, { opacity: 0, scale: 0.2, duration: 0.2, transformOrigin: '50% 50%', onComplete: () => c.remove() }) });
    };
    const done = list.filter((x) => x.status === 'completed').length;
    const ring = el.querySelector('.sw-ring-fill');
    const target = RING * (1 - (n ? done / n : 0));
    const before = prev.current;
    if (!before) {
      gsap.set(ring, { strokeDashoffset: target });
    } else {
      list.forEach((ag, i) => {
        const was = before[i];
        if (was && ag.status === 'running' && was.status !== 'running') pulse(pathIn(rows[i].cy), 'is-run', 0.7);
        if (was && ag.status === 'completed' && was.status !== 'completed') pulse(pathOut(rows[i].cy), 'is-ok', 0.8);
        if (was && (ag.stepCount || 0) > (was.stepCount || 0) && !a.still) {
          const bar = el.querySelectorAll(`.sw-win-${i} .sw-bar`)[Math.min(ag.stepCount - 1, 3)];
          if (bar) gsap.fromTo(bar, { opacity: 0.95 }, { opacity: 0.4, duration: 0.9, ease: 'power2.out' });
        }
      });
      if (!a.still) gsap.to(ring, { strokeDashoffset: target, duration: 0.8, ease: 'power3.out' });
      else gsap.set(ring, { strokeDashoffset: target });
    }
    // first dispatch for agents that are already running when this mounts
    if (!before && !a.still) list.forEach((ag, i) => { if (ag.status === 'running') gsap.delayedCall(0.15 + i * 0.12, () => pulse(pathIn(rows[i].cy), 'is-run', 0.7)); });
    // while a window is running it is read by a slow scan and streams small packets toward the result
    if (!a.still) {
      list.forEach((ag, i) => {
        const live = a.loops[i];
        const scanEl = el.querySelector(`.sw-win-${i} .sw-scan`);
        if (ag.status === 'running' && scanEl && !live) {
          const scanT = gsap.fromTo(scanEl, { x: 0 }, { x: WIN.w - 14, duration: 2.1, ease: 'power1.inOut', repeat: -1, repeatDelay: 0.5, delay: i * 0.35 });
          const flowT = gsap.timeline({ repeat: -1, repeatDelay: 1.7, delay: 0.8 + i * 0.45 }).call(() => pulse(pathOut(rows[i].cy), 'is-run', 1.0, 2.2));
          a.loops[i] = [scanT, flowT];
        } else if (ag.status !== 'running' && live) {
          live.forEach((t) => t.kill());
          delete a.loops[i];
        }
      });
    }
    prev.current = list.map((x) => ({ status: x.status, stepCount: x.stepCount || 0 }));
  }, [list.map((x) => `${x.status}:${x.stepCount || 0}`).join('|'), n]);

  // phases: while comparing, the lines converge and the result node pulses; when done it settles
  useEffect(() => {
    const a = api.current;
    if (!a || a.still) return undefined;
    const el = root.current;
    const node = el.querySelector('.sw-result');
    if (phase !== 'comparing') { gsap.set(node, { scale: 1, transformOrigin: '50% 50%' }); return undefined; }
    const t = gsap.to(node, { scale: 1.14, duration: 0.7, yoyo: true, repeat: -1, ease: 'sine.inOut', transformOrigin: '50% 50%' });
    const conv = gsap.delayedCall(0, function loop() {
      rows.forEach((r, i) => gsap.delayedCall(i * 0.12, () => {
        const c = document.createElementNS(SVG_NS, 'circle');
        c.setAttribute('r', '3'); c.setAttribute('class', 'sw-pulse is-ok'); el.appendChild(c);
        const p = document.createElementNS(SVG_NS, 'path'); p.setAttribute('d', pathOut(r.cy));
        gsap.to(c, { duration: 0.8, ease: 'power2.inOut', motionPath: { path: p, align: p, alignOrigin: [0.5, 0.5] }, onComplete: () => c.remove() });
      }));
      gsap.delayedCall(1.3, loop);
    });
    return () => { t.kill(); conv.kill(); gsap.set(node, { scale: 1 }); };
  }, [phase, n]);

  const allDone = n > 0 && list.every((x) => x.status === 'completed') && (phase === 'done');
  return (
    <svg ref={root} className="stage stage-swarm" viewBox="0 0 312 120" role="img"
      aria-label={planning ? 'Splitting the task between agents' : `${list.filter((x) => x.status === 'completed').length} of ${n} agents finished`}>
      {rows.map((r, i) => (
        <g key={`l${i}`}>
          <path className={`sw-line ${list[i].status === 'queued' ? 'is-queued' : ''}`} d={pathIn(r.cy)} />
          <path className={`sw-line ${list[i].status === 'completed' ? 'is-ok' : 'is-queued'}`} d={pathOut(r.cy)} />
        </g>
      ))}
      <circle className="sw-hub-ring" cx={HUB.x} cy={HUB.y} r="9" />
      <circle className="sw-hub" cx={HUB.x} cy={HUB.y} r="9" />
      <circle className="sw-hub-dot" cx={HUB.x} cy={HUB.y} r="3" />
      {rows.map((r, i) => {
        const ag = list[i];
        const lit = Math.min(ag.stepCount || 0, 4);
        return (
          <g key={`w${i}`} className={`sw-win sw-win-${i} is-${ag.status}`}>
            <rect className="sw-frame" x={WIN.x} y={r.y} width={WIN.w} height={r.h} rx="6" />
            <rect className="sw-addr" x={WIN.x + 8} y={r.y + 5} width="38" height="3" rx="1.5" />
            {[0, 1, 2, 3].map((k) => (
              <rect key={k} className={`sw-bar ${k < lit ? 'is-lit' : ''}`} x={WIN.x + 8 + k * 21} y={r.y + r.h - 10} width="17" height="4" rx="2" />
            ))}
            {ag.status === 'running' && <rect className="sw-scan" data-x0={WIN.x + 4} x={WIN.x + 4} y={r.y + 3} width="1.4" height={r.h - 6} rx="0.7" />}
            {ag.status === 'completed' && <path className="sw-tick" d={`M${WIN.x + WIN.w - 17} ${r.cy} l3 3 l6 -7`} />}
            {(ag.status === 'failed' || ag.status === 'blocked') && <path className="sw-cross" d={`M${WIN.x + WIN.w - 16} ${r.cy - 4} l8 8 M${WIN.x + WIN.w - 8} ${r.cy - 4} l-8 8`} />}
          </g>
        );
      })}
      <g className="sw-result">
        <circle className="sw-ring-bg" cx={RESULT.x} cy={RESULT.y} r={RESULT.r} />
        <circle className="sw-ring-fill" cx={RESULT.x} cy={RESULT.y} r={RESULT.r} strokeDasharray={RING} strokeDashoffset={RING} transform={`rotate(-90 ${RESULT.x} ${RESULT.y})`} />
        {allDone
          ? <path className="sw-tick sw-tick-big" d={`M${RESULT.x - 5} ${RESULT.y} l4 4 l7 -8`} />
          : <circle className="sw-result-dot" cx={RESULT.x} cy={RESULT.y} r="3" />}
      </g>
    </svg>
  );
}
