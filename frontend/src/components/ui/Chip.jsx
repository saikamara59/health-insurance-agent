export default function Chip({ tone = '', children, dot = false, style, onClick }) {
  return (
    <span className={`chip ${tone}`} style={style} onClick={onClick}>
      {dot && <span className="dot" />}
      {children}
    </span>
  );
}
