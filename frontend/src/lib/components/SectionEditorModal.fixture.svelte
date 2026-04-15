<script lang="ts">
	import type { EditCitationSelection } from '$lib/edit-citation';
	import SectionEditorModal from './SectionEditorModal.svelte';

	let open = $state(false);
	let closeCount = $state(0);
	let saveCount = $state(0);
	let lastNote = $state('');
	let lastCitation = $state<EditCitationSelection | null>(null);

	function openModal() {
		open = true;
	}

	function closeModal() {
		closeCount++;
		open = false;
	}

	function saveModal(meta: { note: string; citation: EditCitationSelection | null }) {
		saveCount++;
		lastNote = meta.note;
		lastCitation = meta.citation;
		open = false;
	}
</script>

<button type="button" onclick={openModal}>Open editor</button>

<SectionEditorModal heading="Overview" {open} onclose={closeModal} onsave={saveModal}>
	<label>
		Description
		<input type="text" value="Prototype content" />
	</label>
</SectionEditorModal>

<p data-testid="close-count">{closeCount}</p>
<p data-testid="save-count">{saveCount}</p>
<p data-testid="last-note">{lastNote}</p>
<p data-testid="last-citation">{lastCitation ? String(lastCitation.citationInstanceId) : ''}</p>
