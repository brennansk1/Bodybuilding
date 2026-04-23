"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

interface NavBarProps {
  username?: string;
  onLogout?: () => void;
}

// localStorage key migration — keep reading the old Coronado key once, then
// move it forward under the Viltrum namespace and clean up.
const VILTRUM_PROFILE_PIC_KEY = "viltrum_profile_pic_url";
const LEGACY_PROFILE_PIC_KEY = "coronado_profile_pic_url";

function loadProfilePic(): string | null {
  if (typeof window === "undefined") return null;
  const current = window.localStorage.getItem(VILTRUM_PROFILE_PIC_KEY);
  if (current) return current;
  const legacy = window.localStorage.getItem(LEGACY_PROFILE_PIC_KEY);
  if (legacy) {
    window.localStorage.setItem(VILTRUM_PROFILE_PIC_KEY, legacy);
    window.localStorage.removeItem(LEGACY_PROFILE_PIC_KEY);
    return legacy;
  }
  return null;
}

function saveProfilePic(dataUrl: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(VILTRUM_PROFILE_PIC_KEY, dataUrl);
}

// Build a breadcrumb trail from the current pathname. Returns up to two crumbs
// so the nav stays compact — `Training › Program`, `Nutrition › Meal plan`.
const PATH_LABEL_OVERRIDES: Record<string, string> = {
  training: "Training",
  program: "Program",
  nutrition: "Nutrition",
  checkin: "Check-in",
  progress: "Progress",
  timeline: "Timeline",
  dashboard: "Dashboard",
  settings: "Settings",
  onboarding: "Onboarding",
};
function buildCrumbs(pathname: string): Array<{ href: string; label: string }> {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length <= 1) return [];
  const crumbs: Array<{ href: string; label: string }> = [];
  let acc = "";
  for (const segment of parts) {
    acc += `/${segment}`;
    const pretty =
      PATH_LABEL_OVERRIDES[segment] ??
      segment.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    crumbs.push({ href: acc, label: pretty });
  }
  return crumbs;
}

