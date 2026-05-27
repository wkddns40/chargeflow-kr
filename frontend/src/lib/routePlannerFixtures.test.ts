import { describe, expect, it } from 'vitest';
import { resolveRouteFixture } from './routePlannerFixtures';

describe('resolveRouteFixture', () => {
  it('matches the supported Seoul to Daejeon fixture', () => {
    expect(resolveRouteFixture('Seoul', 'Daejeon')?.id).toBe('fixture-seoul-daejeon');
    expect(resolveRouteFixture('서울역', '대전역')?.id).toBe('fixture-seoul-daejeon');
  });

  it('does not create routes for unsupported origin and destination pairs', () => {
    expect(resolveRouteFixture('Busan', 'Daejeon')).toBeNull();
    expect(resolveRouteFixture('Daejeon', 'Seoul')).toBeNull();
  });
});
