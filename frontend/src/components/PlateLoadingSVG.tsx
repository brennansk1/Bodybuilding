"use client";

// ─── Plate Loading Visual ───────────────────────────────────────────────────
// Shows a cheat-sheet SVG of how to load plates for a given weight.
// Supports barbell, dumbbell, and machine equipment types.
// Automatically switches between kg and lbs standard plate sizes.

interface PlateLoadingSVGProps {
  targetWeight: number; // in the display unit
  equipment: string;    // "barbell" | "dumbbell" | "machine" | "cable" etc.
  useLbs: boolean;
}

// ─── Standard plate configs ─────────────────────────────────────────────────

interface PlateConfig {
  weight: number;
  color: string;
  textColor: string;
  height: number; // relative height in SVG units
}

const KG_PLATES: PlateConfig[] = [
  { weight: 25,   color: "#dc2626", textColor: "#fff", height: 50 },
  { weight: 20,   color: "#2563eb", textColor: "#fff", height: 48 },
  { weight: 15,   color: "#eab308", textColor: "#000", height: 44 },
  { weight: 10,   color: "#16a34a", textColor: "#fff", height: 40 },
  { weight: 5,    color: "#fff",    textColor: "#000", height: 34 },
  { weight: 2.5,  color: "#ef4444", textColor: "#fff", height: 28 },
  { weight: 1.25, color: "#9ca3af", textColor: "#000", height: 24 },
];

const LBS_PLATES: PlateConfig[] = [
  { weight: 45,  color: "#2563eb", textColor: "#fff", height: 50 },
  { weight: 35,  color: "#eab308", textColor: "#000", height: 46 },
  { weight: 25,  color: "#16a34a", textColor: "#fff", height: 42 },
  { weight: 10,  color: "#fff",    textColor: "#000", height: 36 },
  { weight: 5,   color: "#ef4444", textColor: "#fff", height: 30 },
  { weight: 2.5, color: "#9ca3af", textColor: "#000", height: 24 },
];

function calculatePlates(
  targetWeight: number,
  barWeight: number,
  plateConfigs: PlateConfig[]
): PlateConfig[] {
  const plates: PlateConfig[] = [];
  let remaining = Math.max(0, (targetWeight - barWeight) / 2);
  for (const config of plateConfigs) {
    while (remaining >= config.weight - 0.001) {
      plates.push(config);
      remaining -= config.weight;
      remaining = Math.round(remaining * 1000) / 1000;
    }
  }
  return plates;
}

// ─── Machine weight stack ───────────────────────────────────────────────────

const MACHINE_INCREMENTS_LBS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250, 260, 280, 300];
const MACHINE_INCREMENTS_KG = [2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100, 110, 120, 130, 140, 150];

// ─── SVG Components ─────────────────────────────────────────────────────────

function BarbellSVG({ plates, barWeight, unit }: { plates: PlateConfig[]; barWeight: number; unit: string }) {
  const totalWidth = 280;
  const centerY = 50;
  const barLength = 240;
  const plateStartX = 40;
  const plateWidth = 10;
  const plateGap = 2;

  return (
    <svg viewBox={`0 0 ${totalWidth} 100`} className="w-full max-w-xs" role="img" aria-label="Barbell plate loading">
      {/* Bar */}
      <rect x={20} y={centerY - 3} width={barLength} height={6} rx={2} fill="#71717a" />
      {/* Collar left */}
      <rect x={plateStartX - 4} y={centerY - 6} width={4} height={12} rx={1} fill="#a1a1aa" />

      {/* Left plates (mirrored display) */}
      {plates.map((plate, i) => {
        const x = plateStartX + i * (plateWidth + plateGap);
        return (
          <g key={`l${i}`}>
            <rect
              x={x}
              y={centerY - plate.height / 2}
              width={plateWidth}
              height={plate.height}
              rx={2}
              fill={plate.color}
              stroke="#333"
              strokeWidth={0.5}
            />
            <text
              x={x + plateWidth / 2}
              y={centerY + 1}
              textAnchor="middle"
              fontSize={plate.weight >= 10 ? 6 : 5}
              fill={plate.textColor}
              fontWeight="bold"
            >
              {plate.weight}
            </text>
          </g>
        );
      })}

      {/* Right plates (mirror) */}
      {plates.map((plate, i) => {
        const x = totalWidth - 20 - plateStartX + 20 - (i + 1) * (plateWidth + plateGap);
        return (
          <g key={`r${i}`}>
            <rect
              x={x}
              y={centerY - plate.height / 2}
              width={plateWidth}
              height={plate.height}
              rx={2}
              fill={plate.color}
              stroke="#333"
              strokeWidth={0.5}
            />
          </g>
        );
      })}

      {/* Collar right */}
      <rect x={totalWidth - plateStartX} y={centerY - 6} width={4} height={12} rx={1} fill="#a1a1aa" />

      {/* Bar weight label */}
      <text x={totalWidth / 2} y={90} textAnchor="middle" fontSize={8} fill="#a1a1aa">
        Bar: {barWeight}{unit}
      </text>
    </svg>
  );
}

