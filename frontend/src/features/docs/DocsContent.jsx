import React from "react";
import OracleReferenceDocs from "./OracleReferenceDocs.jsx";

/* ── Shared neo-brutalist UI primitives ── */

function SectionLabel({ children }) {
  return (
    <div
      style={{
        fontFamily: "var(--font-display)",
        fontWeight: 800,
        fontSize: 10,
        letterSpacing: "0.15em",
        textTransform: "uppercase",
        color: "var(--text-muted)",
        marginBottom: 12,
      }}
    >
      {children}
    </div>
  );
}

function SkewedTitle({ text1, text2 }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "14px", marginBottom: "32px", alignItems: "flex-start" }}>
      <div
        style={{
          background: "var(--brand-gradient)",
          color: "#ffffff",
          padding: "12px 32px",
          fontFamily: "var(--font-display)",
          fontWeight: 900,
          fontSize: "64px",
          lineHeight: "0.95",
          letterSpacing: "0.02em",
          border: "1px solid var(--bg-border-solid)",
          boxShadow: "var(--shadow-sm)",
          transform: "rotate(-1.5deg) skewX(-6deg)",
          display: "inline-block",
        }}
      >
        {text1}
      </div>
      {text2 && (
        <div
          style={{
            background: "var(--brand-gradient)",
            color: "#ffffff",
            padding: "12px 32px",
            fontFamily: "var(--font-display)",
            fontWeight: 900,
            fontSize: "64px",
            lineHeight: "0.95",
            letterSpacing: "0.02em",
            border: "1px solid var(--bg-border-solid)",
            boxShadow: "var(--shadow-sm)",
            transform: "rotate(1deg) skewX(-6deg)",
            display: "inline-block",
            marginLeft: "24px",
          }}
        >
          {text2}
        </div>
      )}
    </div>
  );
}

function SkewedHeading({ children, bg, fg, angle }) {
  // Legacy props (bg/fg/angle) are accepted for call-site compatibility but no
  // longer drive brutalist skew/hard-border styling — every heading now uses
  // one consistent glass + gradient treatment.
  return (
    <div style={{ display: "inline-block", marginBottom: "32px" }}>
      <div
        className="glass-panel"
        style={{
          padding: "10px 26px",
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: "22px",
          letterSpacing: "0.01em",
        }}
      >
        <span className="gradient-text">{children}</span>
      </div>
    </div>
  );
}

function BodyText({ children, style }) {
  return (
    <p
      style={{
        fontFamily: "var(--font-body)",
        fontSize: 16,
        lineHeight: 1.7,
        color: "var(--text-secondary)",
        marginBottom: 20,
        ...style,
      }}
    >
      {children}
    </p>
  );
}

function CodeBlock({ lang, children }) {
  return (
    <div
      style={{
        background: "var(--bg-elevated)",
        border: "1px solid var(--bg-border-solid)",
        boxShadow: "var(--shadow-sm)",
        marginBottom: 28,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          background: "var(--bg-elevated-2)",
          padding: "8px 18px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--warning)", letterSpacing: "0.08em", fontWeight: "bold" }}>
          {lang?.toUpperCase()}
        </span>
        <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-muted)" }}>trestle_terminal v2.0</span>
      </div>
      <pre
        style={{
          fontFamily: "var(--mono)",
          fontSize: 13,
          lineHeight: 1.6,
          color: "var(--text-primary)",
          padding: "20px",
          overflowX: "auto",
          background: "var(--bg-elevated)",
          margin: 0,
        }}
      >
        <code>{children}</code>
      </pre>
    </div>
  );
}

function Callout({ type = "info", title, children }) {
  const colors = {
    info: { bg: "var(--success-dim)", accent: "var(--success)" },
    warning: { bg: "var(--warning-dim)", accent: "var(--warning)" },
    danger: { bg: "var(--danger-dim)", accent: "var(--danger)" },
  };
  const c = colors[type];
  return (
    <div
      style={{
        background: c.bg,
        border: "1px solid var(--bg-border-solid)",
        borderLeft: `8px solid ${c.accent}`,
        boxShadow: "var(--shadow-sm)",
        padding: "20px 24px",
        marginBottom: 28,
      }}
    >
      {title && (
        <div
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 900,
            fontSize: 13,
            marginBottom: 8,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-primary)",
          }}
        >
          {title}
        </div>
      )}
      <div style={{ fontFamily: "var(--font-body)", fontSize: 14, lineHeight: 1.6, color: "var(--text-secondary)" }}>
        {children}
      </div>
    </div>
  );
}

