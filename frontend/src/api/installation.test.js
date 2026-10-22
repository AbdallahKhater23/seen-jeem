import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  registerInstallation: vi.fn(),
  installationMe: vi.fn(),
}));

vi.mock('./server.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    api: { ...actual.api, ...mocks },
  };
});

const installation = await import('./installation.js');

const STORAGE_KEY = 'seenjeem:installation:v1';

beforeEach(() => {
  window.localStorage.clear();
  mocks.registerInstallation.mockReset();
  mocks.installationMe.mockReset();
});

describe('installation identity', () => {
  it('registers once and shares the in-flight promise across concurrent mounts', async () => {
    mocks.registerInstallation.mockResolvedValue({
      credential: 'a'.repeat(40),
      installation_id: 7,
      shadow_user_id: 9,
    });

    const [first, second] = await Promise.all([
      installation.ensureInstallation(),
      installation.ensureInstallation(),
    ]);

    expect(mocks.registerInstallation).toHaveBeenCalledTimes(1);
    expect(first.credential).toBe('a'.repeat(40));
    expect(second).toEqual(first);

    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY));
    expect(stored.credential).toBe('a'.repeat(40));
    expect(stored.installationId).toBe(7);
    expect(stored.shadowUserId).toBe(9);
    expect(typeof stored.regKey).toBe('string');
    expect(installation.installationTokenSync()).toBe('a'.repeat(40));
  });

  it('reuses a valid stored credential via installationMe without re-registering', async () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        credential: 'b'.repeat(40),
        installationId: 3,
        shadowUserId: 4,
        regKey: 'reg-1',
      }),
    );
    mocks.installationMe.mockResolvedValue({
      installation_id: 3,
      shadow_user_id: 4,
    });

    const record = await installation.ensureInstallation();

    expect(mocks.installationMe).toHaveBeenCalledWith({ installToken: 'b'.repeat(40) });
    expect(mocks.registerInstallation).not.toHaveBeenCalled();
    expect(record.installationId).toBe(3);
  });

  it('re-registers with the stored regKey when the credential is rejected', async () => {
    const { ApiError } = await import('./server.js');
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ credential: 'c'.repeat(40), regKey: 'reg-kept' }),
    );
    mocks.installationMe.mockRejectedValue(new ApiError(403, 'INSTALL_TOKEN_INVALID', 'مرفوض'));
    mocks.registerInstallation.mockResolvedValue({
      credential: 'd'.repeat(40),
      installation_id: 11,
      shadow_user_id: 12,
    });

    const record = await installation.ensureInstallation();

    expect(mocks.registerInstallation).toHaveBeenCalledWith({ key: 'reg-kept' });
    expect(record.credential).toBe('d'.repeat(40));
    expect(installation.getStoredInstallation().installationId).toBe(11);
  });
});