function DumbbellSVG({ weight, unit }: { weight: number; unit: string }) {
  const centerY = 40;
  return (
    <svg viewBox="0 0 120 80" className="w-full max-w-[160px]" role="img" aria-label="Dumbbell weight">
      {/* Left weight block */}
      <rect x={10} y={centerY - 20} width={20} height={40} rx={3} fill="#52525b" stroke="#71717a" strokeWidth={1} />
      {/* Handle */}
      <rect x={30} y={centerY - 5} width={60} height={10} rx={3} fill="#71717a" />
      {/* Grip texture */}
      {[0, 1, 2, 3, 4].map(i => (
        <line key={i} x1={42 + i * 8} y1={centerY - 4} x2={42 + i * 8} y2={centerY + 4} stroke="#a1a1aa" strokeWidth={0.5} />
      ))}
      {/* Right weight block */}
      <rect x={90} y={centerY - 20} width={20} height={40} rx={3} fill="#52525b" stroke="#71717a" strokeWidth={1} />
      {/* Weight label */}
      <text x={60} y={72} textAnchor="middle" fontSize={10} fill="#a1a1aa" fontWeight="bold">
        {weight} {unit}
      </text>
    </svg>
  );
}

function MachineStackSVG({ weight, unit, increments }: { weight: number; unit: string; increments: number[] }) {
  // Find the closest pin position
  const closest = increments.reduce((prev, curr) =>
    Math.abs(curr - weight) < Math.abs(prev - weight) ? curr : prev, increments[0]);

  const visibleStack = increments.filter(w => w <= Math.max(closest + 20, 60)).slice(0, 12);
  const stackHeight = visibleStack.length * 10 + 10;

  return (
    <svg viewBox={`0 0 80 ${stackHeight + 20}`} className="w-full max-w-[100px]" role="img" aria-label="Machine weight stack">
      {/* Cable */}
      <line x1={40} y1={0} x2={40} y2={5} stroke="#71717a" strokeWidth={1.5} />

      {visibleStack.map((w, i) => {
        const y = 5 + i * 10;
        const isSelected = w <= closest;
        const isPinPlate = w === closest;
        return (
          <g key={i}>
            <rect
              x={10}
              y={y}
              width={60}
              height={9}
              rx={1}
              fill={isSelected ? "#52525b" : "#27272a"}
              stroke={isPinPlate ? "#22c55e" : "#3f3f46"}
              strokeWidth={isPinPlate ? 1.5 : 0.5}
            />
            <text x={40} y={y + 7} textAnchor="middle" fontSize={6} fill={isSelected ? "#e4e4e7" : "#52525b"}>
              {w}
            </text>
            {/* Pin indicator */}
            {isPinPlate && (
              <circle cx={6} cy={y + 4.5} r={2.5} fill="#22c55e" />
            )}
          </g>
        );
      })}

      {/* Weight label */}
      <text x={40} y={stackHeight + 15} textAnchor="middle" fontSize={8} fill="#a1a1aa" fontWeight="bold">
        {weight} {unit}
      </text>
    </svg>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────────

export default function PlateLoadingSVG({ targetWeight, equipment, useLbs }: PlateLoadingSVGProps) {
  const unit = useLbs ? "lbs" : "kg";
  const plateConfigs = useLbs ? LBS_PLATES : KG_PLATES;
  const barWeight = useLbs ? 45 : 20;

  if (equipment === "barbell" || equipment === "e-z bar") {
    const bar = equipment === "e-z bar" ? (useLbs ? 25 : 10) : barWeight;
    const plates = calculatePlates(targetWeight, bar, plateConfigs);
    return <BarbellSVG plates={plates} barWeight={bar} unit={unit} />;
  }

  if (equipment === "dumbbell") {
    return <DumbbellSVG weight={targetWeight} unit={unit} />;
  }

  if (equipment === "machine" || equipment === "cable" || equipment === "smith_machine" || equipment === "leg_press" || equipment === "hack_squat") {
    const increments = useLbs ? MACHINE_INCREMENTS_LBS : MACHINE_INCREMENTS_KG;
    return <MachineStackSVG weight={targetWeight} unit={unit} increments={increments} />;
  }

  // Bodyweight or unknown — no loading visual
  return null;
}
