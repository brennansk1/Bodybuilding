"use client";

// Pure SVG line chart — no external dependencies
interface MiniLineChartProps {
  data: { label: string; value: number }[];
  height?: number;
  color?: string;
  domain?: [number, number]; // [min, max] — auto if omitted
  showPoints?: boolean;
  bandMin?: number; // optional horizontal band (e.g. tier floor)
  bandMax?: number;
  bandColor?: string;
}

export default function MiniLineChart({
  data,
  height = 120,
  color = "#c8a84e",
  domain,
  showPoints = true,
  bandMin,
  bandMax,
  bandColor = "#c8a84e22",
}: MiniLineChartProps) {
  if (!data || data.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-jungle-dim text-xs border border-dashed border-jungle-border rounded-lg"
        style={{ height }}
      >
        Not enough data
      </div>
    );
  }

  const vW = 240;
  const vH = height;
  const pad = { top: 8, right: 6, bottom: 20, left: 28 };
  const plotW = vW - pad.left - pad.right;
  const plotH = vH - pad.top - pad.bottom;

  const values = data.map((d) => d.value);
  const minVal = domain ? domain[0] : Math.floor(Math.min(...values) * 0.97);
  const maxVal = domain ? domain[1] : Math.ceil(Math.max(...values) * 1.03);
  const range = maxVal - minVal || 1;

  const xPos = (i: number) => pad.left + (i / (data.length - 1)) * plotW;
  const yPos = (v: number) => pad.top + plotH - ((v - minVal) / range) * plotH;

  const linePath = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${xPos(i).toFixed(1)} ${yPos(d.value).toFixed(1)}`)
    .join(" ");

  const areaPath = `${linePath} L ${xPos(data.length - 1).toFixed(1)} ${(pad.top + plotH).toFixed(1)} L ${xPos(0).toFixed(1)} ${(pad.top + plotH).toFixed(1)} Z`;

  const yLabels = [minVal, Math.round((minVal + maxVal) / 2), maxVal];

  // Determine which x labels to show (avoid crowding)
  const maxLabels = Math.min(6, data.length);
  const labelStep = Math.ceil(data.length / maxLabels);
  const showLabel = (i: number) =>
    i === 0 || i === data.length - 1 || i % labelStep === 0;

  return (
    <svg viewBox={`0 0 ${vW} ${vH}`} width="100%" height={height}>
      {/* Optional tier band */}
      {bandMin !== undefined && bandMax !== undefined && (
        <rect
          x={pad.left}
          y={yPos(bandMax)}
          width={plotW}
          height={yPos(bandMin) - yPos(bandMax)}
          fill={bandColor}
        />
      )}

      {/* Grid lines */}
      {[0, 0.5, 1].map((t) => {
        const y = pad.top + plotH * (1 - t);
        return (
          <line
            key={t}
            x1={pad.left}
            y1={y}
            x2={vW - pad.right}
            y2={y}
            stroke="#1a3328"
            strokeWidth="0.75"
          />
        );
      })}

      {/* Y-axis labels */}
      {yLabels.map((val, j) => {
        const t = (val - minVal) / range;
        const y = pad.top + plotH * (1 - t);
        return (
          <text
            key={j}
            x={pad.left - 3}
            y={y}
            textAnchor="end"
            dominantBaseline="middle"
            fill="#5a7a62"
            fontSize="7.5"
          >
            {val}
          </text>
        );
      })}

      {/* Area fill */}
      <path d={areaPath} fill={color + "1a"} />

      {/* Line */}
      <path
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth="1.75"
        strokeLinejoin="round"
        strokeLinecap="round"
      />

      {/* Points and x-labels */}
      {data.map((d, i) => (
        <g key={i}>
          {showPoints && (
            <circle cx={xPos(i)} cy={yPos(d.value)} r="2.5" fill={color} />
          )}
          {showLabel(i) && (
            <text
              x={xPos(i)}
              y={vH - 3}
              textAnchor="middle"
              fill="#5a7a62"
              fontSize="6.5"
            >
              {d.label.length > 6 ? d.label.slice(-5) : d.label}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}
