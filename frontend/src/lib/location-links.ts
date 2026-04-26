import type { CorporateEntityLocationSchema } from '$lib/api/schema';

export type LocationPart = {
  text: string;
  href: string;
};

export function buildLocationParts(loc: CorporateEntityLocationSchema): LocationPart[] {
  const parts: LocationPart[] = [
    { text: loc.display_name, href: `/locations/${loc.location_path}` },
  ];
  for (const ancestor of loc.ancestors) {
    parts.push({ text: ancestor.display_name, href: `/locations/${ancestor.location_path}` });
  }
  return parts;
}
