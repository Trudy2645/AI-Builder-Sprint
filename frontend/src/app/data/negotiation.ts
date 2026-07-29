import type { ContractVersion } from "../components/contract/VersionBadge";

export type ChangeLabel =
  | "deleted"
  | "added"
  | "priceChange"
  | "periodChange"
  | "riskUp"
  | "riskDown";

export interface VersionMeta {
  version: ContractVersion;
  author: "seller" | "buyer";
  authorName: string;
  date: string;
}

export interface ClauseChange {
  clauseNo: string;
  title: string;
  prevText?: string;
  newText?: string;
  labels: ChangeLabel[];
  note: string;
}

export interface VersionDiff {
  from: ContractVersion;
  to: ContractVersion;
  aiSummary: string[];
  changes: ClauseChange[];
}

export const NEGOTIATION_CONTRACT_ID = "ocean-stay-2026-summer";

export const versionMetas: Record<ContractVersion, VersionMeta> = {
  v1: { version: "v1", author: "seller", authorName: "해운대 오션스테이", date: "2026.07.02" },
  v2: { version: "v2", author: "buyer", authorName: "GlobalTrip Japan", date: "2026.07.10" },
  v3: { version: "v3", author: "seller", authorName: "해운대 오션스테이", date: "2026.07.16" },
  v4: { version: "v4", author: "buyer", authorName: "GlobalTrip Japan", date: "2026.07.24" },
};

export const VERSION_ORDER: ContractVersion[] = ["v1", "v2", "v3", "v4"];

const V1_CANCEL = "바이어는 필요에 따라 예약을 무료로 취소할 수 있다.";
const V1_NOSHOW = "노쇼 발생 시 처리 기준은 별도로 정하지 않는다.";
const V1_SETTLEMENT = "객실 이용 금액은 추후 정산한다.";

const V2_CANCEL = "체크인 5일 전까지 무료 취소하고 이후에는 객실 1박 요금의 30%를 부과한다.";
const V2_NOSHOW = "노쇼 발생 시 해당 객실의 1박 요금 100%를 부과한다.";
const V2_SETTLEMENT = "매월 말 이용 내역을 마감하고 익월 15일까지 바이어가 셀러에게 지급한다.";

const FINAL_CANCEL = "체크인 7일 전까지 무료 취소하고 이후에는 객실 1박 요금의 50%를 부과한다.";

export const versionDiffs: Record<Exclude<ContractVersion, "v1">, VersionDiff> = {
  v2: {
    from: "v1",
    to: "v2",
    aiSummary: [
      "바이어가 무료 취소 기한과 취소 수수료를 구체적으로 제안했습니다.",
      "누락되었던 노쇼 비용 기준이 새로 추가되었습니다.",
      "정산 지급일과 지급 주체가 명확해져 미수금 분쟁 위험이 감소했습니다.",
    ],
    changes: [
      {
        clauseNo: "제4조",
        title: "취소 및 환불",
        prevText: V1_CANCEL,
        newText: V2_CANCEL,
        labels: ["periodChange", "priceChange", "riskDown"],
        note: "무료 취소 기한과 이후 수수료 기준 추가",
      },
      {
        clauseNo: "제5조",
        title: "노쇼",
        prevText: V1_NOSHOW,
        newText: V2_NOSHOW,
        labels: ["added", "priceChange", "riskDown"],
        note: "노쇼 시 객실 1박 요금 100% 기준 추가",
      },
      {
        clauseNo: "제6조",
        title: "정산 및 지급",
        prevText: V1_SETTLEMENT,
        newText: V2_SETTLEMENT,
        labels: ["periodChange", "riskDown"],
        note: "익월 15일 지급과 지급 주체 명시",
      },
    ],
  },
  v3: {
    from: "v2",
    to: "v3",
    aiSummary: [
      "셀러가 재판매 기간 확보를 위해 무료 취소 기한을 7일 전으로 조정했습니다.",
      "체크인 7일 이내 취소 수수료를 50%로 대안 제시했습니다.",
      "노쇼와 정산 조건은 바이어 요청안을 수락했습니다.",
    ],
    changes: [
      {
        clauseNo: "제4조",
        title: "취소 및 환불",
        prevText: V2_CANCEL,
        newText: FINAL_CANCEL,
        labels: ["periodChange", "priceChange"],
        note: "셀러 대안: 7일 전 무료 취소, 이후 50%",
      },
    ],
  },
  v4: {
    from: "v3",
    to: "v4",
    aiSummary: [
      "양측이 셀러 대응안에 합의해 최종 계약안이 완성되었습니다.",
      "취소·노쇼·정산 기준이 모두 명확해졌습니다.",
      "최종안은 전자서명을 진행할 수 있는 상태입니다.",
    ],
    changes: [
      {
        clauseNo: "제4~6조",
        title: "최종 합의 확인",
        prevText: `${FINAL_CANCEL} ${V2_NOSHOW} ${V2_SETTLEMENT}`,
        newText: `${FINAL_CANCEL} ${V2_NOSHOW} ${V2_SETTLEMENT}`,
        labels: ["riskDown"],
        note: "셀러 대응안을 최종 합의안으로 확정",
      },
    ],
  },
};

export const finalContractInfo = {
  buyer: "GlobalTrip Japan",
  seller: "해운대 오션스테이",
  period: "2026.07.01 ~ 2026.08.31",
  finalVersion: "v4" as ContractVersion,
  unitPrice: 145000,
  priceUnit: "객실당",
  travelers: 30,
  standardOccupancy: 2,
  estimatedRooms: 15,
  nights: 2,
  estimatedTotal: 4350000,
};

export function getVersionDiff(to: ContractVersion): VersionDiff | undefined {
  if (to === "v1") return undefined;
  return versionDiffs[to];
}
