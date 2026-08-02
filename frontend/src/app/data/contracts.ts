export type Category = "vehicle_rental" | "activity" | "tour" | "accommodation";

export interface RiskInfo {
  reason: string;
  recommendation: string;
}

export interface Clause {
  no: string;
  title: string;
  text: string;
  risk?: RiskInfo;
}

export interface Contract {
  id: string;
  seller: string;
  title: string;
  category: Category;
  district: string;
  start: string;
  end: string;
  unitPrice: number;
  priceUnit: string;
  quantityLabel: string;
  capacity: number;
  available: boolean;
  popularity: number;
  createdOrder: number;
  recommendScore: number;
  image: string;
  aiSummary: string[];
  details: {
    period: string;
    supplyQuantity: string;
    unitPrice: string;
    cancellation: string;
    noShow: string;
    settlement: string;
  };
  clauses: Clause[];
}

export const CATEGORIES: { value: Category | "all"; labelKey: string }[] = [
  { value: "all", labelKey: "cat.all" },
  { value: "vehicle_rental", labelKey: "cat.vehicleRental" },
  { value: "activity", labelKey: "cat.activity" },
  { value: "tour", labelKey: "cat.tour" },
  { value: "accommodation", labelKey: "cat.accommodation" },
];

export const DISTRICTS = [
  "해운대구",
  "수영구",
  "부산진구",
  "중구",
  "서구",
  "남구",
  "동구",
  "강서구",
  "기장군",
];

// 계약 목록은 백엔드 공개 공고 API에서만 제공한다.
export const contracts: Contract[] = [];

export const DEMO_SERVER_IDS: Record<string, string> = {
  "coastline-hotel-room-2026": "11111111-1111-4111-8111-111111111111",
  "bluewave-surf-lesson-2026": "22222222-2222-4222-8222-222222222222",
  "route-rental-van-2026": "33333333-3333-4333-8333-333333333333",
};

export function getContract(id: string | undefined): Contract | undefined {
  return contracts.find((c) => c.id === id || DEMO_SERVER_IDS[c.id] === id);
}

export function riskCount(c: Contract): number {
  return c.clauses.filter((cl) => cl.risk).length;
}

export function formatKRW(n: number): string {
  return n.toLocaleString("ko-KR") + "원";
}
