import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MapShell } from './components/map/MapShell';
import { useStations } from './hooks/useStations';

const queryClient = new QueryClient();

function StationMap() {
  const { stations, isLoading, isError, error } = useStations();

  if (isLoading) return <div className="status-screen">Loading station data...</div>;
  if (isError) return <div className="status-screen">Station data failed: {String(error)}</div>;

  return <MapShell stations={stations} />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <StationMap />
    </QueryClientProvider>
  );
}
