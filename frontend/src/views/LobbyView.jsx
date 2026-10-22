import TeamAvatar from '../components/TeamAvatar.jsx';
import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
  AVATARS,
  TEAM_COLORS,
  TEAM_NAME_MAX_LENGTH,
  avatarForTeam,
  colorForTeam,
} from '../game/constants.js';
import { countPlayedTiles, stageLabel } from '../game/state.js';
import { TOTAL_PRIMARY_TILES } from '../data/mockData.js';
import { useGameStore } from '../store/gameStore.js';
import soundEngine from '../utils/soundEngine.js';
import Icon from '../components/Icon.jsx';
import CategoryVisual from '../components/CategoryVisual.jsx';
import StageBackdrop from '../components/StageBackdrop.jsx';
import { HERO_ART } from '../ui/categoryArt.js';

function StepRail() {
  const steps = [
    { n: 1, label: 'الفئات', hint: 'اختاروا ست' },
    { n: 2, label: 'الفرق', hint: 'جهّزوا التحدّي' },
    { n: 3, label: 'القوى', hint: 'ثلاث لكل فريق' },
    { n: 4, label: 'اللّعب', hint: '٣٦ سؤال' },
  ];
  return (
    <ol className="grid w-full grid-cols-2 gap-1.5 sm:flex sm:items-stretch sm:gap-1" aria-label="مراحل المباراة">
      {steps.map((step, index) => {
        const active = index === 0;
        return (
          <li key={step.n} className="flex min-w-0 items-center gap-1 sm:flex-1">
            <div
              className={`flex min-w-0 flex-1 items-center gap-2 rounded-xl border px-2.5 py-2 ${
                active
                  ? 'border-orange-300/30 bg-orange-400/[0.08]'
                  : 'border-stone-200 bg-stone-100/70'
              }`}
              aria-current={active ? 'step' : undefined}
            >
              <span
                className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border text-xs font-black ${
                  active
                    ? 'border-orange-300/50 bg-orange-300 text-ink-950'
                    : 'border-stone-300 bg-white text-stone-600'
                }`}
              >
                {step.n}
              </span>
              <span className="min-w-0">
                <span
                  className={`block truncate text-xs font-black ${
                    active ? 'text-brand-700' : 'text-stone-600'
                  }`}
                >
                  {step.label}
                </span>
                <span className="hidden truncate text-xs text-stone-600 sm:block">{step.hint}</span>
              </span>
            </div>
            {index < steps.length - 1 && (
              <span aria-hidden="true" className="hidden h-px w-3 shrink-0 bg-stone-100 sm:block" />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function TeamSetupCard({ team, otherTeam, position }) {
  const updateTeam = useGameStore((state) => state.updateTeam);
  const color = colorForTeam(team);
  const avatar = avatarForTeam(team);

  return (
    <section
      className="panel photo-card group flex flex-col overflow-hidden rounded-3xl p-4 xl:p-5"
      style={{ borderColor: `${color.hex}2e` }}
      aria-label={`إعداد ${team.name || `الفريق ${position}`}`}
    >
      <span
        aria-hidden="true"
        className="absolute inset-x-0 top-0 h-px"
        style={{ background: `linear-gradient(90deg, transparent, ${color.hex}bb, transparent)` }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -start-16 -top-24 h-52 w-52 rounded-full blur-3xl"
        style={{ backgroundColor: `${color.hex}13` }}
      />

      <div className="relative flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-black tracking-[0.2em] text-stone-600">
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color.hex }} />
          الفريق {position === 1 ? 'الأول' : 'الثاني'}
        </p>
        <span className="rounded-full border border-stone-200 bg-white/[0.03] px-2 py-0.5 text-xs font-bold text-stone-600">
          {team.name.trim() ? 'جاهز' : 'بانتظار الاسم'}
        </span>
      </div>

      <div className="relative mt-3 flex items-center gap-3">
        <span
          className="relative grid h-14 w-14 shrink-0 place-items-center rounded-2xl border text-3xl xl:h-16 xl:w-16 xl:text-4xl"
          style={{
            borderColor: `${color.hex}55`,
            backgroundColor: `${color.hex}16`,
            boxShadow: `inset 0 0 24px ${color.hex}14`,
          }}
          aria-hidden="true"
        >
          <TeamAvatar avatar={avatar} />
          <span
            className="absolute -bottom-1 -end-1 grid h-5 w-5 place-items-center rounded-full border-2 border-ink-950 text-xs font-black text-ink-950"
            style={{ backgroundColor: color.hex }}
          >
            {position}
          </span>
        </span>
        <div className="min-w-0 flex-1">
          <label htmlFor={`team-name-${team.id}`} className="mb-1 block text-xs font-bold text-stone-600">
            اسم الفريق على الشاشة
          </label>
          <input
            id={`team-name-${team.id}`}
            type="text"
            value={team.name}
            maxLength={TEAM_NAME_MAX_LENGTH}
            onChange={(event) => updateTeam(team.id, { name: event.target.value })}
            placeholder="اكتب اسم الفريق"
            className="w-full rounded-xl border border-stone-200 bg-stone-100/70 px-3 py-2 text-lg font-black text-ink-900 outline-none transition placeholder:text-stone-600 focus:border-orange-300/60 focus:bg-stone-100/70 xl:text-xl"
            style={{ caretColor: color.hex }}
          />
          <p className="mt-1 text-xs font-bold text-stone-600">
            <span className="ltr">{team.name.trim().length}</span> /{' '}
            <span className="ltr">{TEAM_NAME_MAX_LENGTH}</span> حرف
          </p>
        </div>
      </div>

      <div className="relative mt-4 space-y-2.5">
        <div className="flex items-center gap-3">
          <p className="w-14 shrink-0 text-xs font-bold text-stone-600">لون الهوية</p>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label={`لون ${team.name}`}>
            {TEAM_COLORS.map((option) => {
              const taken = otherTeam.color === option.id;
              const selected = team.color === option.id;
              return (
                <button
                  key={option.id}
                  type="button"
                  disabled={taken}
                  onClick={() => updateTeam(team.id, { color: option.id })}
                  aria-label={`${option.name}${taken ? ' — محجوز للفريق الثاني' : ''}`}
                  aria-pressed={selected}
                  className={`relative grid h-9 w-9 place-items-center rounded-full border-2 transition ${
                    selected
                      ? 'scale-105 border-stone-200 shadow-[0_0_0_3px_rgba(255,255,255,0.08)]'
                      : 'border-transparent'
                  } ${taken ? 'cursor-not-allowed opacity-20' : 'hover:scale-110 hover:border-stone-200'}`}
                  style={{ backgroundColor: option.hex }}
                >
                  {selected && <Icon name="Check" size={14} className="text-ink-950" strokeWidth={3} />}
                  <span className="sr-only">{option.name}</span>
                </button>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <p className="w-14 shrink-0 text-xs font-bold text-stone-600">رمز الفريق</p>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label={`رمز ${team.name}`}>
            {AVATARS.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => updateTeam(team.id, { avatar: option.id })}
                aria-label={`اختيار رمز ${option.label}`}
                aria-pressed={team.avatar === option.id}
                className={`grid h-9 w-9 place-items-center rounded-xl border text-base transition ${
                  team.avatar === option.id
                    ? 'border-stone-200 bg-white/15 shadow-[inset_0_0_16px_rgba(255,255,255,0.06)]'
                    : 'border-stone-200 bg-stone-100/70 hover:border-stone-200 hover:bg-white/[0.07]'
                }`}
              >
                <TeamAvatar avatar={option} />
                <span className="sr-only">{option.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="relative mt-4 flex items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-stone-100/70 px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="h-7 w-1 rounded-full" style={{ backgroundColor: color.hex }} />
          <div className="min-w-0">
            <p className="truncate text-sm font-black text-ink-900">{team.name.trim() || 'بدون اسم'}</p>
            <p className="text-xs font-bold text-stone-600">الاسم واللون والرمز يظهرون بالبث</p>
          </div>
        </div>
        <div className="shrink-0 text-left">
          <p className="text-xs font-bold text-stone-600">النقاط</p>
          <p className="ltr tv-number text-2xl font-black leading-none" style={{ color: color.hex }}>
            0
          </p>
        </div>
      </div>
    </section>
  );
}

function CoinToss() {
  const coinToss = useGameStore((state) => state.coinToss);
  const teams = useGameStore((state) => state.teams);
  const finishCoinToss = useGameStore((state) => state.finishCoinToss);
  const [flipping, setFlipping] = useState(false);
  const [pendingWinner, setPendingWinner] = useState(null);
  const timeoutRef = useRef(null);

  useEffect(() => () => clearTimeout(timeoutRef.current), []);

  const winner = teams.find((team) => team.id === coinToss.result) ?? null;

  const handleToss = () => {
    if (flipping || coinToss.completed) return;
    const chosen = teams[Math.random() < 0.5 ? 0 : 1];
    setPendingWinner(chosen);
    setFlipping(true);
    soundEngine.tick();
    timeoutRef.current = setTimeout(() => {
      finishCoinToss(chosen.id);
      soundEngine.power();
      setFlipping(false);
      setPendingWinner(null);
    }, 1750);
  };

  return (
    <section
      className="panel panel-gold relative flex flex-col overflow-hidden rounded-3xl"
      aria-label="قرعة العملة"
    >
      <div className="coin-header photo-card relative h-20 shrink-0 overflow-hidden border-b border-stone-200">
        <img
          src={HERO_ART.crowd.src}
          alt=""
          aria-hidden="true"
          className="h-full w-full object-cover opacity-55"
          style={{ objectPosition: HERO_ART.crowd.position }}
          loading="lazy"
          decoding="async"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-ink-950 via-ink-950/55 to-ink-950/15" />
        <div className="absolute inset-x-4 bottom-2.5 flex items-center justify-between">
          <p className="text-xs font-black tracking-[0.24em] text-amber-800">قرعة البداية</p>
          <p className="flex items-center gap-1 text-xs font-bold text-stone-600">
            <span className={`h-1.5 w-1.5 rounded-full ${coinToss.completed ? 'bg-emerald-400' : 'bg-amber-300'}`} />
            {coinToss.completed ? 'النتيجة مثبتة' : 'عادلة ٥٠ / ٥٠'}
          </p>
        </div>
      </div>

      <div className="relative flex flex-1 flex-col items-center px-4 pb-4 pt-3 text-center xl:px-5">
        <h2 className="text-balance text-xl font-black leading-7 text-ink-900 xl:text-2xl xl:leading-8">
          من يفتح أول خانة؟
        </h2>
        <p className="mt-1 text-xs leading-5 text-stone-600">ارمِ العملة، وخلّ البداية للحظ.</p>

        <div className="coin-3d relative my-4 flex h-28 w-28 items-center justify-center xl:h-32 xl:w-32" aria-hidden="true">
          <span className="absolute inset-[-14px] rounded-full border border-amber-300/10" />
          <span className="absolute inset-[-28px] rounded-full border border-amber-300/[0.06]" />
          <span className="absolute inset-[-12px] rounded-full bg-amber-300/10 blur-2xl" />
          <div
            className={`relative flex h-full w-full items-center justify-center rounded-full border-[3px] border-amber-100/70 bg-[radial-gradient(circle_at_32%_26%,#fff3c4,#f2c14e_44%,#9a6b12_100%)] shadow-[0_0_55px_rgba(251,191,36,0.32),inset_0_-8px_18px_rgba(90,50,0,0.35),inset_0_6px_14px_rgba(255,255,255,0.5)] ${
              flipping ? 'is-flipping' : ''
            }`}
          >
            <div className="absolute inset-2 rounded-full border border-amber-800/25" />
            <div className="absolute inset-4 rounded-full border border-amber-100/25" />
            <span className="relative text-4xl drop-shadow-[0_2px_4px_rgba(90,50,0,0.35)] xl:text-5xl">
              {pendingWinner ? <TeamAvatar team={pendingWinner} /> : <Icon name="Sparkles" size={40} />}
            </span>
          </div>
        </div>

        {coinToss.completed && winner ? (
          <motion.div
            initial={{ opacity: 1, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full rounded-2xl border border-emerald-400/25 bg-emerald-400/[0.08] px-3 py-2.5"
            role="status"
          >
            <p className="text-xs font-bold text-emerald-700">الفائز بالقرعة</p>
            <p className="mt-0.5 flex items-center justify-center gap-2 text-base font-black text-ink-900">
              <span aria-hidden="true"><TeamAvatar team={winner} /></span>
              {winner.name}
            </p>
            <p className="mt-1 text-xs text-stone-600">يبدأ السحب، ويبدأ أول خانة باللوحة.</p>
          </motion.div>
        ) : (
          <button
            type="button"
            onClick={handleToss}
            disabled={flipping}
            className="group flex min-h-[3rem] w-full items-center justify-center gap-2 rounded-2xl border border-amber-200/50 bg-amber-300/[0.14] px-4 py-3 text-sm font-black text-amber-800 transition hover:border-amber-200/80 hover:bg-amber-300/25 disabled:cursor-wait disabled:opacity-70"
          >
            <Icon name="Dices" size={17} className={flipping ? 'animate-spin' : ''} />
            {flipping ? 'العملة بالهوا…' : 'ارمِ العملة'}
          </button>
        )}

        <ul className="mt-3 w-full space-y-1 border-t border-stone-200 pt-2 text-right text-xs leading-5 text-stone-600">
          <li className="flex gap-1.5">
            <span className="text-amber-800">٠١</span>
            الفائز يبدأ أول اختيار بالقوى وأول خانة.
          </li>
          <li className="flex gap-1.5">
            <span className="text-amber-800">٠٢</span>
            كل فريق ياخذ ثلاث قوى، ويقدر الفريقان يختارون نفس القوة.
          </li>
          <li className="flex gap-1.5">
            <span className="text-amber-800">٠٣</span>
            المقدم يثبّت النتيجة بعد إظهار الإجابة.
          </li>
        </ul>
      </div>
    </section>
  );
}

function CategoryPicker() {
  const categories = useGameStore((state) => state.categories);
  const selected = useGameStore((state) => state.selectedCategorySlugs);
  const toggleCategory = useGameStore((state) => state.toggleCategory);
  const pickRandomCategories = useGameStore((state) => state.pickRandomCategories);
  const loadCategories = useGameStore((state) => state.loadCategories);
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  const remaining = 6 - selected.length;

  const handleToggle = (categoryId) => {
    const result = toggleCategory(categoryId);
    setNotice(result.ok ? '' : result.reason ?? 'ما قدرنا نختار هالفئة.');
  };

  const handleRandom = () => {
    const result = pickRandomCategories();
    setNotice(result.ok ? '' : result.reason ?? 'ما قدرنا نختار فئات عشوائية.');
  };

  return (
    <section className="panel category-picker" aria-label="اختيار فئات المباراة">
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-px rule-gold" />
      <div className="relative flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="eyebrow">فئات المباراة</p>
          <h2 className="mt-1 text-lg font-black text-ink-900 xl:text-xl">
            اختاروا <span className="text-brand-700">ست فئات</span> للتحدّي
          </h2>
          <p className="mt-1 text-xs font-bold text-stone-600">
            ثلاث فئات لكم، وثلاث للمنافس. اختاروا اللي تبدعون فيه!
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`ltr tv-number rounded-xl border px-2.5 py-1.5 text-xs font-black ${
              selected.length === 6
                ? 'border-emerald-400/35 bg-emerald-400/10 text-emerald-700'
                : 'border-amber-300/30 bg-amber-300/10 text-amber-800'
            }`}
          >
            {selected.length}/6
          </span>
          <button
            type="button"
            onClick={handleRandom}
            className="flex items-center gap-1.5 rounded-xl border border-orange-300/35 bg-orange-400/10 px-3 py-2 text-[13px] font-black text-brand-700 transition hover:bg-orange-400/20"
          >
            <Icon name="Shuffle" size={13} />
            اختيار عشوائي (6 فئات)
          </button>
        </div>
      </div>

      {categories.status === 'loading' && categories.items.length === 0 && (
        <p className="relative mt-4 flex items-center gap-2 text-[13px] font-bold text-stone-600">
          <Icon name="RotateCcw" size={13} className="animate-spin" /> جاري تحميل الفئات من الخادم…
        </p>
      )}
      {categories.status === 'error' && (
        <div className="relative mt-4 flex flex-wrap items-center gap-2 rounded-xl border border-rose-400/30 bg-white px-3 py-2" role="alert">
          <p className="flex-1 text-xs font-bold text-red-700">{categories.error}</p>
          <button
            type="button"
            onClick={() => loadCategories(true)}
            className="rounded-lg border border-rose-300/40 px-2 py-1 text-xs font-black text-red-700"
          >
            إعادة المحاولة
          </button>
        </div>
      )}

      <label className="category-search mt-5" htmlFor="category-search">
        <Icon name="ScanSearch" size={19} />
        <input id="category-search" type="search" placeholder="تدور على فئة؟ ابحث هنا…" value={search} onChange={(event) => setSearch(event.target.value)} />
        <span className="sr-only">البحث عن فئة</span>
      </label>
      <div className="category-picker__grid">
        {categories.items.filter((category) => category.name.includes(search.trim())).map((category) => {
          const active = selected.includes(category.id);
          const disabled = !active && (selected.length >= 6 || category.eligibleCount < 3);
          return (
            <button key={category.id} type="button" disabled={disabled} data-category={category.id}
              onClick={() => handleToggle(category.id)} aria-pressed={active}
              aria-label={`${category.name}، ${category.eligibleCount} سؤالًا متاحًا`}
              className="category-choice">
              <CategoryVisual id={category.id} icon={category.icon} />
              <span className="category-choice__check">{active && <Icon name="Check" size={14} />}</span>
              <span className="category-choice__title">{category.name}</span>
              <span className="category-choice__count"><span className="ltr">{category.eligibleCount}</span> سؤال متاح</span>
            </button>
          );
        })}
      </div>
      {search.trim() && !categories.items.some((category) => category.name.includes(search.trim())) && <p className="mt-5 text-center text-sm text-stone-600" role="status">ما لقينا فئة بهذا الاسم. جرّب كلمة ثانية.</p>}

      {notice && (
        <p className="relative mt-2 rounded-xl border border-amber-400/30 bg-amber-400/[0.07] px-3 py-2 text-xs font-bold text-amber-800" role="status">
          {notice}
        </p>
      )}
      {remaining > 0 && categories.status === 'ready' && (
        <p className="relative mt-2 text-xs font-bold text-stone-600">
          باقي <span className="ltr text-brand-700">{remaining}</span> فئة لإكمال الاختيار.
        </p>
      )}
    </section>
  );
}

function PlayersCard() {
  const teams = useGameStore((state) => state.teams);
  const profiles = useGameStore((state) => state.profiles);
  const teamProfileIds = useGameStore((state) => state.teamProfileIds);
  const loadProfiles = useGameStore((state) => state.loadProfiles);
  const createProfile = useGameStore((state) => state.createProfile);
  const toggleTeamProfile = useGameStore((state) => state.toggleTeamProfile);
  const [name, setName] = useState('');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  const assigned = new Set([...(teamProfileIds[teams[0]?.id] ?? []), ...(teamProfileIds[teams[1]?.id] ?? [])]);

  const handleAdd = async () => {
    if (adding || !name.trim()) return;
    setAdding(true);
    setError('');
    const result = await createProfile(name.trim());
    if (result.ok) {
      setName('');
      soundEngine.tick();
    } else {
      setError(result.reason ?? 'ما قدرنا ننشئ الملف.');
    }
    setAdding(false);
  };

  return (
    <section
      className="panel photo-card relative mt-3 overflow-hidden rounded-3xl p-4 xl:p-5"
      aria-label="اللاعبون المشاركون"
    >
      <div className="relative flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl border border-violet-300/25 bg-violet-400/10 text-violet-700">
            <Icon name="UserCheck" size={17} />
          </span>
          <div>
            <h2 className="text-sm font-black text-ink-900">ضيوف إضافيون على هذه الشاشة</h2>
            <p className="text-xs font-bold text-stone-600">
              حسابك محفوظ تلقائيًا. اختياريًا أضف ملفات ضيوف محلية؛ هذه الملفات ليست حسابات دخول.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <label htmlFor="profile-name" className="sr-only">اسم لاعب جديد</label>
          <input
            id="profile-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') handleAdd();
            }}
            placeholder="اسم لاعب جديد…"
            maxLength={32}
            className="h-9 w-36 rounded-xl border border-stone-200 bg-stone-100/70 px-2.5 text-[13px] font-bold text-ink-900 placeholder:text-stone-600 focus:border-violet-300/50"
          />
          <button
            type="button"
            onClick={handleAdd}
            disabled={adding || !name.trim()}
            className="grid h-9 w-9 place-items-center rounded-xl border border-violet-300/40 bg-violet-400/15 text-violet-700 transition hover:bg-violet-400/25 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="إضافة لاعب"
          >
            <Icon name={adding ? 'RotateCcw' : 'Plus'} size={14} className={adding ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {error && (
        <p className="relative mt-2 rounded-xl border border-rose-400/30 bg-white px-3 py-1.5 text-xs font-bold text-red-700" role="alert">
          {error}
        </p>
      )}

      <div className="relative mt-3">
        {profiles.status === 'loading' && profiles.items.length === 0 && (
          <p className="flex items-center gap-2 text-xs font-bold text-stone-600">
            <Icon name="RotateCcw" size={12} className="animate-spin" /> جاري تحميل اللاعبين…
          </p>
        )}
        {profiles.status === 'error' && (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-rose-400/30 bg-white px-3 py-2" role="alert">
            <p className="flex-1 text-xs font-bold text-red-700">{profiles.error}</p>
            <button
              type="button"
              onClick={() => loadProfiles(true)}
              className="rounded-lg border border-rose-300/40 px-2 py-1 text-xs font-black text-red-700"
            >
              إعادة المحاولة
            </button>
          </div>
        )}
        {profiles.status === 'ready' && profiles.items.length === 0 && (
          <p className="text-xs font-bold text-stone-600">لا يوجد لاعبون بعد — أضف أول ملف فوق.</p>
        )}
        {profiles.items.length > 0 && (
          <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 xl:grid-cols-3">
            {profiles.items.map((profile) => (
              <li
                key={profile.id}
                className="flex items-center gap-2 rounded-xl border border-stone-200 bg-stone-100/70 px-2.5 py-1.5"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-black text-ink-900">
                    {profile.display_name || profile.username}
                  </span>
                  <span className="ltr block truncate text-xs text-stone-600">@{profile.username}</span>
                </span>
                {teams.map((team) => {
                  const color = colorForTeam(team);
                  const active = (teamProfileIds[team.id] ?? []).includes(profile.id);
                  return (
                    <button
                      key={team.id}
                      type="button"
                      onClick={() => toggleTeamProfile(team.id, profile.id)}
                      aria-pressed={active}
                      aria-label={`${active ? 'إزالة' : 'إسناد'} ${profile.display_name || profile.username} ${active ? 'من' : 'إلى'} ${team.name}`}
                      title={team.name}
                      className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg border text-sm transition active:scale-95 ${
                        active ? '' : 'border-stone-200 bg-white/[0.03] opacity-60 hover:opacity-100'
                      }`}
                      style={active ? { borderColor: `${color.hex}88`, backgroundColor: `${color.hex}22` } : undefined}
                    >
                      <span aria-hidden="true"><TeamAvatar team={team} /></span>
                    </button>
                  );
                })}
              </li>
            ))}
          </ul>
        )}
        {assigned.size > 0 && (
          <p className="mt-2 text-xs font-bold text-stone-600" role="status">
            <span className="ltr text-stone-600">{assigned.size}</span> مشاركين — أسئلتهم السابقة مستبعدة من المباراة.
          </p>
        )}
      </div>
    </section>
  );
}

