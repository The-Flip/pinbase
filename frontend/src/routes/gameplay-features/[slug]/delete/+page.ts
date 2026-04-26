import { resolve } from '$app/paths';
import { loadDeletePreview } from '$lib/delete-preview-loader';
import type { TaxonomyDeletePreviewSchema } from '$lib/api/schema';
import type { PageLoad } from './$types';

export type DeletePreview = TaxonomyDeletePreviewSchema;

export const load: PageLoad = ({ fetch, params }) =>
  loadDeletePreview<DeletePreview>({
    fetch,
    slug: params.slug,
    apiPath: 'gameplay-features',
    notFoundRedirect: resolve('/gameplay-features'),
  });
