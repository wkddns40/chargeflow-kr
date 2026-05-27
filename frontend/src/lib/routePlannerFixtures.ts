import type { RouteCoordinate, RoutePlannerRoute } from './routePlanner';

export type RoutePlaceId =
  | 'seoul-gangnam'
  | 'seoul-seocho'
  | 'seoul-songpa'
  | 'seoul-mapo'
  | 'seoul-seongdong'
  | 'seoul-yongsan'
  | 'seoul-jongno'
  | 'suwon'
  | 'seongnam'
  | 'goyang'
  | 'yongin'
  | 'bucheon'
  | 'ansan'
  | 'anyang'
  | 'incheon-songdo'
  | 'busan-station'
  | 'busan-haeundae'
  | 'daegu-suseong'
  | 'daejeon-central'
  | 'daejeon-yuseong'
  | 'gwangju-sangmu'
  | 'ulsan-samsan'
  | 'sejong'
  | 'jeju-city'
  | 'seogwipo'
  | 'aewol';

export type RoutePlannerPlace = {
  id: RoutePlaceId;
  slug: string;
  label: string;
  aliases: string[];
  coordinate: RouteCoordinate;
};

export type RoutePlannerFixture = RoutePlannerRoute & {
  label: string;
  origin: string;
  destination: string;
  originPlaceId: RoutePlaceId;
  destinationPlaceId: RoutePlaceId;
  originAliases: string[];
  destinationAliases: string[];
};

type RouteDefinition = {
  origin: RoutePlaceId;
  destination: RoutePlaceId;
  distance_km: number;
  path?: RoutePlaceId[];
  polyline?: RouteCoordinate[];
};

