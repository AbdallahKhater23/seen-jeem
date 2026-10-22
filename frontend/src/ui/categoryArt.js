/**
 * صور محلية مرخّصة من Unsplash، محفوظة داخل المشروع حتى تشتغل اللعبة بدون إنترنت.
 * الموضع (position) مضبوط لكل صورة حتى يبقى العنصر المهم داخل الإطار.
 */
export const CATEGORY_ART = Object.freeze({
  flags: {
    src: '/images/categories/flags.jpg',
    position: 'center 38%',
    caption: 'أعلام ترفرف فوق واجهة كلاسيكية',
    tone: '#22d3ee',
  },
  football: {
    src: '/images/categories/football.jpg',
    position: 'center 58%',
    caption: 'كرة وقدم على عشب الملعب',
    tone: '#a3e635',
  },
  worldcup: {
    src: '/images/categories/worldcup.jpg',
    position: 'center 48%',
    caption: 'مدرجات ملعب مضاءة ليلًا',
    tone: '#fbbf24',
  },
  career: {
    src: '/images/categories/career.jpg',
    position: 'center 30%',
    caption: 'لاعب شاب في عز المباراة',
    tone: '#a78bfa',
  },
  riddles: {
    src: '/images/categories/riddles.jpg',
    position: 'center 35%',
    caption: 'تفكير عميق أمام شاشة وقلم',
    tone: '#f472b6',
  },
  spot: {
    src: '/images/categories/spot.jpg',
    position: 'center 45%',
    caption: 'قلعة وسط الضباب',
    tone: '#60a5fa',
  },
  capitals: {
    src: '/images/categories/flags.jpg',
    position: 'center 42%',
    caption: 'خرائط وعواصم',
    tone: '#2dd4bf',
  },
  ucl: {
    src: '/images/categories/football.jpg',
    position: 'center 55%',
    caption: 'ليالي دوري الأبطال',
    tone: '#818cf8',
  },
  clubs: {
    src: '/images/categories/football.jpg',
    position: 'center 60%',
    caption: 'أندية وديربيات',
    tone: '#f97316',
  },
  arab_ftbl: {
    src: '/images/categories/football.jpg',
    position: 'center 50%',
    caption: 'كورة عربية وخليجية',
    tone: '#f43f5e',
  },
  numbers: {
    src: '/images/categories/worldcup.jpg',
    position: 'center 45%',
    caption: 'أرقام قياسية',
    tone: '#eab308',
  },
  general: {
    src: '/images/categories/riddles.jpg',
    position: 'center 38%',
    caption: 'معلومات عامة وعلوم',
    tone: '#38bdf8',
  },
  quran: {
    src: '/images/categories/riddles.jpg',
    position: 'center 30%',
    caption: 'تلاوة وتدبّر',
    tone: '#34d399',
  },
  nicknames: {
    src: '/images/categories/career.jpg',
    position: 'center 32%',
    caption: 'ألقاب نجوم الكرة',
    tone: '#fbbf24',
  },
  technology: {
    src: '/images/categories/riddles.jpg',
    position: 'center 42%',
    caption: 'شركات ومؤسسون وتقنية',
    tone: '#22d3ee',
  },
  videogames: {
    src: '/images/categories/spot.jpg',
    position: 'center 50%',
    caption: 'عوالم ألعاب الفيديو',
    tone: '#a78bfa',
  },
  matchstick: {
    src: '/images/categories/riddles.jpg',
    position: 'center 50%',
    caption: 'ألغاز أعواد الثقاب',
    tone: '#fb923c',
  },
  reverse: {
    src: '/images/categories/riddles.jpg',
    position: 'center 58%',
    caption: 'الجواب معروف… شنو السؤال؟',
    tone: '#f472b6',
  },
});

export const HERO_ART = Object.freeze({
  stage: { src: '/images/hero/stage.jpg', position: 'center 42%' },
  crowd: { src: '/images/hero/crowd.jpg', position: 'center 35%' },
});

export function categoryArt(categoryId) {
  return CATEGORY_ART[categoryId] ?? CATEGORY_ART.flags;
}

export const CATEGORY_TONES = Object.freeze(
  Object.fromEntries(Object.entries(CATEGORY_ART).map(([id, art]) => [id, art.tone])),
);
