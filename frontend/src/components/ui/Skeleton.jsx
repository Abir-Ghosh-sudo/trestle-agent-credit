/**
 * Skeleton.jsx — Shimmer loading placeholder.
 *
 * Renders a pulsing shimmer rectangle for loading states.
 */

import React from "react";

export default function Skeleton({
  width = "100%",
  height = 20,
  borderRadius = 6,
  className = "",
}) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{
        width,
        height,
        borderRadius,
      }}
    />
  );
}

/**
 * SkeletonStatCard — Full skeleton replacement for StatCard
 */
export function SkeletonStatCard({ className = "" }) {
  return (
    <div className={`glass-panel p-4 flex flex-col gap-2 ${className}`}>
      <Skeleton width={80} height={12} />
      <Skeleton width={120} height={28} />
      <Skeleton width={40} height={12} />
    </div>
  );
}
