import { useEffect, useRef, useState } from 'react';
import api from '../../api/client';
import Icon from './Icon';

const DEBOUNCE_MS = 300;
const RESULT_LIMIT = 8;
// RxNav's /drugs.json needs a full drug name; /approximateTerm.json starts
// returning candidates around 5 chars. Below this threshold we show a hint
// instead of an empty dropdown, which would look broken.
const MIN_QUERY_CHARS = 4;

// Shared drug autocomplete (RxNav-backed via GET /drugs/search).
// Stores selected drug NAMES as strings in `values`. Typed-but-unmatched
// text is accepted on Enter (RxNorm doesn't have every brand-new drug).
//
// Props:
//   values:      string[]   - current drug names
//   onChange:    (string[]) => void
//   placeholder: string?
export default function DrugAutocomplete({ values, onChange, placeholder = 'Medication name' }) {
  const [input, setInput] = useState('');
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const containerRef = useRef(null);
  // Track the latest fired query so out-of-order responses don't overwrite
  // newer state (user typed "metf" then "metfo" — "metf" must not win).
  const latestQueryRef = useRef('');

  // Debounced fetch on input change.
  useEffect(() => {
    const q = input.trim();
    if (!q) {
      setMatches([]);
      setOpen(false);
      latestQueryRef.current = '';
      return;
    }
    if (q.length < MIN_QUERY_CHARS) {
      setMatches([]);
      setOpen(true);  // open so the "keep typing" hint shows
      latestQueryRef.current = q;
      setLoading(false);
      return;
    }
    latestQueryRef.current = q;
    setLoading(true);
    const handle = setTimeout(async () => {
      try {
        const res = await api.get(`/drugs/search?q=${encodeURIComponent(q)}&limit=${RESULT_LIMIT}`);
        // Discard if a newer query has started since this one was fired.
        if (latestQueryRef.current !== q) return;
        setMatches(Array.isArray(res?.matches) ? res.matches : []);
        setOpen(true);
        setHighlight(-1);
      } catch {
        if (latestQueryRef.current !== q) return;
        // Silent — autocomplete should never block typing on a backend hiccup.
        setMatches([]);
        setOpen(false);
      } finally {
        if (latestQueryRef.current === q) setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [input]);

  // Close dropdown on click outside.
  useEffect(() => {
    const onDocClick = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const addValue = (name) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    // Skip duplicates (case-insensitive).
    if (values.some((v) => v.toLowerCase() === trimmed.toLowerCase())) {
      setInput('');
      setOpen(false);
      return;
    }
    onChange([...values, trimmed]);
    setInput('');
    setMatches([]);
    setOpen(false);
    setHighlight(-1);
  };

  const remove = (i) => onChange(values.filter((_, j) => j !== i));

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (open && highlight >= 0 && matches[highlight]) {
        addValue(matches[highlight].name);
      } else if (input.trim()) {
        // Typed fallback — accept raw text even if RxNav had no match.
        addValue(input);
      }
    } else if (e.key === 'ArrowDown') {
      if (matches.length === 0) return;
      e.preventDefault();
      setHighlight((h) => (h + 1) % matches.length);
      setOpen(true);
    } else if (e.key === 'ArrowUp') {
      if (matches.length === 0) return;
      e.preventDefault();
      setHighlight((h) => (h <= 0 ? matches.length - 1 : h - 1));
      setOpen(true);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <div className="input-group">
        <input
          className="input"
          placeholder={placeholder}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => { if (matches.length > 0) setOpen(true); }}
          autoComplete="off"
        />
        <button type="button" className="btn" onClick={() => addValue(input)} disabled={!input.trim()}>
          Add
        </button>
      </div>

      {open && (matches.length > 0 || loading || (input.trim().length > 0 && input.trim().length < MIN_QUERY_CHARS)) && (
        <div
          role="listbox"
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            right: 0,
            zIndex: 20,
            background: 'var(--card)',
            border: '1px solid var(--line)',
            borderRadius: 6,
            boxShadow: '0 6px 24px rgba(0, 0, 0, 0.08)',
            maxHeight: 280,
            overflowY: 'auto',
          }}
        >
          {input.trim().length > 0 && input.trim().length < MIN_QUERY_CHARS && (
            <div className="muted" style={{ padding: '10px 14px', fontSize: 12 }}>
              Keep typing… (RxNav needs at least {MIN_QUERY_CHARS} characters)
            </div>
          )}
          {loading && matches.length === 0 && input.trim().length >= MIN_QUERY_CHARS && (
            <div className="muted" style={{ padding: '10px 14px', fontSize: 12 }}>
              Searching RxNav…
            </div>
          )}
          {matches.map((m, i) => (
            <div
              key={m.rxcui}
              role="option"
              aria-selected={i === highlight}
              onMouseDown={(e) => { e.preventDefault(); addValue(m.name); }}
              onMouseEnter={() => setHighlight(i)}
              style={{
                padding: '8px 14px',
                cursor: 'pointer',
                background: i === highlight ? 'var(--bg-2)' : 'transparent',
                borderBottom: i < matches.length - 1 ? '1px solid var(--line)' : 0,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                fontSize: 13.5,
              }}
            >
              <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {m.name}
              </span>
              <span
                className="mono"
                style={{
                  fontSize: 10,
                  color: 'var(--ink-4)',
                  padding: '2px 6px',
                  border: '1px solid var(--line)',
                  borderRadius: 3,
                  flex: '0 0 auto',
                }}
                title={m.is_brand ? 'Branded drug' : 'Clinical / generic'}
              >
                {m.is_brand ? 'BRAND' : 'GENERIC'}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="row" style={{ gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
        {values.map((v, i) => (
          <span key={i} className="chip">
            {v}
            <button
              type="button"
              onClick={() => remove(i)}
              style={{ marginLeft: 4, color: 'var(--ink-4)' }}
              aria-label={`Remove ${v}`}
            >
              <Icon name="x" size={10} />
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}
