"use client";

/**
 * Oil Orbs Loader — matte-black viscous blobs orbiting the spinning logo.
 * Per Claude Design (`Oil Orbs Loader.html`): position + velocity per orb;
 * radial spring to target orbit radius + tangential drive + viscous damping
 * + elastic collisions. Each blob stretches along its velocity vector for
 * inertia-driven deformation.
 *
 * Variants:
 *   - fullscreen — route-level Suspense fallback (default)
 *   - inline     — data-fetch placeholder inside a page
 *   - compact    — small loader for buttons / tight rows (no orbs, just spinning logo)
 *
 * Respects `prefers-reduced-motion` — orbs disabled, logo holds static.
 */

import { useEffect, useRef } from "react";

interface Orb {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  targetR: number;
  dir: 1 | -1;
}

function useOilOrbsCanvas(
  stageRef: React.RefObject<HTMLDivElement>,
  logoRef: React.RefObject<HTMLDivElement>,
  canvasRef: React.RefObject<HTMLCanvasElement>,
  enabled: boolean,
  ringScale: number,
) {
  useEffect(() => {
    if (!enabled) return;
    const stage = stageRef.current;
    const logo = logoRef.current;
    const canvas = canvasRef.current;
    if (!stage || !logo || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
    let W = 0, H = 0;
    let frame = 0;

    function resize() {
      const rect = stage!.getBoundingClientRect();
      W = rect.width;
      H = rect.height;
      canvas!.width = Math.floor(W * dpr);
      canvas!.height = Math.floor(H * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(stage);

    function logoCircle() {
      const lr = logo!.getBoundingClientRect();
      const sr = stage!.getBoundingClientRect();
      return {
        cx: lr.left - sr.left + lr.width / 2,
        cy: lr.top - sr.top + lr.height / 2,
        r: lr.width / 2,
      };
    }

    const orbs: Orb[] = [];
    function initOrbs() {
      orbs.length = 0;
      const lc = logoCircle();
      const rings: Array<{ count: number; rad: number; size: [number, number]; dir: 1 | -1 }> = [
        { count: 6, rad: 22 * ringScale, size: [18 * ringScale, 26 * ringScale], dir: 1 },
        { count: 5, rad: 58 * ringScale, size: [14 * ringScale, 20 * ringScale], dir: -1 },
        { count: 4, rad: 94 * ringScale, size: [10 * ringScale, 16 * ringScale], dir: 1 },
      ];
      for (const ring of rings) {
        for (let i = 0; i < ring.count; i++) {
          const a = (i / ring.count) * Math.PI * 2 + Math.random() * 0.2;
          const size = ring.size[0] + Math.random() * (ring.size[1] - ring.size[0]);
          const targetR = lc.r + ring.rad;
          const speed = (0.8 + Math.random() * 0.25) * ring.dir;
          const px = lc.cx + Math.cos(a) * (lc.r + ring.rad);
          const py = lc.cy + Math.sin(a) * (lc.r + ring.rad);
          const vx = -Math.sin(a) * speed * targetR;
          const vy = Math.cos(a) * speed * targetR;
          orbs.push({ x: px, y: py, vx, vy, size, targetR, dir: ring.dir });
        }
      }
    }
    initOrbs();

    function step(dt: number) {
      const lc = logoCircle();
      const d = Math.min(0.033, dt);
      for (const o of orbs) {
        const dx = o.x - lc.cx;
        const dy = o.y - lc.cy;
        const dist = Math.hypot(dx, dy) || 0.01;
        const nx = dx / dist;
        const ny = dy / dist;
        // Radial spring
        const radError = dist - o.targetR;
        const springK = 18;
        const radialDamp = 2.6;
        const radVel = o.vx * nx + o.vy * ny;
        const ax = -nx * (springK * radError) - nx * (radialDamp * radVel);
        const ay = -ny * (springK * radError) - ny * (radialDamp * radVel);
        // Tangential drive
        const tx = -ny * o.dir;
        const ty = nx * o.dir;
        const targetTangentSpeed = 70;
        const curTangentSpeed = o.vx * tx + o.vy * ty;
        const tangentAcc = (targetTangentSpeed - curTangentSpeed) * 0.8;
        o.vx += (ax + tx * tangentAcc) * d;
        o.vy += (ay + ty * tangentAcc) * d;
        // Viscous damping
        o.vx *= 1 - 0.3 * d;
        o.vy *= 1 - 0.3 * d;
        o.x += o.vx * d;
        o.y += o.vy * d;
      }
      // Elastic collisions
      for (let i = 0; i < orbs.length; i++) {
        for (let j = i + 1; j < orbs.length; j++) {
          const a = orbs[i];
          const b = orbs[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.hypot(dx, dy);
          const minDist = (a.size + b.size) * 0.85;
          if (dist < minDist && dist > 0.01) {
            const nx = dx / dist;
            const ny = dy / dist;
            const overlap = minDist - dist;
            a.x -= nx * overlap * 0.5;
            a.y -= ny * overlap * 0.5;
            b.x += nx * overlap * 0.5;
            b.y += ny * overlap * 0.5;
            const rvx = b.vx - a.vx;
            const rvy = b.vy - a.vy;
            const velAlongN = rvx * nx + rvy * ny;
            if (velAlongN < 0) {
              const e = 0.3;
              const imp = (-(1 + e) * velAlongN) / 2;
              a.vx -= imp * nx;
              a.vy -= imp * ny;
              b.vx += imp * nx;
              b.vy += imp * ny;
            }
          }
        }
      }
    }

    function draw() {
      ctx!.clearRect(0, 0, W, H);
      ctx!.fillStyle = "#000";
      for (const o of orbs) {
        const speed = Math.hypot(o.vx, o.vy);
        const stretch = 1 + Math.min(0.4, speed / 400);
        const squash = 1 / (0.5 + stretch * 0.5);
        const ang = Math.atan2(o.vy, o.vx);
        ctx!.save();
        ctx!.translate(o.x, o.y);
        ctx!.rotate(ang);
        ctx!.beginPath();
        ctx!.ellipse(0, 0, o.size * stretch, o.size * squash, 0, 0, Math.PI * 2);
        ctx!.fill();
        ctx!.restore();
      }
    }

    let last = performance.now();
    function loop(t: number) {
      const dt = (t - last) / 1000;
      last = t;
      step(dt);
      draw();
      frame = requestAnimationFrame(loop);
    }
    frame = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(frame);
      ro.disconnect();
    };
  }, [enabled, ringScale, stageRef, logoRef, canvasRef]);
}

export default function OilOrbsLoader({
  variant = "fullscreen",
  label,
}: {
  variant?: "fullscreen" | "inline" | "compact";
  label?: string;
}) {
  const stageRef = useRef<HTMLDivElement>(null);
  const logoRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Honor prefers-reduced-motion: still render the logo, skip the physics.
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Compact variant: tight inline loader for buttons / rows. Just the
  // spinning logo, no orbs (orbs need stage room).
  if (variant === "compact") {
    return (
      <span
        role="status"
        aria-label={label ?? "Loading"}
        className="inline-flex items-center justify-center"
      >
        <span className="relative w-7 h-7 inline-block">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/viltrum-logo.png"
            alt=""
            width={28}
            height={28}
            className="block oil-orbs-logo-spin"
          />
        </span>
        <style jsx>{`
          .oil-orbs-logo-spin {
            animation: oil-orbs-spin 2.4s linear infinite;
            transform-origin: 50% 50%;
          }
          @keyframes oil-orbs-spin {
            0% {
              transform: rotateY(0deg);
            }
            100% {
              transform: rotateY(360deg);
            }
          }
          @media (prefers-reduced-motion: reduce) {
            .oil-orbs-logo-spin {
              animation: none;
            }
          }
        `}</style>
      </span>
    );
  }

  const isFullscreen = variant === "fullscreen";
  const ringScale = isFullscreen ? 1 : 0.6;
  const logoSize = isFullscreen ? 180 : 110;

  // Wire up the canvas physics.
  useOilOrbsCanvas(stageRef, logoRef, canvasRef, !reduced, ringScale);

  const stageStyle: React.CSSProperties = isFullscreen
    ? {
        position: "fixed",
        inset: 0,
        zIndex: 60,
        background: "var(--viltrum-bone, #FBF8F1)",
      }
    : {
        position: "relative",
        width: "100%",
        minHeight: 280,
      };

  return (
    <div
      ref={stageRef}
      role="status"
      aria-live="polite"
      aria-label={label ?? "Loading"}
      style={{
        ...stageStyle,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
        }}
      />
      <div
        ref={logoRef}
        className="oil-orbs-logo"
        style={{
          position: "relative",
          zIndex: 2,
          width: logoSize,
          height: logoSize,
          backgroundImage: "url(/viltrum-logo.png)",
          backgroundSize: "contain",
          backgroundPosition: "center",
          backgroundRepeat: "no-repeat",
          animation: reduced ? undefined : "oil-orbs-logo-spin 4s linear infinite",
        }}
      />
      {label && isFullscreen && (
        <div
          style={{
            position: "absolute",
            bottom: 60,
            left: 0,
            right: 0,
            textAlign: "center",
            fontFamily: "var(--font-display)",
            fontSize: 11,
            letterSpacing: "4px",
            textTransform: "uppercase",
            color: "var(--viltrum-iron)",
            opacity: 0.7,
          }}
        >
          {label}
        </div>
      )}
      <style jsx>{`
        @keyframes oil-orbs-logo-spin {
          0% {
            transform: rotateY(0deg);
          }
          100% {
            transform: rotateY(360deg);
          }
        }
      `}</style>
    </div>
  );
}
