<script lang="ts">
	import { untrack } from 'svelte';
	import MarkdownTextArea from '$lib/components/form/MarkdownTextArea.svelte';
	import { saveModelClaims, type SaveResult, type SaveMeta } from './save-model-claims';

	let {
		initialDescription = '',
		slug,
		onsaved,
		onerror
	}: {
		initialDescription?: string;
		slug: string;
		onsaved: () => void;
		onerror: (message: string) => void;
	} = $props();

	// untrack: intentional one-time capture; component re-mounts when modal reopens
	const original = untrack(() => initialDescription);
	let description = $state(original);

	export async function save(meta?: SaveMeta): Promise<void> {
		if (description === original) {
			onsaved();
			return;
		}

		const result: SaveResult = await saveModelClaims(slug, {
			fields: { description },
			...meta
		});

		if (result.ok) {
			onsaved();
		} else {
			onerror(result.error);
		}
	}
</script>

<div class="overview-editor">
	<MarkdownTextArea label="Description" bind:value={description} rows={8} />
</div>

<style>
	.overview-editor {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}
</style>
