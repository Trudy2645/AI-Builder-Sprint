import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { AuthLayout } from "../../components/layout/AuthLayout";
import { SignupStepper } from "../../components/auth/SignupStepper";
import {
  TextField,
  SelectField,
  FileField,
  EmailVerifyField,
} from "../../components/auth/AuthFields";
import { useEmailVerify } from "../../components/auth/useEmailVerify";
import { Button } from "../../components/ui/button";
import { useApp } from "../../context/AppContext";

const STEPS = ["signup.step.role", "signup.step.account", "signup.step.business", "signup.step.done"];

export function SellerSignupPage() {
  const { t, setCompanyName } = useApp();
  const navigate = useNavigate();
  const email = useEmailVerify();

  const [step, setStep] = useState<1 | 2>(1); // 1 = account, 2 = business

  // account
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [contactName, setContactName] = useState("");
  const [phone, setPhone] = useState("");
  // business
  const [company, setCompany] = useState("");
  const [repName, setRepName] = useState("");
  const [bizNumber, setBizNumber] = useState("");
  const [bizFile, setBizFile] = useState("");
  const [address, setAddress] = useState("");
  const [supplyField, setSupplyField] = useState("");
  const [jobTitle, setJobTitle] = useState("");

  const [errors, setErrors] = useState<Record<string, string>>({});

  const supplyOptions = [
    { value: "hotel", label: t("opt.sf.hotel") },
    { value: "leisure", label: t("opt.sf.leisure") },
    { value: "sports", label: t("opt.sf.sports") },
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

  const validateBusiness = () => {
    const e: Record<string, string> = {};
    if (!company.trim()) e.company = "err.required";
    if (!repName.trim()) e.repName = "err.required";
    if (!/^\d{10}$/.test(bizNumber.replace(/\D/g, ""))) e.bizNumber = "err.bizNumber";
    if (!bizFile) e.bizFile = "err.required";
    if (!address.trim()) e.address = "err.required";
    if (!supplyField) e.supplyField = "err.required";
    if (!jobTitle.trim()) e.jobTitle = "err.required";
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
    if (validateBusiness()) {
      setCompanyName(company.trim());
      navigate("/signup/complete?role=seller");
    }
  };

  return (
    <AuthLayout>
      <div className="mb-4">
        <h1 style={{ color: "var(--navy)" }}>{t("signup.sellerTitle")}</h1>
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
            placeholder="+82 51-000-0000"
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
            {t("signup.businessSection")}
          </p>
          <TextField
            id="company"
            label={t("field.companyName")}
            value={company}
            onChange={setCompany}
            required
            error={errors.company}
            placeholder="해운대 오션스테이"
          />
          <TextField
            id="repName"
            label={t("field.repName")}
            value={repName}
            onChange={setRepName}
            required
            error={errors.repName}
          />
          <TextField
            id="bizNumber"
            label={t("field.bizNumber")}
            value={bizNumber}
            onChange={setBizNumber}
            required
            error={errors.bizNumber}
            placeholder="000-00-00000"
          />
          <FileField
            id="bizFile"
            label={t("field.bizFile")}
            fileName={bizFile}
            onChange={setBizFile}
            required
            error={errors.bizFile}
          />
          <TextField
            id="address"
            label={t("field.address")}
            value={address}
            onChange={setAddress}
            required
            error={errors.address}
            placeholder="부산광역시 해운대구 ..."
          />
          <SelectField
            id="supplyField"
            label={t("field.supplyField")}
            value={supplyField}
            onChange={setSupplyField}
            options={supplyOptions}
            required
            error={errors.supplyField}
          />
          <TextField
            id="jobTitle"
            label={t("field.jobTitle")}
            value={jobTitle}
            onChange={setJobTitle}
            required
            error={errors.jobTitle}
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