function StatCard({ value, label, bg = "var(--bg-elevated)", rotate = 0 }) {
  return (
    <div
      style={{
        background: bg,
        border: "1px solid var(--bg-border-solid)",
        boxShadow: "var(--shadow-sm)",
        padding: "24px 20px",
        textAlign: "center",
        transform: `rotate(${rotate}deg)`,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "140px",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 900,
          fontSize: 32,
          color: "var(--text-primary)",
          marginBottom: 8,
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      <div
        style={{
          borderTop: "1px solid var(--bg-border-solid)",
          width: "100%",
          paddingTop: 8,
          fontFamily: "var(--mono)",
          fontSize: 10,
          fontWeight: "bold",
          color: "var(--text-primary)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          lineHeight: "1.3",
        }}
      >
        {label}
      </div>
    </div>
  );
}


/* ── Page Views ── */

// 1. Getting Started: Introduction (Quickstart Landing Page)
function Introduction({ onNavigate }) {
  return (
    <div className="animate-fade-in" style={{ width: "100%" }}>
      <div
        style={{
          display: "inline-block",
          background: "var(--success)",
          color: "var(--text-primary)",
          border: "1px solid var(--bg-border-solid)",
          padding: "4px 12px",
          fontFamily: "var(--mono)",
          fontSize: "11px",
          fontWeight: "bold",
          marginBottom: "20px",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        [ FOR AUTONOMOUS AGENTS ]
      </div>

      <SkewedTitle text1="TRESTLE" text2="DOCS" />

      <div
        style={{
          background: "var(--bg-elevated)",
          border: "1px solid var(--bg-border-solid)",
          boxShadow: "var(--shadow-sm)",
          padding: "20px 24px",
          fontFamily: "var(--font-body)",
          fontSize: "16px",
          lineHeight: "1.6",
          color: "var(--text-primary)",
          marginBottom: "32px",
          maxWidth: "680px",
        }}
      >
        The first on-chain credit protocol where a secure LLM decision oracle decides if your agent's loan is responsible before it hits the chain.
      </div>

      <div style={{ display: "flex", gap: "16px", marginBottom: "48px", flexWrap: "wrap" }}>
        <button
          onClick={() => onNavigate("quickstart")}
          style={{
            background: "var(--brand-gradient)",
            color: "#ffffff",
            border: "1px solid var(--bg-border-solid)",
            boxShadow: "var(--shadow-sm)",
            padding: "14px 28px",
            fontFamily: "var(--font-display)",
            fontWeight: 800,
            fontSize: "14px",
            letterSpacing: "0.05em",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            cursor: "pointer",
            transition: "all 0.1s",
          }}
          className="btn-3d"
        >
          QUICK START <span style={{ fontSize: "16px" }}>→</span>
        </button>
        <button
          onClick={() => onNavigate("abi")}
          style={{
            background: "var(--warning)",
            color: "var(--text-primary)",
            border: "1px solid var(--bg-border-solid)",
            boxShadow: "var(--shadow-sm)",
            padding: "14px 28px",
            fontFamily: "var(--font-display)",
            fontWeight: 800,
            fontSize: "14px",
            letterSpacing: "0.05em",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            cursor: "pointer",
            transition: "all 0.1s",
          }}
          className="btn-3d"
        >
          VIEW CONTRACT <span style={{ fontSize: "16px" }}>↗</span>
        </button>
      </div>

      <div
        style={{
          background: "var(--bg-elevated-2)",
          border: "1px solid var(--bg-border-solid)",
          padding: "12px 0",
          margin: "0 -48px 48px -48px",
          overflow: "hidden",
          display: "flex",
        }}
      >
        <div
          className="animate-marquee"
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 900,
            fontSize: "13px",
            color: "#ffffff",
            letterSpacing: "0.1em",
            display: "flex",
            gap: "32px",
            alignItems: "center",
          }}
        >
          <span>MIC CREDIT ★ FOR AI AGENTS ★ NO HUMANS IN THE LOOP ★ TRUSTLESS ALGORITHMIC CREDIT ★ FOR AI AGENTS ★ NO HUMANS IN THE LOOP ★</span>
          <span>MIC CREDIT ★ FOR AI AGENTS ★ NO HUMANS IN THE LOOP ★ TRUSTLESS ALGORITHMIC CREDIT ★ FOR AI AGENTS ★ NO HUMANS IN THE LOOP ★</span>
        </div>
      </div>

      <div style={{ width: "100%", marginBottom: "48px" }} id="what-is-trestle">
        <SkewedHeading bg="var(--bg-elevated)" fg="var(--text-primary)" angle={-1.5}>
          WHAT IS TRESTLE?
        </SkewedHeading>

        <BodyText style={{ maxWidth: "720px", marginBottom: "28px" }}>
          Trestle is built for autonomous agents operating in decentralized finance. Rather than requiring heavy over-collateralization, Trestle routes loan drawing requests through a Large Language Model credit oracle. Good agents establish high confidence ratings and unlock higher credit capacity.
        </BodyText>

        {/* Live Simulation Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(310px, 1fr))", gap: "28px" }} id="live-sim">
          {/* Card 1: Approved */}
          <div
            style={{
              background: "var(--success)",
              border: "1px solid var(--bg-border-solid)",
              boxShadow: "var(--shadow-sm)",
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderBottom: "1px solid var(--bg-border-solid)",
                paddingBottom: "12px",
              }}
            >
              <span style={{ fontFamily: "var(--mono)", fontWeight: "bold", fontSize: "13px" }}>AGENT_8X8F2...</span>
              <span
                style={{
                  width: "18px",
                  height: "18px",
                  borderRadius: "50%",
                  border: "1px solid var(--bg-border-solid)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "11px",
                  fontWeight: "bold",
                  background: "var(--bg-elevated)",
                }}
              >
                ✓
              </span>
            </div>
            <div style={{ fontFamily: "var(--mono)", fontSize: "13px", lineHeight: "1.6", color: "var(--text-primary)" }}>
              <div>&gt; Analyzing risk profile...</div>
              <div>&gt; LLM Confidence: 94.2%</div>
              <div style={{ fontWeight: "bold", color: "var(--success)", marginTop: "4px" }}>✓ Approved Draw</div>
            </div>
            <div
              style={{
                background: "var(--brand-gradient)",
                color: "#ffffff",
                border: "1px solid var(--bg-border-solid)",
                padding: "12px 16px",
                fontFamily: "var(--mono)",
                fontSize: "12px",
                fontWeight: "bold",
                marginTop: "4px",
              }}
            >
              10,000 USDC sent to agent vault.
            </div>
          </div>

          {/* Card 2: Denied */}
          <div
            style={{
              background: "var(--danger-dim)",
              border: "1px solid var(--bg-border-solid)",
              boxShadow: "var(--shadow-sm)",
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderBottom: "1px solid var(--bg-border-solid)",
                paddingBottom: "12px",
              }}
            >
              <span style={{ fontFamily: "var(--mono)", fontWeight: "bold", fontSize: "13px" }}>AGENT_0X3A9...</span>
            </div>
            <div style={{ fontFamily: "var(--mono)", fontSize: "13px", lineHeight: "1.6", color: "var(--text-primary)" }}>
              <div>&gt; Analyzing risk profile...</div>
              <div style={{ color: "var(--danger)" }}>&gt; Warning: Historical liquidation rate high.</div>
              <div>&gt; LLM Confidence: 12.8%</div>
              <div style={{ fontWeight: "bold", color: "var(--danger)", marginTop: "4px" }}>🚫 Denied Draw</div>
            </div>
            <div
              style={{
                background: "var(--bg-elevated)",
                border: "2px solid #dc2626",
                color: "var(--danger)",
                padding: "12px 16px",
                fontFamily: "var(--mono)",
                fontSize: "12px",
                fontWeight: "bold",
                marginTop: "4px",
              }}
            >
              REASON: Excessive leverage detected.
            </div>
          </div>
        </div>
      </div>

      <div style={{ width: "100%", marginBottom: "24px" }} id="protocol-stats">
        <SkewedHeading bg="var(--text-primary)" fg="#ffffff" angle={1}>
          PROTOCOL STATS
        </SkewedHeading>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: "24px",
            marginTop: "8px",
          }}
        >
          <StatCard value="4" label="CRITERIA / LLM GATE" bg="var(--accent-dim)" rotate={-2} />
          <StatCard value="1" label="ALGO / MIN STAKE" bg="var(--warning-dim)" rotate={1.5} />
          <StatCard value="100%" label="ON-CHAIN" bg="var(--bg-elevated)" rotate={-1} />
          <StatCard value="24h" label="HRS / REPAY WINDOW" bg="var(--brand-end)" rotate={2} />
        </div>
      </div>
    </div>
  );
}

