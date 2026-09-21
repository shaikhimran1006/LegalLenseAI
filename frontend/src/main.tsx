import React from "react";
import ReactDOM from "react-dom/client";
import App from "@/App";
import { AppProvider } from "@/context/AppContext";
import { ToastProvider } from "@/lib/toast";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </AppProvider>
  </React.StrictMode>,
);