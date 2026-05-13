<script lang="ts">
  import ClaimValue from './ClaimValue.svelte';

  let { value, display }: { value: unknown; display?: string | null } = $props();
</script>

<ClaimValue {value} {display} />
