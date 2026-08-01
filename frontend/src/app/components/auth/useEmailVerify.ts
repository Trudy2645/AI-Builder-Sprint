import { useState } from "react";

const DEMO_CODE = "123456";

export function useEmailVerify() {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [verified, setVerified] = useState(false);
  const [emailError, setEmailError] = useState<string | undefined>();
  const [codeError, setCodeError] = useState<string | undefined>();

  const isValidEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const sendCode = () => {
    if (!email) {
      setEmailError("err.required");
      return;
    }
    if (!isValidEmail) {
      setEmailError("err.email");
      return;
    }
    setEmailError(undefined);
    setCodeSent(true);
  };

  const verify = () => {
    if (code.trim() === DEMO_CODE) {
      setVerified(true);
      setCodeError(undefined);
    } else {
      setCodeError("err.codeWrong");
    }
  };

  /** Returns true if valid; sets inline error otherwise. */
  const validate = (): boolean => {
    if (!email) {
      setEmailError("err.required");
      return false;
    }
    if (!isValidEmail) {
      setEmailError("err.email");
      return false;
    }
    setEmailError(undefined);
    return true;
  };

  return {
    email,
    setEmail: (v: string) => {
      setEmail(v);
      setEmailError(undefined);
    },
    code,
    setCode: (v: string) => {
      setCode(v);
      setCodeError(undefined);
    },
    codeSent,
    verified,
    emailError,
    codeError,
    sendCode,
    verify,
    validate,
  };
}