// 2. Getting Started: Quickstart View
function QuickStart() {
  return (
    <div className="animate-fade-in" style={{ width: "100%" }}>
      <SectionLabel>Getting Started</SectionLabel>
      <SkewedHeading bg="var(--bg-elevated)" fg="var(--text-primary)" angle={-1}>
        Quick Start
      </SkewedHeading>

      <BodyText>
        Get your autonomous AI agent staking, drawing loans, and repaying positions on the Algorand blockchain in under 5 minutes.
      </BodyText>

      <Callout type="info" title="Prerequisites" id="prerequisites">
        Python 3.11+ · Venice AI or Anthropic API Key · Algorand Testnet ALGO
      </Callout>

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, marginBottom: 8 }} id="clone-sdk">
          Step 1. Clone & Install the Repository
        </h3>
        <BodyText>
          Clone the main project repository and install the Trestle SDK in editable mode.
        </BodyText>
        <CodeBlock lang="bash">
{`git clone https://github.com/ShahiTechnovation/Trestle
cd Trestle
pip install -e "./trestle_sdk"`}
        </CodeBlock>

        <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, marginBottom: 8 }} id="bootstrap-cli">
          Step 2. Bootstrap via CLI
        </h3>
        <BodyText>
          Use the built-in CLI command to generate a new developer wallet mnemonic, request faucet funding, opt-in to the contract, and stake ALGO collateral.
        </BodyText>
        <CodeBlock lang="bash">
{`trestle init --network testnet`}
        </CodeBlock>
        <CodeBlock lang="terminal output">
{`[1/6] Generating agent keypair...
      Address: 7XQ3...DEMO
[2/6] Funding wallet...
      Requesting from Algonode testnet faucet...
      Faucet request sent. Waiting...
[3/6] Waiting 6 rounds for funding to confirm (~6 seconds)...
[4/6] Connecting to Algorand testnet...
[5/6] Opting in to Trestle contract...
      Opted in. Txn: OPTIN_TXID...
[6/6] Registering with Trestle (staking 1,000,000 μA)...
      Registered! Txn: REGISTER_TXID...
      Credentials saved to .trestle.env
      ⚠ Keep .trestle.env secret. Add it to .gitignore.
──────────────────────────────────────────────────
Done. Trestle agent ready.`}
        </CodeBlock>

        <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, marginBottom: 8 }} id="setup-env">
          Step 3. Set Up API Key
        </h3>
        <BodyText>
          Your environment file <code>.trestle.env</code> has been created automatically. Just append your LLM provider key to it (e.g. Venice AI or Anthropic API Key).
        </BodyText>
        <CodeBlock lang=".trestle.env">
{`TRESTLE_ADDRESS=7XQ3...DEMO
TRESTLE_MNEMONIC="word1 word2 word3 ... word25"
TRESTLE_NETWORK=testnet
TRESTLE_APP_ID=<YOUR_APP_ID>
ALGOD_URL=https://testnet-api.algonode.cloud
VENICE_API_KEY=your-venice-api-key`}
        </CodeBlock>

        <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, marginBottom: 8 }} id="run-demo">
          Step 4. Run the Live Demo Agent
        </h3>
        <BodyText>
          Run the combination skill and credit demo which demonstrates an approved price-feed check and a denied speculative check.
        </BodyText>
        <CodeBlock lang="bash">
{`python demo/SDK_DEMO.py`}
        </CodeBlock>

        <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, marginBottom: 8 }} id="run-tests">
          Step 5. Run the Local Test Suite
        </h3>
        <BodyText>
          Validate your local SDK setup by running the offline unit tests using <code>pytest</code>.
        </BodyText>
        <CodeBlock lang="bash">
{`python -m pytest tests/ -v`}
        </CodeBlock>

        <Callout type="warning" title="Testnet Faucet">
          Need ALGO to fund your test agent wallet? Visit the developer faucet at <strong>bank.testnet.algorand.network</strong> to request test funds instantly.
        </Callout>
      </div>
    </div>
  );
}

// 3. Getting Started: Installation View
function InstallationView() {
  return (
    <div className="animate-fade-in" style={{ width: "100%" }} id="install-top">
      <SectionLabel>Getting Started</SectionLabel>
      <SkewedHeading bg="var(--warning-dim)" fg="var(--text-primary)" angle={1.5}>
        Installation
      </SkewedHeading>

      <BodyText>
        Trestle SDK is published as a Python library and can be integrated into standard AI agent stacks like Autogen, LangChain, or custom autonomous script loops.
      </BodyText>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, marginBottom: 8 }} id="pip-package">
        1. Install Pip Package
      </h3>
      <BodyText>
        Install the core package directly from PyPI.
      </BodyText>
      <CodeBlock lang="bash">
{`pip install trestle-sdk`}
      </CodeBlock>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, marginBottom: 8 }} id="optional-extras">
        2. Optional Extras
      </h3>
      <BodyText>
        If you wish to use the Anthropic oracle models directly, you can install the optional Anthropic extra:
      </BodyText>
      <CodeBlock lang="bash">
{`pip install trestle-sdk[anthropic]`}
      </CodeBlock>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, marginBottom: 8 }} id="verify-install">
        3. Verification
      </h3>
      <BodyText>
        Run a quick script to verify that the library was installed successfully:
      </BodyText>
      <CodeBlock lang="python">
{`import trestle_sdk
print(f"Trestle SDK Version: {trestle_sdk.__version__ if hasattr(trestle_sdk, '__version__') else '2.0'}")`}
      </CodeBlock>
    </div>
  );
}

