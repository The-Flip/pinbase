<script lang="ts">
	import type { components } from '$lib/api/schema';
	import PeopleEditor from './PeopleEditor.svelte';

	type Credit = components['schemas']['CreditSchema'];

	let {
		initialCredits = [],
		slug = 'medieval-madness'
	}: {
		initialCredits?: Credit[];
		slug?: string;
	} = $props();

	let savedCount = $state(0);
	let lastError = $state('');

	let editorRef: { save(): Promise<void> } | undefined = $state();

	function handleSaved() {
		savedCount++;
	}

	function handleError(msg: string) {
		lastError = msg;
	}
</script>

<PeopleEditor
	bind:this={editorRef}
	{initialCredits}
	{slug}
	onsaved={handleSaved}
	onerror={handleError}
/>

<button type="button" onclick={() => editorRef?.save()}>Save</button>

<p data-testid="saved-count">{savedCount}</p>
<p data-testid="last-error">{lastError}</p>
