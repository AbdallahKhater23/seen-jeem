export default function BrandMark({ compact = false }) {
  return (
    <span className={`brand-mark ${compact ? 'brand-mark--compact' : ''}`} aria-label="سين جيم">
      <span className="brand-mark__symbol" aria-hidden="true">س<span>ج</span></span>
      <span className="brand-mark__words">سين جيم<small>اللّمّة تحلى بالتحدّي</small></span>
    </span>
  );
}
