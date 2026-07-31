export type Category = "vehicle_rental" | "activity" | "tour" | "accommodation";

export interface RiskInfo {
  reason: string;
  recommendation: string;
}

export interface Clause {
  no: string; // e.g. "제3조"
  title: string;
  text: string;
  risk?: RiskInfo;
}

export interface Contract {
  id: string;
  seller: string;
  title: string;
  category: Category;
  district: string; // 부산 구 단위
  start: string; // YYYY.MM.DD
  end: string;
  unitPrice: number; // KRW
  priceUnit: string; // 단위 라벨 (예: 객실당 / 1인당)
  quantityLabel: string; // 공급 수량 라벨
  capacity: number; // 수용/공급 인원 또는 실 수
  available: boolean; // 계약 가능 여부
  popularity: number; // 인기순 정렬용
  createdOrder: number; // 최신순 정렬용 (클수록 최신)
  recommendScore: number; // 추천순 정렬용
  image: string;
  aiSummary: string[]; // 3줄 요약
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
  "기장군",
];

export const contracts: Contract[] = [
  {
    id: "ocean-stay-2026-summer",
    seller: "해운대 오션스테이",
    title: "2026 부산 여름 패키지 객실 공급 계약",
    category: "accommodation",
    district: "해운대구",
    start: "2026.07.01",
    end: "2026.08.31",
    unitPrice: 145000,
    priceUnit: "객실당",
    quantityLabel: "주말 객실 최대 30실",
    capacity: 30,
    available: true,
    popularity: 98,
    createdOrder: 100,
    recommendScore: 99,
    image:
      "https://images.unsplash.com/photo-1769847778899-649ebe5bed2a?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
    aiSummary: [
      "성수기 주말 객실 30실을 객실당 145,000원에 안정적으로 확보할 수 있는 계약입니다.",
      "무료 취소 기한과 노쇼 처리 기준이 명확하지 않아 협의가 필요합니다.",
      "정산 지급일과 지급 주체가 불명확해 AI가 확인 필요 조항 3개를 표시했습니다.",
    ],
    details: {
      period: "2026.07.01 ~ 2026.08.31",
      supplyQuantity: "주말 객실 최대 30실",
      unitPrice: "객실당 145,000원 (VAT 별도)",
      cancellation: "무료 취소 가능 · 기한 협의 필요",
      noShow: "기준 미정",
      settlement: "추후 정산 · 지급일 협의 필요",
    },
    clauses: [
      {
        no: "제1조",
        title: "계약의 목적",
        text: "본 계약은 셀러(해운대 오션스테이)가 바이어에게 2026년 여름 성수기 객실을 공급하고, 바이어가 이를 판매·유통하는 데 필요한 조건을 정함을 목적으로 한다.",
      },
      {
        no: "제2조",
        title: "공급 기간 및 수량",
        text: "공급 기간은 2026년 7월 1일부터 8월 31일까지로 하며, 주말(금·토) 기준 최대 30실을 공급한다. 평일 객실은 상호 협의에 따라 추가 공급할 수 있다.",
      },
      {
        no: "제3조",
        title: "공급 단가",
        text: "객실 공급 단가는 객실당 145,000원(VAT 별도)으로 한다.",
      },
      {
        no: "제4조",
        title: "취소 및 환불",
        text: "바이어는 필요에 따라 예약을 무료로 취소할 수 있다.",
        risk: {
          reason: "무료 취소가 가능한 기한과 이후 수수료 기준이 없어 셀러가 체크인 직전까지 취소 위험을 부담할 수 있습니다.",
          recommendation: "체크인 7일 전까지 무료 취소하고 이후 취소 시 객실 1박 요금의 50%를 부과하도록 기준을 명시하세요.",
        },
      },
      {
        no: "제5조",
        title: "노쇼(No-show) 처리",
        text: "노쇼 발생 시 처리 기준은 별도로 정하지 않는다.",
        risk: {
          reason: "예약자가 방문하지 않은 경우의 비용 기준이 없어 노쇼 발생 시 정산 범위를 두고 분쟁이 생길 수 있습니다.",
          recommendation: "노쇼 발생 시 해당 객실의 1박 요금 100%를 부과하도록 명시하세요.",
        },
      },
      {
        no: "제6조",
        title: "정산 및 지급",
        text: "객실 이용 금액은 추후 정산한다.",
        risk: {
          reason: "대금 지급 시점과 지급 주체가 명확하지 않아 정산 지연이나 미수금 분쟁이 발생할 수 있습니다.",
          recommendation: "매월 말 이용 내역을 마감하고 익월 15일까지 바이어가 셀러에게 지급하도록 명시하세요.",
        },
      },
      {
        no: "제8조",
        title: "분쟁 해결",
        text: "본 계약과 관련하여 분쟁이 발생하는 경우 부산지방법원을 제1심 관할 법원으로 한다.",
      },
    ],
  },
  {
    id: "gwangan-seabreeze",
    seller: "광안 씨브리즈 호텔",
    title: "2026 광안리 오션뷰 객실 공급 계약",
    category: "accommodation",
    district: "수영구",
    start: "2026.06.15",
    end: "2026.09.15",
    unitPrice: 128000,
    priceUnit: "객실당",
    quantityLabel: "주중·주말 객실 최대 40실",
    capacity: 40,
    available: true,
    popularity: 84,
    createdOrder: 92,
    recommendScore: 90,
    image:
      "https://images.unsplash.com/photo-1575907789733-c3dda018bae7?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
    aiSummary: [
      "광안대교 오션뷰 객실 40실을 객실당 128,000원에 장기간 확보하는 계약입니다.",
      "취소·노쇼 조건이 표준적이며 바이어에게 유리한 편입니다.",
      "정산 주기가 60일로 다소 길어 현금 흐름 측면에서 확인이 필요합니다.",
    ],
    details: {
      period: "2026.06.15 ~ 2026.09.15",
      supplyQuantity: "주중·주말 객실 최대 40실",
      unitPrice: "객실당 128,000원 (VAT 별도)",
      cancellation: "체크인 5일 전까지 무료 취소",
      noShow: "객실 1박 요금의 80% 청구",
      settlement: "매월 말 마감 후 익익월 15일 지급",
    },
    clauses: [
      {
        no: "제1조",
        title: "계약의 목적",
        text: "셀러가 바이어에게 광안리 오션뷰 객실을 공급하는 조건을 정한다.",
      },
      {
        no: "제2조",
        title: "공급 기간 및 수량",
        text: "2026년 6월 15일부터 9월 15일까지 주중·주말 최대 40실을 공급한다.",
      },
      {
        no: "제3조",
        title: "정산 및 지급",
        text: "정산은 매월 말 마감 후 익익월(60일) 15일에 지급한다.",
        risk: {
          reason:
            "정산 주기가 60일로 업계 표준(30일)보다 길어, 바이어의 운전자금 부담이 증가할 수 있습니다.",
          recommendation:
            "정산 주기를 익월 15일(30일)로 단축하거나, 60일 유지 시 조기 정산 할인 조건을 추가할 것을 권장합니다.",
        },
      },
      {
        no: "제4조",
        title: "취소 및 노쇼",
        text: "체크인 5일 전까지 무료 취소하며, 노쇼 시 1박 요금의 80%를 청구한다.",
      },
    ],
  },
  {
    id: "marina-yacht-tour",
    seller: "부산 마리나 요트클럽",
    title: "2026 요트 선셋 투어 좌석 공급 계약",
    category: "tour",
    district: "수영구",
    start: "2026.05.01",
    end: "2026.10.31",
    unitPrice: 89000,
    priceUnit: "1인당",
    quantityLabel: "1회당 최대 20석",
    capacity: 20,
    available: true,
    popularity: 76,
    createdOrder: 88,
    recommendScore: 82,
    image:
      "https://images.unsplash.com/photo-1712739034224-2904f23c4c5f?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
    aiSummary: [
      "수영만 요트 선셋 투어 좌석을 1인당 89,000원에 공급받는 체험형 계약입니다.",
      "우천·기상 악화 시 취소·환불 기준이 명확하게 규정되어 있습니다.",
      "안전사고 배상 책임의 범위가 셀러에게 유리하게 설정되어 확인이 필요합니다.",
    ],
    details: {
      period: "2026.05.01 ~ 2026.10.31",
      supplyQuantity: "1회 운항당 최대 20석",
      unitPrice: "1인당 89,000원 (VAT 포함)",
      cancellation: "투어 3일 전까지 무료 취소",
      noShow: "좌석 요금 전액 청구",
      settlement: "매월 말 마감 후 익월 20일 지급",
    },
    clauses: [
      { no: "제1조", title: "계약의 목적", text: "요트 선셋 투어 좌석 공급 조건을 정한다." },
      {
        no: "제2조",
        title: "안전사고 배상 책임",
        text: "투어 중 발생한 안전사고에 대한 배상 책임은 이용객의 고의·과실이 없는 경우에 한하여 셀러가 부담하되, 배상 한도는 1인당 500만 원으로 제한한다.",
        risk: {
          reason:
            "배상 한도를 1인당 500만 원으로 제한하고 있어, 중대 사고 발생 시 바이어(여행사)가 추가 배상 책임에 노출될 수 있습니다.",
          recommendation:
            "셀러의 영업배상책임보험 가입을 계약 조건으로 명시하고, 보험 한도 내에서는 별도 상한을 두지 않도록 조정할 것을 권장합니다.",
        },
      },
      { no: "제3조", title: "기상 악화 시 처리", text: "기상 악화로 운항이 취소되면 전액 환불 또는 일정 변경한다." },
    ],
  },
  {
    id: "songjeong-surf",
    seller: "송정 서핑클럽",
    title: "2026 송정 서핑 강습 패키지 공급 계약",
    category: "activity",
    district: "해운대구",
    start: "2026.06.01",
    end: "2026.09.30",
    unitPrice: 65000,
    priceUnit: "1인당",
    quantityLabel: "1일 최대 40명",
    capacity: 40,
    available: true,
    popularity: 71,
    createdOrder: 80,
    recommendScore: 74,
    image:
      "https://images.unsplash.com/photo-1601505804121-45e2c5506c94?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
    aiSummary: [
      "송정 해변 서핑 강습(장비 포함) 패키지를 1인당 65,000원에 공급받는 계약입니다.",
      "강사 대 수강생 비율(1:5)이 명시되어 서비스 품질이 보장됩니다.",
      "취소 정책이 이용 1일 전 기준으로 짧아 확인이 필요합니다.",
    ],
    details: {
      period: "2026.06.01 ~ 2026.09.30",
      supplyQuantity: "1일 최대 40명 (강사 1인당 5명)",
      unitPrice: "1인당 65,000원 (장비 대여 포함)",
      cancellation: "이용 1일 전까지 무료 취소",
      noShow: "강습료 전액 청구",
      settlement: "매월 말 마감 후 익월 15일 지급",
    },
    clauses: [
      { no: "제1조", title: "계약의 목적", text: "서핑 강습 패키지 공급 조건을 정한다." },
      {
        no: "제2조",
        title: "취소 정책",
        text: "이용 1일 전까지 무료 취소가 가능하며, 당일 취소 시 강습료 전액을 청구한다.",
        risk: {
          reason:
            "무료 취소 기한이 이용 1일 전으로 짧아, 단체 예약 변경 시 바이어의 취소 수수료 부담이 커질 수 있습니다.",
          recommendation:
            "단체(10인 이상) 예약에 한해 무료 취소 기한을 이용 3일 전으로 완화하는 조항 추가를 권장합니다.",
        },
      },
    ],
  },
  {
    id: "busan-city-package",
    seller: "부산 시티투어 파트너스",
    title: "2026 부산 시티 하이라이트 패키지 공급 계약",
    category: "tour",
    district: "부산진구",
    start: "2026.04.01",
    end: "2026.12.31",
    unitPrice: 210000,
    priceUnit: "1인당",
    quantityLabel: "1일 최대 25명",
    capacity: 25,
    available: false,
    popularity: 88,
    createdOrder: 70,
    recommendScore: 86,
    image:
      "https://images.unsplash.com/photo-1769847760685-f940834048fd?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
    aiSummary: [
      "숙박·투어·식사를 묶은 1박 2일 부산 시티 패키지를 1인당 210,000원에 공급받는 계약입니다.",
      "성수기·비수기 요금이 분리되어 있어 가격 예측이 용이합니다.",
      "현재 공급사 사정으로 신규 계약이 일시 마감된 상태입니다.",
    ],
    details: {
      period: "2026.04.01 ~ 2026.12.31",
      supplyQuantity: "1일 최대 25명",
      unitPrice: "1인당 210,000원 (숙박·식사 포함)",
      cancellation: "출발 5일 전까지 무료 취소",
      noShow: "패키지 요금의 70% 청구",
      settlement: "매월 말 마감 후 익월 15일 지급",
    },
    clauses: [
      { no: "제1조", title: "계약의 목적", text: "부산 시티 패키지 상품 공급 조건을 정한다." },
      { no: "제2조", title: "요금 구성", text: "성수기·비수기 요금을 분리 적용하며 세부 요금표는 별첨한다." },
    ],
  },
  {
    id: "gijang-glamping",
    seller: "기장 오션 글램핑",
    title: "2026 기장 오션뷰 글램핑 공급 계약",
    category: "accommodation",
    district: "기장군",
    start: "2026.05.01",
    end: "2026.10.31",
    unitPrice: 175000,
    priceUnit: "1동당",
    quantityLabel: "1일 최대 15동",
    capacity: 15,
    available: true,
    popularity: 69,
    createdOrder: 96,
    recommendScore: 78,
    image:
      "https://images.unsplash.com/photo-1697983586877-1ae4e3656f6b?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
    aiSummary: [
      "기장 해안 글램핑 15동을 1동당 175,000원에 공급받는 계약입니다.",
      "바비큐·조식 옵션이 포함되어 부가 상품 구성이 용이합니다.",
      "취소·정산 조건이 표준적이며 특이 위험 조항은 없습니다.",
    ],
    details: {
      period: "2026.05.01 ~ 2026.10.31",
      supplyQuantity: "1일 최대 15동",
      unitPrice: "1동당 175,000원 (조식 포함)",
      cancellation: "체크인 7일 전까지 무료 취소",
      noShow: "1박 요금 기준 청구",
      settlement: "매월 말 마감 후 익월 15일 지급",
    },
    clauses: [
      { no: "제1조", title: "계약의 목적", text: "오션뷰 글램핑 공급 조건을 정한다." },
      { no: "제2조", title: "취소 및 정산", text: "체크인 7일 전까지 무료 취소하며, 정산은 익월 15일에 지급한다." },
    ],
  },
];

export function getContract(id: string | undefined): Contract | undefined {
  return contracts.find((c) => c.id === id);
}

export function riskCount(c: Contract): number {
  return c.clauses.filter((cl) => cl.risk).length;
}

export function formatKRW(n: number): string {
  return n.toLocaleString("ko-KR") + "원";
}
