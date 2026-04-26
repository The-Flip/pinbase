import type { RichTextSchema } from '$lib/api/schema';

/**
 * Structural superset of GameplayFeatureDetailSchema and ThemeDetailSchema —
 * the fields the hierarchical-taxonomy section editors consume.
 */
export type HierarchicalTaxonomyEditView = {
  name: string;
  slug: string;
  description: RichTextSchema;
  parents: { name: string; slug: string }[];
  aliases: string[];
};
