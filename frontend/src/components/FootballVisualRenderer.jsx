/** Original diagrams from server-validated data; never accept SVG/HTML markup. */
const safeText = (value, max = 120) => typeof value === 'string' && value.trim().length > 0
  && value.length <= max && !/[<>\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f]/u.test(value);
const visibleLabel = (item, revealed) => item.hidden && !revealed ? null : item.label;

function valid(visual, revealed) {
  if (!visual || visual.version !== 1 || (visual.title !== undefined && !safeText(visual.title))) return false;
  if (visual.type === 'career_tree') {
    return Array.isArray(visual.nodes) && visual.nodes.length >= 3 && visual.nodes.length <= 12
      && visual.nodes.every(node => node && (node.hidden === true && !revealed || safeText(node.label))
        && (node.years === undefined || safeText(node.years, 30)));
  }
  if (visual.type === 'lineup_svg') {
    return visual.schematic === true && safeText(visual.formation, 30)
      && Array.isArray(visual.players) && visual.players.length === 11
      && visual.players.filter(player => player?.hidden === true).length === 1
      && visual.players.every(player => player
        && [player.x, player.y].every(value => typeof value === 'number' && Number.isFinite(value) && value >= 5 && value <= 95)
        && (player.number === undefined || Number.isInteger(player.number) && player.number >= 1 && player.number <= 99)
        && (player.hidden === true && !revealed || safeText(player.label, 60)));
  }
  if (visual.type === 'shot_radar') {
    return visual.schematic === true
      && [visual.shot_x, visual.shot_y, visual.goal_x, visual.goal_y].every(value => typeof value === 'number' && Number.isFinite(value) && value >= 5 && value <= 95)
      && (visual.shot_x !== visual.goal_x || visual.shot_y !== visual.goal_y)
      && safeText(visual.context_label, 160)
      && (visual.answer_label === undefined || safeText(visual.answer_label, 120));
  }
  return visual.type === 'odd_one_out_grid' && Array.isArray(visual.items) && visual.items.length === 4
    && visual.items.every(item => item && safeText(item.label, 60))
    && (!revealed || (Number.isInteger(visual.odd_index) && visual.odd_index >= 0
      && visual.odd_index < 4 && safeText(visual.common_property, 300)));
}

function Lineup({ visual, revealed }) {
  return <>
    <p className="mb-2 text-base font-bold text-stone-600">رسم توضيحي للمراكز · <bdi>{visual.formation}</bdi></p>
    <div className="overflow-hidden rounded-2xl border-2 border-emerald-700 bg-emerald-900">
      <svg viewBox="0 0 800 500" className="block h-auto w-full" role="img" aria-label="ملعب فيه عشرة لاعبين ومكان اللاعب الناقص">
        <g fill="none" stroke="white" strokeOpacity="0.55" strokeWidth="2" aria-hidden="true">
          <rect x="18" y="18" width="764" height="464" rx="3" /><path d="M400 18V482" />
          <circle cx="400" cy="250" r="64" /><rect x="18" y="130" width="112" height="240" />
          <rect x="670" y="130" width="112" height="240" />
        </g>
        {visual.players.map((player, index) => {
          const label = visibleLabel(player, revealed);
          return <g key={index} transform={`translate(${player.x * 8} ${30 + player.y * 4.2})`}>
            <circle r="19" fill={label ? '#fffaf5' : '#f57928'} stroke="#382720" strokeWidth="2" />
            <text textAnchor="middle" dy="7" fontSize="22" fill="#382720" fontWeight="900">{label ? (player.number ?? '•') : '؟'}</text>
            <text textAnchor="middle" y="43" fontSize="19" fill="white" fontWeight="700">{label ?? 'اللاعب الناقص'}</text>
          </g>;
        })}
      </svg>
    </div>
    <ul className="sr-only">{visual.players.map((player, i) => <li key={i}>{visibleLabel(player, revealed) ?? 'اللاعب الناقص'}</li>)}</ul>
  </>;
}

