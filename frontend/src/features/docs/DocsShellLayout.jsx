/**
 * DocsShellLayout.jsx — Three-column docs shell (Obsidian dark theme).
 * Left: search-enabled sidebar nav, grouped, with active-page highlight.
 * Center: max-800px scrollable content column.
 * Right: sticky "On this page" TOC + support card.
 */

import React, { useState, useEffect } from "react";
import {
  Search, Zap, Download, Landmark, ShieldCheck, Code2, Wallet,
  FileText, Compass, CreditCard, Repeat, Menu, X, MessageCircle,
} from "lucide-react";

// Maps the legacy Material-Symbols icon names used in NAV_GROUPS to lucide icons
const ICON_MAP = {
  bolt: Zap,
  install_desktop: Download,
  architecture: Landmark,
  security: ShieldCheck,
  code_blocks: Code2,
  account_balance_wallet: Wallet,
  article: FileText,
  explore: Compass,
  payments: CreditCard,
  swap_calls: Repeat,
};

// Navigation Groups
const NAV_GROUPS = [
  {
    title: "GETTING STARTED",
    isHighlighted: false,
    items: [
      { id: "introduction", label: "Quickstart", icon: "bolt" },
      { id: "installation", label: "Installation", icon: "install_desktop" }
    ]
  },
  {
    title: "PROTOCOL",
    isHighlighted: false,
    items: [
      { id: "protocol", label: "Architecture", icon: "architecture" },
      { id: "security-model", label: "Security Model", icon: "security" }
    ]
  },
  {
    title: "SDK REFERENCE",
    isHighlighted: true, // Slanted yellow header badge-chip
    items: [
      { id: "sdk", label: "TrestleCreditAgent", icon: "code_blocks", hasSubMenu: true },
      { id: "wallet-manager", label: "WalletManager", icon: "account_balance_wallet" }
    ]
  },
  {
    title: "CONTRACT INTERFACE",
    isHighlighted: false,
    items: [
      { id: "abi", label: "TEAL / ABI Specs", icon: "article" },
      { id: "guides", label: "Guides & Safety", icon: "explore" }
    ]
  },
  {
    title: "INTEGRATIONS",
    isHighlighted: false,
    items: [
      { id: "x402", label: "x402 Integration", icon: "payments" },
      { id: "intents", label: "Intent Router", icon: "swap_calls" }
    ]
  }
];

// Dynamic Table of Contents (TOC) matching each page's actual heading sections
const TOC_MAP = {
  introduction: [
    { label: "What is Trestle?", href: "#what-is-trestle" },
    { label: "Live Simulation", href: "#live-sim" },
    { label: "Protocol Stats", href: "#protocol-stats" }
  ],
  quickstart: [
    { label: "Prerequisites", href: "#prerequisites" },
    { label: "Step 1. Clone SDK", href: "#clone-sdk" },
    { label: "Step 2. Environment", href: "#setup-env" },
    { label: "Step 3. Run Demo", href: "#run-demo" }
  ],
  installation: [
    { label: "Installation", href: "#install-top" },
    { label: "Pip Package", href: "#pip-package" },
    { label: "Optional Extras", href: "#optional-extras" },
    { label: "Verification", href: "#verify-install" }
  ],
  protocol: [
    { label: "Economic Engine", href: "#core-engine" },
    { label: "State Transitions", href: "#states" },
    { label: "Credit Grades", href: "#credit-grades" }
  ],
  "security-model": [
    { label: "Trust Engine", href: "#trust-engine" },
    { label: "How It Works", href: "#how-it-works" },
    { label: "Oracle Response", href: "#oracle-response" },
    { label: "Signature Verification", href: "#sig-verification" }
  ],
  sdk: [
    { label: "Constructor", href: "#constructor" },
    { label: "Methods Overview", href: "#methods" },
    { label: "draw()", href: "#draw", isSub: true },
    { label: "repay()", href: "#repay", isSub: true },
    { label: "slash()", href: "#slash", isSub: true },
    { label: "get_position()", href: "#get_position", isSub: true }
  ],
  "wallet-manager": [
    { label: "WalletManager", href: "#wm-top" },
    { label: "Initialization", href: "#wm-init" },
    { label: "Account Control", href: "#wm-control" },
    { label: "Signing Transactions", href: "#wm-signing" }
  ],
  abi: [
    { label: "TEAL Interface", href: "#teal-top" },
    { label: "ABI Specifications", href: "#abi-specs" },
    { label: "State Schema", href: "#state-schema" }
  ],
  guides: [
    { label: "Safety Guides", href: "#guides-top" },
    { label: "Avoiding Liquidation", href: "#avoiding-liquidation" },
    { label: "Changelog", href: "#changelog" }
  ],
  x402: [
    { label: "x402 Integration", href: "#x402-top" },
    { label: "The Flow", href: "#x402-flow" },
    { label: "Python Client", href: "#x402-python" },
    { label: "Tier Caps", href: "#x402-tiers" },
    { label: "Installation", href: "#x402-install" }
  ],
  intents: [
    { label: "Intent Router", href: "#intents-top" },
    { label: "Architecture", href: "#intents-arch" },
    { label: "Solver Agent", href: "#intents-solver" },
    { label: "Atomic Settle", href: "#intents-settle" },
    { label: "Running the Demo", href: "#intents-demo" }
  ]
};

