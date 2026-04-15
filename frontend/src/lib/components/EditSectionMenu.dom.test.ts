import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import EditSectionMenuFixture from './EditSectionMenu.fixture.svelte';

describe('EditSectionMenu', () => {
	it('renders edit sections in a menu', async () => {
		const user = userEvent.setup();

		render(EditSectionMenuFixture);

		const trigger = screen.getByRole('button', { name: 'Edit' });
		await user.click(trigger);

		expect(screen.getByRole('menu')).toBeInTheDocument();
		expect(screen.getByRole('menuitem', { name: 'Overview' })).toHaveAttribute(
			'href',
			'/models/medieval-madness/edit/overview'
		);
		expect(screen.getByRole('menuitem', { name: 'Specifications' })).toHaveAttribute(
			'href',
			'/models/medieval-madness/edit/specifications'
		);
		expect(screen.getByRole('menuitem', { name: 'Relationships' })).toHaveAttribute(
			'href',
			'/models/medieval-madness/edit/relationships'
		);
	});
});
