import { useId } from 'react';

/**
 * Canonical HealthFlow brand mark. The gradient + accent stroke are part of
 * the identity, so reuse this component everywhere a HealthFlow logo appears
 * (sidebar, login, landing nav/footer) instead of inlining one-off SVGs.
 * `useId` gives each instance a unique gradient id so multiple logos on the
 * same page don't collide.
 */
export default function BrandLogo({ size = 30, className = '' }) {
  const gid = `hfLogo-${useId().replace(/[:]/g, '')}`;
  return (
    <span className={`hf-mark ${className}`.trim()} aria-hidden="true" style={{ width: size, height: size, display: 'inline-flex' }}>
      <svg viewBox="0 0 32 32" width={size} height={size} fill="none" strokeLinecap="round" strokeLinejoin="round">
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="oklch(0.66 0.14 190)" />
            <stop offset="1" stopColor="oklch(0.44 0.13 222)" />
          </linearGradient>
        </defs>
        <rect x="1" y="1" width="30" height="30" rx="9" fill={`url(#${gid})`} />
        <path d="M9 7 L9 25" strokeWidth="2.4" stroke="#fff" />
        <path d="M23 7 L23 25" strokeWidth="2.4" stroke="#fff" />
        <path d="M9 16 C 13 13, 19 19, 23 16" strokeWidth="2.4" stroke="oklch(0.78 0.18 45)" />
        <circle cx="23" cy="16" r="2.2" fill="oklch(0.78 0.18 45)" />
      </svg>
    </span>
  );
}
