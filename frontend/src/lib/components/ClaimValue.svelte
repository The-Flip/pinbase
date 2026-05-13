<script lang="ts">
  import { formatValue, simplifyClaimValue } from './change-display';

  let { value, display = undefined }: { value: unknown; display?: string | null | undefined } =
    $props();

  let simple = $derived(simplifyClaimValue(value));

  // A relationship-claim dict with exists:false is a negative assertion
  // ("X is *not* the value"). The backend produces the same display
  // string for positive and negative assertions, so the strike-through
  // — driven by the raw value's exists flag, not by the display string
  // — is what disambiguates the two.
  let negated = $derived(
    typeof value === 'object' &&
      value !== null &&
      !Array.isArray(value) &&
      (value as { exists?: unknown }).exists === false,
  );
</script>

{#if display}
  {#if negated}
    <s>{display}</s>
  {:else}
    {display}
  {/if}
{:else if simple}
  {#if simple.exists}
    {simple.display}
  {:else}
    <s>{simple.display}</s>
  {/if}
{:else}
  {formatValue(value)}
{/if}
