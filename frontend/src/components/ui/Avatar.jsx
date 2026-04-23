export default function Avatar({ name, size = 'sm', tint, style }) {
  const initials = (name || '?')
    .split(/\s+/)
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();
  const sizeCls = size === 'lg' ? 'lg' : size === 'md' ? 'md' : '';
  const merged = tint ? { background: tint, ...style } : style;
  return <span className={`avatar ${sizeCls}`} style={merged}>{initials}</span>;
}
