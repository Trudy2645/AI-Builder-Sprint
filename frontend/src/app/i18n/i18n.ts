import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { strings, type Lang, type TranslationDictionary } from "./translations";

const LANGUAGE_STORAGE_KEY = "busan-link-language";

function resourcesFor(language: Lang): TranslationDictionary {
  return Object.fromEntries(
    Object.entries(strings).map(([key, translations]) => [key, translations[language] ?? translations.en ?? key]),
  );
}

const savedLanguage = typeof window === "undefined" ? null : window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
const initialLanguage: Lang = savedLanguage === "en" || savedLanguage === "ja" || savedLanguage === "zh" || savedLanguage === "ko"
  ? savedLanguage
  : "ko";

void i18n
  .use(initReactI18next)
  .init({
    resources: {
      ko: { translation: resourcesFor("ko") },
      en: { translation: resourcesFor("en") },
      ja: { translation: resourcesFor("ja") },
      zh: { translation: resourcesFor("zh") },
    },
    lng: initialLanguage,
    fallbackLng: "en",
    interpolation: { escapeValue: false },
    keySeparator: false,
    react: { useSuspense: false },
  });

export { LANGUAGE_STORAGE_KEY, initialLanguage, i18n };
