import { AlertCircle, CheckCircle2, Upload } from "lucide-react";
import type { ReactNode } from "react";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Button } from "../ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { useApp } from "../../context/AppContext";

export function FieldError({ message }: { message?: string }) {
  const { t } = useApp();
  if (!message) return null;
  return (
    <p
      className="mt-1 flex items-center gap-1"
      style={{ color: "var(--coral)", fontSize: "12px" }}
      role="alert"
    >
      <AlertCircle className="size-3.5 shrink-0" />
      <span>{t(message)}</span>
    </p>
  );
}

interface FieldShellProps {
  id: string;
  label: string;
  required?: boolean;
  error?: string;
  children: ReactNode;
}

function FieldShell({ id, label, required, error, children }: FieldShellProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="whitespace-nowrap">
        {label}
        {required && <span style={{ color: "var(--coral)" }}> *</span>}
      </Label>
      {children}
      <FieldError message={error} />
    </div>
  );
}

interface TextFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
  error?: string;
  autoComplete?: string;
}

export function TextField({
  id,
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  required,
  error,
  autoComplete,
}: TextFieldProps) {
  return (
    <FieldShell id={id} label={label} required={required} error={error}>
      <Input
        id={id}
        type={type}
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        aria-invalid={!!error}
        onChange={(e) => onChange(e.target.value)}
      />
    </FieldShell>
  );
}

interface SelectFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
  required?: boolean;
  error?: string;
}

export function SelectField({
  id,
  label,
  value,
  onChange,
  options,
  placeholder,
  required,
  error,
}: SelectFieldProps) {
  return (
    <FieldShell id={id} label={label} required={required} error={error}>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id} aria-invalid={!!error}>
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </FieldShell>
  );
}

interface FileFieldProps {
  id: string;
  label: string;
  fileName: string;
  onChange: (name: string) => void;
  required?: boolean;
  error?: string;
}

export function FileField({ id, label, fileName, onChange, required, error }: FileFieldProps) {
  const { t } = useApp();
  return (
    <FieldShell id={id} label={label} required={required} error={error}>
      <label
        htmlFor={id}
        className="flex cursor-pointer items-center gap-2 rounded-md border border-border bg-input-background px-3 py-2 hover:bg-secondary"
        style={{ fontSize: "14px" }}
      >
        <Upload className="size-4 shrink-0" style={{ color: "var(--ocean)" }} />
        <span className="min-w-0 flex-1 truncate whitespace-nowrap">
          {fileName || t("field.uploadFile")}
        </span>
      </label>
      <input
        id={id}
        type="file"
        className="hidden"
        onChange={(e) => onChange(e.target.files?.[0]?.name ?? "")}
      />
    </FieldShell>
  );
}

interface EmailVerifyFieldProps {
  email: string;
  onEmailChange: (v: string) => void;
  emailError?: string;
  verified: boolean;
  onVerify: () => void;
  code: string;
  onCodeChange: (v: string) => void;
  codeSent: boolean;
  onSendCode: () => void;
  codeError?: string;
}

export function EmailVerifyField({
  email,
  onEmailChange,
  emailError,
  verified,
  onVerify,
  code,
  onCodeChange,
  codeSent,
  onSendCode,
  codeError,
}: EmailVerifyFieldProps) {
  const { t } = useApp();
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="email" className="whitespace-nowrap">
        {t("field.email")}
        <span style={{ color: "var(--coral)" }}> *</span>
      </Label>
      <div className="flex gap-2">
        <Input
          id="email"
          type="email"
          value={email}
          disabled={verified}
          aria-invalid={!!emailError}
          autoComplete="email"
          onChange={(e) => onEmailChange(e.target.value)}
          className="flex-1"
        />
        <Button
          type="button"
          variant="outline"
          className="shrink-0 whitespace-nowrap"
          disabled={verified}
          onClick={onSendCode}
        >
          {t("field.sendCode")}
        </Button>
      </div>
      <FieldError message={emailError} />

      {codeSent && !verified && (
        <>
          <p className="mt-1" style={{ color: "var(--ocean)", fontSize: "12px" }}>
            {t("field.codeSent")}
          </p>
          <div className="mt-1 flex gap-2">
            <Input
              id="verifyCode"
              value={code}
              placeholder={t("field.verifyCode")}
              inputMode="numeric"
              aria-invalid={!!codeError}
              onChange={(e) => onCodeChange(e.target.value)}
              className="flex-1"
            />
            <Button
              type="button"
              className="shrink-0 whitespace-nowrap"
              style={{ background: "var(--ocean)" }}
              onClick={onVerify}
            >
              {t("field.confirm")}
            </Button>
          </div>
          <FieldError message={codeError} />
        </>
      )}

      {verified && (
        <p
          className="mt-1 flex items-center gap-1"
          style={{ color: "var(--success)", fontSize: "12px" }}
        >
          <CheckCircle2 className="size-3.5" />
          {t("field.verified")}
        </p>
      )}
    </div>
  );
}
