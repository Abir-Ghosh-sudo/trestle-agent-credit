/**
 * TabBar.jsx — Segmented glass tab control: "Position" | "Score"
 *
 * Active tab: gradient pill background
 * Inactive: muted text, hover lift
 */

import React from "react";

const TABS = [
  { id: "position", label: "Position" },
  { id: "score", label: "Score" },
  { id: "payment", label: "⚡ x402" },
];

export default function SegmentedTabs({ activeTab, onTabChange }) {
  return (
    <div className="inline-flex p-1 rounded-full bg-elevated backdrop-blur border border-border gap-1">
      {TABS.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            onClick={() => onTabChange(tab.id)}
            className={[
              "px-5 py-2 rounded-full font-sans font-semibold text-sm transition-all duration-200",
              isActive
                ? "bg-brand-gradient text-white shadow-soft-sm"
                : "text-text-muted hover:text-text-secondary",
            ].join(" ")}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
