import { redirect } from '@sveltejs/kit';
import { resolveFrontDoor } from '$lib/frontDoors';
import type { PageServerLoad } from './$types';

/**
 * If the device is flagged as a registered front door (e.g. a museum kiosk),
 * redirect from `/` to that front door's home. Regular visitors hit the
 * normal homepage rendered by +page.svelte.
 */
export const load: PageServerLoad = ({ cookies }) => {
  const frontDoor = resolveFrontDoor(cookies.get('mode'));
  if (frontDoor) {
    throw redirect(307, frontDoor.homePath);
  }
  return {};
};
