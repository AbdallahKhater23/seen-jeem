/**
 * عميل الكتالوج والمزامنة.
 *
 * يبقى `server.js` مسؤولًا عن محوّل المباراة (snake_case ↔ camelCase)، وهذا
 * الملف يضيف ما تحتاجه الصالة وشاشة المقدم فقط: قراءة الفئات الاثنتي عشرة،
 * وبدء/متابعة مزامنة بنك الأسئلة. كل عملية تغيير تمر بـ Idempotency-Key عند
 * الحاجة، وأي فشل يُرمى كخطأ API واضح لا يُبتلع.
 */
import { api, API_BASE_URL, ApiError } from './server.js';
import { toFrontendCategory } from '@trivia-adapter';

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { Accept: 'application/json', ...(options.headers ?? {}) },
  });
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = null;
  }
  if (!response.ok) throw new ApiError(response.status, payload);
  return payload;
}

/** يطبّع استجابة /categories إلى شكل ثابت للواجهة. */
export function normalizeCategories(rows) {
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => ({
    id: toFrontendCategory(row.slug),
    backendSlug: row.slug,
    name: row.name_ar,
    icon: row.icon || 'Sparkles',
    sortOrder: row.sort_order ?? 0,
    eligibleCount: Number.isFinite(row.eligible_count) ? row.eligible_count : 0,
    factGroups: Number.isFinite(row.fact_groups) ? row.fact_groups : 0,
    capacity100Matches: Boolean(row.capacity_100_matches),
  }));
}

export async function fetchCategories() {
  return normalizeCategories(await api.categories());
}

export async function startPoolSync(source = 'restcountries') {
  return requestJson(`/pool/sync?source=${encodeURIComponent(source)}`, { method: 'POST' });
}

export async function fetchPoolSyncStatus() {
  return requestJson('/pool/sync');
}

export { api, API_BASE_URL, ApiError };
