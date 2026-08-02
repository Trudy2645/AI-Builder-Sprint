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

export const contracts: Contract[] = [
  {
    id: "coastline-hotel-room-2026",
    seller: "해운대 오션스테이",
    title: "2026 해운대 단체 객실 공급 계약",
    category: "accommodation",
    district: "해운대구",
    start: "2026.07.01",
    end: "2026.08.31",
    unitPrice: 146000,
    priceUnit: "객실당",
    quantityLabel: "1일 최대 32실",
    capacity: 32,
    available: true,
    popularity: 97,
    createdOrder: 100,
    recommendScore: 99,
    image:
      "https://images.unsplash.com/photo-1566073771259-6a8506099945?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
    aiSummary: [
      "숙박 예약 약관의 예약확정·취소·노쇼·현장결제 구조를 바탕으로 만든 단체 객실 공급 계약입니다.",
      "객실 사정에 따른 예약 거절 또는 조건 변경 가능성이 있어 확정 시점을 명확히 확인해야 합니다.",
      "노쇼와 보증금·부대비용 정산 기준을 계약서에 구체화할 필요가 있습니다.",
    ],
    details: {
      period: "2026.07.01 ~ 2026.08.31",
      supplyQuantity: "1일 최대 32실 · 객실당 기준 인원 2명",
      unitPrice: "객실당 146,000원 (VAT 별도)",
      cancellation: "체크인 7일 전까지 무료 취소",
      noShow: "객실 1박 공급가 100% 청구",
      settlement: "매월 말 마감 후 익월 15일 지급",
    },
    clauses: [
      {
        no: "제1조",
        title: "계약의 목적",
        text: "본 계약은 셀러가 바이어에게 해운대 지역 단체 관광객용 객실을 공급하고, 바이어가 이를 여행 일정에 맞게 배정·이용하는 조건을 정함을 목적으로 한다.",
      },
      {
        no: "제2조",
        title: "예약 요청 및 확정",
        text: "바이어의 예약 요청은 객실 공급에 대한 청약이며, 셀러가 객실 타입·투숙일·인원·요금을 확인하고 확정 통지를 보낸 때 예약이 성립한다.",
        risk: {
          reason: "예약 요청과 예약 확정의 시점이 다르면, 바이어가 요청만으로 객실이 확보되었다고 오해할 수 있습니다.",
          recommendation: "예약 성립 시점을 '셀러의 확정 통지 도달 시'로 명시하고, 확정 전에는 객실 확보가 보장되지 않음을 표시하세요.",
        },
      },
      {
        no: "제3조",
        title: "공급 기간 및 수량",
        text: "공급 기간은 2026년 7월 1일부터 8월 31일까지이며, 셀러는 1일 최대 32실을 공급한다. 객실 수량은 확정 통지서에 기재된 객실 수를 기준으로 한다.",
      },
      {
        no: "제4조",
        title: "요금 및 부대비용",
        text: "객실 공급 단가는 객실당 146,000원으로 한다. 세금, 봉사료, 리조트피, 객실 파손 보증금, 미니바 등 부대비용은 별도 고지된 기준에 따라 정산한다.",
        risk: {
          reason: "숙박 상품은 세금·봉사료·보증금·부대비용이 추가될 수 있어 총 계약 금액과 실제 청구액이 달라질 수 있습니다.",
          recommendation: "계약서에 포함 비용과 불포함 비용을 분리하고, 현장 추가 비용의 청구 주체와 정산 방식을 명시하세요.",
        },
      },
      {
        no: "제5조",
        title: "변경·취소 및 노쇼",
        text: "바이어는 체크인 7일 전까지 무료로 객실 수량을 변경하거나 취소할 수 있다. 이후 취소는 취소 객실의 1박 공급가 50%, 노쇼는 해당 객실 1박 공급가 100%를 청구한다.",
      },
      {
        no: "제6조",
        title: "오버부킹 및 조건 변경",
        text: "셀러 사정으로 확정 객실 제공이 어려운 경우 셀러는 동급 이상 대체 객실을 제공하거나 바이어와 협의하여 예약을 취소하고 이미 지급된 금액을 환급한다.",
        risk: {
          reason: "대체 객실의 등급, 위치, 차액 기준이 모호하면 단체 일정 변경 비용을 누가 부담하는지 분쟁이 생길 수 있습니다.",
          recommendation: "대체 객실은 동일 지역·동급 이상으로 제한하고, 낮은 등급 대체 시 차액 환급과 이동 비용 부담 기준을 추가하세요.",
        },
      },
      {
        no: "제7조",
        title: "정산 및 지급",
        text: "셀러와 바이어는 매월 말 이용 내역을 확인하고, 바이어는 다음 달 15일까지 확정된 공급 대금을 셀러에게 지급한다.",
      },
      {
        no: "제8조",
        title: "분쟁 해결",
        text: "본 계약과 관련한 분쟁은 당사자 협의를 우선하며, 합의가 어려운 경우 대한민국 법령과 관할 법원 기준에 따른다.",
      },
    ],
  },
  {
    id: "bluewave-surf-lesson-2026",
    seller: "송정 블루웨이브 서프",
    title: "2026 송정 단체 서핑 강습 공급 계약",
    category: "activity",
    district: "해운대구",
    start: "2026.06.01",
    end: "2026.09.30",
    unitPrice: 68000,
    priceUnit: "1인당",
    quantityLabel: "1일 최대 45명",
    capacity: 45,
    available: true,
    popularity: 82,
    createdOrder: 96,
    recommendScore: 88,
    image:
      "https://images.unsplash.com/photo-1502680390469-be75c86b636f?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
    aiSummary: [
      "여행 체험 플랫폼 약관의 주문 확인·전자증빙·공급업체 책임·취소 환불 구조를 바탕으로 만든 액티비티 계약입니다.",
      "전자바우처 제시와 집합 시간 미준수 시 환불 제한 조건이 포함되어 있습니다.",
      "기상 악화와 안전사고 처리 기준은 보험 및 대체 일정 조항을 더 명확히 해야 합니다.",
    ],
    details: {
      period: "2026.06.01 ~ 2026.09.30",
      supplyQuantity: "1일 최대 45명 · 강사 1명당 최대 6명",
      unitPrice: "1인당 68,000원 (장비 대여 포함)",
      cancellation: "이용 3일 전까지 무료 취소",
      noShow: "강습료 전액 청구",
      settlement: "매월 말 마감 후 익월 15일 지급",
    },
    clauses: [
      {
        no: "제1조",
        title: "계약의 목적",
        text: "본 계약은 셀러가 바이어의 단체 여행객에게 서핑 강습과 장비 대여 서비스를 제공하는 조건을 정함을 목적으로 한다.",
      },
      {
        no: "제2조",
        title: "주문 확인 및 이용권",
        text: "바이어의 요청은 셀러 확인을 거쳐 확정되며, 확정 후 바이어는 참가자에게 전자 이용권 또는 예약번호를 전달한다. 참가자는 이용 당일 지정 장소에서 이용권과 신분 확인 자료를 제시한다.",
      },
      {
        no: "제3조",
        title: "강습 인원 및 운영 기준",
        text: "셀러는 1일 최대 45명까지 강습을 제공하며, 강사 1명당 참가자는 최대 6명으로 한다. 강습에는 슈트, 보드, 기본 안전 교육이 포함된다.",
      },
      {
        no: "제4조",
        title: "취소 및 환불",
        text: "바이어는 이용 3일 전까지 무료 취소할 수 있다. 이용 2일 전 취소는 총액의 50%, 전일 또는 당일 취소와 노쇼는 총액의 100%를 청구한다.",
        risk: {
          reason: "단체 액티비티는 참가자 변동이 잦아 취소 기한과 부분 취소 기준이 없으면 정산 분쟁이 발생할 수 있습니다.",
          recommendation: "전체 취소와 일부 인원 취소를 분리하고, 확정 인원 대비 10% 이내 인원 변동은 이용 1일 전까지 허용하는 조항을 검토하세요.",
        },
      },
      {
        no: "제5조",
        title: "전자 이용권 및 집합 시간",
        text: "참가자가 전자 이용권, 예약번호 또는 셀러가 요구한 확인 자료를 제시하지 못하거나 집합 시간 이후 도착하여 강습에 참여하지 못한 경우 환불이 제한될 수 있다.",
        risk: {
          reason: "전자 이용권 분실이나 지각을 전액 환불 불가로만 처리하면 바이어 입장에서 과도한 부담이 될 수 있습니다.",
          recommendation: "셀러가 예약자 명단으로 참가자 확인이 가능한 경우에는 이용권 재확인 절차를 제공하도록 수정하세요.",
        },
      },
      {
        no: "제6조",
        title: "기상 악화 및 안전",
        text: "태풍, 풍랑, 낙뢰, 현장 안전 판단 등으로 강습이 어렵다고 셀러가 판단한 경우 일정 변경 또는 환불을 제공한다. 참가자는 안전 교육과 강사 지시에 따라야 한다.",
        risk: {
          reason: "기상 악화 판단 주체가 셀러에게만 있으면 바이어가 일정 변경 가능성을 사전에 예측하기 어렵습니다.",
          recommendation: "기상청 특보, 해수욕장 통제, 현장 안전 책임자 판단을 취소 기준으로 명시하고, 대체 일정 우선 제공 후 불가 시 환불하도록 정리하세요.",
        },
      },
      {
        no: "제7조",
        title: "보험 및 사고 처리",
        text: "셀러는 영업배상책임보험 또는 이에 준하는 보험에 가입하고, 사고 발생 시 응급 조치와 보험 접수에 협조한다. 참가자의 고의·중과실 또는 안전 지시 위반으로 발생한 손해는 참가자 또는 바이어가 부담할 수 있다.",
        risk: {
          reason: "보험 종류와 보상 한도가 표시되지 않으면 사고 발생 시 바이어가 추가 책임에 노출될 수 있습니다.",
          recommendation: "보험명, 보상 한도, 자기부담금, 보상 제외 사유를 계약서 또는 별첨으로 제공하도록 추가하세요.",
        },
      },
      {
        no: "제8조",
        title: "정산 및 지급",
        text: "이용 완료 내역은 매월 말 확정하고, 바이어는 다음 달 15일까지 확정 금액을 셀러에게 지급한다.",
      },
    ],
  },
  {
    id: "route-rental-van-2026",
    seller: "김해공항 루트렌탈",
    title: "2026 김해공항 단체 밴 렌탈 계약",
    category: "vehicle_rental",
    district: "강서구",
    start: "2026.03.01",
    end: "2026.12.31",
    unitPrice: 132000,
    priceUnit: "차량 1대·1일",
    quantityLabel: "1일 최대 12대",
    capacity: 96,
    available: true,
    popularity: 74,
    createdOrder: 92,
    recommendScore: 84,
    image:
      "https://images.unsplash.com/photo-1541899481282-d53bffe3c35d?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
    aiSummary: [
      "공정거래위원회 자동차대여표준약관 구조를 바탕으로 만든 외국인 단체 밴 렌탈 계약입니다.",
      "보험·차량손해면책·사고 처리·휴차손해 산정 기준이 핵심 확인 항목입니다.",
      "대체 차량 기준과 반환 지연·연료 정산 기준을 계약서에 명확히 둘 필요가 있습니다.",
    ],
    details: {
      period: "2026.03.01 ~ 2026.12.31",
      supplyQuantity: "1일 최대 12대 · 차량당 최대 8명",
      unitPrice: "차량 1대·1일 132,000원 (VAT 별도)",
      cancellation: "대여 24시간 전까지 무료 취소",
      noShow: "예약금 환급 불가",
      settlement: "예약금 10% 이내 · 잔금 이용 전 정산",
    },
    clauses: [
      {
        no: "제1조",
        title: "계약의 목적",
        text: "본 계약은 셀러가 바이어에게 관광 일정에 필요한 차량을 대여하고, 바이어가 차량을 사용한 뒤 반환하는 조건을 정함을 목적으로 한다.",
      },
      {
        no: "제2조",
        title: "예약 및 대여 조건",
        text: "바이어는 차량 종류, 대여 요금, 대여 장소, 대여 기간, 반환 장소, 운전자 정보, 예약금 등 주요 조건을 확인한 뒤 계약 요청을 보낸다.",
      },
      {
        no: "제3조",
        title: "요금 및 정산",
        text: "대여 요금은 차량 1대 1일 단가를 기준으로 산정한다. 대여 기간 연장, 반환 장소 변경, 추가 운전자 등록 등 바이어 요청으로 발생한 추가 비용은 별도로 정산한다.",
      },
      {
        no: "제4조",
        title: "예약 취소 및 대체 차량",
        text: "바이어가 대여 시작 24시간 전까지 취소하면 예약금을 환급한다. 셀러 사유로 예약 차량을 제공할 수 없으면 동급 이상 차량을 제안하거나 예약금을 환급한다.",
        risk: {
          reason: "대체 차량의 등급, 좌석 수, 요금 차액 기준이 없으면 일정 운영과 비용 정산에서 분쟁이 생길 수 있습니다.",
          recommendation: "대체 차량은 예약 차량과 동일하거나 더 높은 좌석 수와 등급을 갖춘 차량으로 제한하고, 낮은 요금 차량 제공 시 차액을 환급하세요.",
        },
      },
      {
        no: "제5조",
        title: "보험 및 차량손해면책",
        text: "셀러는 대여 차량에 기본 자동차보험을 가입한다. 차량손해면책 또는 자기차량손해 담보는 바이어 선택 항목으로 제공하며, 보상 범위와 면책금은 계약 전에 고지한다.",
        risk: {
          reason: "보험 보상 범위와 면책금이 불명확하면 사고 발생 시 바이어가 예상하지 못한 비용을 부담할 수 있습니다.",
          recommendation: "보험 종류, 대인·대물 보상 한도, 자기차량손해 가입 여부, 면책금, 보상 제외 사유를 서면으로 고지하도록 명시하세요.",
        },
      },
      {
        no: "제6조",
        title: "차량 인도 전 점검",
        text: "셀러와 바이어는 차량 인도 시 외관, 연료 또는 충전 상태, 타이어, 등화장치, 유리, 좌석 안전벨트, 안전 장비를 함께 확인하고 체크리스트에 기록한다.",
      },
      {
        no: "제7조",
        title: "금지 행위 및 운전자 제한",
        text: "등록되지 않은 운전자, 무면허 운전, 음주 또는 약물 영향 상태의 운전, 유상 운송, 전대, 담보 제공, 경주 또는 시험 운전, 불법 목적 사용은 금지된다.",
      },
      {
        no: "제8조",
        title: "사고 처리 및 휴차손해",
        text: "사고가 발생하면 바이어는 즉시 셀러에게 알리고 보험 처리에 협조한다. 바이어 귀책으로 차량 수리가 필요한 경우 셀러는 객관적인 산정 근거를 제시해 휴차손해를 청구할 수 있다.",
        risk: {
          reason: "휴차손해 산정 근거가 없으면 수리 기간의 영업 손실 청구가 과도하게 계산될 수 있습니다.",
          recommendation: "수리 견적서, 수리 기간 확인서, 해당 차량의 통상 대여요금 등 객관 자료를 첨부한 경우에만 휴차손해를 청구하도록 수정하세요.",
        },
      },
      {
        no: "제9조",
        title: "반환 및 연료 정산",
        text: "바이어는 약정 시간과 장소에 차량을 반환한다. 연료 또는 충전량이 인도 시점보다 부족하면 부족분을 정산하며, 반환 지연 시 지연료와 회수 비용을 부담할 수 있다.",
        risk: {
          reason: "반환 지연료와 연료 정산 단가 기준이 사전에 정해져 있지 않으면 사후 비용 분쟁이 생길 수 있습니다.",
          recommendation: "반환 지연료는 시간당 또는 1일 대여 단가 기준으로 산정하고, 연료 부족분은 반환일 기준 셀러 고지 단가로 정산하도록 명시하세요.",
        },
      },
    ],
  },
];

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