// 4. Protocol: Architecture (Protocol System & Engine)
function ProtocolView() {
  return (
    <div className="animate-fade-in" style={{ width: "100%" }}>
      <SectionLabel>Protocol System</SectionLabel>
      <SkewedHeading bg="var(--text-primary)" fg="#ffffff" angle={-1}>
        Architecture
      </SkewedHeading>

      <BodyText>
        Trestle represents a paradigm shift in decentralized credit markets: transitioning from heavy over-collateralization to undercollateralized credit lines governed by real-time risk estimation and on-chain agent reputation history.
      </BodyText>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "24px 0 12px" }} id="core-engine">
        Core Economic Engine
      </h3>
      <BodyText>
        Every opted-in agent builds reputation and draws credit through three core steps:
      </BodyText>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "20px", marginBottom: "32px" }} id="states">
        {[
          { title: "1. Stake", bg: "var(--warning-dim)", desc: "Deposit ALGO collateral (minimum 1.00 ALGO) to establish protocol identity and opt-in." },
          { title: "2. Draw", bg: "var(--success)", desc: "Request loan from treasury escrow. The LLM risk oracle evaluates draw request in real-time." },
          { title: "3. Repay", bg: "var(--brand-end)", desc: "Repay loans with dynamic interest to boost on-chain payment history and upgrade reputation tier." },
        ].map((card) => (
          <div
            key={card.title}
            style={{
              background: card.bg,
              border: "1px solid var(--bg-border-solid)",
              boxShadow: "var(--shadow-sm)",
              padding: "20px",
            }}
          >
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: "14px", marginBottom: "8px" }}>
              {card.title}
            </div>
            <div style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.5" }}>
              {card.desc}
            </div>
          </div>
        ))}
      </div>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "32px 0 12px" }} id="credit-grades">
        On-Chain Reputation Tiers
      </h3>
      <BodyText>
        Trestle smart contracts enforce borrowing caps, daily limits, and dynamic APR rates based on hardcoded credit tiers:
      </BodyText>

      {/* Tiers Table */}
      <div style={{ border: "1px solid var(--bg-border-solid)", boxShadow: "var(--shadow-sm)", overflow: "hidden", marginBottom: "32px" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--font-body)", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "var(--bg-elevated-2)", color: "var(--warning)", borderBottom: "1px solid var(--bg-border-solid)" }}>
              {["Tier", "Payments", "Max Draw Limit", "Daily drawn cap", "APR (Interest)", "Min Stake"].map((h) => (
                <th
                  key={h}
                  style={{
                    padding: "12px 16px",
                    textAlign: "left",
                    fontFamily: "var(--font-display)",
                    fontWeight: 900,
                    fontSize: 12,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[
              { tier: "Tier 0 (Fresh)", count: "0 - 9", draw: "0.10 ALGO", daily: "0.50 ALGO", apr: "24% (2400 bps)", stake: "1.00 ALGO" },
              { tier: "Tier 1 (Trusted)", count: "10 - 49", draw: "0.50 ALGO", daily: "2.00 ALGO", apr: "16% (1600 bps)", stake: "1.00 ALGO" },
              { tier: "Tier 2 (Veteran)", count: "50 - 99", draw: "2.00 ALGO", daily: "10.00 ALGO", apr: "9% (900 bps)", stake: "1.00 ALGO" },
              { tier: "Tier 3 (Elite)", count: "100+", draw: "5.00 ALGO", daily: "25.00 ALGO", apr: "4% (400 bps)", stake: "1.00 ALGO" },
            ].map((row, idx) => (
              <tr
                key={row.tier}
                style={{
                  background: idx % 2 === 0 ? "var(--bg-elevated)" : "var(--bg-elevated-2)",
                  borderBottom: idx === 3 ? "none" : "1px solid var(--bg-border-solid)",
                }}
              >
                <td style={{ padding: "12px 16px", fontFamily: "var(--mono)", fontWeight: 900, color: idx === 3 ? "var(--success)" : "var(--text-primary)" }}>
                  {row.tier}
                </td>
                <td style={{ padding: "12px 16px", fontFamily: "var(--mono)" }}>{row.count}</td>
                <td style={{ padding: "12px 16px", fontFamily: "var(--mono)", fontWeight: "500" }}>{row.draw}</td>
                <td style={{ padding: "12px 16px", fontFamily: "var(--mono)" }}>{row.daily}</td>
                <td style={{ padding: "12px 16px", fontFamily: "var(--mono)" }}>{row.apr}</td>
                <td style={{ padding: "12px 16px", fontFamily: "var(--mono)" }}>{row.stake}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// 5. SDK Reference: TrestleCreditAgent View (Mock layout with real specifications!)
function TrestleCreditAgentDocs() {
  return (
    <div className="animate-fade-in" style={{ width: "100%" }}>
      {/* HEADER */}
      <header className="mb-12">
        <div className="font-label-mono text-[12px] text-text-muted mb-6 flex items-center gap-2">
          SDK <span className="material-symbols-outlined text-[14px]">chevron_right</span> Python <span className="material-symbols-outlined text-[14px]">chevron_right</span> <span className="text-text-primary bg-white border border-border px-1.5 py-0.5 font-bold">Classes</span>
        </div>
        <div className="inline-block bg-warning-soft glass-border px-3 py-1 font-label-mono text-[12px] font-bold tilt-none mb-4 soft-shadow shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
          [ CLASS ]
        </div>
        <h1 className="font-headline-xl text-[48px] md:text-[64px] text-text-primary mb-6 leading-none">TrestleCreditAgent</h1>
        <p className="font-body-lg text-[18px] mb-8 max-w-2xl bg-white p-4 glass-border tilt-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] text-text-primary">
          The core interface for interacting with the Trestle decentralized credit protocol. Handles LLM-gated draw requests, position management, and repayments on the Algorand testnet.
        </p>
      </header>

      {/* MARQUEE */}
      <div className="w-full bg-warning-soft glass-border overflow-hidden py-3 mb-16 tilt-none">
        <div className="whitespace-nowrap font-label-mono text-[12px] font-bold tracking-widest flex gap-8 animate-marquee">
          <span>🐍 PYTHON SDK · ALGORAND TESTNET · LLM-GATED DRAWS · VERSION 2.0 🐍</span>
          <span>🐍 PYTHON SDK · ALGORAND TESTNET · LLM-GATED DRAWS · VERSION 2.0 🐍</span>
        </div>
      </div>

      {/* CONSTRUCTOR */}
      <section className="mb-16" id="constructor">
        <div className="flex items-center gap-4 mb-6">
          <h2 className="font-headline-md text-[32px] text-text-primary font-bold">Constructor</h2>
          <span className="bg-accent-soft glass-border px-2 py-1 font-label-mono text-[12px] tilt-none shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">__init__</span>
        </div>
        <div className="bg-text-primary text-[#4ADE80] font-code-block text-[14px] p-6 glass-border soft-shadow mb-8 relative">
          <div className="absolute -top-3 right-3 bg-white text-text-primary glass-border px-2 py-1 font-label-mono text-[10px] tilt-none font-bold">PYTHON</div>
          <pre className="overflow-x-auto m-0"><code className="font-mono">{`agent = TrestleCreditAgent(
    mnemonic_phrase="word1 word2 word3 ... word25",
    app_id=<YOUR_APP_ID>,
    algod_url="https://testnet-api.algonode.cloud",
    demo_mode=True
)`}</code></pre>
        </div>
        <div className="bg-white glass-border soft-shadow p-6 tilt-none text-text-primary">
          <h3 className="font-label-mono text-[12px] font-bold mb-4 border-b border-border pb-2">PARAMETERS</h3>
          <ul className="space-y-4 list-none p-0 m-0">
            <li className="flex flex-col md:flex-row gap-4 md:items-start border-b border-gray-200 pb-4">
              <div className="w-48 shrink-0"><span className="bg-accent-dim border border-border px-2 py-1 font-code-block text-[12px] font-bold">mnemonic_phrase</span></div>
              <div className="flex-1"><span className="text-text-muted font-label-mono text-[10px] bg-elevated-2 px-1 mr-2">str</span> Your 25-word Algorand developer wallet mnemonic. Required.</div>
            </li>
            <li className="flex flex-col md:flex-row gap-4 md:items-start border-b border-gray-200 pb-4">
              <div className="w-48 shrink-0"><span className="bg-accent-dim border border-border px-2 py-1 font-code-block text-[12px] font-bold">app_id</span></div>
              <div className="flex-1"><span className="text-text-muted font-label-mono text-[10px] bg-elevated-2 px-1 mr-2">int</span> Target app deployment. Default: <code>{"<YOUR_APP_ID>"}</code> (Testnet).</div>
            </li>
            <li className="flex flex-col md:flex-row gap-4 md:items-start border-b border-gray-200 pb-4">
              <div className="w-48 shrink-0"><span className="bg-accent-dim border border-border px-2 py-1 font-code-block text-[12px] font-bold">algod_url</span></div>
              <div className="flex-1"><span className="text-text-muted font-label-mono text-[10px] bg-elevated-2 px-1 mr-2">str</span> Algod client API endpoint URL. Defaults to Algonode Testnet.</div>
            </li>
            <li className="flex flex-col md:flex-row gap-4 md:items-start pb-2">
              <div className="w-48 shrink-0"><span className="bg-accent-dim border border-border px-2 py-1 font-code-block text-[12px] font-bold">demo_mode</span></div>
              <div className="flex-1"><span className="text-text-muted font-label-mono text-[10px] bg-elevated-2 px-1 mr-2">bool</span> Set <code>True</code> to skip on-chain oracle cryptographic signature verification (uses 32-zero-bytes hash).</div>
            </li>
          </ul>
        </div>
      </section>

      {/* METHODS */}
      <section className="mb-16" id="methods">
        <div className="bg-text-primary text-white py-2 px-4 glass-border inline-block mb-8 tilt-none">
          <h2 className="font-label-mono text-[14px] tracking-widest text-warning font-bold">★ METHODS ★</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <a className="block bg-accent-soft p-6 glass-border soft-shadow lift-hover transition-all tilt-none text-text-primary hover:text-text-primary no-underline" href="#draw">
            <div className="font-code-block text-[18px] font-bold mb-2">draw()</div>
            <div className="font-body-md text-[13px] leading-relaxed">Request a credit draw. Requires LLM oracle approval based on profit margin, round timing, and risk criteria.</div>
          </a>
          <a className="block bg-success-soft p-6 glass-border soft-shadow lift-hover transition-all tilt-none text-text-primary hover:text-text-primary no-underline" href="#repay">
            <div className="font-code-block text-[18px] font-bold mb-2">repay()</div>
            <div className="font-body-md text-[13px] leading-relaxed">Settle outstanding balances back to the contract, resolving principal and accrued interest.</div>
          </a>
          <a className="block bg-danger-soft p-6 glass-border soft-shadow lift-hover transition-all tilt-none text-text-primary hover:text-text-primary no-underline" href="#record_payment">
            <div className="font-code-block text-[18px] font-bold mb-2">record_payment()</div>
            <div className="font-body-md text-[13px] leading-relaxed">Record an off-chain transaction to build reputation count and trigger tier progression.</div>
          </a>
          <a className="block bg-warning-soft p-6 glass-border soft-shadow lift-hover transition-all tilt-none text-text-primary hover:text-text-primary no-underline" href="#get_position">
            <div className="font-code-block text-[18px] font-bold mb-2">get_position()</div>
            <div className="font-body-md text-[13px] leading-relaxed">Fetch the agent's current on-chain state, outstanding debt, limits, and deadlines.</div>
          </a>
        </div>
      </section>

      {/* DRAW DEEP DIVE */}
      <section className="mb-16" id="draw">
        <div className="relative bg-white glass-border soft-shadow p-8 mt-12 text-text-primary">
          <div className="absolute -top-5 left-8 bg-warning-soft glass-border px-4 py-2 font-code-block text-[13px] font-bold tilt-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            def draw(amount_microalgo: int, task_description: str, expected_return_microalgo: int, estimated_task_rounds: int = 300) -&gt; dict
          </div>
          <div className="mt-6 mb-8 border-l-4 border-accent pl-4 py-2 bg-accent-dim">
            <p className="font-body-md text-[15px] leading-relaxed">
              Initiates an LLM-gated credit draw. The oracle evaluates the task profit margins and risk classification in real-time before approving the loan.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 mb-8">
            <span className="bg-white glass-border px-2 py-1 font-label-mono text-[11px] shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] tilt-none font-bold">STATE MUTATING</span>
            <span className="bg-white glass-border px-2 py-1 font-label-mono text-[11px] shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] tilt-none font-bold">GAS INTENSIVE</span>
            <span className="bg-white glass-border px-2 py-1 font-label-mono text-[11px] shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] tilt-none font-bold">ORACLE REQUIRED</span>
          </div>
          <div className="bg-text-primary text-[#4ADE80] font-code-block text-[14px] p-6 glass-border shadow-[inset_4px_4px_0px_0px_rgba(255,255,255,0.2)] mb-8">
            <pre className="overflow-x-auto m-0"><code className="font-mono">{`try:
    receipt = agent.draw(
        amount_microalgo=50_000,
        task_description="Fetch CoinGecko ETH price",
        expected_return_microalgo=80_000,
        estimated_task_rounds=120
    )
    print(f"Draw successful: TxID {receipt['txid']}")
except TrestleCreditDenied as e:
    print(f"LLM Oracle Denied: {e.reason}")`}</code></pre>
          </div>
          <div className="bg-danger-soft glass-border p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] tilt-none flex gap-4 items-start" id="exceptions">
            <span className="material-symbols-outlined text-[32px] mt-1 shrink-0">warning</span>
            <div>
              <h4 className="font-label-mono font-bold mb-1 text-[13px]">EXCEPTION: TrestleCreditDenied</h4>
              <p className="text-sm leading-relaxed m-0">Raised if the LLM oracle determines the wallet history is too risky or lacks sufficient collateral footprint. Contains a generated <code>reason</code> string and full <code>criteria_results</code>.</p>
            </div>
          </div>
        </div>
      </section>

      {/* REPAY DEEP DIVE */}
      <section className="mb-16" id="repay">
        <div className="relative bg-white glass-border soft-shadow p-8 mt-12 text-text-primary">
          <div className="absolute -top-5 left-8 bg-warning-soft glass-border px-4 py-2 font-code-block text-[13px] font-bold tilt-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            def repay(amount_microalgo: int) -&gt; dict
          </div>
          <div className="mt-6 mb-8 border-l-4 border-success pl-4 py-2 bg-success-dim">
            <p className="font-body-md text-[15px] leading-relaxed">
              Repays outstanding credit balances. Updates agent credit history dynamically, unlocking next levels of reputation.
            </p>
          </div>
          <div className="bg-text-primary text-[#4ADE80] font-code-block text-[14px] p-6 glass-border shadow-[inset_4px_4px_0px_0px_rgba(255,255,255,0.2)] mb-8">
            <pre className="overflow-x-auto m-0"><code className="font-mono">{`receipt = agent.repay(50024) # Settles outstanding balance + dynamic on-chain interest
print(f"Repaid: TxID {receipt['txid']}")`}</code></pre>
          </div>
        </div>
      </section>

      {/* RECORD PAYMENT DEEP DIVE */}
      <section className="mb-16" id="record_payment">
        <div className="relative bg-white glass-border soft-shadow p-8 mt-12 text-text-primary">
          <div className="absolute -top-5 left-8 bg-warning-soft glass-border px-4 py-2 font-code-block text-[13px] font-bold tilt-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            def record_payment(amount_microalgo: int = 1000) -&gt; int
          </div>
          <div className="mt-6 mb-8 border-l-4 border-danger pl-4 py-2 bg-danger-dim">
            <p className="font-body-md text-[15px] leading-relaxed">
              Records an off-chain payment. Increments the agent's <code>payment_count</code> local state slot on the contract to build reputation and advance tiers.
            </p>
          </div>
          <div className="bg-text-primary text-[#4ADE80] font-code-block text-[14px] p-6 glass-border shadow-[inset_4px_4px_0px_0px_rgba(255,255,255,0.2)] mb-8">
            <pre className="overflow-x-auto m-0"><code className="font-mono">{`new_tier = agent.record_payment(amount_microalgo=1000)
print(f"Payment recorded! New reputation tier: Tier {new_tier}")`}</code></pre>
          </div>
          <div className="bg-accent-soft glass-border p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] tilt-none flex gap-4 items-start">
            <span className="material-symbols-outlined text-[32px] mt-1 shrink-0 font-bold">info</span>
            <div>
              <h4 className="font-label-mono font-bold mb-1 text-[13px]">TIER PROGRESSION</h4>
              <p className="text-sm leading-relaxed m-0 text-text-primary">Upgrades occur automatically at <strong>10 payments</strong> (Tier 1), <strong>50 payments</strong> (Tier 2), and <strong>100 payments</strong> (Tier 3). Upgrades decrease borrow interest rates and unlock higher draw caps.</p>
            </div>
          </div>
        </div>
      </section>

      {/* GET POSITION DEEP DIVE */}
      <section className="mb-16" id="get_position">
        <div className="relative bg-white glass-border soft-shadow p-8 mt-12 text-text-primary">
          <div className="absolute -top-5 left-8 bg-warning-soft glass-border px-4 py-2 font-code-block text-[13px] font-bold tilt-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            def get_position() -&gt; dict
          </div>
          <div className="mt-6 mb-8 border-l-4 border-warning pl-4 py-2 bg-warning-dim">
            <p className="font-body-md text-[15px] leading-relaxed">
              Reads the agent's current on-chain credit position. Uses simulated calls (dry runs) to return instant state variables without submitting a transaction or paying network fees.
            </p>
          </div>
          <div className="bg-text-primary text-[#4ADE80] font-code-block text-[14px] p-6 glass-border shadow-[inset_4px_4px_0px_0px_rgba(255,255,255,0.2)] mb-8">
            <pre className="overflow-x-auto m-0"><code className="font-mono">{`pos = agent.get_position()
print(f"Collateral Staked: {pos['stake_amount']} microALGO")
print(f"Outstanding Debt: {pos['outstanding']} microALGO")
print(f"Reputation Tier: Tier {pos['tier']}")`}</code></pre>
          </div>
        </div>
      </section>
    </div>
  );
}

// 6. SDK Reference: WalletManager View
function WalletManagerView() {
  return (
    <div className="animate-fade-in" style={{ width: "100%" }} id="wm-top">
      <SectionLabel>SDK Reference</SectionLabel>
      <SkewedHeading bg="var(--accent-dim)" fg="var(--text-primary)" angle={-1.5}>
        WalletManager
      </SkewedHeading>

      <BodyText>
        The <code>WalletManager</code> is an advanced utility built into the Trestle SDK designed to securely handle hot-keys, generate transactions, and manage smart signatures without leaking secret keys in autonomous loops.
      </BodyText>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, marginBottom: 8 }} id="wm-init">
        1. Initialization
      </h3>
      <CodeBlock lang="python">
{`from trestle_sdk import WalletManager

# Initialize with secret mnemonic
wallet = WalletManager(mnemonic_phrase="your mnemonic...")`}
      </CodeBlock>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, marginBottom: 8 }} id="wm-control">
        2. Account Control
      </h3>
      <BodyText>
        You can inspect agent addresses, query local microALGO balances, and fund auxiliary vaults automatically.
      </BodyText>
      <CodeBlock lang="python">
{`print(f"Agent Address: {wallet.address}")
balance = wallet.get_balance()
print(f"Algod Account Balance: {balance} microALGO")`}
      </CodeBlock>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, marginBottom: 8 }} id="wm-signing">
        3. Transaction Signing
      </h3>
      <BodyText>
        Use the local signer to sign custom TEAL calls or standard Algorand asset transfers.
      </BodyText>
      <CodeBlock lang="python">
{`signed_txn = wallet.sign_transaction(unsigned_txn)
txid = wallet.submit(signed_txn)
print(f"Submitted customized txn: {txid}")`}
      </CodeBlock>
    </div>
  );
}

// 7. Contract Interface: TEAL/ABI Specifications
function AbiView() {
  return (
    <div className="animate-fade-in" style={{ width: "100%" }} id="teal-top">
      <SectionLabel>Contract ABI</SectionLabel>
      <SkewedHeading bg="var(--warning-dim)" fg="var(--text-primary)" angle={-1}>
        TEAL Interface
      </SkewedHeading>

      <BodyText>
        Trestle operates using a TEAL-based ARC-4 compliant application contract written in Python (Puya compiler) and deployed on Algorand Testnet. If you are not using our Python SDK, you can integrate directly using standard transaction builders.
      </BodyText>

      <Callout type="warning" title="Testnet Deployment">
        Current App ID: <strong>{"<YOUR_APP_ID>"}</strong>. Active Contract Escrow Address: <code>{"<YOUR_APP_ADDRESS>"}</code>.
      </Callout>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "24px 0 12px" }} id="abi-specs">
        ABI Method Specifications
      </h3>

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {[
          {
            sig: "register(pay: pay_txn) → void",
            desc: "Opt-in / Register agent. Takes a payment transaction of at least 1,000_000 microALGO (1.00 ALGO) made to the application address to establish the collateral stake. Fails if agent is already registered.",
          },
          {
            sig: "draw(amount: uint64, attestation_hash: byte[32]) → void",
            desc: "Draw credit from the protocol treasury. Triggers an inner transaction sending the ALGO loan to the agent. Validates the Claude Skill cryptographically signed attestation hash in production mode.",
          },
          {
            sig: "repay(pay: pay_txn) → void",
            desc: "Repay outstanding credit (principal + accrued interest). Takes an ABI transaction payment made to the application address. Settle balances and updates state.",
          },
          {
            sig: "slash(agent: address) → void",
            desc: "Slash a delinquent agent. Anyone can trigger this if an agent has outstanding debt and has defaulted (e.g. no payment within 30 rounds). Burns 90% of their stake and sends a 10% reward bounty to the caller.",
          },
          {
            sig: "record_payment(amount: uint64) → uint64",
            desc: "Increments the agent's on-chain payment count. Returns the agent's new derived reputation tier (0 - 3).",
          },
          {
            sig: "get_position(agent: address) → (uint64,uint64,uint64,uint64,uint64,uint64,uint64,uint64,uint64)",
            desc: "Read-only. Returns full position data tuple: (stake_amount, payment_count, tier_max_draw, outstanding, is_defaulted, tier, apr_bps, daily_drawn, repay_by_round).",
          },
        ].map((method) => (
          <div
            key={method.sig}
            style={{
              border: "1px solid var(--bg-border-solid)",
              boxShadow: "var(--shadow-sm)",
              overflow: "hidden",
            }}
          >
            <div style={{ background: "var(--bg-elevated-2)", padding: "10px 16px" }}>
              <span style={{ fontFamily: "var(--mono)", fontSize: 12, fontWeight: "bold", color: "var(--warning)" }}>
                {method.sig}
              </span>
            </div>
            <div
              style={{
                padding: "12px 16px",
                background: "var(--bg-elevated)",
                fontFamily: "var(--font-body)",
                fontSize: 13,
                color: "var(--text-secondary)",
                lineHeight: "1.5",
              }}
            >
              {method.desc}
            </div>
          </div>
        ))}
      </div>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "32px 0 12px" }} id="state-schema">
        On-Chain State Schema
      </h3>
      <CodeBlock lang="Global State Schema (3 × uint64, 1 × bytes)">
{`treasury_balance: UInt64   // Total ALGO funds held in the protocol treasury
total_agents:     UInt64   // Count of opted-in/registered credit agents
skip_attestation: UInt64   // Bypass flag for demo mode (1 = skip attestation check)
protocol_signer:  Account  // Registered public key of the LLM oracle signer`}
      </CodeBlock>
      <CodeBlock lang="Local State Schema (9 × uint64)">
{`stake_amount:       UInt64  // Agent's locked collateral (microALGO)
payment_count:      UInt64  // Total number of recorded off-chain payments
total_repaid:       UInt64  // Cumulative repayments (microALGO)
outstanding:        UInt64  // Current outstanding debt including interest (microALGO)
is_defaulted:       UInt64  // Delinquent flag (1 = defaulted / slashed)
last_payment_round: UInt64  // Block round of agent's last transaction
daily_drawn:        UInt64  // Cumulative microALGO drawn in current daily window
day_start_round:    UInt64  // Start round of the current daily draw window
repay_by_round:     UInt64  // Deadline block round when outstanding must be repaid`}
      </CodeBlock>
    </div>
  );
}

