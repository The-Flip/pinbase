import { error } from '@sveltejs/kit';
import { createServerClient } from '$lib/api/server';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, url, request, params, cookies }) => {
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) throw error(404, 'Kiosk not found');

  const client = createServerClient(fetch, url, request);
  const { data, response } = await client.GET('/api/kiosk/configs/{config_id}/', {
    params: { path: { config_id: id } },
  });

  if (!data) {
    if (response?.status === 404) throw error(404, 'Kiosk not found');
    throw error(response?.status || 500, 'Failed to load kiosk');
  }

  const rawId = cookies.get('kioskConfigId');
  const parsed = rawId ? Number(rawId) : NaN;
  const activeId = Number.isInteger(parsed) && parsed > 0 ? parsed : null;

  return { config: data, activeId };
};
