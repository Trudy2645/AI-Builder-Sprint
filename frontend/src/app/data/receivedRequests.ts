// 셀러가 바이어로부터 받은 수정 요청 (데모 데이터).
// 메인 숙박 공급계약의 취소·노쇼·정산 위험 시나리오와 연결한다.

export interface ReceivedRevision {
  id: string;
  clauseNo: string;
  clauseTitle: string;
  original: string;
  requested: string;
  reason: string;
  aiImpact: string;
  aiRecommend: string;
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
    id: "rcv-summer",
    buyer: "GlobalTrip Japan",
    contractId: "ocean-stay-2026-summer",
    contractTitle: "2026 부산 여름 객실 공급 계약",
    status: "new",
    createdAt: "2026.07.26",
    period: "2026.07.01 ~ 2026.08.31",
    estimatedAmount: "4,350,000원",
    currentVersion: "v2 바이어 수정 요청안",
    revisions: [
      {
        id: "rrev-cancel",
        clauseNo: "제4조",
        clauseTitle: "취소 및 환불",
        original:
          "예약 취소 시 발생하는 취소 수수료와 적용 시점은 최종 객실 수량 확정 후 상호 협의한다.",
        requested:
          "체크인 5일 전까지 무료 취소하며, 이후 취소 시 객실 1박 요금의 30%를 부과한다.",
        reason:
          "해외 단체 일정은 변경 가능성이 높으므로 무료 취소 기한과 수수료 기준을 계약서에 명확히 남기고 싶습니다.",
        aiImpact:
          "기한과 수수료가 명확해져 분쟁 위험은 줄지만, 체크인 5일 전까지 무상 취소를 허용하면 셀러의 성수기 객실 재판매 기간이 짧아질 수 있습니다.",
        aiRecommend:
          "체크인 7일 전까지 무료 취소하며, 이후 취소 시 객실 1박 요금의 50%를 부과한다.",
      },
      {
        id: "rrev-noshow",
        clauseNo: "제5조",
        clauseTitle: "노쇼",
        original:
          "예약자가 사전 통보 없이 방문하지 않은 경우의 요금은 별도로 협의한다.",
        requested:
          "노쇼 발생 시 해당 객실의 1박 요금 100%를 부과한다.",
        reason:
          "노쇼가 발생했을 때 어느 금액을 정산하는지 양측이 동일하게 이해할 수 있도록 기준을 추가해 주세요.",
        aiImpact:
          "객실 1박 요금을 기준으로 정하면 셀러의 손실 보전 범위와 바이어의 최대 부담이 모두 명확해집니다.",
        aiRecommend:
          "노쇼 발생 시 해당 객실의 1박 공급 요금 100%를 부과하며, 천재지변 등 불가항력 사유는 상호 협의한다.",
      },
      {
        id: "rrev-settle",
        clauseNo: "제6조",
        clauseTitle: "정산",
        original:
          "객실 이용 금액은 이용 실적을 확인한 뒤 추후 정산한다.",
        requested:
          "매월 말 이용 내역을 마감하고, 바이어는 다음 달 15일까지 셀러에게 공급 대금을 지급한다.",
        reason:
          "대금 지급 시점과 지급 주체가 불명확하면 정산 지연이 생길 수 있어 날짜를 확정하고 싶습니다.",
        aiImpact:
          "마감일, 지급일, 지급 주체가 명확해져 셀러의 현금 흐름 예측과 미수금 관리가 쉬워집니다.",
        aiRecommend:
          "매월 말 이용 내역을 마감하고, 바이어는 다음 달 15일까지 확인된 공급 대금을 셀러에게 지급한다.",
      },
    ],
  },
  {
    id: "rcv-weekday",
    buyer: "Sakura Tour",
    contractId: "lst-weekday-room",
    contractTitle: "2026 해운대 평일 비즈니스 객실 공급 계약",
    status: "negotiating",
    createdAt: "2026.07.24",
    period: "2026.09.01 ~ 2026.09.30",
    estimatedAmount: "1,960,000원",
    currentVersion: "v3 셀러 대안 협상 중",
    revisions: [
      {
        id: "rrev-weekday-settle",
        clauseNo: "제6조",
        clauseTitle: "정산",
        original: "이용 완료 후 30일 이내 정산한다.",
        requested: "매월 말 이용 내역을 마감하고 다음 달 10일까지 지급한다.",
        reason: "월 단위 정산 일정을 명확히 하고 싶습니다.",
        aiImpact: "지급일이 빨라져 셀러 현금 흐름에는 긍정적이지만 확인 기간이 짧아질 수 있습니다.",
        aiRecommend: "매월 말 마감 후 다음 달 15일까지 지급한다.",
      },
    ],
  },
  {
    id: "rcv-winter-sign",
    buyer: "AsiaTrip OTA",
    contractId: "lst-winter-paused",
    contractTitle: "2025 겨울 시즌 객실 공급 계약",
    status: "signing",
    createdAt: "2026.07.18",
    period: "2026.12.01 ~ 2026.12.31",
    estimatedAmount: "3,168,000원",
    currentVersion: "v4 최종 합의안",
    revisions: [],
  },
  {
    id: "rcv-signed-month",
    buyer: "Busan Study Group",
    contractId: "lst-summer-room",
    contractTitle: "2026 부산 여름 객실 공급 계약",
    status: "signed",
    createdAt: "2026.07.12",
    period: "2026.07.20 ~ 2026.07.24",
    estimatedAmount: "4,350,000원",
    currentVersion: "v4 양측 서명 완료",
    revisions: [],
  },
];

export function getReceivedRequest(id: string | undefined): ReceivedRequest | undefined {
  return receivedRequests.find((request) => request.id === id);
}
