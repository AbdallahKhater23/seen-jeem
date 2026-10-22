const EDITABLE_SELECTOR =
  'input, textarea, select, [contenteditable="true"], [contenteditable=""], [role="textbox"]';

export function isEditableTarget(target) {
  if (!target || typeof target !== 'object') return false;
  if (target.isContentEditable) return true;
  if (typeof target.tagName === 'string') {
    const tag = target.tagName.toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  }
  if (typeof target.closest === 'function') {
    try {
      return Boolean(target.closest(EDITABLE_SELECTOR));
    } catch {
      return false;
    }
  }
  return false;
}

/**
 * اختصارات الساحة تُتجاهل داخل الحقول، أثناء تركيب IME، مع أزرار التعديل،
 * وعند ضغط مطوّل (repeat) حتى لا تتكرر الحركة.
 */
export function shouldIgnoreShortcut(event) {
  if (!event) return true;
  if (event.isComposing || event.keyCode === 229) return true;
  if (event.repeat) return true;
  if (event.ctrlKey || event.metaKey || event.altKey) return true;
  return isEditableTarget(event.target);
}

export const ARENA_SHORTCUTS = Object.freeze([
  { key: ' ', label: 'مسافة', action: 'تشغيل / إيقاف عدّاد الوقت' },
  { key: 'r', label: 'R', action: 'إظهار الإجابة' },
  { key: '1', label: '1', action: 'فوز الفريق الأول' },
  { key: '2', label: '2', action: 'فوز الفريق الثاني' },
  { key: '0', label: '0', action: 'ولا أحد' },
  { key: 'Escape', label: 'Esc', action: 'ترك الخانة بدون تسجيل' },
]);
