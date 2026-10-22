/**
 * مصدر الحقيقة الوحيد لبيانات اللعبة:
 * - 6 فئات، 36 خانة أساسية (خانتان لكل قيمة في كل فئة).
 * - 6 أسئلة احتياطية عامة متوافقة مع أي فئة وأي قيمة (لقوة «تغيير الميدان»).
 * - 7 قوى، ولكل قوة نافذة تفعيل يقرأها المتجر والواجهة من نفس التعريف.
 *
 * كل إجابة ثابتة وموثقة بشرح قصير. الأعلام من FlagCDN، ومشاهد الفروقات مرسومة
 * محليًا بـ SVG أصلي.
 */

export const SCHEMA_VERSION = 1;

export const POINT_VALUES = Object.freeze([200, 400, 600]);

export const CATEGORY_IDS = Object.freeze({
  FLAGS: 'flags',
  FOOTBALL: 'football',
  WORLD_CUP: 'worldcup',
  CAREER: 'career',
  RIDDLES: 'riddles',
  SPOT: 'spot',
});

export const CATEGORIES = Object.freeze([
  {
    id: CATEGORY_IDS.FLAGS,
    name: 'أعلام ودول',
    tagline: 'من وين هالعلم؟',
    description: 'أعلام وعواصم ومعلومات جغرافية من الخليج والعالم.',
    icon: 'Flag',
    accent: 'cyan',
  },
  {
    id: CATEGORY_IDS.FOOTBALL,
    name: 'كورة عامة',
    tagline: 'حبايب الكورة',
    description: 'أندية ولاعبون وقوانين اللعبة الأكثر شعبية.',
    icon: 'Goal',
    accent: 'lime',
  },
  {
    id: CATEGORY_IDS.WORLD_CUP,
    name: 'كأس العالم',
    tagline: 'ذاكرة المونديال',
    description: 'نسخ المونديال، أبطالها، وهدافوها عبر التاريخ.',
    icon: 'Trophy',
    accent: 'amber',
  },
  {
    id: CATEGORY_IDS.CAREER,
    name: 'مسيرة لاعب',
    tagline: 'منو هاللاعب؟',
    description: 'تتبّع محطات اللاعب من نادٍ لنادٍ… واعرف من هو.',
    icon: 'Route',
    accent: 'violet',
  },
  {
    id: CATEGORY_IDS.RIDDLES,
    name: 'ألغاز وفوازير',
    tagline: 'شغّل مخك',
    description: 'ألغاز شعبية وفوازير سريعة تحتاج تفكير.',
    icon: 'Puzzle',
    accent: 'pink',
  },
  {
    id: CATEGORY_IDS.SPOT,
    name: 'طلع الفرق',
    tagline: 'عينك عليها',
    description: 'لقّط ثلاث فروقات بين صورتين قبل ما يخلص الوقت.',
    icon: 'ScanSearch',
    accent: 'blue',
  },
]);

export const POWER_IDS = Object.freeze({
  PIT: 'pit',
  TRAP: 'trap',
  STEAL: 'steal',
  TWO_ANSWERS: 'two_answers',
  NOISE: 'noise',
  DOUBLE: 'double',
  SWITCH: 'switch',
});

/**
 * تعريفات القوى. الحقول activation هي مصدر التحقق في المتجر،
 * وtimingLabel/description هي نفس النصوص المعروضة بالبطاقات.
 */
export const POWERS = Object.freeze([
  {
    id: POWER_IDS.PIT,
    name: 'الحفرة',
    type: 'offensive',
    side: 'active',
    icon: 'TriangleAlert',
    tagline: 'طيح خصمك وياك',
    description:
      'إذا فزت بالسؤال، تاخذ قيمته كاملة وخصمك ينزل بنفس القيمة. ما يعطيك نقاط زيادة عن الجائزة العادية.',
    timingLabel: 'قبل إظهار الإجابة — للفريق صاحب الدور',
    activation: { side: 'active', phases: ['primary'], beforeReveal: true },
    accent: 'rose',
  },
  {
    id: POWER_IDS.TRAP,
    name: 'الفخ',
    type: 'defensive',
    side: 'defending',
    icon: 'Radar',
    tagline: 'مو كل سؤال يفوزون فيه',
    description:
      'تنصبه وأنت الفريق المدافع. إذا ما فاز صاحب الدور بالسؤال، ينخصم منه نص قيمة الخانة (تقريب للأسفل).',
    timingLabel: 'بعد فتح الخانة وقبل إظهار الإجابة',
    activation: { side: 'defending', phases: ['primary'], beforeReveal: true },
    accent: 'orange',
  },
  {
    id: POWER_IDS.STEAL,
    name: 'السرقة',
    type: 'tactical',
    side: 'defending',
    icon: 'Swords',
    tagline: 'الفريق الثاني يجاوب بدال الأول',
    description:
      'تسرق السؤال من صاحب الدور: فريقك يصير هو المطالب بالإجابة قبل الإظهار، وصاحب الدور الأصلي يصير مدافعًا. بعد الإظهار يظل المقدم مخيّرًا بين الفريقين.',
    timingLabel: 'قبل إظهار الإجابة — للفريق الثاني فقط',
    activation: { side: 'defending', phases: ['primary'], beforeReveal: true },
    accent: 'emerald',
  },
  {
    id: POWER_IDS.TWO_ANSWERS,
    name: 'جاوب جوابين',
    type: 'offensive',
    side: 'active',
    icon: 'GitBranch',
    tagline: 'لك محاولتين',
    description:
      'يعطيك محاولتين قبل إظهار الإجابة. المحاولة الخاطئة ما توقف الساعة ولا تكشف الإجابة.',
    timingLabel: 'قبل إظهار الإجابة',
    activation: { side: 'active', phases: ['primary'], beforeReveal: true },
    accent: 'sky',
  },
  {
    id: POWER_IDS.NOISE,
    name: 'التشويش',
    type: 'defensive',
    side: 'defending',
    icon: 'CloudFog',
    tagline: 'شوّش عليه 12 ثانية',
    description:
      'يضبّب نص السؤال وصوره لمدة 12 ثانية حقيقية والوقت يستمر. يشتغل مرة وحدة لكل مباراة.',
    timingLabel: 'خلال دور الخصم وقبل إظهار الإجابة',
    activation: { side: 'defending', phases: ['primary'], beforeReveal: true },
    accent: 'slate',
  },
  {
    id: POWER_IDS.DOUBLE,
    name: 'دبل أو ابلع',
    type: 'tactical',
    side: 'active',
    icon: 'Dices',
    tagline: 'ضعف الجائزة أو ضعف الخسارة',
    description:
      'إذا فزت تاخذ ضعف قيمة الخانة. إذا ما فزت تنخصم منك قيمة الخانة، وإذا فاز الخصم ياخذ قيمته العادية.',
    timingLabel: 'قبل إظهار الإجابة — للفريق صاحب الدور',
    activation: { side: 'active', phases: ['primary'], beforeReveal: true },
    accent: 'yellow',
  },
  {
    id: POWER_IDS.SWITCH,
    name: 'تغيير الميدان',
    type: 'tactical',
    side: 'active',
    icon: 'Shuffle',
    tagline: 'سؤال ثاني… من نفس الخانة',
    description:
      'خلال أول 15 ثانية من السؤال، بدّل السؤال بسؤال احتياطي غير مستخدم وأعد المؤقت من الصفر. قيمة الخانة وفئتها ما يتغيرون.',
    timingLabel: 'أول 15 ثانية من بداية السؤال فقط',
    activation: {
      side: 'active',
      phases: ['primary'],
      beforeReveal: true,
      maxElapsedMs: 15000,
      requiresBackup: true,
    },
    accent: 'indigo',
  },
]);

