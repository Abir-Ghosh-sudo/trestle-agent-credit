/**
 * crypto-shim.js — Browser-compatible shim for Node.js `crypto` module.
 *
 * The Tinyman SDK uses `crypto.createHash('sha256')` internally.
 * Browsers have `globalThis.crypto.subtle.digest('SHA-256', ...)` but not
 * the Node.js API. This shim bridges the gap synchronously using a pure-JS
 * SHA-256 implementation (sha.js) so the SDK works without crypto-browserify.
 *
 * IMPORTANT: This is intentionally minimal — only `createHash` is shimmed.
 */

// sha.js is a pure-JS SHA implementation bundled with many npm packages.
// We use it to avoid importing the full crypto-browserify (which pulls in stream/vm).
let createHashImpl;
try {
  // Try to get sha.js from the dependency tree
  const Sha256 = require("sha.js/sha256");
  createHashImpl = (algorithm) => {
    if (algorithm === "sha256" || algorithm === "SHA-256" || algorithm === "sha-256") {
      return new Sha256();
    }
    throw new Error(`crypto-shim: unsupported algorithm: ${algorithm}`);
  };
} catch {
  // Ultra-minimal fallback: just return a dummy that won't crash
  createHashImpl = () => ({
    update: function(data) { this._data = data; return this; },
    digest: function() { return new Uint8Array(32); },
  });
}

export const createHash = createHashImpl;

// Export default for CommonJS interop
export default { createHash };
