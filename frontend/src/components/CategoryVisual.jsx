import Icon from './Icon.jsx';

const VISUALS = {
  flags: ['Flag', '#d9eaff', '#2962aa'], capitals: ['Globe2', '#cceee6', '#21796e'],
  football: ['Goal', '#e0edce', '#457431'], worldcup: ['Trophy', '#ffe9b4', '#a46d15'],
  career: ['Footprints', '#ecdffd', '#7853a5'], riddles: ['Lightbulb', '#ffe3bb', '#ba6a24'],
  spot: ['ScanEye', '#f9dcdf', '#b95767'], ucl: ['Star', '#dfe2ff', '#5554a0'],
  clubs: ['Shield', '#d2e5fa', '#326c9d'], arab_ftbl: ['Goal', '#f9d9ce', '#b35e41'],
  numbers: ['Hash', '#f8e5bd', '#a77d25'], general: ['Brain', '#e4dff4', '#776398'],
  quran: ['BookOpen', '#cfe9d9', '#3d7c58'], nicknames: ['Medal', '#fbe5b5', '#aa751f'],
  technology: ['Cpu', '#d4e9eb', '#337b86'], videogames: ['Gamepad2', '#e6ddf6', '#7c56a9'],
  matchstick: ['Flame', '#fbdcc7', '#bb6a37'],
  reverse: ['RotateCcw', '#fbd9e6', '#a83b6a'],
};

export default function CategoryVisual({ id, icon, className = '' }) {
  const [symbol, background, foreground] = VISUALS[id] ?? [icon || 'Sparkles', '#f5dfce', '#a46a42'];
  return (
    <span className={`category-visual ${className}`} style={{ '--art-bg': background, '--art-ink': foreground }} aria-hidden="true">
      <span className="category-visual__orbit" />
      <span className="category-visual__disc"><Icon name={symbol} size={58} strokeWidth={1.6} /></span>
      <svg viewBox="0 0 220 150" className="category-visual__details" fill="none">
        <path d="M28 35v14m-7-7h14M184 106v18m-9-9h18" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        <circle cx="179" cy="32" r="5" fill="currentColor" /><circle cx="39" cy="119" r="3" fill="currentColor" />
        <path d="M155 128l8-11 8 11-8 11zM51 21l6-8 6 8-6 8z" fill="currentColor" opacity=".5" />
      </svg>
    </span>
  );
}
