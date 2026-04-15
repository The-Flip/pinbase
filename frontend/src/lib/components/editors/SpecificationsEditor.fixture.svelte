<script lang="ts">
	import SpecificationsEditor from './SpecificationsEditor.svelte';

	type SpecsModel = {
		technology_generation?: { slug: string } | null;
		technology_subgeneration?: { slug: string } | null;
		system?: { slug: string } | null;
		display_type?: { slug: string } | null;
		display_subtype?: { slug: string } | null;
		cabinet?: { slug: string } | null;
		game_format?: { slug: string } | null;
		player_count?: number | null;
		flipper_count?: number | null;
		production_quantity: string;
	};

	let {
		initialModel,
		slug = 'medieval-madness'
	}: {
		initialModel: SpecsModel;
		slug?: string;
	} = $props();

	let savedCount = $state(0);
	let lastError = $state('');

	let editorRef: { save(meta?: unknown): Promise<void> } | undefined = $state();

	function handleSaved() {
		savedCount++;
	}

	function handleError(msg: string) {
		lastError = msg;
	}
</script>

<SpecificationsEditor
	bind:this={editorRef}
	{initialModel}
	{slug}
	onsaved={handleSaved}
	onerror={handleError}
/>

<button type="button" onclick={() => editorRef?.save()}>Save</button>
<button
	type="button"
	onclick={() =>
		editorRef?.save({
			note: 'Corrected per flyer',
			citation: { citation_instance_id: 42 }
		})}
>
	Save with meta
</button>

<p data-testid="saved-count">{savedCount}</p>
<p data-testid="last-error">{lastError}</p>
