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

/** UI projection of a listing. It is always built from a public API response. */
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
  attentionRequiredCount?: number;
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

export function riskCount(contract: Contract): number {
  return contract.clauses.filter((clause) => clause.risk).length;
}

export function formatKRW(amount: number): string {
  return `${amount.toLocaleString("ko-KR")}원`;
}
