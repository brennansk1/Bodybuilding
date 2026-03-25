"use client";

interface LogoProps {
  size?: "sm" | "md" | "lg" | "xl";
  showTagline?: boolean;
}

const sizes = {
  sm: { icon: "text-xl", text: "text-lg" },
  md: { icon: "text-2xl", text: "text-xl" },
  lg: { icon: "text-4xl", text: "text-3xl" },
  xl: { icon: "text-6xl", text: "text-5xl" },
};

export default function Logo({ size = "md", showTagline = false }: LogoProps) {
  const s = sizes[size];

  return (
    <div className="flex flex-col items-center">
      <div className="flex items-center gap-2">
        <span className={`${s.icon}`}>
          <svg
            viewBox="0 0 32 32"
            className="w-[1em] h-[1em]"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Pine tree */}
            <path d="M16 2L10 12H13L8 20H12L6 28H26L20 20H24L19 12H22L16 2Z" fill="#2d8a4e" />
            <path d="M16 4L11.5 11H14L9.5 19H13L8 27H24L19 19H22.5L18 11H20.5L16 4Z" fill="#3aad5e" opacity="0.6" />
            <rect x="14" y="27" width="4" height="4" rx="0.5" fill="#8B6914" />
          </svg>
        </span>
        <h1 className={`${s.text} font-bold tracking-tight`}>
          <span className="text-jungle-accent">Coronado</span>
        </h1>
      </div>
      {showTagline && (
        <p className="text-jungle-muted text-sm mt-1 tracking-widest uppercase">
          Physique Optimization System
        </p>
      )}
    </div>
  );
}
