import { Building2, Plane, ChevronRight } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { AuthLayout } from "../../components/layout/AuthLayout";
import { Button } from "../../components/ui/button";
import { useApp, type Role } from "../../context/AppContext";

function RoleCard({
  role,
  icon,
  onSelect,
}: {
  role: Role;
  icon: React.ReactNode;
  onSelect: () => void;
}) {
  const { t } = useApp();
  const title = t(role === "buyer" ? "role.buyer" : "role.seller");
  const desc = t(role === "buyer" ? "auth.buyerCard.desc" : "auth.sellerCard.desc");

  return (
    <button
      type="button"
      onClick={onSelect}
      className="group flex flex-col gap-3 rounded-xl border border-border bg-card p-5 text-left transition-all hover:-translate-y-0.5 hover:border-transparent hover:shadow-md"
      style={{ outlineColor: "var(--ocean)" }}
    >
      <div className="flex items-center gap-3">
        <div
          className="flex size-11 shrink-0 items-center justify-center rounded-lg"
          style={{ background: "var(--info-soft)", color: "var(--ocean)" }}
        >
          {icon}
        </div>
        <div className="min-w-0">
          <div className="whitespace-nowrap" style={{ fontWeight: 700, color: "var(--navy)" }}>
            {title}
          </div>
          <div className="text-muted-foreground" style={{ fontSize: "12px" }}>
            {t(role === "buyer" ? "role.buyer.desc" : "role.seller.desc")}
          </div>
        </div>
      </div>
      <p className="text-muted-foreground" style={{ fontSize: "13px", lineHeight: 1.5 }}>
        {desc}
      </p>
      <span
        className="mt-1 inline-flex items-center gap-1 whitespace-nowrap"
        style={{ color: "var(--ocean)", fontSize: "13px", fontWeight: 600 }}
      >
        {t("auth.selectThisRole")}
        <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" />
      </span>
    </button>
  );
}

export function RoleSelectPage() {
  const { t } = useApp();
  const navigate = useNavigate();

  return (
    <AuthLayout>
      <div className="mb-6">
        <h1 style={{ color: "var(--navy)" }}>{t("auth.chooseRole")}</h1>
        <p className="mt-1 text-muted-foreground" style={{ fontSize: "14px" }}>
          {t("auth.chooseRole.desc")}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <RoleCard role="buyer" icon={<Plane className="size-5" />} onSelect={() => navigate("/signup/buyer")} />
        <RoleCard role="seller" icon={<Building2 className="size-5" />} onSelect={() => navigate("/signup/seller")} />
      </div>

      <p className="mt-6 text-center text-muted-foreground" style={{ fontSize: "14px" }}>
        {t("common.haveAccount")}{" "}
        <Link to="/login" className="underline" style={{ color: "var(--ocean)" }}>
          {t("common.login")}
        </Link>
      </p>
    </AuthLayout>
  );
}