export default function NavBar({ username, onLogout }: NavBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profilePicUrl, setProfilePicUrl] = useState<string | null>(null);
  const avatarInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setProfilePicUrl(loadProfilePic());
  }, []);

  // Close mobile menu on route change so nav taps don't leave the drawer open.
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const handleAvatarSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result as string;
      saveProfilePic(base64);
      setProfilePicUrl(base64);
    };
    reader.readAsDataURL(file);
    if (avatarInputRef.current) avatarInputRef.current.value = "";
  };

  const navLinks = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/checkin", label: "Check-in" },
    { href: "/training", label: "Training" },
    { href: "/training/program", label: "Program" },
    { href: "/nutrition", label: "Nutrition" },
    { href: "/timeline", label: "Timeline" },
    { href: "/progress", label: "Progress" },
    { href: "/archive", label: "Archive" },
  ];

  const firstLetter = username ? username.charAt(0).toUpperCase() : "?";
  const crumbs = buildCrumbs(pathname || "");

  const activeFor = (href: string) => {
    const others = navLinks.filter((l) => l.href !== href);
    const moreSpecific = others.some(
      (l) => l.href.startsWith(href + "/") && (pathname === l.href || pathname?.startsWith(l.href + "/")),
    );
    return !moreSpecific && (pathname === href || pathname?.startsWith(href + "/"));
  };

  // Imperial dark nav per Claude Design — obsidian gradient, hexagonal red brand
  // mark, Contrail One stenciled links, legion-red bottom edge stripe.
  return (
    <nav
      className="sticky top-0 z-50 text-viltrum-bone"
      style={{
        background: "linear-gradient(180deg, var(--viltrum-obsidian) 0%, #0E0D0C 100%)",
        borderBottom: "1px solid #000",
        boxShadow: "0 2px 0 var(--viltrum-legion), 0 6px 20px -6px rgba(26,24,22,0.4)",
      }}
    >
      <div className="container-app">
        <div className="flex items-center justify-between h-16 sm:h-20 gap-4">
          {/* Brand: logo image + VILTRUM wordmark + "All is Ours" tagline */}
          <button
            onClick={() => router.push("/dashboard")}
            className="flex items-center gap-2.5 shrink-0 hover:opacity-85 transition-opacity"
            aria-label="Viltrum — home"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/viltrum-logo.png"
              alt=""
              className="w-8 h-8 sm:w-9 sm:h-9 object-contain"
              style={{ filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.4))" }}
            />
            <div className="leading-none text-left">
              <div
                className="text-viltrum-bone"
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: "16px",
                  letterSpacing: "6px",
                  textTransform: "uppercase",
                  fontWeight: 400,
                }}
              >
                Viltrum
              </div>
              <div
                className="mt-0.5 italic"
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: "10px",
                  color: "rgba(245,244,241,0.55)",
                  letterSpacing: "1.5px",
                }}
              >
                All is Ours
              </div>
            </div>
          </button>

          {/* Desktop nav — stenciled */}
          <div className="hidden md:flex items-center gap-1.5 flex-1 justify-center">
            {navLinks.map((link) => {
              const active = activeFor(link.href);
              return (
                <a
                  key={link.href}
                  href={link.href}
                  className="relative px-2.5 py-1.5 transition-colors"
                  style={{
                    fontFamily: "var(--font-display)",
                    fontSize: "11px",
                    letterSpacing: "2.5px",
                    textTransform: "uppercase",
                    fontWeight: 400,
                    color: active ? "var(--viltrum-bone)" : "rgba(245,244,241,0.6)",
                    borderBottom: active ? "2px solid var(--viltrum-legion)" : "2px solid transparent",
                  }}
                  onMouseEnter={(e) => { if (!active) (e.currentTarget as HTMLElement).style.color = "var(--viltrum-bone)"; }}
                  onMouseLeave={(e) => { if (!active) (e.currentTarget as HTMLElement).style.color = "rgba(245,244,241,0.6)"; }}
                >
                  {link.label}
                </a>
              );
            })}
          </div>

          {/* User section */}
          <div className="hidden md:flex items-center gap-3 shrink-0">
            {username && (
              <span style={{ color: "rgba(245,244,241,0.55)", fontSize: "11px", letterSpacing: "1px" }}>
                {username}
              </span>
            )}

            <button
              onClick={() => avatarInputRef.current?.click()}
              title="Change profile picture"
              className="relative w-8 h-8 rounded-full overflow-hidden focus:outline-none focus-visible:ring-2 focus-visible:ring-viltrum-legion focus-visible:ring-offset-2"
              style={{ background: "var(--viltrum-legion)", border: "1px solid rgba(245,244,241,0.2)" }}
              aria-label="Change profile picture"
            >
              {profilePicUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={profilePicUrl} alt="" className="w-full h-full object-cover" />
              ) : (
                <span className="w-full h-full flex items-center justify-center text-white text-[12px] font-semibold">
                  {firstLetter}
                </span>
              )}
            </button>
            <input
              ref={avatarInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleAvatarSelect}
            />

            <a
              href="/settings"
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "11px",
                letterSpacing: "2.5px",
                textTransform: "uppercase",
                color: pathname === "/settings" ? "var(--viltrum-bone)" : "rgba(245,244,241,0.6)",
                borderBottom: pathname === "/settings" ? "2px solid var(--viltrum-legion)" : "2px solid transparent",
                paddingBottom: "6px",
              }}
            >
              Settings
            </a>
            {onLogout && (
              <button
                onClick={onLogout}
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: "11px",
                  letterSpacing: "2.5px",
                  textTransform: "uppercase",
                  color: "rgba(245,244,241,0.45)",
                }}
                className="hover:!text-viltrum-legion transition-colors"
              >
                Logout
              </button>
            )}
          </div>

          {/* Mobile: avatar + hamburger */}
          <div className="flex items-center gap-2 md:hidden">
            <button
              onClick={() => avatarInputRef.current?.click()}
              className="relative w-8 h-8 rounded-full overflow-hidden"
              style={{ background: "var(--viltrum-legion)" }}
              aria-label="Change profile picture"
            >
              {profilePicUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={profilePicUrl} alt="" className="w-full h-full object-cover" />
              ) : (
                <span className="w-full h-full flex items-center justify-center text-white text-[12px] font-semibold">
                  {firstLetter}
                </span>
              )}
            </button>
            <button
              onClick={() => setMobileOpen((o) => !o)}
              className="p-2 text-viltrum-bone"
              aria-label="Toggle menu"
              aria-expanded={mobileOpen}
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                {mobileOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Breadcrumb strip — only on nested pages */}
        {crumbs.length > 1 && (
          <div className="hidden md:flex items-center gap-2 pb-2" style={{ fontSize: "10px" }}>
            {crumbs.map((c, i) => (
              <span key={c.href} className="flex items-center gap-2">
                {i > 0 && <span style={{ color: "rgba(245,244,241,0.3)" }}>›</span>}
                <a
                  href={c.href}
                  style={{
                    fontFamily: "var(--font-display)",
                    letterSpacing: "2px",
                    textTransform: "uppercase",
                    color: i === crumbs.length - 1 ? "var(--viltrum-bone)" : "rgba(245,244,241,0.5)",
                  }}
                >
                  {c.label}
                </a>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Mobile menu — obsidian drawer */}
      {mobileOpen && (
        <div className="md:hidden" style={{ background: "#0E0D0C", borderTop: "1px solid #000" }}>
          <div className="container-app py-3 space-y-1">
            {navLinks.map((link) => {
              const active = activeFor(link.href);
              return (
                <a
                  key={link.href}
                  href={link.href}
                  className="block px-3 py-3 transition-colors"
                  style={{
                    fontFamily: "var(--font-display)",
                    fontSize: "13px",
                    letterSpacing: "2.5px",
                    textTransform: "uppercase",
                    color: active ? "var(--viltrum-bone)" : "rgba(245,244,241,0.6)",
                    background: active ? "rgba(196,64,64,0.08)" : "transparent",
                    borderLeft: active ? "2px solid var(--viltrum-legion)" : "2px solid transparent",
                  }}
                >
                  {link.label}
                </a>
              );
            })}
            <div className="mt-3 pt-3 space-y-1" style={{ borderTop: "1px solid rgba(245,244,241,0.08)" }}>
              <a
                href="/settings"
                className="block px-3 py-3"
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: "13px",
                  letterSpacing: "2.5px",
                  textTransform: "uppercase",
                  color: pathname === "/settings" ? "var(--viltrum-bone)" : "rgba(245,244,241,0.6)",
                }}
              >
                Settings
              </a>
              {onLogout && (
                <button
                  onClick={onLogout}
                  className="w-full text-left px-3 py-3"
                  style={{
                    fontFamily: "var(--font-display)",
                    fontSize: "13px",
                    letterSpacing: "2.5px",
                    textTransform: "uppercase",
                    color: "var(--viltrum-legion)",
                  }}
                >
                  Logout
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
