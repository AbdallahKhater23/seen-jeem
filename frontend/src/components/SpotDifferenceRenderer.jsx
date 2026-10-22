import { useEffect, useMemo, useState } from 'react';
import { clientToSvgPoint, hitTestDifference } from '../game/spotHitTest.js';
import { SPOT_SCENES } from './spotScenes.jsx';
import Icon from './Icon.jsx';

const VIEW_BOX = { width: 400, height: 300 };

/**
 * خلفيات المشاهد الاثني عشر. الرسم نفسه بيانات من الخادم (`anchors`)، وهذه
 * الخلفية تعطي كل مشهد هويته البصرية فقط. أي تغيير في المراسي يجي من الحمولة
 * لا من هنا، حتى تبقى الفروقات الثلاثة متزامنة مع البيانات المفحوصة.
 */
const SCENE_META = Object.freeze({
  pitch: { title: 'ملعب كورة', sky: '#052e16', ground: '#166534', accent: '#4ade80' },
  locker: { title: 'غرفة الملابس', sky: '#0f172a', ground: '#1e293b', accent: '#fbbf24' },
  ucl_stage: { title: 'منصة دوري الأبطال', sky: '#0b1120', ground: '#1e3a8a', accent: '#93c5fd' },
  diwaniya: { title: 'ديوانية', sky: '#2a1a12', ground: '#3f2d1d', accent: '#f59e0b' },
  towers: { title: 'كورنيش أبراج الكويت', sky: '#082f49', ground: '#0c4a6e', accent: '#67e8f9' },
  studio: { title: 'استوديو البث', sky: '#1e1b4b', ground: '#312e81', accent: '#c4b5fd' },
  var_room: { title: 'غرفة تقنية الفيديو', sky: '#020617', ground: '#111827', accent: '#f87171' },
  desert_camp: { title: 'مخيّم بالبر', sky: '#451a03', ground: '#78350f', accent: '#fcd34d' },
  arcade: { title: 'أركيد قديم', sky: '#2e1065', ground: '#3b0764', accent: '#f0abfc' },
  cafe: { title: 'مقهى خارجي', sky: '#052e16', ground: '#14532d', accent: '#86efac' },
  airport: { title: 'بوابة المطار', sky: '#172554', ground: '#1e3a8a', accent: '#bfdbfe' },
  market: { title: 'سوق شعبي', sky: '#431407', ground: '#7c2d12', accent: '#fdba74' },
});

function ScenePanel({ label, children, interactive = false, onBackgroundClick = null, ariaLabel }) {
  return (
    <div className="min-w-0">
      <div className="mb-1.5 flex items-center justify-between px-1">
        <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-bold text-stone-600">
          {label}
        </span>
        {interactive && (
          <span className="flex items-center gap-1 text-[10px] font-bold text-cyan-300">
            <Icon name="Target" size={12} />
            اضغط على الفرق
          </span>
        )}
      </div>
      <div className="mx-auto w-full max-w-[34rem] overflow-hidden rounded-xl border border-white/10 bg-ink-950 shadow-panel">
        <svg
          viewBox={`0 0 ${VIEW_BOX.width} ${VIEW_BOX.height}`}
          className="block h-auto w-full select-none"
          role={interactive ? 'group' : 'img'}
          aria-label={ariaLabel}
          onClick={interactive ? onBackgroundClick : undefined}
        >
          {children}
        </svg>
      </div>
    </div>
  );
}

function starPoints(x, y, radius) {
  const points = [];
  for (let index = 0; index < 10; index += 1) {
    const r = index % 2 === 0 ? radius : radius * 0.45;
    const angle = (Math.PI / 5) * index - Math.PI / 2;
    points.push(`${(x + Math.cos(angle) * r).toFixed(2)},${(y + Math.sin(angle) * r).toFixed(2)}`);
  }
  return points.join(' ');
}

function AnchorShape({ anchor, mutation }) {
  if (!anchor) return null;
  if (mutation?.type === 'missing') return null;
  const shape = buildAnchorShape({ anchor, mutation });
  if (!shape) return null;
  return (
    <g data-anchor-id={anchor.id} data-mutation={mutation?.type ?? 'none'}>
      {shape}
    </g>
  );
}