export const POWER_BY_ID = Object.freeze(
  Object.fromEntries(POWERS.map((power) => [power.id, power])),
);

export const CATEGORY_BY_ID = Object.freeze(
  Object.fromEntries(CATEGORIES.map((category) => [category.id, category])),
);

const PRIMARY_QUESTIONS = [
  // ── أعلام ودول ────────────────────────────────────────────────
  {
    id: 'q-flags-200-1',
    tileId: 'flags-200-1',
    categoryId: CATEGORY_IDS.FLAGS,
    points: 200,
    type: 'flag',
    iso2: 'lb',
    question: 'هالعلم فيه شجرة أرز خضراء بالوسط على خلفية بيضاء وحمراء… علم أي دولة؟',
    answer: 'لبنان',
    tolerance: 'لبنان، الجمهورية اللبنانية',
    explanation: 'شجرة الأرز رمز لبنان الوطني وتظهر في وسط علمه.',
  },
  {
    id: 'q-flags-200-2',
    tileId: 'flags-200-2',
    categoryId: CATEGORY_IDS.FLAGS,
    points: 200,
    type: 'flag',
    iso2: 'pt',
    question: 'علم أوروبي نصفه أخضر ونصفه أحمر، وفيه دائرة صفراء وشعار… لأي دولة؟',
    answer: 'البرتغال',
    tolerance: 'البرتغال، برتغال، Portugal',
    explanation: 'هذا العلم البرتغالي، والأخضر والأحمر هما لونا الجمهورية.',
  },
  {
    id: 'q-flags-400-1',
    tileId: 'flags-400-1',
    categoryId: CATEGORY_IDS.FLAGS,
    points: 400,
    type: 'standard',
    question: 'عاصمتها مسقط وتطل على بحر العرب… أي دولة خليجية هذي؟',
    answer: 'عُمان',
    tolerance: 'عمان، عُمان، سلطنة عمان',
    explanation: 'مسقط هي عاصمة سلطنة عُمان.',
  },
  {
    id: 'q-flags-400-2',
    tileId: 'flags-400-2',
    categoryId: CATEGORY_IDS.FLAGS,
    points: 400,
    type: 'flag',
    iso2: 'jp',
    question: 'علم أبيض وفي وسطه دائرة حمراء تمثل الشمس… علم أي دولة؟',
    answer: 'اليابان',
    tolerance: 'اليابان، يابان، Japan',
    explanation: 'الدائرة الحمراء في العلم الياباني ترمز للشمس.',
  },
  {
    id: 'q-flags-600-1',
    tileId: 'flags-600-1',
    categoryId: CATEGORY_IDS.FLAGS,
    points: 600,
    type: 'standard',
    question: 'علمها الوطني مكون من مثلثين ومو مستطيل ولا مربع… شنو هالدولة الوحيدة بالعالم؟',
    answer: 'نيبال',
    tolerance: 'نيبال، Nepal',
    explanation: 'علم نيبال مكوّن من مثلثين ويُعتبر العلم الوطني الوحيد غير الرباعي.',
  },
  {
    id: 'q-flags-600-2',
    tileId: 'flags-600-2',
    categoryId: CATEGORY_IDS.FLAGS,
    points: 600,
    type: 'flag',
    iso2: 'br',
    question: 'هالعلم فيه كرة سماوية ونجوم وعبارة وطنية… علم أي دولة؟',
    answer: 'البرازيل',
    tolerance: 'البرازيل، برازيل، Brazil',
    explanation: 'الكرة السماوية في علم البرازيل ترمز للسماء فوق البلاد.',
  },

  // ── كورة عامة ─────────────────────────────────────────────────
  {
    id: 'q-football-200-1',
    tileId: 'football-200-1',
    categoryId: CATEGORY_IDS.FOOTBALL,
    points: 200,
    type: 'standard',
    question: 'بداية المباراة ومعاهم الحارس… جم لاعب أساسي ينزل بالملعب لكل فريق؟',
    answer: '11',
    tolerance: '11، أحد عشر، احد عشر، ١١',
    explanation: 'كل فريق يبدأ بـ11 لاعبًا بينهم حارس مرمى.',
  },
  {
    id: 'q-football-200-2',
    tileId: 'football-200-2',
    categoryId: CATEGORY_IDS.FOOTBALL,
    points: 200,
    type: 'standard',
    question: 'من غير الوقت بدل الضايع… جم دقيقة مدة الشوط الواحد بكرة القدم؟',
    answer: '45',
    tolerance: '45، خمس وأربعين، خمس واربعين، ٤٥',
    explanation: 'المباراة شوطان، كل شوط 45 دقيقة مع الوقت بدل الضائع.',
  },
  {
    id: 'q-football-400-1',
    tileId: 'football-400-1',
    categoryId: CATEGORY_IDS.FOOTBALL,
    points: 400,
    type: 'standard',
    question: 'سجّل 260 هدف بمسيرته مع بلاكبيرن ونيوكاسل… منو الهداف التاريخي للبريميرليغ؟',
    answer: 'آلان شيرر',
    tolerance: 'الان شيرر، آلان شيرر، شيرر، Alan Shearer',
    explanation: 'سجّل آلان شيرر 260 هدفًا في البريميرليغ.',
  },
  {
    id: 'q-football-400-2',
    tileId: 'football-400-2',
    categoryId: CATEGORY_IDS.FOOTBALL,
    points: 400,
    type: 'standard',
    question: 'غلب ميلان 1–0 بنهائي ميونخ… أي نادي فرنسي فاز بأول نسخة من دوري الأبطال بمسماه الحديث 1992-93؟',
    answer: 'مارسيليا',
    tolerance: 'مارسيليا، مرسيليا، أولمبيك مارسيليا، Olympique Marseille',
    explanation: 'فاز أولمبيك مارسيليا على ميلان 1-0 في نهائي 1993.',
  },
  {
    id: 'q-football-600-1',
    tileId: 'football-600-1',
    categoryId: CATEGORY_IDS.FOOTBALL,
    points: 600,
    type: 'standard',
    question: 'يلقبونه العنكبوت الأسود وفاز فيها سنة 1963… منو حارس المرمى الوحيد اللي خذ الكرة الذهبية؟',
    answer: 'ليف ياشين',
    tolerance: 'ليف ياشين، ياشين، لف ياشين، Lev Yashin',
    explanation: 'فاز الحارس السوفييتي ليف ياشين بالكرة الذهبية سنة 1963.',
  },
  {
    id: 'q-football-600-2',
    tileId: 'football-600-2',
    categoryId: CATEGORY_IDS.FOOTBALL,
    points: 600,
    type: 'standard',
    question: 'المنتخب الوحيد اللي حاط خمس نجمات على شعاره… جم مرة فازت البرازيل بكأس العالم؟',
    answer: '5',
    tolerance: '5، خمس، خمس مرات، ٥',
    explanation: 'فازت البرازيل بأعوام 1958 و1962 و1970 و1994 و2002.',
  },

  // ── كأس العالم ────────────────────────────────────────────────
  {
    id: 'q-worldcup-200-1',
    tileId: 'worldcup-200-1',
    categoryId: CATEGORY_IDS.WORLD_CUP,
    points: 200,
    type: 'standard',
    question: 'استضافت أول نسخة سنة 1930 وفازت فيها على أرضها… أي دولة هذي؟',
    answer: 'أوروغواي',
    tolerance: 'أوروغواي، اوروغواي، أوروجواي، اوروجواي، الأوروغواي، Uruguay',
    explanation: 'استضافت أوروغواي مونديال 1930 وفازت فيه أيضًا.',
  },
  {
    id: 'q-worldcup-200-2',
    tileId: 'worldcup-200-2',
    categoryId: CATEGORY_IDS.WORLD_CUP,
    points: 200,
    type: 'standard',
    question: 'قبل التوسعة لـ48 منتخب… جم منتخب شارك في مونديال قطر 2022؟',
    answer: '32',
    tolerance: '32، اثنين وثلاثين، ٣٢',
    explanation: 'شارك 32 منتخبًا في نسخة 2022، قبل توسيعها لـ48 منتخبًا.',
  },
  {
    id: 'q-worldcup-400-1',
    tileId: 'worldcup-400-1',
    categoryId: CATEGORY_IDS.WORLD_CUP,
    points: 400,
    type: 'standard',
    question: 'حسمها ميسي ورفاقه بالترجيح على ملعب لوسيل… أي منتخب فاز بكأس العالم 2022؟',
    answer: 'الأرجنتين',
    tolerance: 'الأرجنتين، الارجنتين، ارجنتين، Argentina',
    explanation: 'فازت الأرجنتين على فرنسا بركلات الترجيح في نهائي قطر 2022.',
  },
  {
    id: 'q-worldcup-400-2',
    tileId: 'worldcup-400-2',
    categoryId: CATEGORY_IDS.WORLD_CUP,
    points: 400,
    type: 'standard',
    question: 'هدف ماريو غوتزه بالوقت الإضافي في الماراكانا… عطى مونديال 2014 لأي منتخب؟',
    answer: 'ألمانيا',
    tolerance: 'ألمانيا، المانيا، Germany',
    explanation: 'فازت ألمانيا على الأرجنتين 1-0 في نهائي 2014.',
  },
  {
    id: 'q-worldcup-600-1',
    tileId: 'worldcup-600-1',
    categoryId: CATEGORY_IDS.WORLD_CUP,
    points: 600,
    type: 'standard',
    question: 'وصل لـ16 هدف في أربع نسخ وكسر رقم الظاهرة رونالدو… منو الهداف التاريخي لكأس العالم؟',
    answer: 'ميروسلاف كلوزه',
    tolerance: 'كلوزه، ميروسلاف كلوزه، ميروسلاف كلوزة، Miroslav Klose',
    explanation: 'سجّل الألماني ميروسلاف كلوزه 16 هدفًا في نهائيات كأس العالم.',
  },
  {
    id: 'q-worldcup-600-2',
    tileId: 'worldcup-600-2',
    categoryId: CATEGORY_IDS.WORLD_CUP,
    points: 600,
    type: 'standard',
    question: 'أسود الأطلس أقصوا إسبانيا والبرتغال في قطر 2022… أي منتخب عربي وصل نص نهائي المونديال؟',
    answer: 'المغرب',
    tolerance: 'المغرب، مغرب، منتخب المغرب، Morocco',
    explanation: 'وصل المغرب لنصف نهائي 2022، أول منتخب عربي وأفريقي يصل لهذا الدور.',
  },

  // ── مسيرة لاعب ────────────────────────────────────────────────
  {
    id: 'q-career-200-1',
    tileId: 'career-200-1',
    categoryId: CATEGORY_IDS.CAREER,
    points: 200,
    type: 'career',
    question: 'هذي محطات لاعب من الأرجنتين… منو هو؟',
    career: [
      { club: 'برشلونة', years: '2004–2021' },
      { club: 'باريس سان جيرمان', years: '2021–2023' },
      { club: 'إنتر ميامي', years: '2023–' },
    ],
    answer: 'ليونيل ميسي',
    tolerance: 'ميسي، ليونيل ميسي، Lionel Messi',
    explanation: 'المسيرة تطابق ليونيل ميسي، صاحب ثماني كرات ذهبية.',
  },
  {
    id: 'q-career-200-2',
    tileId: 'career-200-2',
    categoryId: CATEGORY_IDS.CAREER,
    points: 200,
    type: 'career',
    question: 'محطات هذا اللاعب تبدأ من البرتغال وتنتهي بالسعودية… منو هو؟',
    career: [
      { club: 'سبورتينغ لشبونة', years: '2002–2003' },
      { club: 'مانشستر يونايتد', years: '2003–2009' },
      { club: 'ريال مدريد', years: '2009–2018' },
      { club: 'يوفنتوس', years: '2018–2021' },
      { club: 'مانشستر يونايتد', years: '2021–2022' },
      { club: 'النصر', years: '2023–' },
    ],
    answer: 'كريستيانو رونالدو',
    tolerance: 'رونالدو، كريستيانو رونالدو، كرستيانو رونالدو، Cristiano Ronaldo',
    explanation: 'هذه محطات كريستيانو رونالدو من سبورتينغ حتى النصر السعودي.',
  },
  {
    id: 'q-career-400-1',
    tileId: 'career-400-1',
    categoryId: CATEGORY_IDS.CAREER,
    points: 400,
    type: 'career',
    question: 'لاعب مصري بدأ من المقاولون العرب ووصل لليفربول… منو هو؟',
    career: [
      { club: 'المقاولون العرب', years: '2010–2012' },
      { club: 'بازل', years: '2012–2014' },
      { club: 'تشيلسي', years: '2014–2016' },
      { club: 'فيورنتينا', years: '2015', loan: true },
      { club: 'روما', years: '2015–2016', loan: true },
      { club: 'روما', years: '2016–2017' },
      { club: 'ليفربول', years: '2017–' },
    ],
    answer: 'محمد صلاح',
    tolerance: 'صلاح، محمد صلاح، Mohamed Salah',
    explanation: 'هذه مسيرة محمد صلاح، ومنها فترتا إعارة لفيورنتينا وروما.',
  },
  {
    id: 'q-career-400-2',
    tileId: 'career-400-2',
    categoryId: CATEGORY_IDS.CAREER,
    points: 400,
    type: 'career',
    question: 'لاعب فرنسي يلقّب بالقط، لعب لليون وريال مدريد… منو هو؟',
    career: [
      { club: 'ليون', years: '2004–2009' },
      { club: 'ريال مدريد', years: '2009–2023' },
      { club: 'الاتحاد', years: '2023–' },
    ],
    answer: 'كريم بنزيما',
    tolerance: 'بنزيما، كريم بنزيما، Karim Benzema',
    explanation: 'هذه محطات كريم بنزيما الفائز بالكرة الذهبية 2022.',
  },
  {
    id: 'q-career-600-1',
    tileId: 'career-600-1',
    categoryId: CATEGORY_IDS.CAREER,
    points: 600,
    type: 'career',
    question: 'مسيرة طويلة من السويد مرورًا بهولندا وإيطاليا وفرنسا… منو اللاعب؟',
    career: [
      { club: 'مالمو', years: '1999–2001' },
      { club: 'أياكس', years: '2001–2004' },
      { club: 'يوفنتوس', years: '2004–2006' },
      { club: 'إنتر ميلان', years: '2006–2009' },
      { club: 'برشلونة', years: '2009–2010' },
      { club: 'ميلان', years: '2010–2012' },
      { club: 'باريس سان جيرمان', years: '2012–2016' },
      { club: 'مانشستر يونايتد', years: '2016–2018' },
      { club: 'لوس أنجلوس غالاكسي', years: '2018–2019' },
      { club: 'ميلان', years: '2020–2023' },
    ],
    answer: 'زلاتان إبراهيموفيتش',
    tolerance: 'زلاتان، إبراهيموفيتش، ابراهيموفيتش، زلاتان ابراهيموفيتش، Zlatan Ibrahimovic',
    explanation: 'هذه مسيرة زلاتان إبراهيموفيتش الطويلة بين أندية أوروبا.',
  },
  {
    id: 'q-career-600-2',
    tileId: 'career-600-2',
    categoryId: CATEGORY_IDS.CAREER,
    points: 600,
    type: 'career',
    question: 'لاعب إسباني صنع مجد برشلونة ثم لعب في اليابان والإمارات… منو؟',
    career: [
      { club: 'برشلونة', years: '2002–2018' },
      { club: 'فيسيل كوبي', years: '2018–2023' },
      { club: 'الإمارات', years: '2023–2024' },
    ],
    answer: 'أندريس إنييستا',
    tolerance: 'إنييستا، انييستا، أندريس إنييستا، اندريس انييستا، Andres Iniesta',
    explanation: 'هذه محطات أندريس إنييستا بعد مسيرته الطويلة مع برشلونة.',
  },

  // ── ألغاز وفوازير ────────────────────────────────────────────
  {
    id: 'q-riddles-200-1',
    tileId: 'riddles-200-1',
    categoryId: CATEGORY_IDS.RIDDLES,
    points: 200,
    type: 'standard',
    question: 'شي إذا أخذت منه كِبر… وإذا تركته صِغر. شنو هو؟',
    answer: 'الحفرة',
    tolerance: 'حفرة، الحفرة، الحفره، حفره',
    explanation: 'كل ما نزيل منه تراب يكبر، وكل ما نردّه يصغر.',
  },
  {
    id: 'q-riddles-200-2',
    tileId: 'riddles-200-2',
    categoryId: CATEGORY_IDS.RIDDLES,
    points: 200,
    type: 'standard',
    question: 'شي يمشي بلا رجلين ويبكي بلا عينين؟',
    answer: 'السحاب',
    tolerance: 'السحاب، سحاب، الغيم، غيم، الغيوم',
    explanation: 'السحاب يتحرك مع الريح وينزل منه المطر.',
  },
  {
    id: 'q-riddles-400-1',
    tileId: 'riddles-400-1',
    categoryId: CATEGORY_IDS.RIDDLES,
    points: 400,
    type: 'standard',
    question: 'أنا ابن الماء، وإذا حطيتني في الماء أموت. من أنا؟',
    answer: 'الثلج',
    tolerance: 'ثلج، الثلج، الجليد',
    explanation: 'الثلج يتكوّن من الماء ويتحول لماء إذا ذاب.',
  },
  {
    id: 'q-riddles-400-2',
    tileId: 'riddles-400-2',
    categoryId: CATEGORY_IDS.RIDDLES,
    points: 400,
    type: 'standard',
    question: 'شي كلما زاد… نقص. شنو هو؟',
    answer: 'العمر',
    tolerance: 'العمر، عمر، العمر',
    explanation: 'كل سنة تمر تزيد عمرك وتنقص من الوقت المتبقي.',
  },
  {
    id: 'q-riddles-600-1',
    tileId: 'riddles-600-1',
    categoryId: CATEGORY_IDS.RIDDLES,
    points: 600,
    type: 'standard',
    question: 'شي يكتب ولا يقرأ؟',
    answer: 'القلم',
    tolerance: 'القلم، قلم، اليراع',
    explanation: 'القلم يكتب لكنه لا يقرأ ما كتب.',
  },
  {
    id: 'q-riddles-600-2',
    tileId: 'riddles-600-2',
    categoryId: CATEGORY_IDS.RIDDLES,
    points: 600,
    type: 'standard',
    question: 'شي عنده أسنان بس ما يعض؟',
    answer: 'المشط',
    tolerance: 'المشط، مشط',
    explanation: 'أسنان المشط مرتبة لكنها لا تعض.',
  },

  // ── طلع الفرق ────────────────────────────────────────────────
  {
    id: 'q-spot-200-1',
    tileId: 'spot-200-1',
    categoryId: CATEGORY_IDS.SPOT,
    points: 200,
    type: 'spot_diff',
    sceneId: 'towers',
    question: 'لقّط الفروقات الثلاثة بين الصورتين… عينك على أبراج الكويت.',
    answer: 'العصفور الإضافي، لون العلم، وعدد النوافذ المضيئة.',
    tolerance: 'العصفور، العلم، النوافذ',
    explanation:
      'الصورة الثانية فيها عصفور ثالث، العلم صار أحمر بدل الأخضر، وفي نافذة مضيئة إضافية بالبرج.',
    differences: [
      { id: 'bird', label: 'العصفور الإضافي', x: 315, y: 70, r: 32 },
      { id: 'flag', label: 'لون العلم', x: 150, y: 80, r: 28 },
      { id: 'window', label: 'نافذة مضيئة إضافية', x: 215, y: 170, r: 34 },
    ],
  },
  {
    id: 'q-spot-200-2',
    tileId: 'spot-200-2',
    categoryId: CATEGORY_IDS.SPOT,
    points: 200,
    type: 'spot_diff',
    sceneId: 'dhow',
    question: 'لقّط الفروقات الثلاثة… هذي المرة على سطح البحر.',
    answer: 'لون الشراع، مكان الشمس، وعدد الأسماك.',
    tolerance: 'الشراع، الشمس، الأسماك',
    explanation:
      'الشراع صار بلون مختلف، الشمس تحركت خلف السحاب، وظهرت سمكة ثالثة قريبة من المركب.',
    differences: [
      { id: 'sail', label: 'لون الشراع', x: 205, y: 155, r: 40 },
      { id: 'sun', label: 'مكان الشمس', x: 330, y: 70, r: 32 },
      { id: 'fish', label: 'السمكة الإضافية', x: 320, y: 230, r: 30 },
    ],
  },
  {
    id: 'q-spot-400-1',
    tileId: 'spot-400-1',
    categoryId: CATEGORY_IDS.SPOT,
    points: 400,
    type: 'spot_diff',
    sceneId: 'desert',
    question: 'في مخيّم بالبر… لقّط الفروقات الثلاثة بين الصورتين.',
    answer: 'عدد الجمال، لون باب الخيمة، واتجاه الهلال.',
    tolerance: 'الجمال، باب الخيمة، الهلال',
    explanation:
      'ظهر جمل إضافي، تغيّر لون باب الخيمة، وانعكس اتجاه الهلال في السماء.',
    differences: [
      { id: 'camel', label: 'الجمل الإضافي', x: 150, y: 205, r: 40 },
      { id: 'tent-door', label: 'لون باب الخيمة', x: 260, y: 205, r: 26 },
      { id: 'moon', label: 'اتجاه الهلال', x: 340, y: 65, r: 28 },
    ],
  },
  {
    id: 'q-spot-400-2',
    tileId: 'spot-400-2',
    categoryId: CATEGORY_IDS.SPOT,
    points: 400,
    type: 'spot_diff',
    sceneId: 'souq',
    question: 'هالمشهد من سوق قديم… لقّط الفروقات الثلاثة.',
    answer: 'عدد الفوانيس، لون المظلة، وحجم الصندوق.',
    tolerance: 'الفوانيس، المظلة، الصندوق',
    explanation:
      'فانوس ثالث معلّق، تغيّر لون خطوط المظلة، وصار الصندوق أكبر.',
    differences: [
      { id: 'lantern', label: 'الفانوس الإضافي', x: 130, y: 110, r: 28 },
      { id: 'awning', label: 'لون خطوط المظلة', x: 270, y: 105, r: 34 },
      { id: 'crate', label: 'حجم الصندوق', x: 320, y: 235, r: 28 },
    ],
  },
  {
    id: 'q-spot-600-1',
    tileId: 'spot-600-1',
    categoryId: CATEGORY_IDS.SPOT,
    points: 600,
    type: 'spot_diff',
    sceneId: 'stadium',
    question: 'دقيقة أخيرة بالملعب… لقّط الفروقات الثلاثة بين اللقطتين.',
    answer: 'نتيجة الشاشة، لون الراية، وعدد الأوشحة.',
    tolerance: 'الشاشة، الراية، الأوشحة',
    explanation:
      'رقم الشاشة تغيّر، صار لون الراية أصفر، وظهر وشاح ثالث بالمدرجات.',
    differences: [
      { id: 'score', label: 'نتيجة الشاشة', x: 200, y: 80, r: 38 },
      { id: 'flag', label: 'لون الراية', x: 330, y: 120, r: 30 },
      { id: 'scarf', label: 'الوشاح الإضافي', x: 110, y: 225, r: 32 },
    ],
  },
  {
    id: 'q-spot-600-2',
    tileId: 'spot-600-2',
    categoryId: CATEGORY_IDS.SPOT,
    points: 600,
    type: 'spot_diff',
    sceneId: 'mosque',
    question: 'ليلة هادئة عند المسجد… لقّط الفروقات الثلاثة.',
    answer: 'شكل القمر، عدد نوافذ المئذنة، ووجود النخلة.',
    tolerance: 'القمر، النوافذ، النخلة',
    explanation:
      'القمر صار بدرًا، ظهرت نافذة إضافية بالمئذنة، واختفت نخلة من الجهة اليسرى.',
    differences: [
      { id: 'moon', label: 'شكل القمر', x: 330, y: 65, r: 28 },
      { id: 'window', label: 'نافذة المئذنة الإضافية', x: 250, y: 170, r: 26 },
      { id: 'palm', label: 'النخلة المختفية', x: 90, y: 190, r: 38 },
    ],
  },
];

