/**
 * حدود الواجهة مع FastAPI.
 *
 * المحوّل نفسه يعيش في backend/integration/frontendAdapter.js ويُستورد عبر
 * alias `@trivia-adapter` حتى يبقى مصدر حقيقة واحد للعقد (snake_case ↔ camelCase).
 * Vite يوجّه /api/v1 إلى FastAPI محليًا (انظر vite.config.js).
 */
import {
  ApiError,
  createApiClient,
  makeIdempotencyKey,
  toFrontendActivationResult,
  toFrontendBoard,
  toFrontendDraft,
  toFrontendDraftResult,
  toFrontendParticipant,
  toFrontendResolveResult,
  toFrontendRerollResult,
  toFrontendTileSessionResult,
} from '@trivia-adapter';

export const API_BASE_URL = (import.meta.env?.VITE_API_URL || '/api/v1').replace(/\/$/, '');

export const api = createApiClient({ baseUrl: API_BASE_URL });

export {
  ALL_CATEGORY_SLUGS,
  ApiError,
  makeIdempotencyKey,
  toBackendCategorySlug,
  toFrontendActivationResult,
  toFrontendBoard,
  toFrontendCategory,
  toFrontendDraft,
  toFrontendDraftResult,
  toFrontendParticipant,
  toFrontendRerollResult,
  toFrontendResolveResult,
  toFrontendTileSessionResult,
} from '@trivia-adapter';

const ERROR_LABELS = {
  STALE_MATCH_VERSION: 'نسخة المباراة تغيّرت — جاري المزامنة مع السيرفر.',
  MATCH_NOT_ACTIVE: 'هالمباراة منتهية على السيرفر.',
  TILE_ALREADY_PLAYED: 'هالخانة انلعبت من قبل على السيرفر.',
  TILE_NOT_PLAYABLE: 'ما نقدر نلعب هالخانة.',
  BACKUP_EXHAUSTED: 'ما بقى سؤال احتياطي متوافق.',
  INSUFFICIENT_QUESTIONS: 'ما بقيت أسئلة جديدة كافية في إحدى الفئات بعد استبعاد سجل اللاعبين. اختاروا فئات ثانية.',
  LOGIN_REQUIRED: 'انتهت جلسة حسابك. سجّل دخولك مرة ثانية قبل بدء المباراة.',
  INVALID_TEAM_NAME: 'اسم الفريق غير صالح للسيرفر.',
  DUPLICATE_TEAM_NAMES: 'أسماء الفريقين لازم تكون مختلفة.',
  VALIDATION_ERROR: 'بيانات الطلب غير صالحة.',
  DRAFT_COMPLETE: 'السحب مكتمل بالفعل.',
  POWER_ALREADY_DRAFTED: 'هالقوة انسحبت من قبل لنفس الفريق.',
  POWER_NOT_OWNED: 'هالقوة مو من اختيار هالفريق.',
  POWER_ALREADY_USED: 'هالقوة استُخدمت من قبل بهالمباراة.',
  POWER_SIDE_NOT_ALLOWED: 'هالقوة مو متاحة لهالفريق في هالسؤال.',
  POWER_WINDOW_CLOSED: 'انتهت نافذة تفعيل القوة على السيرفر.',
  POWER_ALREADY_ACTIVE: 'القوة شغالة بالفعل.',
  POWERS_MISMATCH: 'تفعيلات القوى تغيّرت — جاري المزامنة مع السيرفر.',
  QUESTION_REVEALED: 'الإجابة ظهرت على السيرفر، ما تنفع القوى.',
  TILE_NOT_OPEN: 'الخانة مو مفتوحة على السيرفر.',
  TILE_ALREADY_OPEN: 'الخانة مفتوحة بالفعل على السيرفر.',
  ANOTHER_TILE_OPEN: 'في سؤال ثاني مفتوح على السيرفر.',
  QUESTION_ALREADY_REVEALED: 'الإجابة ظاهرة بالفعل على السيرفر.',
  HOST_TOKEN_REQUIRED: 'الجلسة فقدت توكن المضيف — ابدأ مباراة جديدة.',
  HOST_TOKEN_INVALID: 'توكن المضيف غير صالح — ابدأ مباراة جديدة.',
  HOST_TOKEN_UNSET: 'هالمباراة أُنشئت قبل حماية المضيف — ابدأ مباراة جديدة.',
  INSTALL_TOKEN_REQUIRED: 'تعذّر تحديد هوية الجهاز — أعد تحميل الصفحة وحاول مجددًا.',
  INSTALL_TOKEN_INVALID: 'هوية الجهاز غير معروفة — أعد تحميل الصفحة.',
  INSTALL_TOKEN_REVOKED: 'هوية الجهاز مسحوبة — أعد تحميل الصفحة.',
  INSUFFICIENT_QUESTIONS: 'بنك الأسئلة ما يكفي بعد استبعاد ما شافه اللاعبون.',
  PARTICIPANT_NOT_FOUND: 'مشارك غير مسجّل — حدّث قائمة اللاعبين.',
  PARTICIPANT_TEAM_CONFLICT: 'مشارك مختار في الفريقين معًا.',
  PROFILE_USERNAME_TAKEN: 'اسم المستخدم محجوز لملف آخر.',
};

export function apiErrorCode(error) {
  return error instanceof ApiError ? error.code : null;
}

export function apiErrorDetails(error) {
  return error instanceof ApiError ? error.details ?? {} : {};
}

/** رسالة عربية قصيرة تصلح للعرض فوق خطأ الشبكة أو خطأ الـ API. */
export function apiErrorMessage(error) {
  if (error instanceof ApiError) {
    // خادم التطوير يرجّع 500 عندما يكون FastAPI متوقفًا؛ نعطي رسالة مفهومة.
    if (error.status >= 500) {
      return 'السيرفر ما رد. تأكد من تشغيل FastAPI ثم جرّب مرة ثانية.';
    }
    return ERROR_LABELS[error.code] || error.message || `خطأ من السيرفر (${error.status}).`;
  }
  if (error?.name === 'TypeError') {
    return 'ما وصلنا للسيرفر. تأكد من تشغيل FastAPI ثم جرّب مرة ثانية.';
  }
  return error?.message || 'صار خطأ غير متوقع بالاتصال بالسيرفر.';
}

export function isVersionConflict(error) {
  return error instanceof ApiError && error.status === 409 && error.code === 'STALE_MATCH_VERSION';
}

export { TEAM_A_ID, TEAM_B_ID, toBackendTeamKey } from '@trivia-adapter';
