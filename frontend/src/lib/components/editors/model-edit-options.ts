/**
 * Shared helper for fetching model edit options.
 *
 * Used by section editors that need dropdown options (people, roles,
 * taxonomy terms, etc.). Eliminates duplicated fetch + type boilerplate.
 */

import client from '$lib/api/client';
import type { components } from '$lib/api/schema';

export type ModelEditOptions = components['schemas']['ModelEditOptionsSchema'];

export const EMPTY_EDIT_OPTIONS: ModelEditOptions = {
	themes: [],
	tags: [],
	reward_types: [],
	gameplay_features: [],
	technology_generations: [],
	technology_subgenerations: [],
	display_types: [],
	display_subtypes: [],
	cabinets: [],
	game_formats: [],
	systems: [],
	corporate_entities: [],
	people: [],
	credit_roles: [],
	models: []
};

/** Fetch model edit options. Returns the empty shape until the request resolves. */
export async function fetchModelEditOptions(): Promise<ModelEditOptions> {
	const { data } = await client.GET('/api/models/edit-options/');
	return data ?? EMPTY_EDIT_OPTIONS;
}
