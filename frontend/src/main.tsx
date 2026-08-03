
  import { createRoot } from "react-dom/client";
  import "./app/i18n/i18n.ts";
  import App from "./app/App.tsx";
  import "./styles/index.css";

  createRoot(document.getElementById("root")!).render(<App />);
