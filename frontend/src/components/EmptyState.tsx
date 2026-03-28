"use client";

// Reusable empty state component with actionable CTA

interface EmptyStateProps {
  icon?: string;
  title: string;
  description: string;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
  compact?: boolean;
}

export default function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  actionHref,
  onAction,
  compact = false,
}: EmptyStateProps) {
  const Action = actionHref ? "a" : "button";

  return (
    <div className={`text-center ${compact ? "py-6" : "py-10"}`}>
      {icon && (
        <div className={`${compact ? "text-2xl" : "text-3xl"} mb-2`}>{icon}</div>
      )}
      <p className={`font-medium text-jungle-muted ${compact ? "text-sm" : "text-base"}`}>
        {title}
      </p>
      <p className={`text-jungle-dim mt-1 ${compact ? "text-xs" : "text-sm"}`}>
        {description}
      </p>
      {(actionLabel && (actionHref || onAction)) && (
        <Action
          href={actionHref}
          onClick={onAction}
          className="btn-primary inline-block mt-4 text-sm"
        >
          {actionLabel}
        </Action>
      )}
    </div>
  );
}
