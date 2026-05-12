<script lang="ts">
  import ChangeSetAuthor from './ChangeSetAuthor.svelte';
  import SmartDate from './SmartDate.svelte';

  let {
    cs,
  }: {
    cs: {
      is_ingest?: boolean;
      source_name?: string | null;
      user_username?: string | null;
      user_display_name?: string | null;
      created_at: string;
    };
  } = $props();
</script>

<ChangeSetAuthor {cs} />
<span aria-hidden="true">·</span>
<SmartDate iso={cs.created_at} />
