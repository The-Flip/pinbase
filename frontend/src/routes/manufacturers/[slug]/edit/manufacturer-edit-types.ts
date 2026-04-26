import type { ManufacturerDetailSchema } from '$lib/api/schema';

export type ManufacturerEditView = Pick<
  ManufacturerDetailSchema,
  'name' | 'slug' | 'website' | 'logo_url' | 'description'
>;