export const ROUTE_PLACE_CATALOG: RoutePlannerPlace[] = [
  {
    id: 'seoul-gangnam',
    slug: 'seoul-gangnam',
    label: 'Seoul Gangnam',
    aliases: ['Gangnam', 'Gangnam Station', '서울 강남', '강남', '강남구', '강남역'],
    coordinate: [127.048, 37.5115],
  },
  {
    id: 'seoul-seocho',
    slug: 'seoul-seocho',
    label: 'Seoul Seocho',
    aliases: ['Seocho', '서울 서초', '서초', '서초구', '교대', '교대역'],
    coordinate: [127.014, 37.489],
  },
  {
    id: 'seoul-songpa',
    slug: 'seoul-songpa',
    label: 'Seoul Songpa',
    aliases: ['Songpa', 'Jamsil', '서울 송파', '송파', '송파구', '잠실', '잠실역'],
    coordinate: [127.1075, 37.51],
  },
  {
    id: 'seoul-mapo',
    slug: 'seoul-mapo',
    label: 'Seoul Mapo',
    aliases: ['Mapo', 'Hongdae', '서울 마포', '마포', '마포구', '홍대', '홍대입구', '공덕'],
    coordinate: [126.9125, 37.558],
  },
  {
    id: 'seoul-seongdong',
    slug: 'seoul-seongdong',
    label: 'Seoul Seongdong',
    aliases: ['Seongdong', 'Wangsimni', '서울 성동', '성동', '성동구', '왕십리', '왕십리역'],
    coordinate: [127.0425, 37.555],
  },
  {
    id: 'seoul-yongsan',
    slug: 'seoul-yongsan',
    label: 'Seoul Yongsan',
    aliases: ['Yongsan', '서울 용산', '용산', '용산구', '용산역'],
    coordinate: [126.9815, 37.532],
  },
  {
    id: 'seoul-jongno',
    slug: 'seoul',
    label: 'Seoul',
    aliases: [
      'Jongno',
      'Seoul Station',
      'Seoul Center',
      '서울',
      '서울시',
      '서울특별시',
      '서울역',
      '서울 중심',
      '서울중심',
      '종로',
      '종로구',
      '광화문',
      '시청',
    ],
    coordinate: [126.9825, 37.578],
  },
  {
    id: 'suwon',
    slug: 'suwon',
    label: 'Suwon',
    aliases: ['Suwon Station', '수원', '수원시', '수원역'],
    coordinate: [127.03, 37.27],
  },
  {
    id: 'seongnam',
    slug: 'seongnam',
    label: 'Seongnam',
    aliases: ['Bundang', '성남', '성남시', '분당', '분당구', '서현'],
    coordinate: [127.1415, 37.42],
  },
  {
    id: 'goyang',
    slug: 'goyang',
    label: 'Goyang',
    aliases: ['Ilsan', '고양', '고양시', '일산', '일산동구'],
    coordinate: [126.795, 37.653],
  },
  {
    id: 'yongin',
    slug: 'yongin',
    label: 'Yongin',
    aliases: ['Suji', '용인', '용인시', '수지', '수지구'],
    coordinate: [127.1325, 37.245],
  },
  {
    id: 'bucheon',
    slug: 'bucheon',
    label: 'Bucheon',
    aliases: ['부천', '부천시'],
    coordinate: [126.7685, 37.5],
  },
  {
    id: 'ansan',
    slug: 'ansan',
    label: 'Ansan',
    aliases: ['안산', '안산시', '단원구'],
    coordinate: [126.836, 37.32],
  },
  {
    id: 'anyang',
    slug: 'anyang',
    label: 'Anyang',
    aliases: ['안양', '안양시', '동안구', '평촌'],
    coordinate: [126.959, 37.395],
  },
  {
    id: 'incheon-songdo',
    slug: 'incheon-songdo',
    label: 'Incheon Songdo',
    aliases: ['Incheon', 'Songdo', '인천', '인천시', '인천광역시', '송도', '인천 송도', '송도동', '연수구'],
    coordinate: [126.6575, 37.3825],
  },
  {
    id: 'busan-station',
    slug: 'busan',
    label: 'Busan',
    aliases: ['Busan Station', '부산', '부산시', '부산광역시', '부산역', '부산 동구', '동구'],
    coordinate: [129.0575, 35.1175],
  },
  {
    id: 'busan-haeundae',
    slug: 'busan-haeundae',
    label: 'Busan Haeundae',
    aliases: ['Haeundae', '부산 해운대', '해운대', '해운대구', '해운대역', '센텀', '센텀시티'],
    coordinate: [129.1475, 35.1675],
  },
  {
    id: 'daegu-suseong',
    slug: 'daegu',
    label: 'Daegu',
    aliases: ['Daegu Suseong', '대구', '대구시', '대구광역시', '대구역', '동대구', '동대구역', '수성', '수성구'],
    coordinate: [128.63, 35.8525],
  },
  {
    id: 'daejeon-central',
    slug: 'daejeon',
    label: 'Daejeon',
    aliases: ['Daejeon Station', 'Daejeon Central', '대전', '대전시', '대전광역시', '대전역', '대전중앙', '중앙로'],
    coordinate: [127.4325, 36.35],
  },
  {
    id: 'daejeon-yuseong',
    slug: 'daejeon-yuseong',
    label: 'Daejeon Yuseong',
    aliases: ['Yuseong', '대전 유성', '유성', '유성구', '충남대'],
    coordinate: [127.35, 36.365],
  },
  {
    id: 'gwangju-sangmu',
    slug: 'gwangju',
    label: 'Gwangju',
    aliases: ['Gwangju Sangmu', '광주', '광주시', '광주광역시', '상무', '상무지구', '서구'],
    coordinate: [126.86, 35.155],
  },
  {
    id: 'ulsan-samsan',
    slug: 'ulsan',
    label: 'Ulsan',
    aliases: ['Ulsan Samsan', '울산', '울산시', '울산광역시', '삼산', '삼산동', '남구'],
    coordinate: [129.34, 35.5425],
  },
  {
    id: 'sejong',
    slug: 'sejong',
    label: 'Sejong',
    aliases: ['세종', '세종시', '세종특별자치시', '한누리대로'],
    coordinate: [127.2725, 36.5025],
  },
  {
    id: 'jeju-city',
    slug: 'jeju-city',
    label: 'Jeju City',
    aliases: ['Jeju', 'Jeju Airport', 'Jeju International Airport', '제주', '제주시', '제주공항', '제주국제공항'],
    coordinate: [126.523, 33.4975],
  },
  {
    id: 'seogwipo',
    slug: 'seogwipo',
    label: 'Seogwipo',
    aliases: ['서귀포', '서귀포시', '중앙로'],
    coordinate: [126.5685, 33.255],
  },
  {
    id: 'aewol',
    slug: 'aewol',
    label: 'Aewol',
    aliases: ['제주 애월', '애월', '애월읍'],
    coordinate: [126.34, 33.465],
  },
];

