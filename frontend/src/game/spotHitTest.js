/**
 * تحويل نقطة مؤشر من إحداثيات الشاشة إلى إحداثيات viewBox.
 * يستخدم في مشهد الفروقات وفي اختبارات عدة أحجام عرض.
 */
export function clientToSvgPoint(clientX, clientY, rect, viewBox = { width: 400, height: 300 }) {
  if (!rect || !Number.isFinite(rect.width) || !Number.isFinite(rect.height)) return null;
  if (rect.width <= 0 || rect.height <= 0) return null;
  return {
    x: ((clientX - rect.left) / rect.width) * viewBox.width,
    y: ((clientY - rect.top) / rect.height) * viewBox.height,
  };
}

export function distanceToDifference(difference, x, y) {
  return Math.hypot(x - difference.x, y - difference.y);
}

export function hitTestDifference(differences, x, y) {
  if (!Array.isArray(differences)) return null;
  for (const difference of differences) {
    if (distanceToDifference(difference, x, y) <= (difference.r ?? 24)) {
      return difference;
    }
  }
  return null;
}
