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
  const strokeColor = isDone ? "#4ade80" : "#c8a84e";

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#1a3328"
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
      <span className={`absolute text-[10px] font-bold ${isDone ? "text-green-400" : "text-jungle-accent"}`}>
        {isDone ? "✓" : `${completed}`}
      </span>
    </div>
  );
}
