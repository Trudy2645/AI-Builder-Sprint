import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { AuthLayout } from "../../components/layout/AuthLayout";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Plane, Building2 } from "lucide-react";
import { Separator } from "../../components/ui/separator";
import { useApp, type Role } from "../../context/AppContext";
import { friendlyApiError, getMe, loginDemo, loginWithPassword, setAccessToken } from "../../lib/api";

export function LoginPage() {
  const { t, loginWithSession } = useApp();
  const navigate = useNavigate();
  const [email, setEmail] = useState("buyer@globaltrip.jp");
  const [password, setPassword] = useState("demo-password");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const establishSession = async (result: Awaited<ReturnType<typeof loginWithPassword>>) => {
    if (!result.session) throw new Error("Login session was not returned.");
    setAccessToken(result.session.access_token);
    const profile = await getMe();
    const organization = profile.organizations[0];
    const company = organization?.name || profile.affiliation_name || profile.display_name || result.email;
    loginWithSession(profile.role, company, result.session.access_token, organization?.id ?? null);
    navigate(`/${profile.role}`);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMessage(null);
    try {
      const result = await loginWithPassword(email, password);
      await establishSession(result);
    } catch (error) {
      setErrorMessage(friendlyApiError(error));
    } finally {
      setSubmitting(false);
    }
  };

  const demoLogin = async (role: Role) => {
    setSubmitting(true);
    setErrorMessage(null);
    try {
      await establishSession(await loginDemo(role));
    } catch (error) {
      setErrorMessage(friendlyApiError(error));
    } finally {
      setSubmitting(false);
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
          <Input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </div>

        {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}
        <Button type="submit" disabled={submitting} className="mt-2 w-full" style={{ background: "var(--navy)" }}>
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
          onClick={() => void demoLogin("buyer")}
          disabled={submitting}
        >
          <Plane className="size-4 shrink-0" style={{ color: "var(--ocean)" }} />
          {t("login.demoBuyer")}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="w-full justify-start gap-2 whitespace-nowrap"
          onClick={() => void demoLogin("seller")}
          disabled={submitting}
        >
          <Building2 className="size-4 shrink-0" style={{ color: "var(--teal)" }} />
          {t("login.demoSeller")}
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
