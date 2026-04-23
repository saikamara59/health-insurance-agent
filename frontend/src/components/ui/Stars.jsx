import Icon from './Icon';

export default function Stars({ value = 0 }) {
  const full = Math.floor(value);
  return (
    <span className="rating">
      {[0, 1, 2, 3, 4].map((i) => (
        <span key={i} className={i < full ? 'f' : ''}>
          <Icon name="star" size={12} />
        </span>
      ))}
    </span>
  );
}
