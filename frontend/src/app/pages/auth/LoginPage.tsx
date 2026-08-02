import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { AuthLayout } from "../../components/layout/AuthLayout";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Plane, Building2 } from "lucide-react";
import { Separator } from "../../components/ui/separator";
import { useApp, type Role } from "../../context/AppContext";
import { friendlyApiError, loginWithDemoRole } from "../../lib/api";
import { toast } from "sonner";

export function LoginPage() {
  const { t, login } = useApp();
  const navigate = useNavigate();
  const [email, setEmail] = useState("buyer@globaltrip.jp");

  const inferDemoRole = (value: string): Role => {
    const normalized = value.toLocaleLowerCase();
    return normalized.includes("seller") ||
      normalized.includes("ocean") ||
      normalized.includes("haeundae")
      ? "seller"
      : "buyer";
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const role = inferDemoRole(email);
    login(role, email);
    navigate(`/${role}`);
  };

  const demoLogin = async (r: Role, company: string) => {
    try {
      await loginWithDemoRole(r);
      login(r, company, true);
      navigate(`/${r}`);
    } catch (error) {
      toast.error(friendlyApiError(error));
    }
  };

  return (
    <AuthLayout>
      <div className="mb-6">
        <h1 style={{ color: "var(--navy)" }}>{t("common.login")}</h1>
        <p className="mt-1 text-muted-foreground" style={{ fontSize: "14px" }}>
          {t("brand.tagline")}
        </p>
      </div>

      <form className="flex flex-col gap-4" onSubmit={submit}>
        <div className="flex flex-col gap-2">
          <Label htmlFor="email">{t("common.email")}</Label>
          <Input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">{t("common.password")}</Label>
          <Input id="password" type="password" defaultValue="demo1234" required />
        </div>

        <Button type="submit" className="mt-2 w-full" style={{ background: "var(--navy)" }}>
          {t("common.login")}
        </Button>
      </form>

      <div className="my-6 flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px" }}>
          {t("login.demoDivider")}
        </span>
        <Separator className="flex-1" />
      </div>

      <div className="flex flex-col gap-2">
        <Button
          type="button"
          variant="outline"
          className="w-full justify-start gap-2 whitespace-nowrap"
          onClick={() => demoLogin("buyer", "GlobalTrip Japan")}
        >
          <Plane className="size-4 shrink-0" style={{ color: "var(--ocean)" }} />
          바이어 · rlawldbs1237@gmail.com
        </Button>
        <Button
          type="button"
          variant="outline"
          className="w-full justify-start gap-2 whitespace-nowrap"
          onClick={() => demoLogin("seller", "해운대 오션스테이")}
        >
          <Building2 className="size-4 shrink-0" style={{ color: "var(--teal)" }} />
          셀러 · kimjiyoun2645@naver.com
        </Button>
      </div>

      <p className="mt-6 text-center text-muted-foreground" style={{ fontSize: "14px" }}>
        {t("common.noAccount")}{" "}
        <Link to="/signup" className="underline" style={{ color: "var(--ocean)" }}>
          {t("common.signup")}
        </Link>
      </p>
    </AuthLayout>
  );
}
