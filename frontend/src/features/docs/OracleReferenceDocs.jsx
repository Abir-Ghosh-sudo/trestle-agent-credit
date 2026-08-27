/**
 * OracleDocs.jsx — Credit Oracle protocol documentation page.
 * Matches the Trestle brutalist UI.
 */
import React from "react";

function H({ level = 2, children }) {
  const sz = { 1: 30, 2: 22, 3: 16 };
  return <div style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: sz[level], color: "var(--text-primary)", marginBottom: 12, marginTop: level > 1 ? 32 : 0 }}>{children}</div>;
}
function P({ children }) {
  return <p style={{ fontFamily: "var(--font-body)", fontSize: 15, lineHeight: 1.7, color: "var(--text-secondary)", marginBottom: 14 }}>{children}</p>;
}
function Code({ children, lang }) {
  return (
    <div style={{ border: "1px solid var(--bg-border-solid)", boxShadow: "var(--shadow-sm)", marginBottom: 24, overflow: "hidden" }}>
      <div style={{ background: "var(--text-primary)", padding: "6px 14px", display: "flex", justifyContent: "space-between" }}>
        <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--warning)" }}>{lang}</span>
      </div>
      <pre style={{ fontFamily: "var(--mono)", fontSize: 13, lineHeight: 1.6, color: "var(--text-primary)", padding: "18px 20px", background: "var(--bg-elevated)", margin: 0, overflowX: "auto" }}>
        <code>{children}</code>
      </pre>
    </div>
  );
}
function Note({ children }) {
  return (
    <div style={{ background: "var(--success-dim)", border: "1px solid var(--bg-border-solid)", borderLeft: "6px solid var(--success)", boxShadow: "var(--shadow-sm)", padding: "14px 18px", marginBottom: 20, fontFamily: "var(--font-body)", fontSize: 14, lineHeight: 1.6, color: "var(--text-secondary)" }}>
      {children}
    </div>
  );
}

export default function OracleReferenceDocs() {
  return (
    <div className="animate-fade-in">
      <div style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 8 }}>Protocol</div>
      <H level={1}>Credit Oracle</H>
      <P>The Credit Oracle is the trust engine at the heart of Trestle. Every draw request is evaluated by a large language model before the smart contract allows any funds to move.</P>

      <Note>The oracle signature is cryptographically bound to the exact draw amount and agent address — it cannot be replayed or forged.</Note>

      <H level={2}>How the Oracle Works</H>
      <P>When an agent calls <code style={{ fontFamily: "var(--mono)", background: "var(--warning-dim)", border: "1px solid var(--text-primary)", padding: "1px 5px" }}>request_draw()</code>, the SDK fetches the agent's on-chain position and submits it to the oracle endpoint. The LLM evaluates the following factors:</P>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 28 }}>
        {[
          { label: "Repayment History", desc: "Past draws repaid on time vs liquidations triggered." },
          { label: "Stake Ratio", desc: "Current stake relative to outstanding debt." },
          { label: "Draw Frequency", desc: "How often the agent draws vs repays in a given window." },
          { label: "Grade Trajectory", desc: "Whether the grade is improving or declining over time." },
        ].map(f => (
          <div key={f.label} style={{ background: "var(--bg-elevated)", border: "1px solid var(--bg-border-solid)", boxShadow: "var(--shadow-sm)", padding: 16 }}>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>{f.label}</div>
            <div style={{ fontFamily: "var(--font-body)", fontSize: 13, color: "var(--text-muted)", lineHeight: 1.5 }}>{f.desc}</div>
          </div>
        ))}
      </div>

      <H level={2}>Oracle Response</H>
      <Code lang="json">
{`{
  "approved": true,
  "grade": "A",
  "confidence": 0.942,
  "max_draw_algo": 31.4,
  "reason": "Strong repayment history. Low leverage ratio.",
  "signature": "0xabc123..."
}`}
      </Code>

      <H level={2}>Grade Table</H>
      <div style={{ border: "1px solid var(--bg-border-solid)", boxShadow: "var(--shadow-sm)", overflow: "hidden", marginBottom: 28 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--font-body)", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "var(--text-primary)", color: "var(--warning)" }}>
              {["Grade", "Max Draw Ratio", "Condition"].map(h => (
                <th key={h} style={{ padding: "10px 16px", textAlign: "left", fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[
              { grade: "A", ratio: "3.14×", cond: "Perfect repayment history" },
              { grade: "B", ratio: "2.00×", cond: "Minor late repayments" },
              { grade: "C", ratio: "1.50×", cond: "Some missed repayments" },
              { grade: "D", ratio: "1.00×", cond: "Multiple missed repayments" },
              { grade: "F", ratio: "0.00×", cond: "Draw blocked — liquidation risk" },
            ].map((row, i) => (
              <tr key={row.grade} style={{ background: i % 2 === 0 ? "var(--bg-elevated)" : "var(--bg-elevated-2)", borderBottom: "1px solid var(--bg-border)" }}>
                <td style={{ padding: "10px 16px", fontFamily: "var(--mono)", fontWeight: 700, color: row.grade === "F" ? "var(--danger)" : row.grade === "A" ? "var(--success)" : "var(--text-primary)" }}>{row.grade}</td>
                <td style={{ padding: "10px 16px", fontFamily: "var(--mono)", color: "var(--text-secondary)" }}>{row.ratio}</td>
                <td style={{ padding: "10px 16px", color: "var(--text-secondary)" }}>{row.cond}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <H level={2}>Signature Verification</H>
      <P>The smart contract verifies the oracle signature using an ed25519 public key hardcoded at deployment. If verification fails, the draw reverts.</P>
      <Code lang="python">
{`# Oracle signature payload (what the LLM signs)
payload = {
    "agent_address": agent.address,
    "amount_microalgo": amount_microalgo,
    "max_draw_microalgo": max_draw_microalgo,
    "timestamp": int(time.time()),
    "nonce": secrets.token_hex(16),
}
signature = ed25519_sign(ORACLE_PRIVATE_KEY, json.dumps(payload))`}
      </Code>
    </div>
  );
}
