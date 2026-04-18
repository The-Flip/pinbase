import type { EditSectionDef } from './edit-section-def';

export type DisplayTypeEditSectionKey = 'name' | 'description' | 'display-order';

export type DisplayTypeEditSectionDef = EditSectionDef<DisplayTypeEditSectionKey>;

export const DISPLAY_TYPE_EDIT_SECTIONS: DisplayTypeEditSectionDef[] = [
	{
		key: 'name',
		segment: 'name',
		label: 'Name',
		showCitation: true,
		showMixedEditWarning: false
	},
	{
		key: 'description',
		segment: 'description',
		label: 'Description',
		showCitation: false,
		showMixedEditWarning: false
	},
	{
		key: 'display-order',
		segment: 'display-order',
		label: 'Display order',
		showCitation: false,
		showMixedEditWarning: false
	}
];

export function findDisplayTypeSectionBySegment(
	segment: string
): DisplayTypeEditSectionDef | undefined {
	return DISPLAY_TYPE_EDIT_SECTIONS.find((section) => section.segment === segment);
}

export function findDisplayTypeSectionByKey(
	key: DisplayTypeEditSectionKey
): DisplayTypeEditSectionDef | undefined {
	return DISPLAY_TYPE_EDIT_SECTIONS.find((section) => section.key === key);
}

export function defaultDisplayTypeSectionSegment(): string {
	return 'name';
}
