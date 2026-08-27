import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// algosdk, @perawallet/connect, and @tinymanorg/tinyman-js-sdk need
// Node.js Buffer and process globals.
// The Tinyman SDK uses crypto.createHash — we alias it to a minimal shim
// to avoid pulling in crypto-browserify (which requires stream/vm).
export default defineConfig({
  plugins: [react()],
  define: {
    global: "globalThis",
    "process.env": {},
  },
  resolve: {
    alias: {
      buffer: "buffer/",
      // Shim crypto → our thin wrapper that only implements createHash(sha256)
      crypto: path.resolve(__dirname, "src/lib/crypto-shim.js"),
    },
  },
  optimizeDeps: {
    include: ["buffer", "@tinymanorg/tinyman-js-sdk"],
  },
});
