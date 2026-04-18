<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { untrack } from 'svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import type { SectionEditorProps } from '$lib/components/editors/editor-contract';
	import { reconcileSlug, slugifyForCatalog } from '$lib/create-form';
	import { diffScalarFields } from '$lib/edit-helpers';
	import type { DisplayTypeEditView } from './display-type-edit-types';
	import {
		type DisplayTypeSaveResult,
		saveDisplayTypeClaims,
		type FieldErrors,
		type SaveMeta
	} from './save-display-type-claims';

	type NameFields = {
		name: string;
		slug: string;
	};

	let {
		initialData,
		slug,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: SectionEditorProps<DisplayTypeEditView> = $props();

	function extractFields(displayType: DisplayTypeEditView): NameFields {
		return {
			name: displayType.name,
			slug: displayType.slug
		};
	}

	const original = untrack(() => extractFields(initialData));
	let fields = $state<NameFields>({ ...original });
	let syncedSlug = $state(slugifyForCatalog(original.name));
	let fieldErrors = $state<FieldErrors>({});
	let changedFields = $derived(diffScalarFields(fields, original));
	let dirty = $derived(Object.keys(changedFields).length > 0);

	$effect(() => {
		const next = reconcileSlug({ name: fields.name, slug: fields.slug, syncedSlug });
		if (next.slug !== fields.slug) {
			fields.slug = next.slug;
			syncedSlug = next.syncedSlug;
		}
	});

	$effect(() => {
		ondirtychange(dirty);
	});

	export function isDirty(): boolean {
		return dirty;
	}

	export async function save(meta?: SaveMeta): Promise<void> {
		fieldErrors = {};
		if (!dirty) {
			onsaved();
			return;
		}

		const result: DisplayTypeSaveResult = await saveDisplayTypeClaims(slug, {
			fields: changedFields,
			...meta
		});

		if (result.ok) {
			if (result.updatedSlug && result.updatedSlug !== slug) {
				const nextPathname = page.url.pathname.replace(`/${slug}`, `/${result.updatedSlug}`);
				await goto(`${nextPathname}${page.url.search}`, { replaceState: true });
			}
			onsaved();
		} else {
			fieldErrors = result.fieldErrors;
			onerror(
				Object.keys(result.fieldErrors).length > 0 ? 'Please fix the errors below.' : result.error
			);
		}
	}
</script>

<div class="editor-fields">
	<TextField label="Name" bind:value={fields.name} error={fieldErrors.name ?? ''} />
	<TextField label="Slug" bind:value={fields.slug} error={fieldErrors.slug ?? ''} />
</div>

<style>
	.editor-fields {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}
</style>