const REQUIRED_QUESTION_FIELDS = ['id', 'categoryId', 'points', 'type', 'question', 'answer', 'tolerance', 'explanation'];
const VALID_QUESTION_TYPES = new Set(['standard', 'flag', 'career', 'spot_diff']);

const BACKUP_QUESTIONS = [
  {
    id: 'backup-1',
    type: 'standard',
    question: 'يرتفع حوالي 413 متر في قلب العاصمة… شنو اسم أطول برج في الكويت؟',
    answer: 'برج الحمراء',
    tolerance: 'الحمراء، برج الحمراء، Al Hamra Tower',
    explanation: 'برج الحمراء في مدينة الكويت هو أطول برج في البلاد (حوالي 413 مترًا).',
    compatibleCategoryIds: CATEGORIES.map((category) => category.id),
    compatiblePoints: [...POINT_VALUES],
  },
  {
    id: 'backup-2',
    type: 'standard',
    question: 'الكويت والسعودية والإمارات وقطر والبحرين وعُمان… جم عدد دول مجلس التعاون الخليجي؟',
    answer: '6',
    tolerance: '6، ست، ست دول، ٦',
    explanation: 'الدول الأعضاء: السعودية، الإمارات، قطر، الكويت، البحرين، وعُمان.',
    compatibleCategoryIds: CATEGORIES.map((category) => category.id),
    compatiblePoints: [...POINT_VALUES],
  },
  {
    id: 'backup-3',
    type: 'standard',
    question: 'ينقسم لـ1000 فلس ويُعتبر من أقوى العملات بالعالم… شنو العملة الرسمية في الكويت؟',
    answer: 'الدينار الكويتي',
    tolerance: 'الدينار، دينار، الدينار الكويتي، دينار كويتي',
    explanation: 'الدينار الكويتي هو العملة الرسمية، ويُقسم إلى 1000 فلس.',
    compatibleCategoryIds: CATEGORIES.map((category) => category.id),
    compatiblePoints: [...POINT_VALUES],
  },
  {
    id: 'backup-4',
    type: 'standard',
    question: 'في عهد الشيخ عبدالله السالم الصباح بتاريخ 19 يونيو… بأي سنة استقلت الكويت؟',
    answer: '1961',
    tolerance: '1961، ألف وتسعمية وواحد وستين، ١٩٦١',
    explanation: 'استقلت الكويت في 19 يونيو 1961.',
    compatibleCategoryIds: CATEGORIES.map((category) => category.id),
    compatiblePoints: [...POINT_VALUES],
  },
  {
    id: 'backup-5',
    type: 'standard',
    question: 'فيها آثار إغريقية ودلمونية بالخليج العربي… شنو اسم الجزيرة الكويتية الأثرية الشهيرة؟',
    answer: 'فيلكا',
    tolerance: 'فيلكا، فيلكه، جزيرة فيلكا',
    explanation: 'جزيرة فيلكا من أهم المواقع الأثرية في الكويت.',
    compatibleCategoryIds: CATEGORIES.map((category) => category.id),
    compatiblePoints: [...POINT_VALUES],
  },
  {
    id: 'backup-6',
    type: 'standard',
    question: 'من الأحمر لين البنفسجي بالسماء عقب المطر… جم عدد ألوان قوس قزح؟',
    answer: '7',
    tolerance: '7، سبع، سبعة، ٧',
    explanation: 'الألوان السبعة: أحمر، برتقالي، أصفر، أخضر، أزرق، نيلي، بنفسجي.',
    compatibleCategoryIds: CATEGORIES.map((category) => category.id),
    compatiblePoints: [...POINT_VALUES],
  },
];

