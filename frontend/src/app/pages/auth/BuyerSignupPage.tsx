import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { AuthLayout } from "../../components/layout/AuthLayout";
import { SignupStepper } from "../../components/auth/SignupStepper";
import {
  TextField,
  SelectField,
  EmailVerifyField,
} from "../../components/auth/AuthFields";
import { useEmailVerify } from "../../components/auth/useEmailVerify";
import { Button } from "../../components/ui/button";
import { useApp } from "../../context/AppContext";
import type { Lang } from "../../i18n/translations";

const STEPS = ["signup.step.role", "signup.step.account", "signup.step.company", "signup.step.done"];

export function BuyerSignupPage() {
  const { t, setCompanyName, setLang } = useApp();
  const navigate = useNavigate();
  const email = useEmailVerify();

  const [step, setStep] = useState<1 | 2>(1); // 1 = account, 2 = company

  // account
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [contactName, setContactName] = useState("");
  const [phone, setPhone] = useState("");
  // company
  const [company, setCompany] = useState("");
  const [country, setCountry] = useState("");
  const [language, setLanguage] = useState("");
  const [businessType, setBusinessType] = useState("");
  const [currency, setCurrency] = useState("");

  const [errors, setErrors] = useState<Record<string, string>>({});

  const countryOptions = [
    { value: "jp", label: t("field.country") === "국가" ? "일본" : "Japan" },
    { value: "kr", label: "Korea" },
    { value: "cn", label: "China" },
    { value: "us", label: "USA" },
    { value: "other", label: t("common.optional") },
  ];
  const langOptions = [
    { value: "ko", label: "한국어" },
    { value: "en", label: "English" },
    { value: "ja", label: "日本語" },
    { value: "zh", label: "中文" },
  ];
  const btOptions = [
    { value: "agency", label: t("opt.bt.agency") },
    { value: "inbound", label: t("opt.bt.inbound") },
    { value: "ota", label: t("opt.bt.ota") },
    { value: "school", label: t("opt.bt.school") },
    { value: "company_group", label: t("opt.bt.companyGroup") },
    { value: "other_group", label: t("opt.bt.otherGroup") },
  ];
  const currencyOptions = [
    { value: "KRW", label: "KRW ₩" },
    { value: "JPY", label: "JPY ¥" },
    { value: "USD", label: "USD $" },
    { value: "CNY", label: "CNY ¥" },
  ];

  const validateAccount = () => {
    const e: Record<string, string> = {};
    const emailOk = email.validate();
    if (password.length < 8) e.password = "err.passwordLen";
    if (passwordConfirm !== password || !passwordConfirm) e.passwordConfirm = "err.passwordMismatch";
    if (!contactName.trim()) e.contactName = "err.required";
    if (!phone.trim()) e.phone = "err.required";
    setErrors(e);
    return emailOk && Object.keys(e).length === 0;
  };

  const validateCompany = () => {
    const e: Record<string, string> = {};
    if (!company.trim()) e.company = "err.required";
    if (!country) e.country = "err.required";
    if (!language) e.language = "err.required";
    if (!businessType) e.businessType = "err.required";
    if (!currency) e.currency = "err.required";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const onNext = () => {
    if (validateAccount()) {
      setErrors({});
      setStep(2);
    }
  };

  const onSubmit = (ev: React.FormEvent) => {
    ev.preventDefault();
    if (validateCompany()) {
      setCompanyName(company.trim());
      setLang(language as Lang);
      navigate("/signup/complete?role=buyer");
    }
  };

  return (
    <AuthLayout>
      <div className="mb-4">
        <h1 style={{ color: "var(--navy)" }}>{t("signup.buyerTitle")}</h1>
      </div>

      <SignupStepper steps={STEPS} current={step} />

      {step === 1 ? (
        <div className="flex flex-col gap-4">
          <p className="text-muted-foreground" style={{ fontSize: "14px" }}>
            {t("signup.accountSection")}
          </p>
          <EmailVerifyField
            email={email.email}
            onEmailChange={email.setEmail}
            emailError={email.emailError}
            verified={email.verified}
            onVerify={email.verify}
            code={email.code}
            onCodeChange={email.setCode}
            codeSent={email.codeSent}
            onSendCode={email.sendCode}
            codeError={email.codeError}
          />
          <TextField
            id="password"
            label={t("field.password")}
            type="password"
            value={password}
            onChange={setPassword}
            required
            error={errors.password}
            autoComplete="new-password"
          />
          <TextField
            id="passwordConfirm"
            label={t("field.passwordConfirm")}
            type="password"
            value={passwordConfirm}
            onChange={setPasswordConfirm}
            required
            error={errors.passwordConfirm}
            autoComplete="new-password"
          />
          <TextField
            id="contactName"
            label={t("field.contactName")}
            value={contactName}
            onChange={setContactName}
            required
            error={errors.contactName}
          />
          <TextField
            id="phone"
            label={t("field.phone")}
            value={phone}
            onChange={setPhone}
            required
            error={errors.phone}
            placeholder="+81 90-0000-0000"
          />

          <div className="mt-2 flex gap-2">
            <Button type="button" variant="outline" className="flex-1" onClick={() => navigate("/signup")}>
              {t("common.back")}
            </Button>
            <Button type="button" className="flex-1" style={{ background: "var(--navy)" }} onClick={onNext}>
              {t("common.next")}
            </Button>
          </div>
        </div>
      ) : (
        <form className="flex flex-col gap-4" onSubmit={onSubmit}>
          <p className="text-muted-foreground" style={{ fontSize: "14px" }}>
            {t("signup.companySection")}
          </p>
          <TextField
            id="company"
            label={t("field.organizationName")}
            value={company}
            onChange={setCompany}
            required
            error={errors.company}
            placeholder={t("field.organizationNamePh")}
          />
          <SelectField
            id="country"
            label={t("field.country")}
            value={country}
            onChange={setCountry}
            options={countryOptions}
            required
            error={errors.country}
          />
          <SelectField
            id="language"
            label={t("field.defaultLanguage")}
            value={language}
            onChange={(value) => {
              setLanguage(value);
              setLang(value as Lang);
            }}
            options={langOptions}
            required
            error={errors.language}
          />
          <SelectField
            id="businessType"
            label={t("field.businessType")}
            value={businessType}
            onChange={setBusinessType}
            options={btOptions}
            required
            error={errors.businessType}
          />
          <SelectField
            id="currency"
            label={t("field.currency")}
            value={currency}
            onChange={setCurrency}
            options={currencyOptions}
            required
            error={errors.currency}
          />

          <div className="mt-2 flex gap-2">
            <Button type="button" variant="outline" className="flex-1" onClick={() => setStep(1)}>
              {t("common.back")}
            </Button>
            <Button type="submit" className="flex-1" style={{ background: "var(--navy)" }}>
              {t("signup.submit")}
            </Button>
          </div>
        </form>
      )}

      <p className="mt-6 text-center text-muted-foreground" style={{ fontSize: "14px" }}>
        {t("common.haveAccount")}{" "}
        <Link to="/login" className="underline" style={{ color: "var(--ocean)" }}>
          {t("common.login")}
        </Link>
      </p>
    </AuthLayout>
  );
}
