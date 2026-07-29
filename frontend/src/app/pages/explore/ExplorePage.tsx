import { Info } from "lucide-react";
import { PageHeader } from "../../components/PageHeader";
import { ExploreView } from "../../components/explore/ExploreView";
import { useApp } from "../../context/AppContext";
import { useExploreCtx } from "../../hooks/useExploreCtx";

export function ExplorePage() {
  const { t } = useApp();
  const { base, isGuest } = useExploreCtx();

  return (
    <div>
      <PageHeader title={t("explore.title")} description={t("explore.subtitle")} />
      {isGuest && (
        <div
          className="mb-6 flex items-center gap-2 rounded-lg border px-4 py-2.5"
          style={{ background: "var(--info-soft)", borderColor: "var(--ocean)", color: "var(--ocean)", fontSize: "14px" }}
        >
          <Info className="size-4 shrink-0" />
          {t("explore.guestNote")}
        </div>
      )}
      <ExploreView base={base} />
    </div>
  );
}
