import React from "react";
import ReactDOM from "react-dom/client";
import { Buffer } from "buffer";
import { WalletProvider } from "./state/WalletState.jsx";
import { ContractProvider } from "./state/ContractState.jsx";
import { ToastProvider } from "./components/ui/Toast.jsx";
import App from "./App.jsx";
import "./index.css";

// algosdk + @perawallet/connect need Buffer in the browser
globalThis.Buffer = globalThis.Buffer || Buffer;

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <WalletProvider>
      <ContractProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </ContractProvider>
    </WalletProvider>
  </React.StrictMode>
);
