// 셀러가 바이어로부터 받은 수정 요청 (데모 데이터).
// 메인 숙박 공급계약의 예약확정·부대비용·오버부킹 위험 시나리오와 연결한다.

export interface ReceivedRevision {
  id: string;
  clauseNo: string;
  clauseTitle: string;
  original: string;
  requested: string;
  reason: string;
}

export interface ReceivedRequest {
  id: string;
  buyer: string;
  contractId: string;
  contractTitle: string;
  status: "new" | "negotiating" | "signing" | "signed";
  createdAt: string;
  period: string;
  estimatedAmount: string;
  currentVersion: string;
  revisions: ReceivedRevision[];
}

export const receivedRequests: ReceivedRequest[] = [
  {
    id: "rcv-coastline",
    buyer: "GlobalTrip Japan",
    contractId: "coastline-hotel-room-2026",
    contractTitle: "2026 해운대 단체 객실 공급 계약",
    status: "new",
    createdAt: "2026.07.26",
    period: "2026.07.01 ~ 2026.08.31",
    estimatedAmount: "4,380,000원",
    currentVersion: "v2 바이어 수정 요청안",
    revisions: [
      {
        id: "rrev-confirm",
        clauseNo: "제2조",
        clauseTitle: "예약 요청 및 확정",
        original:
          "바이어의 예약 요청은 객실 공급에 대한 청약이며, 셀러가 객실 타입·투숙일·인원·요금을 확인하고 확정 통지를 보낸 때 예약이 성립한다.",
        requested:
          "셀러의 확정 통지가 바이어에게 도달한 때 예약이 성립하며, 확정 전에는 객실 확보가 보장되지 않는다는 문구를 추가한다.",
        reason:
          "해외 단체 일정은 객실 확보 여부가 중요하므로 예약 요청과 확정 시점을 명확히 남기고 싶습니다.",
      },
      {
        id: "rrev-extra-fee",
        clauseNo: "제4조",
        clauseTitle: "요금 및 부대비용",
        original:
          "객실 공급 단가는 객실당 146,000원으로 한다. 세금, 봉사료, 리조트피, 객실 파손 보증금, 미니바 등 부대비용은 별도 고지된 기준에 따라 정산한다.",
        requested:
          "포함 비용과 불포함 비용을 별첨으로 분리하고, 현장 추가 비용은 셀러가 증빙과 함께 청구한다.",
        reason:
          "예약 금액 외 추가 비용이 발생할 때 청구 기준을 확인할 수 있어야 합니다.",
      },
      {
        id: "rrev-overbooking",
        clauseNo: "제6조",
        clauseTitle: "오버부킹 및 조건 변경",
        original:
          "셀러 사정으로 확정 객실 제공이 어려운 경우 셀러는 동급 이상 대체 객실을 제공하거나 바이어와 협의하여 예약을 취소하고 이미 지급된 금액을 환급한다.",
        requested:
          "대체 객실은 동일 지역·동급 이상으로 제공하고, 낮은 등급 대체 시 차액과 이동 비용은 셀러가 부담한다.",
        reason:
          "오버부킹으로 단체 일정이 바뀌는 경우 비용 부담을 명확히 하고 싶습니다.",
      },
    ],
  },
  {
    id: "rcv-surf",
    buyer: "Sakura Tour",
    contractId: "bluewave-surf-lesson-2026",
    contractTitle: "2026 송정 단체 서핑 강습 공급 계약",
    status: "negotiating",
    createdAt: "2026.07.24",
    period: "2026.08.05 ~ 2026.08.05",
    estimatedAmount: "2,040,000원",
    currentVersion: "v3 셀러 대안 협상 중",
    revisions: [
      {
        id: "rrev-surf-insurance",
        clauseNo: "제7조",
        clauseTitle: "보험 및 사고 처리",
        original: "셀러는 영업배상책임보험 또는 이에 준하는 보험에 가입하고, 사고 발생 시 응급 조치와 보험 접수에 협조한다.",
        requested: "보험명, 보상 한도, 자기부담금, 보상 제외 사유를 별첨으로 제공한다.",
        reason: "단체 해양 액티비티라 보험 범위를 사전에 확인하고 싶습니다.",
      },
    ],
  },
  {
    id: "rcv-rental-sign",
    buyer: "AsiaTrip OTA",
    contractId: "route-rental-van-2026",
    contractTitle: "2026 김해공항 단체 밴 렌탈 계약",
    status: "signing",
    createdAt: "2026.07.18",
    period: "2026.08.10 ~ 2026.08.12",
    estimatedAmount: "528,000원",
    currentVersion: "v4 최종 합의안",
    revisions: [],
  },
];

export function getReceivedRequest(id: string | undefined): ReceivedRequest | undefined {
  return receivedRequests.find((request) => request.id === id);
}
