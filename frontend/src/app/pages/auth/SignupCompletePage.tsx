import { CheckCircle2 } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { AuthLayout } from "../../components/layout/AuthLayout";
import { SignupStepper } from "../../components/auth/SignupStepper";
import { Button } from "../../components/ui/button";
import { useApp, type Role } from "../../context/AppContext";

export function SignupCompletePage() {
  const { t, login, companyName } = useApp();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const role: Role = params.get("role") === "seller" ? "seller" : "buyer";

  const steps =
    role === "buyer"
      ? ["signup.step.role", "signup.step.account", "signup.step.company", "signup.step.done"]
      : ["signup.step.role", "signup.step.account", "signup.step.business", "signup.step.done"];

  return (
    <AuthLayout>
      <SignupStepper steps={steps} current={3} />

      <div className="flex flex-col items-center gap-4 rounded-xl border border-border bg-card p-8 text-center">
        <div
          className="flex size-14 items-center justify-center rounded-full"
          style={{ background: "var(--success-soft)", color: "var(--success)" }}
        >
          <CheckCircle2 className="size-8" />
        </div>
        <h1 style={{ color: "var(--navy)" }}>{t("complete.title")}</h1>
        <p className="text-muted-foreground" style={{ fontSize: "14px", lineHeight: 1.5 }}>
          {t(role === "buyer" ? "complete.buyerDesc" : "complete.sellerDesc")}
        </p>
        <Button
          className="mt-2 w-full"
          style={{ background: "var(--navy)" }}
          onClick={() => {
            login(
              role,
              companyName || (role === "buyer" ? "GlobalTrip Japan" : "해운대 오션스테이"),
            );
            navigate(`/${role}`);
          }}
        >
          {t("complete.goDashboard")}
        </Button>
      </div>
    </AuthLayout>
  );
}