export const QUESTIONS = Object.freeze(PRIMARY_QUESTIONS);
export const BACKUPS = Object.freeze(BACKUP_QUESTIONS);

export const QUESTION_BY_ID = Object.freeze(
  Object.fromEntries(QUESTIONS.map((question) => [question.id, question])),
);
export const BACKUP_BY_ID = Object.freeze(
  Object.fromEntries(BACKUPS.map((question) => [question.id, question])),
);

/**
 * الخانات 36. لكل فئة خانتان بقيمة 200، واثنتان 400، واثنتان 600.
 * نستخدم tileId الثابت من السؤال — لا مؤشرات مصفوفة.
 */
export const TILES = Object.freeze(
  QUESTIONS.map((question) =>
    Object.freeze({
      id: question.tileId,
      categoryId: question.categoryId,
      points: question.points,
      questionId: question.id,
    }),
  ),
);

export const TILE_BY_ID = Object.freeze(
  Object.fromEntries(TILES.map((tile) => [tile.id, tile])),
);

export const TILES_BY_CATEGORY = Object.freeze(
  Object.fromEntries(
    CATEGORIES.map((category) => [
      category.id,
      TILES.filter((tile) => tile.categoryId === category.id),
    ]),
  ),
);

export const TOTAL_PRIMARY_TILES = TILES.length;
export const PRIMARY_SECONDS = 60;
export const STEAL_SECONDS = 10;
export const TWO_ANSWER_EXTENSION_MS = 15000;
export const NOISE_DURATION_MS = 12000;
export const SWITCH_FIELD_WINDOW_MS = 15000;

