import { formatClock, PRIMARY_MS } from '../game/timer.js';

/**
 * عدّاد ساعة مفتوحة: يعرض الوقت المنقضي منذ فتح السؤال. الحلقة تمثل دورة
 * عرض مدتها دقيقة، لكنها لا تفرض أي حد زمني على السؤال.
 */
export default function RadialTimer({
  elapsedMs = 0,
  cycleMs = PRIMARY_MS,
  running = false,
  size = 'lg',
}) {
  const safeCycle = Math.max(1000, cycleMs || PRIMARY_MS);
  const safeElapsed = Math.max(0, elapsedMs);
  const fraction = Math.min(1, (safeElapsed % safeCycle) / safeCycle);

  const dimensions = size === 'sm' ? 'h-24 w-24' : 'h-40 w-40 xl:h-48 xl:w-48';
  const radius = size === 'sm' ? 42 : 74;
  const stroke = size === 'sm' ? 6 : 9;
  const viewBox = size === 'sm' ? '0 0 100 100' : '0 0 168 168';
  const center = size === 'sm' ? 50 : 84;
  const circumference = 2 * Math.PI * radius;
  const color = running ? '#16836c' : '#7a6b60';

  return (
    <div
      className={`relative ${dimensions} shrink-0`}
      role="timer"
      aria-label={`وقت السؤال المفتوح، منقضي ${formatClock(safeElapsed)}`}
    >
      <svg
        viewBox={viewBox}
        className="-rotate-90"
        aria-hidden="true"
        focusable="false"
      >
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="rgba(148,163,184,0.16)"
          strokeWidth={stroke}
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - fraction)}
          style={{
            transition: 'stroke-dashoffset 180ms linear, stroke 300ms ease',
            filter: `drop-shadow(0 0 8px ${color}66)`,
          }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center rounded-full bg-white">
        <span
          className={`ltr tv-number font-black leading-none ${
            size === 'sm' ? 'text-xl' : 'text-4xl xl:text-5xl'
          }`}
          style={{ color }}
        >
          {formatClock(safeElapsed)}
        </span>
        <span
          className={`mt-1 font-bold ${
            size === 'sm' ? 'text-xs' : 'text-[13px] xl:text-xs'
          } ${running ? 'text-emerald-700' : 'text-stone-600'}`}
        >
          الوقت المنقضي
        </span>
        {size !== 'sm' && (
          <span className="mt-0.5 text-xs text-stone-600">
            {running ? 'الساعة شغّالة' : 'متوقفة'}
          </span>
        )}
      </div>
      {running && (
        <span className="pointer-events-none absolute inset-0 rounded-full border border-emerald-400/30" />
      )}
    </div>
  );
}
