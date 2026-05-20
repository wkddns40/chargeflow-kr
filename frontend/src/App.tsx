import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MapShell } from './components/map/MapShell';
import { useStations } from './hooks/useStations';
import { isViewportStationsFlagEnabled } from './hooks/useViewportStations';
import { isLlmSearchFlagEnabled } from './lib/llmSearch';

const queryClient = new QueryClient();
const viewportStationsEnabled = isViewportStationsFlagEnabled(import.meta.env.VITE_ENABLE_VIEWPORT_STATIONS);
const llmSearchEnabled = isLlmSearchFlagEnabled(import.meta.env.VITE_ENABLE_LLM_SEARCH);

function StationMap() {
  const { stations, isLoading, isError, error } = useStations({ enabled: !viewportStationsEnabled });

  if (!viewportStationsEnabled && isLoading) return <div className="status-screen">Loading station data...</div>;
  if (!viewportStationsEnabled && isError) return <div className="status-screen">Station data failed: {String(error)}</div>;

  return <MapShell stations={stations} assistantSearchEnabled={llmSearchEnabled} />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <StationMap />
    </QueryClientProvider>
  );
}
