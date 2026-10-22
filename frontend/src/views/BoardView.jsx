import TeamAvatar from '../components/TeamAvatar.jsx';
import { motion } from 'framer-motion';
import { CATEGORIES, POINT_VALUES, TOTAL_PRIMARY_TILES } from '../data/mockData.js';
import { countPlayedTiles } from '../game/state.js';
import { avatarForTeam, colorForTeam } from '../game/constants.js';
import { useGameStore } from '../store/gameStore.js';
import soundEngine from '../utils/soundEngine.js';
import HeaderScoreboard from '../components/HeaderScoreboard.jsx';
import Icon from '../components/Icon.jsx';
import CategoryVisual from '../components/CategoryVisual.jsx';
import StageBackdrop from '../components/StageBackdrop.jsx';
import { HERO_ART, categoryArt } from '../ui/categoryArt.js';

function splitTiles(tiles) {
  const sorted = [...tiles].sort((a, b) => a.points - b.points || a.id.localeCompare(b.id));
  const right = [];
  const left = [];
  for (const points of POINT_VALUES) {
    const group = sorted.filter((tile) => tile.points === points);
    if (group[0]) right.push(group[0]);
    if (group[1]) left.push(group[1]);
  }
  return { right, left };
}

function ResultBadge({ result, teams }) {
  if (!result?.played) return null;
  if (!result.winningTeamId) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-bold text-stone-600">
        <Icon name="Minus" size={9} />
        ولا أحد
      </span>
    );
  }
  const team = teams.find((item) => item.id === result.winningTeamId);
  if (!team) return null;
  const color = colorForTeam(team);
  return (
    <span
      className="inline-flex max-w-full items-center gap-1 rounded-full px-1.5 py-0.5 text-xs font-black"
      style={{ backgroundColor: `${color.hex}18`, color: color.hex }}
    >
      <span aria-hidden="true"><TeamAvatar team={team} /></span>
      <span className="truncate">{team.name}</span>
    </span>
  );
}

function TileButton({ tile, category, result, teams, onSelect }) {
  const played = Boolean(result?.played);
  const winner = teams.find((team) => team.id === result?.winningTeamId);
  return <button type="button" disabled={played} onClick={() => onSelect(tile.id)}
    aria-label={played ? `${category.name} ${tile.points}: ملعوبة — ${winner?.name ?? 'ولا أحد'}` : `${category.name} ${tile.points} — افتح السؤال`}
    className="question-tile">
    <span className="question-tile__value ltr tv-number">{played ? <Icon name="Check" size={23} /> : tile.points}</span>
    <span className="question-tile__hint">{played ? winner?.name ?? 'ولا أحد' : 'نقطة'}</span>
  </button>;
}

function CategoryPod({ category, teams, onSelect, results, index, tiles }) {
  const { right, left } = splitTiles(tiles);
  const played = tiles.filter((tile) => results[tile.id]?.played).length;
  const column = (items) => <div className="flex min-w-0 flex-col gap-2">{items.map((tile) =>
    <TileButton key={tile.id} tile={tile} category={category} result={results[tile.id]} teams={teams} onSelect={onSelect} />
  )}</div>;
  return <motion.section initial={{ opacity: 1, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .2, delay: index * .03 }} className="category-pod" aria-label={category.name}>
    <div className="category-pod__layout">
      {column(right)}
      <div className="category-pod__center"><CategoryVisual id={category.id} icon={category.icon} /><h2>{category.name}</h2><small><span className="ltr">{played} / {tiles.length}</span> انلعبت</small></div>
      {column(left)}
    </div>
  </motion.section>;
}

function ProgressStrip({ results, teams, tiles }) {
  return (
    <div className="flex items-center gap-[3px]" aria-label="تقدم المباراة">
      {tiles.map((tile) => {
        const result = results[tile.id];
        const team = result?.winningTeamId
          ? teams.find((item) => item.id === result.winningTeamId)
          : null;
        const color = team ? colorForTeam(team) : null;
        return (
          <span
            key={tile.id}
            title={`${tile.id}${result?.played ? ' — ملعوبة' : ' — متاحة'}`}
            className={`h-1.5 flex-1 rounded-full ${result?.played ? '' : 'bg-white/[0.09]'}`}
            style={
              result?.played
                ? { backgroundColor: color?.hex ?? '#475569', opacity: color ? 0.85 : 0.5 }
                : undefined
            }
          />
        );
      })}
    </div>
  );
}

