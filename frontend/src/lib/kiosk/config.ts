/**
 * Kiosk configuration and cookie helpers. Browser-only; do not import from
 * server load functions.
 *
 * - `mode=kiosk` cookie answers "is this device a kiosk?" (server-readable).
 * - `kioskConfig` localStorage entry answers "what should it show?" (client-only).
 */

const STORAGE_KEY = 'kioskConfig';
const COOKIE_NAME = 'mode';
const COOKIE_VALUE = 'kiosk';
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365; // 1 year

export const DEFAULT_TITLE = 'Machines Around You';
export const DEFAULT_IDLE_SECONDS = 180;
export const HOOK_MAX_LENGTH = 80;

export type KioskItem = {
  titleSlug: string;
  hook: string;
};

export type KioskConfig = {
  title: string;
  idleSeconds: number;
  items: KioskItem[];
};

export function loadConfig(): KioskConfig | null {
  if (typeof localStorage === 'undefined') return null;
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<KioskConfig>;
    return {
      title: typeof parsed.title === 'string' ? parsed.title : DEFAULT_TITLE,
      idleSeconds:
        typeof parsed.idleSeconds === 'number' && parsed.idleSeconds > 0
          ? parsed.idleSeconds
          : DEFAULT_IDLE_SECONDS,
      items: Array.isArray(parsed.items)
        ? parsed.items.filter(
            (i): i is KioskItem =>
              !!i && typeof i.titleSlug === 'string' && typeof i.hook === 'string',
          )
        : [],
    };
  } catch {
    return null;
  }
}

export function saveConfig(config: KioskConfig): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export function clearConfig(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function setKioskCookie(): void {
  document.cookie = `${COOKIE_NAME}=${COOKIE_VALUE}; Path=/; Max-Age=${COOKIE_MAX_AGE_SECONDS}; SameSite=Lax`;
}

export function clearKioskCookie(): void {
  document.cookie = `${COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax`;
}

export function isKioskCookieSet(): boolean {
  if (typeof document === 'undefined') return false;
  return new RegExp(`(?:^|;\\s*)${COOKIE_NAME}=${COOKIE_VALUE}(?:;|$)`).test(document.cookie);
}
