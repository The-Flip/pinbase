<script lang="ts">
	import ActionMenu from '$lib/components/ActionMenu.svelte';
	import MenuItem from '$lib/components/MenuItem.svelte';

	type EditSectionItem = {
		label: string;
		href?: string;
		onclick?: () => void;
	};

	let {
		label = 'Edit',
		items
	}: {
		label?: string;
		items: EditSectionItem[];
	} = $props();
</script>

<ActionMenu {label}>
	{#each items as item (item.label)}
		<MenuItem href={item.href} onclick={item.onclick}>{item.label}</MenuItem>
	{/each}
</ActionMenu>
