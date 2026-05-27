import { FormEvent, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  fetchChargerSearch,
  fetchNaturalLanguageChargerSearch,
  isNaturalLanguageSearchResult,
  type ChargerSearchCommand,
  type ChargerSearchClarificationResponse,
  type ChargerSearchResponse,
  type PlaceCandidate,
} from '../../lib/llmSearch';
import type { ChargerFeature } from '../../types/charger';

type SearchAssistantPanelProps = {
  onApplyResults: (features: ChargerFeature[]) => void;
  onClearResults: () => void;
};

const STATUS_OPTIONS = [
  { label: 'Any', value: '' },
  { label: 'Available', value: 'available' },
  { label: 'Occupied', value: 'occupied' },
  { label: 'Offline', value: 'offline' },
  { label: 'Unknown', value: 'unknown' },
] as const;

const CONNECTOR_OPTIONS = [
  { label: 'Any', value: '' },
  { label: 'DC', value: 'DC' },
  { label: 'AC', value: 'AC' },
  { label: 'DC Combo', value: 'DC Combo' },
  { label: 'AC Type 2', value: 'AC Type 2' },
  { label: 'CHAdeMO', value: 'CHAdeMO' },
] as const;

const SORT_OPTIONS = [
  { label: 'Distance', value: 'distance' },
  { label: 'Power', value: 'power' },
  { label: 'Availability', value: 'availability' },
] as const;

export function SearchAssistantPanel({ onApplyResults, onClearResults }: SearchAssistantPanelProps) {
  const [message, setMessage] = useState('Gangnam Station nearby 2km fast chargers');
  const [place, setPlace] = useState('Gangnam Station');
  const [radiusM, setRadiusM] = useState(2000);
  const [minKw, setMinKw] = useState(100);
  const [status, setStatus] = useState('');
  const [connectorType, setConnectorType] = useState('DC');
  const [sort, setSort] = useState<ChargerSearchCommand['sort']>('distance');
  const [latestSource, setLatestSource] = useState<'chat' | 'typed' | null>(null);

  const typedMutation = useMutation({
    mutationFn: (command: ChargerSearchCommand) => fetchChargerSearch(command),
    onSuccess: (data) => {
      setLatestSource('typed');
      onApplyResults(data.features);
    },
  });

  const chatMutation = useMutation({
    mutationFn: (nextMessage: string) => fetchNaturalLanguageChargerSearch(nextMessage),
    onSuccess: (data) => {
      setLatestSource('chat');
      if (isNaturalLanguageSearchResult(data)) {
        onApplyResults(data.features);
      }
    },
  });

  const latest =
    latestSource === 'chat' && isNaturalLanguageSearchResult(chatMutation.data)
      ? chatMutation.data
      : latestSource === 'typed'
        ? typedMutation.data
        : undefined;
  const clarification =
    latestSource === 'chat' && chatMutation.data?.type === 'clarification_required' ? chatMutation.data : undefined;
  const hasError = (latestSource === 'chat' && chatMutation.isError) || (latestSource === 'typed' && typedMutation.isError);
  const hasResults = Boolean(latest?.features.length);

  function buildCommand(): ChargerSearchCommand {
    return {
      intent: 'find_chargers',
      place,
      radius_m: radiusM,
      filters: {
        ...(minKw > 0 ? { min_kw: minKw } : {}),
        ...(status ? { status: status as ChargerSearchCommand['filters']['status'] } : {}),
        ...(connectorType ? { connector_type: connectorType } : {}),
      },
      sort,
    };
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    typedMutation.mutate(buildCommand());
  }

  function handleChatSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    chatMutation.mutate(message);
  }

  function handleCandidateSelect(candidate: PlaceCandidate) {
    if (!clarification?.command) {
      setMessage(candidate.name);
      return;
    }

    const nextCommand = { ...clarification.command, place: candidate.name };
    setPlace(candidate.name);
    typedMutation.mutate(nextCommand);
  }

  function handleClear() {
    typedMutation.reset();
    chatMutation.reset();
    setLatestSource(null);
    onClearResults();
  }

  return (
    <aside className="assistant-panel" aria-label="Map assistant">
      <div className="assistant-heading">
        <p className="eyebrow">Assistant</p>
        <button type="button" onClick={handleClear}>
          Clear
        </button>
      </div>

      <form className="assistant-chat-form" onSubmit={handleChatSubmit}>
        <label>
          <span>Ask</span>
          <input value={message} onChange={(event) => setMessage(event.target.value)} />
        </label>
        <button type="submit" disabled={chatMutation.isPending}>
          {chatMutation.isPending ? 'Searching...' : 'Send'}
        </button>
      </form>

      <details className="assistant-advanced">
        <summary>Structured search</summary>
        <form className="assistant-form" onSubmit={handleSubmit}>
          <label>
            <span>Place</span>
            <input value={place} onChange={(event) => setPlace(event.target.value)} />
          </label>

          <div className="assistant-grid">
            <label>
              <span>Radius m</span>
              <input
                min="1"
                max="50000"
                step="100"
                type="number"
                value={radiusM}
                onChange={(event) => setRadiusM(Number(event.target.value))}
              />
            </label>
            <label>
              <span>Min kW</span>
              <input
                min="0"
                max="1000"
                step="10"
                type="number"
                value={minKw}
                onChange={(event) => setMinKw(Number(event.target.value))}
              />
            </label>
          </div>

          <div className="assistant-grid">
            <label>
              <span>Status</span>
              <select value={status} onChange={(event) => setStatus(event.target.value)}>
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Connector</span>
              <select value={connectorType} onChange={(event) => setConnectorType(event.target.value)}>
                {CONNECTOR_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label>
            <span>Sort</span>
            <select value={sort} onChange={(event) => setSort(event.target.value as ChargerSearchCommand['sort'])}>
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <button type="submit" disabled={typedMutation.isPending}>
            {typedMutation.isPending ? 'Searching...' : 'Search'}
          </button>
        </form>
      </details>

      {hasError && <p className="assistant-message">Search failed. Check place or filters.</p>}
      {clarification && <ClarificationPanel clarification={clarification} onSelectCandidate={handleCandidateSelect} />}
      {latest && !hasResults && <p className="assistant-message">No local matches.</p>}
      {latest && hasResults && <SearchResultList result={latest} />}
    </aside>
  );
}

function ClarificationPanel({
  clarification,
  onSelectCandidate,
}: {
  clarification: ChargerSearchClarificationResponse;
  onSelectCandidate: (candidate: PlaceCandidate) => void;
}) {
  return (
    <div className="assistant-clarification">
      <p className="assistant-message">{clarification.message}</p>
      {clarification.candidates && clarification.candidates.length > 0 && (
        <div className="assistant-candidates">
          {clarification.candidates.slice(0, 6).map((candidate) => (
            <button
              key={candidate.place_id}
              type="button"
              className="assistant-candidate-button"
              onClick={() => onSelectCandidate(candidate)}
            >
              <strong>{candidate.name}</strong>
              <span>{candidate.place_type}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SearchResultList({ result }: { result: ChargerSearchResponse }) {
  return (
    <div className="assistant-results">
      <div className="assistant-result-meta">
        <span>{result.features.length.toLocaleString()} results</span>
        <span>{result.explanation.data_freshness}</span>
      </div>
      <ol>
        {result.features.slice(0, 6).map((feature) => (
          <li key={feature.properties.charger_id}>
            <strong>{feature.properties.charger_name}</strong>
            <span>
              {feature.properties.max_kw} kW / {feature.properties.status}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
