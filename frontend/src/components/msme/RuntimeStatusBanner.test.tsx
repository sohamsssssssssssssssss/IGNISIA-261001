import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { RuntimeStatusBanner } from './RuntimeStatusBanner';

describe('RuntimeStatusBanner', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a reduced-mode warning when the health endpoint reports degraded RAG', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        rag: {
          execution_mode: 'reduced',
          degradations: ['local_generation_unavailable', 'web_intel_unavailable'],
        },
      }),
    } as Response);

    render(<RuntimeStatusBanner apiBase="http://127.0.0.1:8000" />);

    await waitFor(() => {
      expect(screen.getByText(/Document RAG runtime in reduced mode/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/local generation and web intelligence/i)).toBeInTheDocument();
    expect(screen.getByText(/MSME scoring remains available/i)).toBeInTheDocument();
  });

  it('does not render when the health endpoint reports full mode', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        rag: {
          execution_mode: 'full',
          degradations: [],
        },
      }),
    } as Response);

    const { container } = render(<RuntimeStatusBanner apiBase="http://127.0.0.1:8000" />);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalled();
    });
    expect(container).toBeEmptyDOMElement();
  });
});
