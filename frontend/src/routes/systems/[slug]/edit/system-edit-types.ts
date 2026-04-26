import type { SystemDetailSchema } from '$lib/api/schema';

export type SystemEditView = Pick<
  SystemDetailSchema,
  'name' | 'slug' | 'description' | 'manufacturer' | 'technology_subgeneration'
>;
