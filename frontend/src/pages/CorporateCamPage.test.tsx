import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import CorporateCamPage from './CorporateCamPage';

describe('CorporateCamPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the persisted CAM workflow shell', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        rag: {
          execution_mode: 'full',
          degradations: [],
        },
      }),
    } as Response);

    render(<CorporateCamPage />);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalled();
    });
    expect(screen.getByText(/Corporate CAM Workflow/i)).toBeInTheDocument();
    expect(screen.getByText(/Persisted document upload, analyst confirmation, RAG execution, and CAM generation/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Upload/i })).toBeInTheDocument();
  });
});