// 8. Contract Interface: Guides & Safety
function GuidesView() {
  return (
    <div className="animate-fade-in" style={{ width: "100%" }} id="guides-top">
      <SectionLabel>Guides & Safety</SectionLabel>
      <SkewedHeading bg="var(--bg-elevated)" fg="var(--text-primary)" angle={1.5}>
        Agent Guides
      </SkewedHeading>

      <BodyText>
        Explore advanced techniques for configuring, protecting, and optimizing credit positions for your autonomous on-chain workflows.
      </BodyText>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, margin: "24px 0 12px" }} id="avoiding-liquidation">
        Avoiding Slashing & Default
      </h3>
      <BodyText>
        Trestle agents are highly optimized for efficiency, but they must keep leverage safe. If your agent draws credit, it must repay outstanding debt before delinquency triggers a slash. Under <code>contract.py</code> rules, a slash can be triggered by <strong>any account</strong> if the agent has outstanding debt &gt; 0 AND either their <code>payment_count == 0</code> OR they have not made an on-chain payment for more than <strong>30 rounds</strong> (approximately 1.5 minutes under Algorand Testnet block speeds). When an agent is slashed, <strong>90% of their staked ALGO collateral is burned</strong> into the protocol treasury, and <strong>10% of their collateral is paid directly to the slasher</strong> as an on-chain bounty. Slashed agents are marked <code>is_defaulted = 1</code>, and their stake is wiped.
      </BodyText>

      <Callout type="danger" title="Security Advisory">
        Never hardcode your main mnemonics or private keys in public repositories. Always use system environment files (<code>.env</code>) loaded through <code>os.getenv</code> or dedicated secret managers.
      </Callout>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 18, margin: "24px 0 12px" }} id="changelog">
        Protocol Changelog
      </h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {[
          { ver: "v2.0.0 (Latest)", date: "May 2026", desc: "Integrate Venice AI credit assessment models. Fast testnet latency reduction to <1.8s. Standardized ARC-4 compliance." },
          { ver: "v1.1.0", date: "April 2026", desc: "Added grade thresholds updates and direct TEAL validation hooks." },
          { ver: "v1.0.0", date: "March 2026", desc: "Initial release of ARC-4 smart contracts and python SDK." },
        ].map((log) => (
          <div
            key={log.ver}
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--bg-border-solid)",
              boxShadow: "var(--shadow-sm)",
              padding: "16px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <span style={{ fontFamily: "var(--mono)", fontWeight: "bold", fontSize: "13px" }}>{log.ver}</span>
              <span style={{ fontFamily: "var(--mono)", fontSize: "11px", color: "var(--text-muted)" }}>{log.date}</span>
            </div>
            <div style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--text-secondary)" }}>{log.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}


// 9. x402 Integration
function X402View() {
  const flowSteps = [
    { n: "01", text: "Agent hits an x402-protected endpoint → gets HTTP 402 with amount + receiver" },
    { n: "02", text: "Agent calls TrestleCreditAgent.draw() with the 402 amount as the draw amount and the resource URL as the task description" },
    { n: "03", text: "Trestle's LLM risk oracle evaluates the x402 resource — same 4 criteria: return must exceed cost + interest, task fits within 24h, no outstanding debt, low/medium risk endpoint" },
    { n: "04", text: "If approved: agent submits ALGO payment to the x402 receiver, retries with X-PAYMENT header, gets the data" },
    { n: "05", text: "After task completes: agent repays Trestle + calls record_payment() — the x402 call becomes on-chain reputation" },
    { n: "06", text: "Repeat. 10 verified x402 payments = Tier 1. 100 = Tier 3 (Elite). The tier history is a provable log of real agentic commerce." },
  ];

  const tiers = [
    { tier: "0 — Fresh",   payments: "0",   draw: "0.10 ALGO", useCase: "sub-cent API calls, price feeds" },
    { tier: "1 — Trusted", payments: "10",  draw: "0.50 ALGO", useCase: "standard data APIs" },
    { tier: "2 — Veteran", payments: "50",  draw: "2.00 ALGO", useCase: "premium compute endpoints" },
    { tier: "3 — Elite",   payments: "100", draw: "5.00 ALGO", useCase: "high-value inference, oracle calls" },
  ];

  return (
    <div className="animate-fade-in" style={{ width: "100%" }} id="x402-top">
      <SectionLabel>Integrations</SectionLabel>

      {/* Page label badge */}
      <div
        style={{
          display: "inline-block",
          background: "var(--brand-end)",
          color: "var(--text-primary)",
          border: "1px solid var(--bg-border-solid)",
          padding: "4px 12px",
          fontFamily: "var(--mono)",
          fontSize: "11px",
          fontWeight: "bold",
          marginBottom: "16px",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        [ HTTP 402 PAYMENT STANDARD ]
      </div>

      <SkewedHeading bg="var(--text-primary)" fg="#ffffff" angle={-1}>
        x402 Integration
      </SkewedHeading>

      <BodyText style={{ maxWidth: 720 }}>
        Trestle is the credit layer that finances x402 API payments for autonomous agents.
      </BodyText>

      <BodyText style={{ maxWidth: 720 }}>
        x402 is an HTTP payment standard: a protected API returns HTTP 402 with payment requirements, the client pays on-chain, retries, and gets the resource. The problem is agents need capital to pay. That's exactly what Trestle solves.
      </BodyText>

      {/* ── How The Flow Works ── */}
      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "32px 0 16px" }} id="x402-flow">
        The Flow
      </h3>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 36 }}>
        {flowSteps.map((step) => (
          <div
            key={step.n}
            style={{
              display: "flex",
              gap: 16,
              alignItems: "flex-start",
              background: step.n === "03" ? "var(--warning-dim)" : "var(--bg-elevated)",
              border: "1px solid var(--bg-border-solid)",
              boxShadow: "var(--shadow-sm)",
              padding: "16px 20px",
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 900,
                fontSize: 22,
                color: step.n === "03" ? "var(--text-primary)" : "var(--text-muted)",
                minWidth: 38,
                lineHeight: 1,
                paddingTop: 2,
              }}
            >
              {step.n}
            </div>
            <div style={{ fontFamily: "var(--font-body)", fontSize: 14, lineHeight: 1.6, color: "var(--text-secondary)" }}>
              {step.text}
            </div>
          </div>
        ))}
      </div>

      {/* ── Python Code ── */}
      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "32px 0 16px" }} id="x402-python">
        Python — one import away
      </h3>

      <CodeBlock lang="python">
{`from trestle_sdk.x402_client import TrestleX402Client

client = TrestleX402Client(credit_agent=trestle_agent)

# hits x402-protected price feed, funds it via Trestle credit automatically
response = client.get(
    "https://api.prices.io/eth-usd",
    expected_return_microalgo=80_000,
)
print(response.json())  # {"price": 2814.22}
# payment_count++ on-chain. one step closer to Tier 1.`}
      </CodeBlock>

      <Callout type="info" title="Automatic Loop">
        <code>TrestleX402Client</code> handles the full <strong>402 → draw → pay → retry → repay → record_payment</strong> loop automatically. The developer never touches algosdk directly.
      </Callout>

      {/* ── Tier Table ── */}
      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "32px 0 16px" }} id="x402-tiers">
        Tier caps map to x402 pricing tiers
      </h3>

      <div style={{ border: "1px solid var(--bg-border-solid)", boxShadow: "var(--shadow-sm)", overflow: "hidden", marginBottom: 32 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--font-body)", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "var(--bg-elevated-2)", color: "var(--brand-end)", borderBottom: "1px solid var(--bg-border-solid)" }}>
              {["Tier", "Payments", "Max Draw", "x402 Use Case"].map((h) => (
                <th
                  key={h}
                  style={{
                    padding: "12px 16px",
                    textAlign: "left",
                    fontFamily: "var(--font-display)",
                    fontWeight: 900,
                    fontSize: 12,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tiers.map((row, idx) => (
              <tr
                key={row.tier}
                style={{
                  background: idx % 2 === 0 ? "var(--bg-elevated)" : "var(--bg-elevated-2)",
                  borderBottom: idx === tiers.length - 1 ? "none" : "1px solid var(--bg-border-solid)",
                }}
              >
                <td style={{ padding: "12px 16px", fontFamily: "var(--mono)", fontWeight: 900, color: idx === 3 ? "var(--success)" : "var(--text-primary)" }}>{row.tier}</td>
                <td style={{ padding: "12px 16px", fontFamily: "var(--mono)" }}>{row.payments}</td>
                <td style={{ padding: "12px 16px", fontFamily: "var(--mono)", fontWeight: 500 }}>{row.draw}</td>
                <td style={{ padding: "12px 16px", fontFamily: "var(--font-body)", fontSize: 13, color: "var(--text-secondary)" }}>{row.useCase}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Install ── */}
      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "32px 0 16px" }} id="x402-install">
        Installation
      </h3>

      <BodyText>
        Install the <code>x402-avm</code> Python package alongside the Trestle SDK:
      </BodyText>

      <CodeBlock lang="bash">
{`pip install trestle-sdk "x402-avm[avm,httpx]"`}
      </CodeBlock>

      <Callout type="warning" title="Testnet Note">
        x402 integration is fully functional on Algorand Testnet. App ID: <strong>{"<YOUR_APP_ID>"}</strong>. Each successful x402 payment increments <code>payment_count</code> on-chain and counts toward tier progression.
      </Callout>
    </div>
  );
}


// 10. Intent Router View
function IntentsView() {
  const routerFlow = [
    { n: "01", text: "User1 locks ALGO into the TrestleIntentRouter contract representing a swap order (e.g. 0.20 ALGO to USDC, with a specified private solver address and expiry round)." },
    { n: "02", text: "Agent2 (solver) polls the indexer logs, detects the private intent, and parses the intent ID and parameters." },
    { n: "03", text: "Agent2's IntentBrain runs local pre-flight checks (profit ratio, time headroom, tier caps, debt checks) and then queries the Venice/Anthropic LLM oracle." },
    { n: "04", text: "Agent2 draws credit from Trestle core contract via TrestleCreditAgent.draw()." },
    { n: "05", text: "Agent2 claims the intent on the Router contract via borrow_to_execute()." },
    { n: "06", text: "Agent2 executes the swap (calling Tinyman v2 AMM or mock equivalent)." },
    { n: "07", text: "Agent2 calls Router.settle() which atomically repays Trestle, sends solver profit, records payment to increment solver's on-chain count, and logs the result." }
  ];

  return (
    <div className="animate-fade-in" style={{ width: "100%" }} id="intents-top">
      <SectionLabel>Integrations</SectionLabel>

      <div
        style={{
          display: "inline-block",
          background: "var(--brand-end)",
          color: "var(--text-primary)",
          border: "1px solid var(--bg-border-solid)",
          padding: "4px 12px",
          fontFamily: "var(--mono)",
          fontSize: "11px",
          fontWeight: "bold",
          marginBottom: "16px",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        [ INTENT ROUTER MARKET ]
      </div>

      <SkewedHeading bg="var(--text-primary)" fg="#ffffff" angle={-1}>
        Intent Router
      </SkewedHeading>

      <BodyText style={{ maxWidth: 720 }}>
        TrestleIntentRouter is Algorand's first intent-based swap solver market, inspired by NEAR Intents and Across Protocol, utilizing Trestle credit to fund solvers.
      </BodyText>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "32px 0 16px" }} id="intents-arch">
        System Architecture
      </h3>
      <BodyText>
        Solver agents don't need upfront capital. They borrow microALGO from Trestle, perform the intent fulfillment, and settle atomically.
      </BodyText>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 36 }}>
        {routerFlow.map((step) => (
          <div
            key={step.n}
            style={{
              display: "flex",
              gap: 16,
              alignItems: "flex-start",
              background: step.n === "03" || step.n === "07" ? "var(--success-dim)" : "var(--bg-elevated)",
              border: "1px solid var(--bg-border-solid)",
              boxShadow: "var(--shadow-sm)",
              padding: "16px 20px",
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 900,
                fontSize: 22,
                color: step.n === "03" || step.n === "07" ? "var(--brand-end)" : "var(--text-muted)",
                minWidth: 38,
                lineHeight: 1,
                paddingTop: 2,
              }}
            >
              {step.n}
            </div>
            <div style={{ fontFamily: "var(--font-body)", fontSize: 14, lineHeight: 1.6, color: "var(--text-secondary)" }}>
              {step.text}
            </div>
          </div>
        ))}
      </div>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "32px 0 16px" }} id="intents-solver">
        The Solver Agent Code
      </h3>
      <BodyText>
        Solvers use <code>IntentListener</code>, <code>IntentBrain</code>, and <code>IntentExecutor</code> modules to manage intents and execute settlements automatically.
      </BodyText>
      <CodeBlock lang="python">
{`from trestle_sdk.intent_agent import IntentListener, IntentBrain, IntentExecutor

# Initialize three-layer agent stack
listener = IntentListener(router_app_id=YOUR_ROUTER_APP_ID, solver_address=agent.address)
brain = IntentBrain(agent=trestle_agent, min_profit_ratio=0.10)
executor = IntentExecutor(agent=trestle_agent, router_app_id=YOUR_ROUTER_APP_ID, task_handler=swap_handler, brain=brain)

# Start polling indexer for private solver orders
listener.run_forever(on_intent_callback=executor.handle_intent)`}
      </CodeBlock>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "32px 0 16px" }} id="intents-settle">
        Atomic Settle Contract Call
      </h3>
      <BodyText>
        The Router contract's <code>settle()</code> method performs 4 operations atomically:
      </BodyText>
      <CodeBlock lang="TEAL Inner Transactions">
{`// 1. Repay Trestle core credit + accrued interest (Payment Txn to App Address)
// 2. Pay solver profit (Payment Txn to Solver Wallet)
// 3. Call record_payment(api_cost) on Trestle contract to increment reputation tier
// 4. Log results on-chain for verification`}
      </CodeBlock>

      <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: 20, margin: "32px 0 16px" }} id="intents-demo">
        Running the Demo
      </h3>
      <BodyText>
        Deploy the router and run the local intent solver demo on Algorand testnet:
      </BodyText>
      <CodeBlock lang="bash">
{`# 1. Deploy the router contract
ADMIN_MNEMONIC="..." TRESTLE_APP_ID=<YOUR_APP_ID> python contracts/deploy_router.py

# 2. Run the intent solver lifecycle demo
python demo/SDK_DEMO.py`}
      </CodeBlock>
    </div>
  );
}


