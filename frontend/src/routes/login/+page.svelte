<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';
	import { SITE_NAME } from '$lib/constants';
	import { resolveHref } from '$lib/utils';

	let username = $state('');
	let password = $state('');
	let error = $state<string | null>(null);
	let submitting = $state(false);

	async function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		error = null;
		submitting = true;
		const err = await auth.login(username, password);
		submitting = false;
		if (err) {
			error = err;
			return;
		}
		const next = new URLSearchParams(window.location.search).get('next');
		await goto(next || resolveHref('/'));
	}
</script>

<svelte:head>
	<title>Sign in — {SITE_NAME}</title>
</svelte:head>

<div class="login-page">
	<form class="login-form" onsubmit={handleSubmit}>
		<h1>Sign in</h1>

		{#if error}
			<p class="error">{error}</p>
		{/if}

		<label>
			<span>Username</span>
			<input
				type="text"
				bind:value={username}
				autocomplete="username"
				required
				disabled={submitting}
			/>
		</label>

		<label>
			<span>Password</span>
			<input
				type="password"
				bind:value={password}
				autocomplete="current-password"
				required
				disabled={submitting}
			/>
		</label>

		<button type="submit" disabled={submitting}>
			{submitting ? 'Signing in...' : 'Sign in'}
		</button>
	</form>
</div>

<style>
	.login-page {
		display: flex;
		justify-content: center;
		padding: var(--size-8) 0;
	}

	.login-form {
		width: 100%;
		max-width: 24rem;
		display: flex;
		flex-direction: column;
		gap: var(--size-4);
	}

	h1 {
		font-size: var(--font-size-5);
		font-weight: 700;
		margin: 0 0 var(--size-2);
	}

	label {
		display: flex;
		flex-direction: column;
		gap: var(--size-1);
		font-size: var(--font-size-2);
		font-weight: 500;
		color: var(--color-text-muted);
	}

	input {
		padding: var(--size-2) var(--size-3);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-2);
		font-size: var(--font-size-2);
		background: var(--color-surface);
		color: var(--color-text-primary);
	}

	input:focus {
		outline: 2px solid var(--color-accent);
		outline-offset: -1px;
		border-color: var(--color-accent);
	}

	button {
		padding: var(--size-2) var(--size-4);
		background: var(--color-accent);
		color: white;
		border: none;
		border-radius: var(--radius-2);
		font-size: var(--font-size-2);
		font-weight: 600;
		cursor: pointer;
		transition: background 0.15s var(--ease-2);
	}

	button:hover:not(:disabled) {
		background: var(--color-accent-hover);
	}

	button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.error {
		color: var(--color-error);
		font-size: var(--font-size-2);
		margin: 0;
		padding: var(--size-2) var(--size-3);
		background: color-mix(in srgb, var(--color-error) 10%, transparent);
		border-radius: var(--radius-2);
	}
</style>