export default function DocsShellLayout({ activePage, onNavigate, children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Auto-scroll to hash when loaded/navigated
  useEffect(() => {
    if (window.location.hash) {
      const id = window.location.hash.substring(1);
      const element = document.getElementById(id);
      if (element) {
        setTimeout(() => {
          element.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 100);
      }
    }
  }, [activePage]);

  // Handle Search Filtering
  const filteredGroups = NAV_GROUPS.map((group) => {
    const items = group.items.filter((item) =>
      item.label.toLowerCase().includes(searchQuery.toLowerCase())
    );
    return { ...group, items };
  }).filter((group) => group.items.length > 0);

  const tocItems = TOC_MAP[activePage] || [];
  const activeItem = NAV_GROUPS.flatMap((g) => g.items).find((i) => i.id === activePage);
  const activeGroup = NAV_GROUPS.find((g) => g.items.some((i) => i.id === activePage));

  return (
    <div className="flex min-h-[calc(100vh-80px)] relative bg-transparent text-text-primary">

      {/* ── Mobile hamburger ── */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="docs-mobile-fab lift-active hidden fixed bottom-5 right-5 z-[200] w-12 h-12 rounded-full bg-brand-gradient shadow-glow-accent items-center justify-center text-white"
        aria-label="Toggle docs navigation"
        aria-expanded={mobileOpen}
      >
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* ── Sidebar ── */}
      <aside
        className="docs-sidebar w-[280px] min-w-[280px] border-r border-border sticky top-20 h-[calc(100vh-80px)] overflow-y-auto shrink-0 z-10 flex flex-col p-6"
      >
        {/* Search Input Box */}
        <div className="mb-8">
          <div className="relative glass-panel !shadow-soft-sm">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted" strokeWidth={2.25} />
            <input
              className="w-full bg-transparent border-none pl-10 pr-4 py-3 font-label-mono text-[12px] focus:ring-0 focus:outline-none placeholder:text-text-muted text-text-primary"
              placeholder="Search docs..."
              type="text"
              aria-label="Search documentation"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {/* Hierarchical Navigation list */}
        <nav className="flex flex-col gap-6 font-label-mono text-[12px]" aria-label="Documentation">
          {filteredGroups.length === 0 && (
            <p className="text-text-muted text-[13px] font-body px-1">No results for "{searchQuery}"</p>
          )}
          {filteredGroups.map((group) => (
            <div key={group.title}>
              {/* Group Title Badge */}
              {group.isHighlighted ? (
                <div className="text-accent-hover mb-2 font-bold tracking-widest bg-accent-dim inline-block px-2 py-1 rounded-md border border-accent/25 text-[11px]">
                  {group.title}
                </div>
              ) : (
                <div className="text-text-muted mb-2 font-bold tracking-widest text-[11px]">
                  {group.title}
                </div>
              )}

              {/* Group Items */}
              <div className="flex flex-col gap-1 mt-1">
                {group.items.map((item) => {
                  const isActive = activePage === item.id;
                  const Icon = ICON_MAP[item.icon] || FileText;

                  if (isActive && item.hasSubMenu) {
                    return (
                      <div key={item.id} className="flex flex-col gap-1">
                        <button
                          onClick={() => onNavigate(item.id)}
                          aria-current="page"
                          className="py-2.5 px-3 rounded-lg flex items-center gap-2.5 bg-brand-gradient shadow-glow-accent font-bold text-white text-left w-full cursor-pointer"
                        >
                          <Icon size={15} strokeWidth={2.25} />
                          {item.label}
                        </button>

                        {/* Sub Menu Links */}
                        <div className="flex flex-col gap-0.5 ml-6 mt-1 text-[11px] text-text-secondary border-l border-border pl-3">
                          <a className="hover:text-text-primary hover:underline py-1 transition-all" href="#constructor">constructor</a>
                          <a className="hover:text-text-primary hover:underline py-1 transition-all" href="#draw">draw()</a>
                          <a className="hover:text-text-primary hover:underline py-1 transition-all" href="#repay">repay()</a>
                          <a className="hover:text-text-primary hover:underline py-1 transition-all" href="#slash">slash()</a>
                          <a className="hover:text-text-primary hover:underline py-1 transition-all" href="#get_position">get_position()</a>
                          <a className="text-danger hover:underline py-1 font-bold transition-all" href="#exceptions">TrestleCreditDenied</a>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        onNavigate(item.id);
                        setMobileOpen(false);
                      }}
                      aria-current={isActive ? "page" : undefined}
                      className={[
                        "py-2.5 px-3 rounded-lg flex items-center gap-2.5 transition-all w-full text-left cursor-pointer font-label-mono text-[12px]",
                        isActive
                          ? "bg-brand-gradient text-white font-bold shadow-glow-accent"
                          : "text-text-secondary hover:text-text-primary hover:bg-elevated font-medium",
                      ].join(" ")}
                    >
                      <Icon size={15} strokeWidth={2.25} />
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      {/* ── Main Layout Wrapper ── */}
      <main className="flex-1 flex min-w-0">
        {/* Center Column for actual documentation content */}
        <div className="docs-center-content flex-1 max-w-[800px] min-w-0 px-12 py-12">
          {/* Breadcrumb / page context header */}
          {activeGroup && activeItem && (
            <div className="mb-8 flex items-center gap-2 font-pixel text-[11px] uppercase tracking-widest text-text-muted">
              <span>{activeGroup.title}</span>
              <span className="text-border-strong">/</span>
              <span className="text-accent-hover">{activeItem.label}</span>
            </div>
          )}
          {children}
        </div>

        {/* Right Sticky TOC (Desktop Only) */}
        {tocItems.length > 0 && (
          <aside className="docs-toc hidden lg:block w-[220px] min-w-[220px] px-6 py-12 sticky top-20 h-[calc(100vh-80px)] overflow-y-auto">
            <div className="font-label-mono text-[12px] font-bold mb-4 border-b border-border pb-2 text-text-primary select-none">
              ON THIS PAGE
            </div>

            <ul className="font-body-md text-[13px] space-y-3 list-none p-0 m-0">
              {tocItems.map((toc) => (
                <li key={toc.href} className={toc.isSub ? "pl-3 border-l border-border" : ""}>
                  <a
                    className="hover:text-accent-hover hover:underline hover:bg-elevated-2 hover:px-1 py-0.5 text-text-secondary transition-all block text-ellipsis overflow-hidden whitespace-nowrap rounded"
                    href={toc.href}
                  >
                    {toc.label}
                  </a>
                </li>
              ))}
            </ul>

            {/* Discord Help Widget */}
            <div className="mt-12 glass-panel p-4">
              <div className="font-label-mono text-[10px] font-bold mb-2 text-text-primary flex items-center gap-1.5">
                <MessageCircle size={13} strokeWidth={2.25} /> NEED HELP?
              </div>
              <p className="text-[11px] mb-3 text-text-secondary leading-normal">
                Join the community for SDK support.
              </p>
              <button
                onClick={() => window.open("https://discord.com", "_blank")}
                className="w-full bg-brand-gradient text-white font-label-mono py-2 text-[10px] rounded-lg lift-hover lift-active cursor-pointer uppercase font-bold"
              >
                Discord →
              </button>
            </div>
          </aside>
        )}
      </main>

      {/* Mobile Responsiveness Rules */}
      <style>{`
        @media (max-width: 768px) {
          .docs-mobile-fab { display: flex !important; }
          .docs-sidebar {
            display: ${mobileOpen ? "flex" : "none"} !important;
            position: fixed !important;
            top: 56px !important;
            left: 0;
            width: 100% !important;
            height: calc(100vh - 56px) !important;
            z-index: 150;
            background: var(--bg-void) !important;
            border-right: none !important;
          }
          .docs-center-content { padding: 24px 20px !important; }
        }
      `}</style>
    </div>
  );
}
