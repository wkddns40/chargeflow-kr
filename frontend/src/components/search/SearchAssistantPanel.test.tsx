import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { SearchAssistantPanel } from './SearchAssistantPanel';

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });

  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <SearchAssistantPanel onApplyResults={vi.fn()} onClearResults={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe('SearchAssistantPanel', () => {
  it('renders the flag-on assistant controls', () => {
    const markup = renderPanel();

    expect(markup).toContain('Assistant');
    expect(markup).toContain('Ask');
    expect(markup).toContain('Gangnam Station nearby 2km fast chargers');
    expect(markup).toContain('Send');
    expect(markup).toContain('Structured search');
    expect(markup).toContain('Place');
    expect(markup).toContain('Radius m');
    expect(markup).toContain('Search');
    expect(markup).toContain('Gangnam Station');
  });
});