function buildAnchorShape({ anchor, mutation }) {
  let width = anchor.w ?? 34;
  let height = anchor.h ?? 34;
  if (mutation?.type === 'scale') {
    const scale = Number(mutation.scale) || 1.4;
    width *= scale;
    height *= scale;
  }
  const fill = mutation?.type === 'color' ? mutation.to : anchor.color;
  const x = anchor.x;
  const y = anchor.y;
  const transform = mutation?.type === 'flip' ? `rotate(180 ${x} ${y})` : undefined;
  const common = { fill, stroke: 'rgba(255,255,255,0.35)', strokeWidth: 1.5, transform };
  if (anchor.shape === 'circle') {
    return <circle cx={x} cy={y} r={Math.min(width, height) / 2} {...common} />;
  }
  if (anchor.shape === 'triangle') {
    return (
      <polygon
        points={`${x},${y - height / 2} ${x - width / 2},${y + height / 2} ${x + width / 2},${y + height / 2}`}
        {...common}
      />
    );
  }
  if (anchor.shape === 'diamond') {
    return (
      <polygon
        points={`${x},${y - height / 2} ${x + width / 2},${y} ${x},${y + height / 2} ${x - width / 2},${y}`}
        {...common}
      />
    );
  }
  if (anchor.shape === 'star') {
    return <polygon points={starPoints(x, y, Math.min(width, height) / 2)} {...common} />;
  }
  if (anchor.shape === 'ring') {
    return (
      <circle
        cx={x}
        cy={y}
        r={Math.min(width, height) / 2}
        fill="none"
        stroke={fill}
        strokeWidth={6}
        transform={transform}
      />
    );
  }
  return (
    <rect
      x={x - width / 2}
      y={y - height / 2}
      width={width}
      height={height}
      rx={4}
      {...common}
    />
  );
}

function SceneBackdrop({ meta }) {
  return (
    <g aria-hidden="true">
      <rect width={VIEW_BOX.width} height={VIEW_BOX.height} fill={meta.sky} />
      <rect y={VIEW_BOX.height * 0.62} width={VIEW_BOX.width} height={VIEW_BOX.height * 0.38} fill={meta.ground} />
      <path
        d={`M0 ${VIEW_BOX.height * 0.62} L${VIEW_BOX.width} ${VIEW_BOX.height * 0.62}`}
        stroke={meta.accent}
        strokeOpacity="0.4"
        strokeWidth="2"
      />
      <circle cx={VIEW_BOX.width - 54} cy="46" r="22" fill={meta.accent} fillOpacity="0.16" />
      <circle cx={VIEW_BOX.width - 54} cy="46" r="12" fill={meta.accent} fillOpacity="0.35" />
    </g>
  );
}

function ParametricScene({ anchors, mutations, meta }) {
  const mutationById = useMemo(
    () => new Map((mutations ?? []).map((mutation) => [mutation.id, mutation])),
    [mutations],
  );
  return (
    <>
      <SceneBackdrop meta={meta} />
      {anchors
        .filter((anchor) => !mutationById.has(anchor.id))
        .map((anchor) => (
          <AnchorShape key={anchor.id} anchor={anchor} />
        ))}
      {anchors
        .filter((anchor) => mutationById.has(anchor.id))
        .map((anchor) => (
          <AnchorShape key={`m-${anchor.id}`} anchor={anchor} mutation={mutationById.get(anchor.id)} />
        ))}
      <text x="14" y="284" fill="rgba(255,255,255,0.45)" fontSize="9" fontWeight="700">
        {meta.title} — مشهد مولّد إجرائيًا
      </text>
    </>
  );
}

