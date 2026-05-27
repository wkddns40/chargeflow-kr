import { describe, expect, it } from 'vitest';
import {
  resolveRouteFixture,
  resolveRoutePlace,
  ROUTE_FIXTURES,
  ROUTE_PLACE_CATALOG,
} from './routePlannerFixtures';

describe('route planner place catalog', () => {
  it('registers the synthetic station areas as route places', () => {
    expect(ROUTE_PLACE_CATALOG).toHaveLength(26);
    expect(resolveRoutePlace('강남')?.id).toBe('seoul-gangnam');
    expect(resolveRoutePlace('송도')?.id).toBe('incheon-songdo');
    expect(resolveRoutePlace('대전역')?.id).toBe('daejeon-central');
    expect(resolveRoutePlace('해운대')?.id).toBe('busan-haeundae');
    expect(resolveRoutePlace('제주시')?.id).toBe('jeju-city');
    expect(resolveRoutePlace('서귀포')?.id).toBe('seogwipo');
  });

  it('normalizes Seoul district prefixes before arbitrary suffixes', () => {
    expect(resolveRoutePlace('강남구청역')?.id).toBe('seoul-gangnam');
    expect(resolveRoutePlace('서울 강남대로')?.id).toBe('seoul-gangnam');
    expect(resolveRoutePlace('종로3가역')?.id).toBe('seoul-jongno');
    expect(resolveRoutePlace('마포구청')?.id).toBe('seoul-mapo');
    expect(resolveRoutePlace('성동왕십리')?.id).toBe('seoul-seongdong');
    expect(resolveRoutePlace('용산전자상가')?.id).toBe('seoul-yongsan');
    expect(resolveRoutePlace('송파잠실역')?.id).toBe('seoul-songpa');
    expect(resolveRoutePlace('서초교대역')?.id).toBe('seoul-seocho');
  });
});

describe('resolveRouteFixture', () => {
  it('matches the supported Seoul to Daejeon fixture in both directions', () => {
    expect(resolveRouteFixture('Seoul', 'Daejeon')?.id).toBe('fixture-seoul-daejeon');
    expect(resolveRouteFixture('서울역', '대전역')?.id).toBe('fixture-seoul-daejeon');
    expect(resolveRouteFixture('대전역', '서울역')?.id).toBe('fixture-daejeon-seoul');
  });

  it('matches supported Korean aliases for local and metro fixtures', () => {
    expect(resolveRouteFixture('서울역', '송도')?.id).toBe('fixture-seoul-incheon-songdo');
    expect(resolveRouteFixture('부산역', '해운대')?.id).toBe('fixture-busan-busan-haeundae');
    expect(resolveRouteFixture('제주시', '서귀포')?.id).toBe('fixture-jeju-city-seogwipo');
    expect(resolveRouteFixture('대구', '울산')?.id).toBe('fixture-daegu-ulsan');
  });

  it('uses Seoul route fixtures for supported Seoul district inputs', () => {
    expect(resolveRouteFixture('강남구청역', '대전역')?.id).toBe('fixture-seoul-daejeon');
    expect(resolveRouteFixture('대전역', '용산전자상가')?.id).toBe('fixture-daejeon-seoul');
    expect(resolveRouteFixture('마포구청', '송도')?.id).toBe('fixture-seoul-incheon-songdo');
  });

  it('keeps route fixtures explicit instead of generating every place pair', () => {
    expect(resolveRouteFixture('강남', '서귀포')).toBeNull();
    expect(resolveRouteFixture('부천', '해운대')).toBeNull();
  });

  it('keeps every deterministic route fixture bidirectional', () => {
    const ids = new Set(ROUTE_FIXTURES.map((fixture) => fixture.id));

    expect(ROUTE_FIXTURES).toHaveLength(50);
    expect(ids.size).toBe(ROUTE_FIXTURES.length);
    for (const fixture of ROUTE_FIXTURES) {
      expect(resolveRouteFixture(fixture.origin, fixture.destination)?.id).toBe(fixture.id);
    }
  });
});
