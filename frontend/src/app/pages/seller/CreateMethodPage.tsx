import { PenSquare, FileUp, ArrowLeft, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { useApp } from "../../context/AppContext";

export function CreateMethodPage() {
  const { t } = useApp();
  const navigate = useNavigate();

  const options = [
    {
      key: "write",
      icon: PenSquare,
      titleKey: "create.write",
      descKey: "create.write.desc",
      to: "/seller/listings/new/write",
    },
    {
      key: "upload",
      icon: FileUp,
      titleKey: "create.upload",
      descKey: "create.upload.desc",
      to: "/seller/listings/new/upload",
    },
  ];

  return (
    <div>
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate("/seller/listings")}>
        <ArrowLeft className="size-4" />
        {t("listings.title")}
      </Button>

      <PageHeader title={t("create.title")} description={t("create.subtitle")} />

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {options.map((o) => {
          const Icon = o.icon;
          return (
            <button
              key={o.key}
              type="button"
              onClick={() => navigate(o.to)}
              className="flex flex-col items-start gap-4 rounded-xl border border-border bg-card p-6 text-left transition-all hover:-translate-y-0.5 hover:shadow-md"
              style={{ borderColor: "var(--border)" }}
            >
              <div className="flex size-12 items-center justify-center rounded-xl" style={{ background: "var(--info-soft)", color: "var(--ocean)" }}>
                <Icon className="size-6" />
              </div>
              <div>
                <h3 style={{ color: "var(--navy)" }}>{t(o.titleKey)}</h3>
                <p className="mt-1.5 text-muted-foreground" style={{ fontSize: "14px", lineHeight: 1.6 }}>{t(o.descKey)}</p>
              </div>
              <span className="mt-auto inline-flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--ocean)", fontWeight: 600, fontSize: "14px" }}>
                {t("create.start")}
                <ArrowRight className="size-4" />
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
