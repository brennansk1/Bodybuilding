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
            {/* Stylized leaf/crown mark */}
            <path
              d="M16 2C16 2 8 8 8 16C8 20.4 11.6 24 16 24C20.4 24 24 20.4 24 16C24 8 16 2 16 2Z"
              fill="#2d8a4e"
              opacity="0.8"
            />
            <path
              d="M16 6C16 6 11 11 11 16C11 18.8 13.2 21 16 21C18.8 21 21 18.8 21 16C21 11 16 6 16 6Z"
              fill="#c8a84e"
            />
            <path
              d="M16 28V24"
              stroke="#2d8a4e"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <path
              d="M12 30H20"
              stroke="#c8a84e"
              strokeWidth="2"
              strokeLinecap="round"
            />
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
