import { useMemo } from 'react';
import { motion } from 'framer-motion';
import segments from '@shared/matchstick_segments.json';

const DIGITS = segments.digits;
const OPERATORS = segments.operators;
const GEOMETRY = segments.geometry;

function kindOf(symbol) {
  if (DIGITS[symbol]) return 'digit';
  if (OPERATORS[symbol]) return 'operator';
  return null;
}

function geometryFor(symbol, segment) {
  const kind = kindOf(symbol);
  if (!kind) return null;
  return GEOMETRY[kind]?.[segment] ?? null;
}

const COLUMN_WIDTH = 110;
const ORIGIN_X = 12;
const ORIGIN_Y = 8;

function offsetGeometry(geometry, symbolIndex) {
  const dx = symbolIndex * COLUMN_WIDTH + ORIGIN_X;
  return [
    geometry[0] + dx,
    geometry[1] + ORIGIN_Y,
    geometry[2] + dx,
    geometry[3] + ORIGIN_Y,
  ];
}

export function buildSticks(payload) {
  if (!payload?.symbols || !payload?.start) return [];
  const moves = Array.isArray(payload.moves) ? payload.moves : [];
  const targets = new Map();
  for (const move of moves) {
    const key = `${move?.from?.symbol}:${move?.from?.segment}`;
    const targetIndex = Number(move?.to?.symbol);
    const targetGeometry = geometryFor(
      payload.symbols[targetIndex],
      move?.to?.segment,
    );
    if (targetGeometry) {
      targets.set(key, { geometry: targetGeometry, symbolIndex: targetIndex });
    }
  }
  const sticks = [];
  payload.symbols.forEach((symbol, symbolIndex) => {
    const startSegments = payload.start[symbolIndex] ?? [];
    startSegments.forEach((segment) => {
      const start = geometryFor(symbol, segment);
      if (!start) return;
      const key = `${symbolIndex}:${segment}`;
      const target = targets.get(key);
      sticks.push({
        key,
        sourceSymbolIndex: symbolIndex,
        targetSymbolIndex: target ? target.symbolIndex : symbolIndex,
        segment,
        from: offsetGeometry(start, symbolIndex),
        to: offsetGeometry(
          target ? target.geometry : start,
          target ? target.symbolIndex : symbolIndex,
        ),
        moved: Boolean(target),
      });
    });
  });
  return sticks;
}

export default function MatchstickRenderer({ question, revealed = false }) {
  const payload = question?.matchstick ?? question?.payload ?? null;
  const sticks = useMemo(() => buildSticks(payload), [payload]);
  const symbolCount = payload?.symbols?.length ?? 0;
  const width = Math.max(360, symbolCount * 110 + 24);
  const movesRequired = Number(payload?.moves_required ?? 1);
  const solution = payload?.solution ?? '';

  if (!payload || sticks.length === 0) {
    return (
      <div className="mx-auto grid h-32 w-full max-w-xl place-items-center rounded-2xl border border-white/10 bg-white/[0.03] text-xs text-stone-600">
        تعذّر عرض لغز الأعواد.
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center gap-2">
      <div
        className="w-full overflow-hidden rounded-2xl border border-orange-400/20 bg-gradient-to-b from-slate-900/80 to-slate-950/90 px-2 py-2 shadow-panel"
        role="img"
        aria-label={`معادلة أعواد الثقاب ${payload.equation}${revealed ? `، الحل ${solution}` : ''}`}
      >
        <svg
          viewBox={`0 0 ${width} 164`}
          className="h-auto w-full"
          xmlns="http://www.w3.org/2000/svg"
          focusable="false"
        >
          <defs>
            <linearGradient id="matchstick-wood" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#fbbf24" />
              <stop offset="55%" stopColor="#f59e0b" />
              <stop offset="100%" stopColor="#b45309" />
            </linearGradient>
          </defs>
          {sticks.map((stick, index) => {
            const delay = revealed && stick.moved ? index * 0.08 : 0;
            return (
              <g key={stick.key}>
                <motion.line
                  initial={false}
                  x1={stick.from[0]}
                  y1={stick.from[1]}
                  x2={stick.from[2]}
                  y2={stick.from[3]}
                  animate={{
                    x1: revealed ? stick.to[0] : stick.from[0],
                    y1: revealed ? stick.to[1] : stick.from[1],
                    x2: revealed ? stick.to[2] : stick.from[2],
                    y2: revealed ? stick.to[3] : stick.from[3],
                  }}
                  transition={{ duration: 0.85, delay, ease: 'easeInOut' }}
                  stroke="url(#matchstick-wood)"
                  strokeWidth="7"
                  strokeLinecap="round"
                  opacity={stick.moved ? 1 : 0.92}
                />
                <motion.circle
                  initial={false}
                  cx={stick.from[2]}
                  cy={stick.from[3]}
                  animate={{
                    cx: revealed ? stick.to[2] : stick.from[2],
                    cy: revealed ? stick.to[3] : stick.from[3],
                  }}
                  transition={{ duration: 0.85, delay, ease: 'easeInOut' }}
                  r="5.2"
                  fill={stick.moved ? '#fde68a' : '#fbbf24'}
                  stroke="#7c2d12"
                  strokeWidth="1.2"
                />
              </g>
            );
          })}
        </svg>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-[10px] text-stone-600">
        <span className="rounded-full border border-orange-400/25 bg-orange-400/10 px-2 py-0.5 font-bold text-brand-700">
          {movesRequired === 1 ? 'حرّك عودًا واحدًا' : 'حرّك عودين فقط'}
        </span>
        <span>الأعواد محفوظة العدد قبل الحل وبعده</span>
        {revealed && solution ? (
          <span className="font-bold text-brand-700">الحل: {solution}</span>
        ) : null}
      </div>
    </div>
  );
}