export default function FootballVisualRenderer({ visual, revealed = false }) {
  if (!valid(visual, revealed)) {
    return <p role="status" dir="rtl" className="rounded-xl border border-orange-200 bg-orange-50 p-6 text-center text-lg text-ink-900">
      الرسم ما ظهر؛ كمّلوا من السؤال المكتوب.
    </p>;
  }
  return <figure dir="rtl" className="mx-auto w-full max-w-4xl rounded-2xl bg-white p-3 text-ink-900 sm:p-5">
    {visual.title && <figcaption className="mb-3 text-center text-xl font-black sm:text-2xl">{visual.title}</figcaption>}
    {visual.type === 'lineup_svg' && <Lineup visual={visual} revealed={revealed} />}
    {visual.type === 'career_tree' && <ol aria-label="مشوار اللاعب بالترتيب" className="grid gap-3 sm:grid-cols-3">
      {visual.nodes.map((node, i) => {
        const label = visibleLabel(node, revealed);
        return <li key={i} className={`flex min-h-28 min-w-0 flex-col items-center justify-center rounded-xl border-2 p-3 text-center ${label ? 'border-orange-200 bg-orange-50' : 'border-dashed border-brand-600 bg-white'}`}>
          <span className="mb-1 text-sm font-bold text-stone-600">المحطة {i + 1}</span>
          <span className="text-xl font-black sm:text-2xl">{label ?? 'النادي الناقص ؟'}</span>
          {label && node.years && <bdi className="mt-1 text-base text-stone-600">{node.years}</bdi>}
          {label && node.loan && <span className="mt-1 text-sm font-bold text-brand-700">إعارة</span>}
        </li>;
      })}
    </ol>}
    {visual.type === 'shot_radar' && <>
      <p className="mb-2 text-base font-bold text-stone-600">مخطط توضيحي لمكان التسديدة · <bdi>{visual.context_label}</bdi></p>
      <div className="overflow-hidden rounded-2xl border-2 border-emerald-700 bg-emerald-900">
        <svg viewBox="0 0 800 500" className="block h-auto w-full" role="img" aria-label="مخطط توضيحي لمكان التسديدة والمرمى">
          <g fill="none" stroke="white" strokeOpacity="0.55" strokeWidth="2" aria-hidden="true">
            <rect x="18" y="18" width="764" height="464" rx="3" /><path d="M400 18V482" />
            <circle cx="400" cy="250" r="64" /><rect x="18" y="130" width="112" height="240" />
            <rect x="670" y="130" width="112" height="240" />
          </g>
          <line x1={visual.shot_x * 8} y1={30 + visual.shot_y * 4.2} x2={visual.goal_x * 8} y2={30 + visual.goal_y * 4.2} stroke="#fbbf24" strokeWidth="4" strokeDasharray="10 6" />
          <g transform={`translate(${visual.shot_x * 8} ${30 + visual.shot_y * 4.2})`}>
            <circle r="18" fill="#f57928" stroke="#382720" strokeWidth="2" />
            <text textAnchor="middle" dy="7" fontSize="20" fill="#382720" fontWeight="900">⚽</text>
          </g>
          <g transform={`translate(${visual.goal_x * 8} ${30 + visual.goal_y * 4.2})`}>
            <circle r="14" fill="#fffaf5" stroke="#382720" strokeWidth="2" />
          </g>
        </svg>
      </div>
      {revealed && visual.answer_label && <p className="mt-3 text-center text-lg font-bold text-emerald-700">{visual.answer_label}</p>}
    </>}
    {visual.type === 'odd_one_out_grid' && <>
      <ol aria-label="اختاروا المختلف" className="grid grid-cols-2 gap-3">
        {visual.items.map((item, i) => <li key={i} className={`flex min-h-28 min-w-0 items-center justify-center rounded-xl border-2 p-4 text-center text-xl font-black sm:text-3xl ${revealed && i === visual.odd_index ? 'border-emerald-700 bg-emerald-50' : 'border-orange-200 bg-orange-50'}`}>
          {item.label}{revealed && i === visual.odd_index ? ' ✓' : ''}
        </li>)}
      </ol>
      {revealed && <p className="mt-3 text-center text-lg font-bold">{visual.common_property}</p>}
    </>}
  </figure>;
}