export default function BoardView() {
  const teams = useGameStore((state) => state.teams);
  const currentTurnTeamId = useGameStore((state) => state.currentTurnTeamId);
  const tileResults = useGameStore((state) => state.tileResults);
  const selectTileOnline = useGameStore((state) => state.selectTileOnline);
  const manualAdjustments = useGameStore((state) => state.manualAdjustments);
  const serverTiles = useGameStore((state) => state.content.tiles);
  const storeCategories = useGameStore((state) => state.categories.items);
  const selectedSlugs = useGameStore((state) => state.selectedCategorySlugs);
  // لا تراجع لأسئلة وهمية في مسار اللعب: اللوحة تعرض المحتوى القادم من الخادم فقط.
  const boardTiles = serverTiles;
  const knownCategories = new Map(CATEGORIES.map((category) => [category.id, category]));
  for (const category of storeCategories) {
    knownCategories.set(category.id, {
      id: category.id,
      name: category.name,
      icon: category.icon,
    });
  }
  const tileCategoryIds = [...new Set(serverTiles.map((tile) => tile.categoryId))];
  const chosenIds = selectedSlugs.length
    ? selectedSlugs
    : tileCategoryIds.length
      ? tileCategoryIds
      : CATEGORIES.map((category) => category.id);
  const boardCategories = chosenIds.map(
    (id) => knownCategories.get(id) ?? { id, name: id, icon: 'Sparkles' },
  );
  const played = countPlayedTiles(tileResults);
  const activeTeam = teams.find((team) => team.id === currentTurnTeamId);
  const activeColor = activeTeam ? colorForTeam(activeTeam) : null;
  const activeAvatar = activeTeam ? avatarForTeam(activeTeam) : null;
  const remaining = TOTAL_PRIMARY_TILES - played;

  const openTile = (tileId) => {
    selectTileOnline(tileId).then((result) => {
      if (result.ok) soundEngine.tick();
    });
  };

  return (
    <div className="stage-bg-photo game-board relative flex flex-col">
      <StageBackdrop image={HERO_ART.stage.src} position="center 55%" variant="stage" />
      <div className="relative z-10 flex min-h-0 flex-1 flex-col">
        <HeaderScoreboard showAdjustments compact={false} />

        <main className="mx-auto flex min-h-0 w-full max-w-[1900px] flex-1 flex-col gap-2 px-3 pb-2 pt-2.5 xl:px-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2.5">
              <span className="flex items-center gap-1.5 rounded-lg border border-rose-400/25 bg-rose-500/[0.08] px-2 py-1 text-xs font-black tracking-[0.18em] text-red-700">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-70" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-rose-400" />
                </span>
                التحدّي شغّال
              </span>
              <div className="min-w-0">
                <h1 className="text-lg font-black leading-tight text-ink-900 xl:text-2xl">اختاروا سؤالكم</h1>
                <p className="hidden truncate text-xs font-bold text-stone-600 sm:block">
                  اختاروا خانة… السؤال يفتح على الشاشة كاملة.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              {activeTeam && (
                <div
                  className="flex items-center gap-2 rounded-xl border px-2.5 py-1.5"
                  style={{
                    borderColor: `${activeColor.hex}40`,
                    backgroundColor: `${activeColor.hex}0d`,
                    boxShadow: `0 0 24px ${activeColor.hex}12`,
                  }}
                  aria-live="polite"
                >
                  <span className="text-base" aria-hidden="true"><TeamAvatar avatar={activeAvatar} /></span>
                  <div>
                    <p className="text-xs font-bold text-stone-600">الدور الآن</p>
                    <p className="text-[13px] font-black text-ink-900">{activeTeam.name}</p>
                  </div>
                  <span
                    aria-hidden="true"
                    className="ms-1 h-2 w-2 rounded-full"
                    style={{ backgroundColor: activeColor.hex }}
                  />
                </div>
              )}
              <div className="min-w-[4.5rem] rounded-xl border border-stone-200 bg-stone-100/70 px-2.5 py-1.5 text-left">
                <p className="ltr tv-number text-base font-black leading-none text-ink-900 xl:text-xl">
                  {played}
                  <span className="text-stone-600">/{TOTAL_PRIMARY_TILES}</span>
                </p>
                <p className="mt-1 text-xs font-bold text-stone-600">
                  باقي <span className="ltr text-stone-600">{remaining}</span> خانة
                </p>
              </div>
            </div>
          </div>

          {boardTiles.length === 0 ? (
            <div className="grid flex-1 place-items-center rounded-2xl border border-dashed border-stone-200 bg-stone-100/70 p-6 text-center">
              <div>
                <Icon name="RotateCcw" size={26} className="mx-auto animate-spin text-brand-700" />
                <p className="mt-2 text-sm font-black text-ink-900">اللوحة تُحمَّل من الخادم</p>
                <p className="mt-1 text-xs font-bold text-stone-600">
                  لحظات ونجهّز لكم أسئلة التحدّي.
                </p>
              </div>
            </div>
          ) : (
            <div className="board-categories">
              {boardCategories.map((category, index) => (
                <CategoryPod
                  key={category.id}
                  category={category}
                  index={index}
                  teams={teams}
                  results={tileResults}
                  onSelect={openTile}
                  tiles={boardTiles.filter((tile) => tile.categoryId === category.id)}
                />
              ))}
            </div>
          )}

          <footer className="flex flex-wrap items-center justify-between gap-2 pb-1">
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <ProgressStrip results={tileResults} teams={teams} tiles={boardTiles} />
              <span className="shrink-0 text-xs font-bold text-stone-600">
                <span className="ltr text-stone-600">{remaining}</span> باقية
              </span>
            </div>
            <div className="flex items-center gap-2.5 text-xs text-stone-600">
              {teams.map((team) => {
                const color = colorForTeam(team);
                return (
                  <span key={team.id} className="flex max-w-[8rem] items-center gap-1">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: color.hex }} />
                    <span className="truncate font-bold">{team.name}</span>
                  </span>
                );
              })}
              <span className="hidden items-center gap-1 md:flex">
                <Icon name="Plus" size={9} /> / <Icon name="Minus" size={9} /> تعديل المقدم ±
                <span className="ltr">100</span>
              </span>
              {manualAdjustments.length > 0 && (
                <span className="rounded-full border border-amber-400/20 bg-amber-400/[0.08] px-1.5 py-0.5 font-bold text-amber-800">
                  <span className="ltr">{manualAdjustments.length}</span> تعديل مسجّل
                </span>
              )}
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}
