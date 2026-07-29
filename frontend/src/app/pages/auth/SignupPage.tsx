import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { AuthLayout } from "../../components/layout/AuthLayout";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { useApp, type Role } from "../../context/AppContext";

export function SignupPage() {
  const { t, setCompanyName } = useApp();
  const navigate = useNavigate();
  const [role, setRole] = useState<Role>("buyer");
  const [company, setCompany] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (company.trim()) setCompanyName(company.trim());
    navigate(`/${role}`);
  };

  return (
    <AuthLayout>
      <div className="mb-6">
        <h1 style={{ color: "var(--navy)" }}>{t("common.signup")}</h1>
        <p className="mt-1 text-muted-foreground" style={{ fontSize: "14px" }}>
          {t("brand.tagline")}
        </p>
      </div>

      <form className="flex flex-col gap-4" onSubmit={submit}>
        <div className="flex flex-col gap-2">
          <Label htmlFor="company">{t("common.companyName")}</Label>
          <Input
            id="company"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="GlobalTrip Japan"
            required
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="email">{t("common.email")}</Label>
          <Input id="email" type="email" required />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">{t("common.password")}</Label>
          <Input id="password" type="password" required />
        </div>
        <div className="flex flex-col gap-2">
          <Label>{t("common.selectRole")}</Label>
          <Select value={role} onValueChange={(v) => setRole(v as Role)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="buyer">{t("role.buyer")}</SelectItem>
              <SelectItem value="seller">{t("role.seller")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button type="submit" className="mt-2 w-full" style={{ background: "var(--navy)" }}>
          {t("common.signup")}
        </Button>
      </form>

      <p className="mt-6 text-center text-muted-foreground" style={{ fontSize: "14px" }}>
        {t("common.haveAccount")}{" "}
        <Link to="/login" className="underline" style={{ color: "var(--ocean)" }}>
          {t("common.login")}
        </Link>
      </p>
    </AuthLayout>
  );
}
