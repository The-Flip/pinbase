import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import MediaLightbox from './MediaLightbox.svelte';
import { MEDIA_ITEMS } from './media-test-fixtures';

function renderLightbox(initialIndex = 0) {
	const onclose = vi.fn();
	const result = render(MediaLightbox, {
		media: MEDIA_ITEMS.slice(0, 2),
		initialIndex,
		onclose
	});
	return { ...result, onclose };
}

describe('MediaLightbox', () => {
	it('locks body scroll while mounted and restores it on unmount', () => {
		const { unmount } = renderLightbox();

		expect(document.body.style.overflow).toBe('hidden');

		unmount();
		expect(document.body.style.overflow).toBe('');
	});

	it('closes on Escape and on backdrop click', async () => {
		const user = userEvent.setup();
		const { onclose, container } = renderLightbox();

		await user.keyboard('{Escape}');
		expect(onclose).toHaveBeenCalledTimes(1);

		const backdrop = container.querySelector('.lightbox-backdrop') as HTMLElement;
		await user.click(backdrop);
		expect(onclose).toHaveBeenCalledTimes(2);
	});

	it('navigates with arrow keys and updates edge button visibility', async () => {
		renderLightbox();

		expect(screen.getByText('1 / 2')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /previous/i })).not.toBeInTheDocument();
		expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();

		await fireEvent.keyDown(window, { key: 'ArrowRight' });
		expect(screen.getByText('2 / 2')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument();

		await fireEvent.keyDown(window, { key: 'ArrowLeft' });
		expect(screen.getByText('1 / 2')).toBeInTheDocument();
	});
});
