import { FileText, FilePenLine, FileClock, FileCheck2 } from "lucide-react";
import { useApp } from "../../context/AppContext";

export type ContractVersion = "v1" | "v2" | "v3" | "v4";

const config: Record<
  ContractVersion,
  { icon: typeof FileText; color: string; bg: string }
> = {
  v1: { icon: FileText, color: "var(--navy)", bg: "var(--info-soft)" },
  v2: { icon: FilePenLine, color: "var(--ocean)", bg: "var(--info-soft)" },
  v3: { icon: FileClock, color: "var(--warning)", bg: "var(--warning-soft)" },
  v4: { icon: FileCheck2, color: "var(--success)", bg: "var(--success-soft)" },
};

/**
 * Document VERSION label (v1 셀러 원본 → v4 최종 합의안).
 * Distinct from the process stepper (ContractStepper).
 */
export function VersionBadge({
  version,
  showLabel = true,
}: {
  version: ContractVersion;
  showLabel?: boolean;
}) {
  const { t } = useApp();
  const { icon: Icon, color, bg } = config[version];

  return (
    <span
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1"
      style={{ background: bg, color, fontSize: "12px", fontWeight: 600 }}
    >
      <Icon className="size-3.5" />
      <span>{version.toUpperCase()}</span>
      {showLabel && (
        <span style={{ fontWeight: 400 }}>· {t(`version.${version}`)}</span>
      )}
    </span>
  );
}
