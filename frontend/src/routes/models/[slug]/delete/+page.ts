import { resolve } from '$app/paths';
import { loadDeletePreview } from '$lib/delete-preview-loader';
import type { ModelDeletePreviewSchema } from '$lib/api/schema';
import type { PageLoad } from './$types';

export type DeletePreview = ModelDeletePreviewSchema;

export const load: PageLoad = ({ fetch, params }) =>
  loadDeletePreview<DeletePreview>({
    fetch,
    slug: params.slug,
    apiPath: 'models',
    notFoundRedirect: resolve('/'),
  });
