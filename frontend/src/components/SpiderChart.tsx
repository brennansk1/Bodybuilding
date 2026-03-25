"use client";

// Pure SVG radar/spider chart — no external dependencies
interface SpiderChartProps {
  data: { label: string; value: number }[]; // value: 0-100
  size?: number;
  color?: string;
}

export default function SpiderChart({ data, size = 220, color = "#c8a84e" }: SpiderChartProps) {
  if (!data || data.length < 3) return null;

  const cx = size / 2;
  const cy = size / 2;
  const maxRadius = size / 2 - 32;
  const n = data.length;

  const angle = (i: number) => (i * 2 * Math.PI) / n - Math.PI / 2;

  // Normalize visual radius: cap at 110% to prevent auto-scale distortion.
  // Without this, a 130% chest would crush 70% calves toward the center.
  const maxVisual = 110;
  const toXY = (i: number, value: number) => {
    const clamped = Math.min(value, maxVisual);
    return {
      x: cx + maxRadius * (clamped / maxVisual) * Math.cos(angle(i)),
      y: cy + maxRadius * (clamped / maxVisual) * Math.sin(angle(i)),
    };
  };

  const outerXY = (i: number) => ({
    x: cx + (maxRadius + 18) * Math.cos(angle(i)),
    y: cy + (maxRadius + 18) * Math.sin(angle(i)),
  });

  const gridLevels = [0.25, 0.5, 0.75, 1.0];
  const gridPolygon = (level: number) =>
    Array.from({ length: n }, (_, i) => {
      const p = {
        x: cx + maxRadius * level * Math.cos(angle(i)),
        y: cy + maxRadius * level * Math.sin(angle(i)),
      };
      return `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
    }).join(" ") + " Z";

  const dataPath =
    data
      .map((d, i) => {
        const p = toXY(i, d.value);
        return `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
      })
      .join(" ") + " Z";

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Grid polygons */}
      {gridLevels.map((level) => (
        <path
          key={level}
          d={gridPolygon(level)}
          fill="none"
          stroke="#1a3328"
          strokeWidth={level === 1 ? 1.5 : 0.75}
        />
      ))}

      {/* Axis lines */}
      {Array.from({ length: n }, (_, i) => {
        const p = toXY(i, 100);
        return (
          <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="#1a3328" strokeWidth="0.75" />
        );
      })}

      {/* Data fill */}
      <path d={dataPath} fill={color + "28"} stroke={color} strokeWidth="1.5" strokeLinejoin="round" />

      {/* Data points */}
      {data.map((d, i) => {
        const p = toXY(i, d.value);
        return <circle key={i} cx={p.x} cy={p.y} r="3" fill={color} />;
      })}

      {/* Labels */}
      {data.map((d, i) => {
        const lp = outerXY(i);
        const textAnchor = lp.x < cx - 8 ? "end" : lp.x > cx + 8 ? "start" : "middle";
        const scoreColor =
          d.value >= 95 ? "#4ade80" : d.value >= 80 ? "#a3e635" : d.value >= 60 ? "#c8a84e" : "#ef4444";

        return (
          <g key={i}>
            <text
              x={lp.x}
              y={lp.y - 4}
              textAnchor={textAnchor}
              dominantBaseline="auto"
              fill="#8faa96"
              fontSize="8.5"
              fontWeight="500"
            >
              {d.label}
            </text>
            <text
              x={lp.x}
              y={lp.y + 6}
              textAnchor={textAnchor}
              dominantBaseline="hanging"
              fill={scoreColor}
              fontSize="8"
              fontWeight="700"
            >
              {Math.round(d.value)}%
            </text>
          </g>
        );
      })}

      {/* Ring labels */}
      <text
        x={cx + 3}
        y={cy - maxRadius * (50 / maxVisual) + 3}
        fill="#5a7a62"
        fontSize="7"
        textAnchor="start"
      >
        50%
      </text>
      <text
        x={cx + 3}
        y={cy - maxRadius * (100 / maxVisual) + 3}
        fill="#5a7a62"
        fontSize="7"
        textAnchor="start"
      >
        100%
      </text>
    </svg>
  );
}