export default function SpotDifferenceRenderer({ question, revealed = false }) {
  const [found, setFound] = useState(() => new Set());
  const differences = useMemo(
    () => (Array.isArray(question?.differences) ? question.differences : []),
    [question?.differences],
  );
  const anchors = useMemo(
    () => (Array.isArray(question?.anchors) ? question.anchors : []),
    [question?.anchors],
  );
  const mutations = useMemo(
    () => (Array.isArray(question?.mutations) ? question.mutations : []),
    [question?.mutations],
  );
  const meta = SCENE_META[question?.sceneId] ?? SCENE_META.pitch;
  const legacyScene = anchors.length === 0 ? SPOT_SCENES[question?.sceneId] ?? SPOT_SCENES.towers : null;

  useEffect(() => {
    setFound(new Set());
  }, [question?.id]);

  const markFound = (differenceId) => {
    if (!differenceId) return;
    setFound((previous) => {
      if (previous.has(differenceId)) return previous;
      const next = new Set(previous);
      next.add(differenceId);
      return next;
    });
  };

  const handleBackgroundClick = (event) => {
    if (revealed) return;
    const point = clientToSvgPoint(
      event.clientX,
      event.clientY,
      event.currentTarget.getBoundingClientRect(),
      VIEW_BOX,
    );
    if (!point) return;
    const hit = hitTestDifference(differences, point.x, point.y);
    if (hit) markFound(hit.id);
  };

  const handleKey = (event, differenceId) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      markFound(differenceId);
    }
  };

  const foundCount = revealed ? differences.length : found.size;

  return (
    <section className="w-full rounded-2xl border border-blue-400/20 bg-blue-950/15 p-3 xl:p-4" aria-label="لعبة الفروقات">
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-blue-300">
          <Icon name="ScanSearch" size={16} />
          <h3 className="text-xs font-extrabold xl:text-sm">{meta.title}</h3>
          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[8px] font-bold text-stone-600">
            مولّد إجرائيًا
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full border px-2.5 py-1 text-[10px] font-black ${
              foundCount === 3
                ? 'border-emerald-400/40 bg-emerald-400/10 text-brand-700'
                : 'border-white/15 bg-white/5 text-stone-600'
            }`}
          >
            لقيته <span className="ltr">{foundCount}</span> من <span className="ltr">3</span>
          </span>
          {revealed && (
            <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-[10px] font-bold text-cyan-200">
              الفروقات ظاهرة
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ScenePanel label="الصورة أ" ariaLabel={`${meta.title}، الصورة أ`}>
          {legacyScene ? <legacyScene.Component variant="a" /> : <ParametricScene anchors={anchors} meta={meta} />}
        </ScenePanel>

        <ScenePanel
          label="الصورة ب"
          interactive
          ariaLabel={`${meta.title}، الصورة ب. اضغط على المناطق المختلفة`}
          onBackgroundClick={handleBackgroundClick}
        >
          {legacyScene ? (
            <legacyScene.Component variant="b" />
          ) : (
            <ParametricScene anchors={anchors} mutations={mutations} meta={meta} />
          )}
          {differences.map((difference, index) => {
            const isFound = found.has(difference.id) || revealed;
            return (
              <g
                key={difference.id}
                role="button"
                tabIndex={0}
                aria-label={`فرق ${index + 1}: ${revealed ? difference.label : 'ابحث هنا'}`}
                aria-pressed={isFound}
                onClick={(event) => {
                  event.stopPropagation();
                  markFound(difference.id);
                }}
                onKeyDown={(event) => handleKey(event, difference.id)}
                className="cursor-pointer outline-none"
              >
                <circle
                  cx={difference.x}
                  cy={difference.y}
                  r={Math.max(difference.r ?? 28, 22)}
                  fill="transparent"
                  className="stroke-transparent transition hover:stroke-white/50 focus:stroke-cyan-300"
                  strokeWidth="2"
                  strokeDasharray="5 5"
                />
                {isFound && (
                  <g className="pointer-events-none">
                    <circle
                      cx={difference.x}
                      cy={difference.y}
                      r={difference.r ?? 28}
                      fill="none"
                      stroke="#34d399"
                      strokeWidth="3"
                      className="motion-safe:animate-pulse-ring"
                      style={{ transformOrigin: `${difference.x}px ${difference.y}px` }}
                    />
                    <circle
                      cx={difference.x}
                      cy={difference.y}
                      r={(difference.r ?? 28) + 3}
                      fill="none"
                      stroke={revealed ? '#22d3ee' : '#34d399'}
                      strokeWidth="2.5"
                    />
                    <circle cx={difference.x} cy={difference.y} r="8" fill="#34d399" />
                    <path
                      d={`M${difference.x - 4} ${difference.y} l3 3 l5 -6`}
                      fill="none"
                      stroke="#052e16"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </g>
                )}
              </g>
            );
          })}
        </ScenePanel>
      </div>

      <div className="mt-3 min-h-[2.25rem] rounded-xl border border-white/10 bg-black/20 px-3 py-2">
        {revealed ? (
          <ul className="flex flex-wrap items-center gap-x-4 gap-y-1">
            {differences.map((difference) => (
              <li key={difference.id} className="flex items-center gap-1.5 text-[11px] font-bold text-brand-700">
                <Icon name="Check" size={12} />
                {difference.label}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[11px] text-stone-600">
            عندك ثلاث فرقات بين الصورتين. تقدر تضغط على الصورة ب أو تستخدم Tab ثم Enter لكل منطقة.
          </p>
        )}
      </div>
    </section>
  );
}
