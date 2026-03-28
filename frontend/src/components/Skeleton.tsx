"use client";

// Reusable loading skeleton components for professional async states

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="card animate-pulse space-y-3">
      <div className="h-4 bg-jungle-deeper rounded w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-3 bg-jungle-deeper rounded" style={{ width: `${70 + Math.random() * 30}%` }} />
      ))}
    </div>
  );
}

export function SkeletonChart({ height = 120 }: { height?: number }) {
  return (
    <div className="card animate-pulse">
      <div className="h-4 bg-jungle-deeper rounded w-1/4 mb-3" />
      <div className="bg-jungle-deeper rounded-lg" style={{ height }} />
    </div>
  );
}

export function SkeletonForm({ fields = 4 }: { fields?: number }) {
  return (
    <div className="space-y-4 animate-pulse">
      {Array.from({ length: fields }).map((_, i) => (
        <div key={i}>
          <div className="h-3 bg-jungle-deeper rounded w-20 mb-1.5" />
          <div className="h-10 bg-jungle-deeper rounded-lg" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonList({ items = 5 }: { items?: number }) {
  return (
    <div className="space-y-2 animate-pulse">
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-3 bg-jungle-card rounded-xl border border-jungle-border">
          <div className="w-10 h-10 bg-jungle-deeper rounded-full shrink-0" />
          <div className="flex-1 space-y-1.5">
            <div className="h-3 bg-jungle-deeper rounded w-2/3" />
            <div className="h-2.5 bg-jungle-deeper rounded w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}
