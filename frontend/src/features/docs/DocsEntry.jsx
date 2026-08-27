/**
 * DocsEntry.jsx — Top-level docs wrapper.
 * Combines DocsShellLayout + DocsContent.
 */
import React, { useState } from "react";
import DocsShellLayout from "./DocsShellLayout.jsx";
import DocsContent from "./DocsContent.jsx";

export default function DocsEntry() {
  const [activePage, setActivePage] = useState("introduction");

  return (
    <DocsShellLayout activePage={activePage} onNavigate={setActivePage}>
      <DocsContent activePage={activePage} onNavigate={setActivePage} />
    </DocsShellLayout>
  );
}
