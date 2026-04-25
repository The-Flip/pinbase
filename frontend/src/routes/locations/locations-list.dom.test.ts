import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockGet, authMock } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  authMock: { isAuthenticated: true, load: () => Promise.resolve() },
}));

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$app/paths', () => ({ resolve: (p: string) => p }));
vi.mock('$lib/api/client', () => ({
  default: { GET: mockGet },
}));
vi.mock('$lib/auth.svelte', () => ({ auth: authMock }));

import Page from './+page.svelte';

const COUNTRIES = {
  countries: [
    {
      name: 'United States',
      location_path: 'united-states',
      manufacturer_count: 100,
      children: [],
    },
  ],
};

async function renderAndWait() {
  mockGet.mockResolvedValue({ data: COUNTRIES });
  render(Page);
  return await screen.findByRole('heading', { name: /United States/ });
}

describe('locations list route', () => {
  beforeEach(() => {
    mockGet.mockReset();
    authMock.isAuthenticated = true;
  });

  it('shows "+ New Country" in the action menu when authenticated', async () => {
    const user = userEvent.setup();
    await renderAndWait();
    await user.click(screen.getByRole('button', { name: 'Edit' }));
    const menuitem = screen.getByRole('menuitem', { name: /\+ New Country/ });
    expect(menuitem).toBeInTheDocument();
    expect(menuitem).toHaveAttribute('href', '/locations/new');
  });

  it('hides the action-menu trigger entirely when unauthenticated', async () => {
    authMock.isAuthenticated = false;
    await renderAndWait();
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
  });
});