export function flagUrl(iso2) {
  return `https://flagcdn.com/w640/${iso2}.png`;
}

export function getCategory(categoryId) {
  return CATEGORY_BY_ID[categoryId] ?? null;
}

export function getPower(powerId) {
  return POWER_BY_ID[powerId] ?? null;
}

export function getTile(tileId) {
  return TILE_BY_ID[tileId] ?? null;
}

export function getQuestion(questionId) {
  return QUESTION_BY_ID[questionId] ?? null;
}

/** يحل سؤال الجلسة سواء كان أساسيًا أو احتياطيًا. */
export function getSessionQuestion(questionId) {
  return QUESTION_BY_ID[questionId] ?? BACKUP_BY_ID[questionId] ?? null;
}

export function getBackup(backupId) {
  return BACKUP_BY_ID[backupId] ?? null;
}

/**
 * الأسئلة الاحتياطية الستة عامة ومعلّمة كمتوافقة مع كل الفئات والقيم،
 * لذلك «تغيير الميدان» يشتغل بأي خانة حتى تنتهي الأسئلة الاحتياطية.
 */
export function getCompatibleBackups(categoryId, points, usedBackupIds = []) {
  const used = new Set(usedBackupIds);
  return BACKUPS.filter(
    (backup) =>
      !used.has(backup.id) &&
      backup.compatibleCategoryIds.includes(categoryId) &&
      backup.compatiblePoints.includes(points),
  );
}