function StartBar() {
  const coinToss = useGameStore((state) => state.coinToss);
  const teams = useGameStore((state) => state.teams);
  const selected = useGameStore((state) => state.selectedCategorySlugs);
  const beginMatch = useGameStore((state) => state.beginMatch);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const namesReady = teams.every((team) => team.name.trim().length > 0);
  const distinctNames = teams[0].name.trim() !== teams[1].name.trim();
  const categoriesReady = selected.length === 6;
  const ready = coinToss.completed && namesReady && distinctNames && categoriesReady;
  const reason = !namesReady
    ? 'سمّوا الفريقين أولًا'
    : !distinctNames
      ? 'أسماء الفريقين لازم تكون مختلفة'
      : !coinToss.completed
        ? 'ارمِ العملة لتحديد البداية'
        : !categoriesReady
          ? 'اختاروا ست فئات مختلفة'
          : '';

  const startMatch = async () => {
    if (busy || !ready) return;
    setBusy(true);
    setError('');
    const result = await beginMatch();
    if (result.ok) {
      soundEngine.power();
    } else {
      setError(result.reason ?? 'ما قدرنا نجهز المباراة على السيرفر.');
    }
    setBusy(false);
  };

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center gap-2">
      <button
        type="button"
        disabled={!ready || busy}
        onClick={startMatch}
        className={`animate-sheen flex min-h-[3.25rem] w-full items-center justify-center gap-2.5 rounded-2xl border px-6 py-3.5 text-base font-black transition ${
          ready && !busy
            ? 'border-amber-100/40 brand-button--primary text-ink-950 shadow-[0_16px_44px_rgba(232,182,77,0.2)] hover:brightness-105 active:scale-[0.99]'
            : 'cursor-not-allowed border-stone-300 bg-stone-100 text-stone-600'
        }`}
      >
        <Icon name={busy ? 'RotateCcw' : 'Swords'} size={19} className={busy ? 'animate-spin' : ''} />
        {busy ? 'نجهز المباراة على السيرفر…' : 'ابدأ سحب القوى'}
        {!busy && <Icon name="ChevronLeft" size={18} className={ready ? 'opacity-70' : 'text-stone-600'} />}
      </button>
      {!ready && !busy && (
        <p className="flex items-center gap-1.5 text-xs font-bold text-amber-800">
          <Icon name="CircleHelp" size={11} />
          {reason}
        </p>
      )}
      {ready && !busy && (
        <p className="flex items-center gap-1.5 text-xs font-bold text-stone-600">
          <Icon name="Radar" size={11} className="text-emerald-400/80" />
          كل شيء جاهز. اختاروا قواكم، وبعدها يبدأ التحدّي!
        </p>
      )}
      {error && (
        <p className="rounded-xl border border-rose-400/30 bg-white px-3 py-2 text-center text-xs font-bold leading-5 text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function ResumeMatch({ onResume, onReset }) {
  const teams = useGameStore((state) => state.teams);
  const stage = useGameStore((state) => state.currentStage);
  const tileResults = useGameStore((state) => state.tileResults);
  const matchStartedAt = useGameStore((state) => state.matchStartedAt);
  const resetSavedMatch = useGameStore((state) => state.resetSavedMatch);
  const [confirming, setConfirming] = useState(false);
  const played = countPlayedTiles(tileResults);

  return (
    <div className="stage-bg-photo relative min-h-[100svh] overflow-hidden">
      <StageBackdrop image={HERO_ART.stage.src} position={HERO_ART.stage.position} variant="hero" />
      <main className="relative z-10 flex min-h-[100svh] items-center justify-center px-4 py-8">
        <motion.section
          initial={{ opacity: 1, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          className="panel photo-card w-full max-w-2xl overflow-hidden rounded-3xl p-5 sm:p-6 xl:p-8"
          aria-label="استئناف مباراة محفوظة"
        >
          <span aria-hidden="true" className="absolute inset-x-0 top-0 h-px rule-gold" />
          <div className="pointer-events-none absolute -end-16 -top-20 h-56 w-56 rounded-full bg-orange-400/[0.08] blur-3xl" />
          <div className="relative flex items-center gap-3">
            <span className="grid h-12 w-12 place-items-center rounded-2xl border border-orange-300/25 bg-orange-400/10 text-brand-700">
              <Icon name="RotateCcw" size={23} />
            </span>
            <div>
              <p className="eyebrow">مباراة محفوظة</p>
              <h1 className="mt-1 text-2xl font-black text-ink-900 xl:text-3xl">نكمّل من وين وقفنا؟</h1>
            </div>
          </div>

          <div className="relative mt-5 grid grid-cols-2 gap-3">
            {teams.map((team) => {
              const color = colorForTeam(team);
              return (
                <div
                  key={team.id}
                  className="relative overflow-hidden rounded-2xl border p-3"
                  style={{ borderColor: `${color.hex}3d`, backgroundColor: `${color.hex}0b` }}
                >
                  <span
                    aria-hidden="true"
                    className="absolute inset-y-0 start-0 w-[3px]"
                    style={{ backgroundColor: color.hex }}
                  />
                  <div className="flex items-center gap-2">
                    <span className="text-2xl" aria-hidden="true"><TeamAvatar team={team} /></span>
                    <p className="min-w-0 truncate text-sm font-extrabold text-ink-900">{team.name}</p>
                  </div>
                  <p className="ltr tv-number mt-2 text-3xl font-black" style={{ color: color.hex }}>
                    {team.score}
                  </p>
                </div>
              );
            })}
          </div>

          <dl className="relative mt-4 grid grid-cols-3 gap-2 text-center">
            {[
              { label: 'المرحلة', value: stageLabel(stage) },
              { label: 'الخانات الملعوبة', value: `${played} / ${TOTAL_PRIMARY_TILES}`, ltr: true },
              {
                label: 'البداية',
                value: matchStartedAt
                  ? new Intl.DateTimeFormat('ar-KW', { hour: '2-digit', minute: '2-digit' }).format(matchStartedAt)
                  : '—',
              },
            ].map((item) => (
              <div key={item.label} className="rounded-xl border border-stone-200 bg-stone-100/70 px-2 py-2">
                <dt className="text-xs text-stone-600">{item.label}</dt>
                <dd className={`mt-0.5 text-xs font-bold text-stone-800 ${item.ltr ? 'ltr tv-number' : ''}`}>
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>

          <div className="relative mt-6 flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={onResume}
              className="flex min-h-[2.9rem] flex-1 items-center justify-center gap-2 rounded-2xl border border-orange-300/45 bg-orange-400/15 px-4 py-3 text-sm font-black text-brand-700 transition hover:bg-orange-400/25 active:scale-[0.99]"
            >
              <Icon name="Play" size={17} />
              استئناف المباراة
            </button>
            {!confirming ? (
              <button
                type="button"
                onClick={() => setConfirming(true)}
                className="min-h-[2.9rem] rounded-2xl border border-rose-400/25 bg-rose-500/[0.08] px-4 py-3 text-sm font-bold text-red-700 transition hover:bg-rose-500/15"
              >
                حذف المباراة المحفوظة
              </button>
            ) : (
              <div className="flex flex-1 items-center gap-2 rounded-2xl border border-rose-400/40 bg-white p-2">
                <span className="flex-1 px-1 text-xs font-bold leading-4 text-red-700">
                  متأكد؟ الحذف نهائي وما ينسترجع.
                </span>
                <button
                  type="button"
                  onClick={() => {
                    resetSavedMatch();
                    onReset();
                  }}
                  className="rounded-xl bg-rose-500 px-3 py-2 text-xs font-black text-ink-900"
                >
                  نعم، احذف
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  className="rounded-xl border border-stone-200 px-2.5 py-2 text-xs font-bold text-stone-600"
                >
                  رجوع
                </button>
              </div>
            )}
          </div>
          <p className="relative mt-3 text-xs leading-5 text-stone-600">
            الاستئناف يزامن المباراة من السيرفر؛ النسخة المحفوظة تبقى احتياطًا لو انقطع الاتصال. الحذف يشيل نسخة الاسترداد من المتصفح فقط، وما يمسح المباراة على السيرفر.
          </p>
        </motion.section>
      </main>
    </div>
  );
}

export default function LobbyView({ resumePending = false, onResume = () => {}, onReset = () => {} }) {
  const teams = useGameStore((state) => state.teams);

  if (resumePending) {
    return <ResumeMatch onResume={onResume} onReset={onReset} />;
  }

  return (
    <div className="stage-bg-photo relative overflow-hidden">
      <StageBackdrop variant="hero" />
      <div className="lobby-content">
        <header className="lobby-hero">
          <div>
            <span className="lobby-hero__badge"><Icon name="Sparkles" size={16} /> وقت اللّمّة الحلوة</span>
            <h1>جمّع ربعك، <span>وورّنا شطارتك!</span></h1>
            <p>مو بس معلومات… سرعة بديهة، شوية حظ، والكثير من الحماس. جهّزوا فريقين وخلّ التحدّي يبدأ.</p>
          </div>
          <div className="lobby-hero__art" aria-hidden="true"><Icon name="Trophy" size={104} strokeWidth={1.5} /></div>
        </header>
        <div className="mt-6"><StepRail /></div>
        <div className="setup-heading"><span>١</span><div><h2>على شنو نتحدّى؟</h2><p>اختاروا ست فئات تصنعون فيها جوّكم.</p></div></div>
        <CategoryPicker />
        <div className="setup-heading"><span>٢</span><div><h2>منو ضد منو؟</h2><p>سمّوا الفريقين، اختاروا هويتكم، وارموا عملة البداية.</p></div></div>
        <main className="grid items-stretch gap-4 lg:grid-cols-[1fr_0.8fr_1fr]">
          <TeamSetupCard team={teams[0]} otherTeam={teams[1]} position={1} />
          <CoinToss />
          <TeamSetupCard team={teams[1]} otherTeam={teams[0]} position={2} />
        </main>
        <details className="guest-details"><summary><Icon name="UserCheck" size={18} /> تلعبون مع ضيوف؟ أضيفوا ملفاتهم <Icon name="Plus" size={15} /></summary><PlayersCard /></details>
        <div className="lobby-start"><StartBar /></div>
        <footer className="mt-8 text-center text-xs text-stone-600">فريقين، شاشة وحدة، وذكريات ما تنملّ. استمتعوا باللّعب!</footer>
      </div>
    </div>
  );
}
