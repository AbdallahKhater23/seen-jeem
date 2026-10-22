/**
 * Node 26 قد يعرّف localStorage عالميًا بلا ملف تخزين، وjsdom لا يوفره دائمًا
 * لأصل about:blank. الاختبارات تحتاج تخزينًا حقيقيًا متزامنًا، فنركّب واحدًا.
 */
class MemoryStorage {
  constructor() {
    this.store = new Map();
  }

  get length() {
    return this.store.size;
  }

  key(index) {
    return Array.from(this.store.keys())[index] ?? null;
  }

  getItem(key) {
    const value = this.store.get(String(key));
    return value === undefined ? null : value;
  }

  setItem(key, value) {
    this.store.set(String(key), String(value));
  }

  removeItem(key) {
    this.store.delete(String(key));
  }

  clear() {
    this.store.clear();
  }
}

const storage = new MemoryStorage();

for (const target of [globalThis, typeof window !== 'undefined' ? window : null]) {
  if (!target) continue;
  try {
    Object.defineProperty(target, 'localStorage', {
      value: storage,
      configurable: true,
      writable: false,
    });
  } catch {
    try {
      target.localStorage = storage;
    } catch {
      // لا شيء إضافي.
    }
  }
}
