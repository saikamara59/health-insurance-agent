import { useState, useEffect } from 'react';
import Icon from './Icon';

const THEMES = [
  { key: 'default', label: 'Warm', color: 'oklch(0.42 0.06 200)' },
  { key: 'slate', label: 'Slate', color: 'oklch(0.38 0.12 260)' },
  { key: 'moss', label: 'Moss', color: 'oklch(0.38 0.07 150)' },
  { key: 'ink', label: 'Ink', color: 'oklch(0.35 0.08 30)' },
];

const STORAGE_KEY = 'hf_tweaks';

function loadTweaks() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* noop */
  }
  return { theme: 'default', density: 'comfortable', mode: 'light' };
}

export default function Tweaks() {
  const [open, setOpen] = useState(false);
  const [vals, setVals] = useState(loadTweaks);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', vals.theme);
    document.documentElement.setAttribute('data-density', vals.density);
    document.documentElement.setAttribute('data-mode', vals.mode);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(vals));
    } catch {
      /* noop */
    }
  }, [vals]);

  const set = (k, v) => setVals((prev) => ({ ...prev, [k]: v }));

  if (!open) {
    return (
      <button className="tweaks-trigger" onClick={() => setOpen(true)} title="Customize appearance">
        <Icon name="sliders" size={14} />
        <span>Tweaks</span>
      </button>
    );
  }

  return (
    <div className="tweaks">
      <header>
        <h3>Tweaks</h3>
        <button onClick={() => setOpen(false)} className="muted" style={{ fontSize: 12 }}>hide</button>
      </header>
      <div className="body">
        <div>
          <label>Accent theme</label>
          <div className="swatches">
            {THEMES.map((t) => (
              <div
                key={t.key}
                className={`swatch ${vals.theme === t.key ? 'on' : ''}`}
                style={{ background: t.color }}
                onClick={() => set('theme', t.key)}
                title={t.label}
              />
            ))}
          </div>
        </div>
        <div>
          <label>Mode</label>
          <div className="opts">
            {['light', 'dark'].map((m) => (
              <button key={m} className={`opt ${vals.mode === m ? 'on' : ''}`} onClick={() => set('mode', m)}>
                {m}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label>Density</label>
          <div className="opts">
            {['comfortable', 'compact'].map((d) => (
              <button key={d} className={`opt ${vals.density === d ? 'on' : ''}`} onClick={() => set('density', d)}>
                {d}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function ThemeToggle() {
  const [mode, setMode] = useState(() => document.documentElement.getAttribute('data-mode') || 'light');

  useEffect(() => {
    document.documentElement.setAttribute('data-mode', mode);
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const prev = raw ? JSON.parse(raw) : {};
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...prev, mode }));
    } catch {
      /* noop */
    }
  }, [mode]);

  const toggle = () => setMode((m) => (m === 'dark' ? 'light' : 'dark'));

  return (
    <button
      className="btn icon ghost"
      title={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      onClick={toggle}
      aria-label="Toggle dark mode"
    >
      <Icon name={mode === 'dark' ? 'sun' : 'moon'} size={16} />
    </button>
  );
}

export function initTweaksFromStorage() {
  const v = loadTweaks();
  document.documentElement.setAttribute('data-theme', v.theme);
  document.documentElement.setAttribute('data-density', v.density);
  document.documentElement.setAttribute('data-mode', v.mode);
}