export function selectCompatibleBackup(categoryId, points, usedBackupIds = []) {
  return getCompatibleBackups(categoryId, points, usedBackupIds)[0] ?? null;
}

/**
 * تحقق تطويري صارم من سلامة البيانات. يُستدعى عند تحميل الوحدة في وضع التطوير،
 * وكذلك من الاختبارات. أي خلل يرمي خطأ واضحًا بدل تشغيل لعبة مكسورة.
 */
export function validateGameData() {
  const errors = [];

  if (CATEGORIES.length !== 6) errors.push('لازم يكون عندنا 6 فئات بالضبط.');
  if (POWERS.length < 6) errors.push('لازم يكون عندنا 6 قوى على الأقل للسحب.');
  if (QUESTIONS.length !== 36) errors.push('لازم يكون عندنا 36 سؤالًا أساسيًا بالضبط.');
  if (BACKUPS.length !== 6) errors.push('لازم يكون عندنا 6 أسئلة احتياطية بالضبط.');
  if (TILES.length !== 36) errors.push('لازم يكون عندنا 36 خانة أساسية بالضبط.');

  const categoryIds = new Set(CATEGORIES.map((category) => category.id));
  const categoryNames = new Set();
  for (const category of CATEGORIES) {
    if (!category.id || !category.name || !category.icon) {
      errors.push(`فئة ناقصة البيانات: ${category.id ?? 'بدون معرّف'}`);
    }
    if (categoryNames.has(category.name)) {
      errors.push(`اسم فئة مكرر: ${category.name}`);
    }
    categoryNames.add(category.name);
  }

  const questionIds = new Set();
  const tileIds = new Set();
  const perCategoryValue = new Map();

  for (const question of QUESTIONS) {
    for (const field of REQUIRED_QUESTION_FIELDS) {
      if (question[field] === undefined || question[field] === null || question[field] === '') {
        errors.push(`السؤال ${question.id ?? 'بدون معرّف'} ناقص الحقل ${field}.`);
      }
    }
    if (questionIds.has(question.id)) errors.push(`معرّف سؤال مكرر: ${question.id}`);
    questionIds.add(question.id);

    if (!tileIds.has(question.tileId)) {
      if (!question.tileId) errors.push(`السؤال ${question.id} بدون tileId.`);
      tileIds.add(question.tileId);
    } else {
      errors.push(`معرّف خانة مكرر: ${question.tileId}`);
    }

    if (!categoryIds.has(question.categoryId)) {
      errors.push(`السؤال ${question.id} يشير لفئة غير موجودة: ${question.categoryId}`);
    }
    if (!POINT_VALUES.includes(question.points)) {
      errors.push(`السؤال ${question.id} له قيمة غير مسموحة: ${question.points}`);
    }
    if (!VALID_QUESTION_TYPES.has(question.type)) {
      errors.push(`السؤال ${question.id} له نوع غير معروف: ${question.type}`);
    }

    const key = `${question.categoryId}:${question.points}`;
    perCategoryValue.set(key, (perCategoryValue.get(key) ?? 0) + 1);

    if (question.type === 'flag') {
      if (!/^[a-z]{2}$/.test(question.iso2 ?? '')) {
        errors.push(`سؤال العلم ${question.id} له رمز ISO غير صالح.`);
      }
    }

    if (question.type === 'career') {
      if (!Array.isArray(question.career) || question.career.length < 2) {
        errors.push(`سؤال المسيرة ${question.id} يحتاج مصفوفة محطات.`);
      } else {
        for (const stop of question.career) {
          if (!stop.club || !stop.years) {
            errors.push(`محطة ناقصة في سؤال المسيرة ${question.id}.`);
          }
        }
      }
    }

    if (question.type === 'spot_diff') {
      if (!question.sceneId) errors.push(`سؤال الفروقات ${question.id} بدون sceneId.`);
      const differences = question.differences;
      if (!Array.isArray(differences) || differences.length !== 3) {
        errors.push(`سؤال الفروقات ${question.id} لازم يكون فيه 3 فروقات بالضبط.`);
      } else {
        const diffIds = new Set();
        for (const diff of differences) {
          if (!diff.id || !diff.label) {
            errors.push(`فرق ناقص المعرّف/الوصف في ${question.id}.`);
          }
          if (diffIds.has(diff.id)) errors.push(`فرق مكرر ${diff.id} في ${question.id}.`);
          diffIds.add(diff.id);
          if (![diff.x, diff.y, diff.r].every(Number.isFinite)) {
            errors.push(`إحداثيات فرق غير صالحة في ${question.id}.`);
          }
        }
      }
    }
  }

  for (const category of CATEGORIES) {
    for (const points of POINT_VALUES) {
      const count = perCategoryValue.get(`${category.id}:${points}`) ?? 0;
      if (count !== 2) {
        errors.push(`الفئة ${category.id} لازم فيها خانتان بقيمة ${points}، الموجود ${count}.`);
      }
    }
  }

  for (const tile of TILES) {
    const question = QUESTION_BY_ID[tile.questionId];
    if (!question) errors.push(`الخانة ${tile.id} تشير لسؤال غير موجود.`);
    if (!categoryIds.has(tile.categoryId)) errors.push(`الخانة ${tile.id} لها فئة غير معروفة.`);
    if (!POINT_VALUES.includes(tile.points)) errors.push(`الخانة ${tile.id} لها قيمة غير صالحة.`);
    if (question && (question.categoryId !== tile.categoryId || question.points !== tile.points)) {
      errors.push(`بيانات الخانة ${tile.id} لا تطابق سؤالها.`);
    }
  }

  const backupIds = new Set();
  for (const backup of BACKUPS) {
    if (!backup.id || backupIds.has(backup.id)) errors.push(`معرّف احتياطي مكرر: ${backup.id}`);
    backupIds.add(backup.id);
    if (!backup.question || !backup.answer || !backup.explanation) {
      errors.push(`سؤال احتياطي ناقص: ${backup.id}`);
    }
    if (!Array.isArray(backup.compatibleCategoryIds) || backup.compatibleCategoryIds.length === 0) {
      errors.push(`السؤال الاحتياطي ${backup.id} بدون فئات متوافقة.`);
    } else {
      for (const categoryId of backup.compatibleCategoryIds) {
        if (!categoryIds.has(categoryId)) {
          errors.push(`السؤال الاحتياطي ${backup.id} يشير لفئة غير موجودة.`);
        }
      }
    }
    if (!Array.isArray(backup.compatiblePoints) || backup.compatiblePoints.length === 0) {
      errors.push(`السؤال الاحتياطي ${backup.id} بدون قيم متوافقة.`);
    } else {
      for (const points of backup.compatiblePoints) {
        if (!POINT_VALUES.includes(points)) {
          errors.push(`السؤال الاحتياطي ${backup.id} له قيمة غير صالحة.`);
        }
      }
    }
  }

  const powerIds = new Set();
  for (const power of POWERS) {
    if (powerIds.has(power.id)) errors.push(`معرّف قوة مكرر: ${power.id}`);
    powerIds.add(power.id);
    if (!power.name || !power.description || !power.timingLabel || !power.icon) {
      errors.push(`قوة ناقصة البيانات: ${power.id}`);
    }
    if (!['offensive', 'defensive', 'tactical'].includes(power.type)) {
      errors.push(`نوع قوة غير معروف: ${power.id}`);
    }
    if (!['active', 'defending'].includes(power.activation?.side)) {
      errors.push(`جهة تفعيل غير معروفة للقوة ${power.id}.`);
    }
    if (!Array.isArray(power.activation?.phases) || power.activation.phases.length === 0) {
      errors.push(`نوافذ طور غير صالحة للقوة ${power.id}.`);
    }
  }

  if (errors.length > 0) {
    throw new Error(`بيانات اللعبة غير صالحة:\n- ${errors.join('\n- ')}`);
  }

  return true;
}

if (import.meta.env?.DEV) {
  validateGameData();
}
