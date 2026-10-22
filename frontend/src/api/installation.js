/**
 * هوية التثبيت: اعتماد عشوائي صادر من الخادم، مخزّن محليًا.
 *
 * - أول تشغيل يسجّل التثبيت مرة واحدة (مفتاح تكرار ثابت مخزّن).
 * - كل إقلاع يتحقق من الاعتماد عبر /installations/me؛ الساقط يُعاد تسجيله.
 * - طلبات متزامنة تتشارك نفس الوعد (StrictMode-safe): لا تثبيت مكرر.
 * - حدّ موثق: مسح التخزين المحلي ينشئ هوية جهاز جديدة؛ سجل الظل القديم
 *   يبقى على الخادم ولا يُنتحل.
 */
import { ApiError, api, makeIdempotencyKey } from './server.js';

const STORAGE_KEY = 'seenjeem:installation:v1';

let inflight = null;

function readStored() {
  try {
    const raw = window?.localStorage?.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeStored(value) {
  try {
    window?.localStorage?.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // التخزين قد يكون محظورًا؛ الهوية تبقى لجلسة الذاكرة فقط.
  }
}

function validCredential(value) {
  return typeof value === 'string' && value.length >= 32 && value.length <= 128
    ? value
    : null;
}

async function registerFresh(regKey) {
  const key = regKey || makeIdempotencyKey('install');
  const stored = readStored() ?? {};
  writeStored({ ...stored, regKey: key });
  const result = await api.registerInstallation({ key });
  const record = {
    credential: result.credential,
    installationId: result.installation_id,
    shadowUserId: result.shadow_user_id,
    regKey: key,
  };
  writeStored(record);
  return record;
}

async function ensureInstallationInner() {
  const stored = readStored();
  const credential = validCredential(stored?.credential);
  if (credential) {
    try {
      const me = await api.installationMe({ installToken: credential });
      const record = {
        credential,
        installationId: me.installation_id,
        shadowUserId: me.shadow_user_id,
        regKey: stored?.regKey ?? null,
      };
      writeStored(record);
      return record;
    } catch (error) {
      if (!(error instanceof ApiError) || (error.status !== 403 && error.status !== 409)) {
        throw error;
      }
      // الاعتماد ساقط أو مسحوب: تسجيل جديد بهوية ظلّ جديدة.
    }
  }
  return registerFresh(stored?.regKey);
}

export function ensureInstallation() {
  if (!inflight) {
    inflight = ensureInstallationInner().finally(() => {
      inflight = null;
    });
  }
  return inflight;
}

export function getStoredInstallation() {
  const stored = readStored();
  const credential = validCredential(stored?.credential);
  return credential ? { ...stored, credential } : null;
}

export function installationTokenSync() {
  return validCredential(readStored()?.credential);
}
