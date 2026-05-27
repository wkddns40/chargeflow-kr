import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { RoutePlannerPanel } from './RoutePlannerPanel';

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });

  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <RoutePlannerPanel />
    </QueryClientProvider>,
  );
}

describe('RoutePlannerPanel', () => {
  it('renders the flag-on route planner controls', () => {
    const markup = renderPanel();

    expect(markup).toContain('Route planner');
    expect(markup).toContain('Origin');
    expect(markup).toContain('Destination');
    expect(markup).toContain('Seoul');
    expect(markup).toContain('Daejeon');
    expect(markup).toContain('Battery kWh');
    expect(markup).toContain('Start SoC %');
    expect(markup).toContain('Plan');
  });
});