const ROUTE_DEFINITIONS: RouteDefinition[] = [
  {
    origin: 'seoul-jongno',
    destination: 'daejeon-central',
    distance_km: 165.2,
    polyline: [
      [126.978, 37.5665],
      [127.0276, 37.4979],
      [127.3845, 36.3504],
      [127.4325, 36.35],
    ],
  },
  { origin: 'seoul-jongno', destination: 'suwon', distance_km: 36, path: ['seoul-jongno', 'seoul-gangnam', 'suwon'] },
  {
    origin: 'seoul-jongno',
    destination: 'seongnam',
    distance_km: 30,
    path: ['seoul-jongno', 'seoul-gangnam', 'seongnam'],
  },
  { origin: 'seoul-jongno', destination: 'goyang', distance_km: 25, path: ['seoul-jongno', 'goyang'] },
  {
    origin: 'seoul-jongno',
    destination: 'yongin',
    distance_km: 45,
    path: ['seoul-jongno', 'seoul-gangnam', 'seongnam', 'yongin'],
  },
  { origin: 'seoul-jongno', destination: 'bucheon', distance_km: 25, path: ['seoul-jongno', 'bucheon'] },
  {
    origin: 'seoul-jongno',
    destination: 'ansan',
    distance_km: 45,
    path: ['seoul-jongno', 'anyang', 'ansan'],
  },
  { origin: 'seoul-jongno', destination: 'anyang', distance_km: 25, path: ['seoul-jongno', 'anyang'] },
  {
    origin: 'seoul-jongno',
    destination: 'incheon-songdo',
    distance_km: 45,
    path: ['seoul-jongno', 'bucheon', 'incheon-songdo'],
  },
  { origin: 'seoul-jongno', destination: 'sejong', distance_km: 130, path: ['seoul-jongno', 'seoul-gangnam', 'sejong'] },
  {
    origin: 'seoul-jongno',
    destination: 'daegu-suseong',
    distance_km: 285,
    path: ['seoul-jongno', 'seoul-gangnam', 'daejeon-central', 'daegu-suseong'],
  },
  {
    origin: 'seoul-jongno',
    destination: 'busan-station',
    distance_km: 395,
    path: ['seoul-jongno', 'seoul-gangnam', 'daejeon-central', 'daegu-suseong', 'busan-station'],
  },
  {
    origin: 'seoul-jongno',
    destination: 'gwangju-sangmu',
    distance_km: 300,
    path: ['seoul-jongno', 'seoul-gangnam', 'daejeon-central', 'gwangju-sangmu'],
  },
  {
    origin: 'seoul-jongno',
    destination: 'ulsan-samsan',
    distance_km: 370,
    path: ['seoul-jongno', 'seoul-gangnam', 'daejeon-central', 'daegu-suseong', 'ulsan-samsan'],
  },
  {
    origin: 'daejeon-central',
    destination: 'daejeon-yuseong',
    distance_km: 12,
    path: ['daejeon-central', 'daejeon-yuseong'],
  },
  {
    origin: 'busan-station',
    destination: 'busan-haeundae',
    distance_km: 16,
    path: ['busan-station', 'busan-haeundae'],
  },
  { origin: 'jeju-city', destination: 'aewol', distance_km: 24, path: ['jeju-city', 'aewol'] },
  { origin: 'jeju-city', destination: 'seogwipo', distance_km: 42, path: ['jeju-city', 'seogwipo'] },
  {
    origin: 'daejeon-central',
    destination: 'daegu-suseong',
    distance_km: 155,
    path: ['daejeon-central', 'daegu-suseong'],
  },
  {
    origin: 'daejeon-central',
    destination: 'gwangju-sangmu',
    distance_km: 170,
    path: ['daejeon-central', 'gwangju-sangmu'],
  },
  {
    origin: 'daejeon-central',
    destination: 'busan-station',
    distance_km: 250,
    path: ['daejeon-central', 'daegu-suseong', 'busan-station'],
  },
  {
    origin: 'daejeon-central',
    destination: 'ulsan-samsan',
    distance_km: 235,
    path: ['daejeon-central', 'daegu-suseong', 'ulsan-samsan'],
  },
  {
    origin: 'daegu-suseong',
    destination: 'busan-station',
    distance_km: 110,
    path: ['daegu-suseong', 'busan-station'],
  },
  {
    origin: 'daegu-suseong',
    destination: 'ulsan-samsan',
    distance_km: 100,
    path: ['daegu-suseong', 'ulsan-samsan'],
  },
  {
    origin: 'busan-station',
    destination: 'ulsan-samsan',
    distance_km: 65,
    path: ['busan-station', 'ulsan-samsan'],
  },
];

const ROUTE_PLACE_BY_ID = new Map<RoutePlaceId, RoutePlannerPlace>(
  ROUTE_PLACE_CATALOG.map((place) => [place.id, place]),
);

export const ROUTE_FIXTURES: RoutePlannerFixture[] = ROUTE_DEFINITIONS.flatMap((definition) => [
  buildRouteFixture(definition),
  buildRouteFixture(definition, true),
]);

const ROUTE_FIXTURE_BY_PLACE_PAIR = new Map(
  ROUTE_FIXTURES.map((fixture) => [routePairKey(fixture.originPlaceId, fixture.destinationPlaceId), fixture]),
);

