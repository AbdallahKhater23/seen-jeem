import Icon from './Icon.jsx';

export default function CareerPathRenderer({ career }) {
  const stops = Array.isArray(career) ? career : [];
  return (
    <section
      className="w-full rounded-2xl border border-violet-400/20 bg-white p-3 xl:p-4"
      aria-label="محطات مسيرة اللاعب"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-violet-700">
          <Icon name="Route" size={16} />
          <h3 className="text-xs font-extrabold xl:text-sm">محطات المسيرة</h3>
        </div>
        <div className="flex items-center gap-1.5 text-xs font-bold text-stone-600">
          <span>الأقدم</span>
          <Icon name="ChevronLeft" size={13} />
          <span className="text-violet-700">الأحدث</span>
        </div>
      </div>

      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" dir="rtl">
        {stops.map((stop, index) => (
          <li
            key={`${stop.club}-${stop.years}-${index}`}
            className="relative flex min-h-[4.25rem] flex-col justify-center rounded-xl border border-stone-200 bg-white px-2.5 py-2"
          >
            <span className="absolute end-2 top-1 text-xs font-bold text-stone-600">
              <span className="ltr">{String(index + 1).padStart(2, '0')}</span>
            </span>
            <p className="pl-3 text-[13px] font-extrabold leading-5 text-ink-900 xl:text-[13px]">
              {stop.club}
            </p>
            <div className="mt-0.5 flex flex-wrap items-center gap-1">
              <span className="ltr rounded-md bg-white/10 px-1.5 py-0.5 text-xs font-bold text-stone-600">
                {stop.years}
              </span>
              {stop.loan && (
                <span className="rounded-md border border-amber-400/30 bg-amber-400/10 px-1.5 py-0.5 text-xs font-bold text-amber-800">
                  إعارة
                </span>
              )}
            </div>
            {index < stops.length - 1 && (
              <Icon
                name="ChevronLeft"
                size={12}
                className="absolute -left-2 top-1/2 hidden -translate-y-1/2 text-violet-400/50 sm:block"
              />
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
