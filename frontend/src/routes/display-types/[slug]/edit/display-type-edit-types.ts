import type { components } from '$lib/api/schema';

export type DisplayTypeEditView = Pick<
	components['schemas']['TaxonomySchema'],
	'name' | 'slug' | 'description' | 'display_order'
>;
