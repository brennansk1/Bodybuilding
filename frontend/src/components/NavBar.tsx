"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Logo from "./Logo";

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

  return (
    <nav className="sticky top-0 z-50 bg-white border-b-[2.5px] border-viltrum-obsidian">
      <div className="container-app">
        <div className="flex items-center justify-between h-16 sm:h-20 gap-4">
          {/* Logo — the circle crops the banner top/bottom, VILTRUM wordmark is oversized. */}
          <button
            onClick={() => router.push("/dashboard")}
            className="flex items-center shrink-0 -my-1 hover:opacity-85 transition-opacity"
            aria-label="Viltrum — home"
          >
            <Logo variant="lockup" size="navbar" />
          </button>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-0 flex-1 justify-center">
            {navLinks.map((link) => {
              const active = activeFor(link.href);
              return (
                <a
                  key={link.href}
                  href={link.href}
                  className={`relative px-3 py-2 text-[12px] font-medium transition-colors ${
                    active ? "text-viltrum-obsidian" : "text-viltrum-travertine hover:text-viltrum-obsidian"
                  }`}
                >
                  {link.label}
                  {active && (
                    <span
                      className="absolute left-3 right-3 -bottom-[17px] h-[2.5px] bg-viltrum-centurion"
                      aria-hidden="true"
                    />
                  )}
                </a>
              );
            })}
          </div>

          {/* User section */}
          <div className="hidden md:flex items-center gap-3 shrink-0">
            {username && (
              <span className="text-viltrum-travertine text-[12px]">{username}</span>
            )}

            <button
              onClick={() => avatarInputRef.current?.click()}
              title="Change profile picture"
              className="relative w-8 h-8 rounded-full overflow-hidden bg-viltrum-obsidian focus:outline-none focus-visible:ring-2 focus-visible:ring-viltrum-obsidian focus-visible:ring-offset-2"
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
              className={`text-[12px] transition-colors ${
                pathname === "/settings"
                  ? "text-viltrum-obsidian font-semibold"
                  : "text-viltrum-travertine hover:text-viltrum-obsidian"
              }`}
            >
              Settings
            </a>
            {onLogout && (
              <button
                onClick={onLogout}
                className="text-[12px] text-viltrum-travertine hover:text-viltrum-legion transition-colors"
              >
                Logout
              </button>
            )}
          </div>

          {/* Mobile: avatar + hamburger */}
          <div className="flex items-center gap-2 md:hidden">
            <button
              onClick={() => avatarInputRef.current?.click()}
              className="relative w-8 h-8 rounded-full overflow-hidden bg-viltrum-obsidian"
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
              className="p-2 text-viltrum-obsidian"
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
          <div className="hidden md:flex items-center gap-2 pb-2 text-[11px] text-viltrum-travertine">
            {crumbs.map((c, i) => (
              <span key={c.href} className="flex items-center gap-2">
                {i > 0 && <span className="text-viltrum-pewter">›</span>}
                <a
                  href={c.href}
                  className={`uppercase tracking-[2px] ${
                    i === crumbs.length - 1 ? "text-viltrum-obsidian" : "hover:text-viltrum-obsidian"
                  }`}
                >
                  {c.label}
                </a>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Mobile menu — full-width slide-down */}
      {mobileOpen && (
        <div className="md:hidden border-t border-viltrum-ash bg-white">
          <div className="container-app py-3 space-y-1">
            {navLinks.map((link) => {
              const active = activeFor(link.href);
              return (
                <a
                  key={link.href}
                  href={link.href}
                  className={`block px-3 py-3 rounded-card transition-colors text-[14px] ${
                    active
                      ? "text-viltrum-obsidian bg-viltrum-limestone font-semibold"
                      : "text-viltrum-iron hover:bg-viltrum-limestone"
                  }`}
                >
                  {link.label}
                </a>
              );
            })}
            <div className="border-t border-viltrum-ash mt-3 pt-3 space-y-1">
              <a
                href="/settings"
                className={`block px-3 py-3 rounded-card text-[14px] transition-colors ${
                  pathname === "/settings"
                    ? "text-viltrum-obsidian bg-viltrum-limestone font-semibold"
                    : "text-viltrum-iron hover:bg-viltrum-limestone"
                }`}
              >
                Settings
              </a>
              {onLogout && (
                <button
                  onClick={onLogout}
                  className="w-full text-left px-3 py-3 text-[14px] text-viltrum-legion hover:bg-viltrum-blush rounded-card"
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
