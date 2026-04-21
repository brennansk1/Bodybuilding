"use client";

// Circular progress ring for training session completion
// Compact and gym-friendly — shows at a glance how far through the workout you are

interface SessionProgressRingProps {
  completed: number;
  total: number;
  size?: number;
}

export default function SessionProgressRing({
  completed,
  total,
  size = 48,
}: SessionProgressRingProps) {
  const pct = total > 0 ? completed / total : 0;
  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct);

  const isDone = completed === total && total > 0;
  // Read from CSS custom props so a theme swap flows through automatically.
  const strokeColor = isDone ? "var(--viltrum-success)" : "var(--viltrum-accent)";

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Session progress: ${completed} of ${total} sets completed`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <title>{`${completed} / ${total} sets`}</title>
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--viltrum-border)"
          strokeWidth="3"
        />
        {/* Progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={strokeColor}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-500"
        />
      </svg>
      <span
        className="absolute text-[10px] font-bold"
        style={{
          color: isDone ? "var(--viltrum-success)" : "var(--viltrum-accent)",
        }}
      >
        {isDone ? "✓" : `${completed}`}
      </span>
    </div>
  );
}
