/** بطاقة سؤال معكوس: الجواب معروض، والاختيارات أسئلة — نكشف الصح بعد الكشف فقط. */
const LABELS = ['أ', 'ب', 'ج', 'د'];
const MAX_OPTION = 96;

const safeText = (value, max = MAX_OPTION) =>
  typeof value === 'string' &&
  value.trim().length > 0 &&
  value.length <= max &&
  !/[<>\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f]/u.test(value);

function validPayload(reverse) {
  if (!reverse || typeof reverse !== 'object') return false;
  if (!safeText(reverse.answer, 60)) return false;
  const options = reverse.options;
  if (!Array.isArray(options) || options.length !== 4) return false;
  if (!options.every((option) => safeText(option))) return false;
  if (new Set(options).size !== 4) return false;
  const index = reverse.correct_index;
  return index === undefined || (Number.isInteger(index) && index >= 0 && index < 4);
}

export default function ReverseRenderer({ question, revealed = false }) {
  const reverse = question?.reverse;
  if (!validPayload(reverse)) {
    return (
      <p role="status" dir="rtl" className="rounded-xl border border-orange-200 bg-orange-50 p-6 text-center text-lg text-ink-900">
        اختيارات السؤال المعكوس ما وصلت؛ جاوبوا من نص السؤال فوق.
      </p>
    );
  }
  const correctIndex = Number.isInteger(reverse.correct_index) ? reverse.correct_index : -1;
  const showCorrect = revealed && correctIndex >= 0;
  return (
    <figure dir="rtl" className="mx-auto w-full max-w-4xl rounded-2xl bg-white p-3 text-ink-900 sm:p-5">
      <figcaption className="mb-3 text-center text-base font-bold text-stone-600">
        نعكس السؤال: الجواب <bdi className="text-xl font-black text-brand-700">«{reverse.answer}»</bdi> — اختاروا السؤال اللي يوصّل له
      </figcaption>
      <ol aria-label="اختيارات السؤال المعكوس" className="grid gap-2 sm:grid-cols-2 sm:gap-3">
        {reverse.options.map((option, index) => {
          const isCorrect = showCorrect && index === correctIndex;
          return (
            <li
              key={option}
              className={`flex min-h-20 min-w-0 items-start gap-2 rounded-xl border-2 p-3 text-start ${
                isCorrect ? 'border-emerald-700 bg-emerald-50' : 'border-orange-200 bg-orange-50'
              }`}
            >
              <span aria-hidden="true" className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-600 text-sm font-black text-white">
                {LABELS[index]}
              </span>
              <span className="text-base font-bold leading-7 sm:text-lg">{option}</span>
              {isCorrect && <span className="ms-auto shrink-0 text-lg font-black text-emerald-700">✓</span>}
            </li>
          );
        })}
      </ol>
      {showCorrect && (
        <p className="mt-3 text-center text-base font-bold text-emerald-700">
          السؤال الصح: {reverse.options[correctIndex]}
        </p>
      )}
    </figure>
  );
}