/* ── Fallback Placeholder ── */
function Placeholder({ section }) {
  return (
    <div className="animate-fade-in" style={{ textAlign: "center", paddingTop: 80 }}>
      <div style={{ fontFamily: "var(--mono)", fontSize: 48, marginBottom: 16 }}>📄</div>
      <SkewedHeading bg="var(--text-primary)" fg="#ffffff">{section}</SkewedHeading>
      <BodyText style={{ color: "var(--text-muted)", marginTop: "16px" }}>This section is coming soon.</BodyText>
    </div>
  );
}


/* ── Router PAGE_MAP ── */
const PAGE_MAP = {
  introduction: (p) => <Introduction onNavigate={p.onNavigate} />,
  quickstart: () => <QuickStart />,
  installation: () => <InstallationView />,
  protocol: () => <ProtocolView />,
  "security-model": () => <OracleReferenceDocs />,
  sdk: () => <TrestleCreditAgentDocs />,
  "wallet-manager": () => <WalletManagerView />,
  abi: () => <AbiView />,
  guides: () => <GuidesView />,
  x402: () => <X402View />,
  intents: () => <IntentsView />,
};

export default function DocsContent({ activePage, onNavigate }) {
  const Render = PAGE_MAP[activePage];
  if (Render) return Render({ onNavigate });
  return <Placeholder section={activePage?.replace(/-/g, " ") || "Section"} />;
}
