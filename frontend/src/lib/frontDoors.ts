/**
 * Front-door registry. A "front door" replaces `/` for devices flagged with a
 * `mode=...` cookie — currently only the museum kiosk. Each front door owns
 * its own routes; the registry just maps the cookie value to the home path
 * so the root `+page.server.ts` can redirect.
 */
export type FrontDoor = {
  homePath: string;
};

const FRONT_DOORS: Record<string, FrontDoor> = {
  kiosk: { homePath: '/kiosk' },
};

export function resolveFrontDoor(mode: string | null | undefined): FrontDoor | null {
  if (!mode) return null;
  return FRONT_DOORS[mode] ?? null;
}
