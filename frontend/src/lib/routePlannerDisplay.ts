import { isRoutePlannerApiError, type RoutePlannerGraphError, type RoutePlannerResponseMeta } from './routePlanner';

const REASON_LABELS: Record<string, string> = {
  connector_match: 'Connector match',
  high_power: 'High power',
  reachable: 'Reachable',
  fresh_availability: 'Fresh availability',
  aging_availability: 'Aging availability',
  stale_availability_penalty: 'Stale availability',
  unknown_availability_penalty: 'Unknown availability',
  offline_fallback: 'Offline fallback',
  unreachable_fallback: 'Unreachable fallback',
  connector_mismatch_fallback: 'Connector fallback',
};

const FALLBACK_REASONS = new Set(['offline_fallback', 'unreachable_fallback', 'connector_mismatch_fallback']);

export function formatRoutePlannerReason(reason: string): string {
  return REASON_LABELS[reason] ?? reason.replace(/_/g, ' ');
}

export function hasFallbackReason(reasons: string[]): boolean {
  return reasons.some((reason) => FALLBACK_REASONS.has(reason));
}

export function formatRoutePlannerScore(score: number): string {
  return score.toFixed(2);
}

export function formatRoutePlannerSoc(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function getRoutePlannerLimitations(meta: RoutePlannerResponseMeta): string[] {
  return meta.limitations;
}

export function getRoutePlannerMetaRows(meta: RoutePlannerResponseMeta): Array<[string, string]> {
  return [
    ['Source', meta.source],
    ...(meta.freshness_label ? [['Freshness', meta.freshness_label] as [string, string]] : []),
    ...(meta.snapshot_date ? [['Snapshot', meta.snapshot_date] as [string, string]] : []),
  ];
}

export function getRoutePlannerErrorMessages(error: unknown): string[] {
  if (isRoutePlannerApiError(error)) {
    return formatRoutePlannerErrorDetail(error.detail);
  }
  if (error instanceof Error) {
    return [error.message];
  }
  return ['Route planner failed.'];
}

function formatRoutePlannerErrorDetail(detail: unknown): string[] {
  if (Array.isArray(detail)) {
    const messages = detail.map(formatRoutePlannerErrorEntry).filter((message) => message.length > 0);
    return messages.length > 0 ? messages : ['Route planner failed.'];
  }
  if (typeof detail === 'string' && detail.length > 0) {
    return [detail];
  }
  return ['Route planner failed.'];
}

function formatRoutePlannerErrorEntry(entry: unknown): string {
  if (!isRoutePlannerGraphError(entry)) {
    return typeof entry === 'string' ? entry : '';
  }

  const prefix = [entry.node, entry.code].filter(Boolean).join(' / ');
  if (entry.message && prefix) {
    return `${prefix}: ${entry.message}`;
  }
  return entry.message ?? prefix;
}

function isRoutePlannerGraphError(entry: unknown): entry is RoutePlannerGraphError {
  if (!entry || typeof entry !== 'object') {
    return false;
  }
  const value = entry as RoutePlannerGraphError;
  return Boolean(value.node || value.message || value.code);
}
