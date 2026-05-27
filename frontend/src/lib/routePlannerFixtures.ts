import type { RoutePlannerRoute } from './routePlanner';

export type RoutePlannerFixture = RoutePlannerRoute & {
  label: string;
  origin: string;
  destination: string;
  originAliases: string[];
  destinationAliases: string[];
};

export const ROUTE_FIXTURES: RoutePlannerFixture[] = [
  {
    id: 'fixture-seoul-daejeon',
    label: 'Seoul-Daejeon',
    origin: 'Seoul',
    destination: 'Daejeon',
    originAliases: ['Seoul', 'Seoul Station', '서울', '서울시', '서울특별시', '서울역'],
    destinationAliases: ['Daejeon', 'Daejeon Station', '대전', '대전시', '대전광역시', '대전역'],
    distance_km: 165.2,
    polyline: [
      [126.978, 37.5665],
      [127.0276, 37.4979],
      [127.3845, 36.3504],
    ],
  },
];

export function resolveRouteFixture(origin: string, destination: string): RoutePlannerFixture | null {
  const normalizedOrigin = normalizeRoutePlace(origin);
  const normalizedDestination = normalizeRoutePlace(destination);

  if (!normalizedOrigin || !normalizedDestination) {
    return null;
  }

  return (
    ROUTE_FIXTURES.find(
      (fixture) =>
        routePlaceMatches(normalizedOrigin, [fixture.origin, ...fixture.originAliases]) &&
        routePlaceMatches(normalizedDestination, [fixture.destination, ...fixture.destinationAliases]),
    ) ?? null
  );
}

export function normalizeRoutePlace(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, ' ');
}

function routePlaceMatches(normalizedValue: string, aliases: string[]): boolean {
  return aliases.some((alias) => normalizeRoutePlace(alias) === normalizedValue);
}
