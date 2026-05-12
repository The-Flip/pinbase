<script lang="ts">
  import UserLink from './UserLink.svelte';

  let {
    cs,
  }: {
    cs: {
      is_ingest?: boolean;
      source_name?: string | null;
      user_username?: string | null;
      user_display_name?: string | null;
    };
  } = $props();
</script>

{#if cs.is_ingest}
  {cs.source_name ?? 'system'}
{:else if cs.user_username}
  <UserLink username={cs.user_username} displayName={cs.user_display_name} />
{:else}
  system
{/if}
