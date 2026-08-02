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

export const NEGOTIATION_CONTRACT_ID = "coastline-hotel-room-2026";

export const versionMetas: Record<ContractVersion, VersionMeta> = {
  v1: { version: "v1", author: "seller", authorName: "해운대 오션스테이", date: "2026.07.02" },
  v2: { version: "v2", author: "buyer", authorName: "GlobalTrip Japan", date: "2026.07.10" },
  v3: { version: "v3", author: "seller", authorName: "해운대 오션스테이", date: "2026.07.16" },
  v4: { version: "v4", author: "buyer", authorName: "GlobalTrip Japan", date: "2026.07.24" },
};

export const VERSION_ORDER: ContractVersion[] = ["v1", "v2", "v3", "v4"];

const V1_CONFIRM = "바이어의 예약 요청은 객실 공급에 대한 청약이며, 셀러가 객실 타입·투숙일·인원·요금을 확인하고 확정 통지를 보낸 때 예약이 성립한다.";
const V1_EXTRA_FEE = "객실 공급 단가는 객실당 146,000원으로 한다. 세금, 봉사료, 리조트피, 객실 파손 보증금, 미니바 등 부대비용은 별도 고지된 기준에 따라 정산한다.";
const V1_OVERBOOKING = "셀러 사정으로 확정 객실 제공이 어려운 경우 셀러는 동급 이상 대체 객실을 제공하거나 바이어와 협의하여 예약을 취소하고 이미 지급된 금액을 환급한다.";

const V2_CONFIRM = "셀러의 확정 통지가 바이어에게 도달한 때 예약이 성립하며, 확정 전에는 객실 확보가 보장되지 않는다는 문구를 추가한다.";
const V2_EXTRA_FEE = "포함 비용과 불포함 비용을 별첨으로 분리하고, 현장 추가 비용은 셀러가 증빙과 함께 청구한다.";
const V2_OVERBOOKING = "대체 객실은 동일 지역·동급 이상으로 제공하고, 낮은 등급 대체 시 차액과 이동 비용은 셀러가 부담한다.";

const FINAL_CONFIRM = "셀러는 예약 요청 접수 후 24시간 이내 확정, 거절 또는 조건 변경 여부를 바이어에게 통지하며, 확정 통지가 도달한 때 예약이 성립한다.";
const FINAL_OVERBOOKING = "대체 객실은 동일 지역·동급 이상으로 하되, 불가피한 경우 양측 합의로 차액 환급 또는 일정 변경을 선택한다.";

export const versionDiffs: Record<Exclude<ContractVersion, "v1">, VersionDiff> = {
  v2: {
    from: "v1",
    to: "v2",
    aiSummary: [
      "바이어가 예약 요청과 예약 확정 시점을 더 명확히 구분하도록 요청했습니다.",
      "부대비용 청구 시 증빙과 포함·불포함 비용 표기를 추가했습니다.",
      "오버부킹 시 대체 객실과 이동 비용 부담 기준을 구체화했습니다.",
    ],
    changes: [
      {
        clauseNo: "제2조",
        title: "예약 요청 및 확정",
        prevText: V1_CONFIRM,
        newText: V2_CONFIRM,
        labels: ["periodChange", "riskDown"],
        note: "예약 성립 시점과 확정 전 유의사항 추가",
      },
      {
        clauseNo: "제4조",
        title: "요금 및 부대비용",
        prevText: V1_EXTRA_FEE,
        newText: V2_EXTRA_FEE,
        labels: ["added", "priceChange", "riskDown"],
        note: "포함 비용과 현장 추가 비용 증빙 기준 추가",
      },
      {
        clauseNo: "제6조",
        title: "오버부킹 및 조건 변경",
        prevText: V1_OVERBOOKING,
        newText: V2_OVERBOOKING,
        labels: ["added", "priceChange", "riskDown"],
        note: "대체 객실과 차액·이동 비용 부담 기준 추가",
      },
    ],
  },
  v3: {
    from: "v2",
    to: "v3",
    aiSummary: [
      "셀러가 예약 확정 통지 기한을 24시간 이내로 제한하는 대안을 제시했습니다.",
      "부대비용 증빙 제공 요청은 수락했습니다.",
      "오버부킹 대체 조건은 동일 지역·동급 이상 원칙을 유지하되, 불가피한 경우 합의 절차를 추가했습니다.",
    ],
    changes: [
      {
        clauseNo: "제2조",
        title: "예약 요청 및 확정",
        prevText: V2_CONFIRM,
        newText: FINAL_CONFIRM,
        labels: ["periodChange", "riskDown"],
        note: "셀러 대안: 24시간 이내 확정·거절·조건 변경 통지",
      },
      {
        clauseNo: "제6조",
        title: "오버부킹 및 조건 변경",
        prevText: V2_OVERBOOKING,
        newText: FINAL_OVERBOOKING,
        labels: ["priceChange"],
        note: "셀러 대안: 불가피한 경우 차액 환급 또는 일정 변경 선택",
      },
    ],
  },
  v4: {
    from: "v3",
    to: "v4",
    aiSummary: [
      "양측이 셀러 대응안에 합의해 최종 계약안이 완성되었습니다.",
      "예약확정·부대비용·오버부킹 기준이 모두 명확해졌습니다.",
      "최종안은 전자서명을 진행할 수 있는 상태입니다.",
    ],
    changes: [
      {
        clauseNo: "제2·4·6조",
        title: "최종 합의 확인",
        prevText: `${FINAL_CONFIRM} ${V2_EXTRA_FEE} ${FINAL_OVERBOOKING}`,
        newText: `${FINAL_CONFIRM} ${V2_EXTRA_FEE} ${FINAL_OVERBOOKING}`,
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
  unitPrice: 146000,
  priceUnit: "객실당",
  travelers: 30,
  standardOccupancy: 2,
  estimatedRooms: 15,
  nights: 2,
  estimatedTotal: 4380000,
};

export function getVersionDiff(to: ContractVersion): VersionDiff | undefined {
  if (to === "v1") return undefined;
  return versionDiffs[to];
}