const SEOUL_ROUTE_PLACE_ID: RoutePlaceId = 'seoul-jongno';
const SEOUL_DISTRICT_PLACE_IDS = new Set<RoutePlaceId>([
  'seoul-gangnam',
  'seoul-seocho',
  'seoul-songpa',
  'seoul-mapo',
  'seoul-seongdong',
  'seoul-yongsan',
  'seoul-jongno',
]);
const SEOUL_DISTRICT_PREFIXES: Array<[string, RoutePlaceId]> = [
  ['강남', 'seoul-gangnam'],
  ['서초', 'seoul-seocho'],
  ['송파', 'seoul-songpa'],
  ['마포', 'seoul-mapo'],
  ['성동', 'seoul-seongdong'],
  ['용산', 'seoul-yongsan'],
  ['종로', 'seoul-jongno'],
];
const SEOUL_REGION_PREFIXES = ['서울특별시', '서울시', '서울'];

export function resolveRouteFixture(origin: string, destination: string): RoutePlannerFixture | null {
  const originPlace = resolveRoutePlace(origin);
  const destinationPlace = resolveRoutePlace(destination);

  if (!originPlace || !destinationPlace) {
    return null;
  }

  return (
    ROUTE_FIXTURE_BY_PLACE_PAIR.get(routePairKey(originPlace.id, destinationPlace.id)) ??
    ROUTE_FIXTURE_BY_PLACE_PAIR.get(
      routePairKey(resolveSeoulRoutePlaceId(originPlace.id), resolveSeoulRoutePlaceId(destinationPlace.id)),
    ) ??
    null
  );
}

export function resolveRoutePlace(value: string): RoutePlannerPlace | null {
  const normalizedValue = normalizeRoutePlace(value);
  const compactValue = compactRoutePlace(value);

  if (!normalizedValue) {
    return null;
  }

  return (
    ROUTE_PLACE_CATALOG.find((place) =>
      [place.label, ...place.aliases].some(
        (alias) => normalizeRoutePlace(alias) === normalizedValue || compactRoutePlace(alias) === compactValue,
      ),
    ) ??
    resolveSeoulDistrictRoutePlace(compactValue) ??
    null
  );
}

export function normalizeRoutePlace(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, ' ');
}

function compactRoutePlace(value: string): string {
  return normalizeRoutePlace(value).replace(/\s+/g, '');
}

function resolveSeoulDistrictRoutePlace(compactValue: string): RoutePlannerPlace | null {
  const compactSeoulDistrict = stripSeoulRegionPrefix(compactValue);
  const matchedPrefix = SEOUL_DISTRICT_PREFIXES.find(([prefix]) => compactSeoulDistrict.startsWith(prefix));
  return matchedPrefix ? getRoutePlace(matchedPrefix[1]) : null;
}

function stripSeoulRegionPrefix(compactValue: string): string {
  const matchedPrefix = SEOUL_REGION_PREFIXES.find((prefix) => compactValue.startsWith(prefix));
  return matchedPrefix ? compactValue.slice(matchedPrefix.length) : compactValue;
}

function resolveSeoulRoutePlaceId(placeId: RoutePlaceId): RoutePlaceId {
  return SEOUL_DISTRICT_PLACE_IDS.has(placeId) ? SEOUL_ROUTE_PLACE_ID : placeId;
}

function buildRouteFixture(definition: RouteDefinition, reverse = false): RoutePlannerFixture {
  const origin = getRoutePlace(reverse ? definition.destination : definition.origin);
  const destination = getRoutePlace(reverse ? definition.origin : definition.destination);
  const sourcePolyline = definition.polyline ?? routePathToPolyline(definition.path);
  const polyline = reverse ? [...sourcePolyline].reverse() : sourcePolyline;

  return {
    id: `fixture-${origin.slug}-${destination.slug}`,
    label: `${origin.label}-${destination.label}`,
    origin: origin.label,
    destination: destination.label,
    originPlaceId: origin.id,
    destinationPlaceId: destination.id,
    originAliases: [origin.label, ...origin.aliases],
    destinationAliases: [destination.label, ...destination.aliases],
    distance_km: definition.distance_km,
    polyline,
  };
}

function routePathToPolyline(path: RoutePlaceId[] | undefined): RouteCoordinate[] {
  if (!path || path.length < 2) {
    throw new Error('route fixture path must contain at least two places');
  }

  return path.map((placeId) => getRoutePlace(placeId).coordinate);
}

function getRoutePlace(id: RoutePlaceId): RoutePlannerPlace {
  const place = ROUTE_PLACE_BY_ID.get(id);
  if (!place) {
    throw new Error(`route place not found: ${id}`);
  }
  return place;
}

function routePairKey(origin: RoutePlaceId, destination: RoutePlaceId): string {
  return `${origin}->${destination}`;
}
