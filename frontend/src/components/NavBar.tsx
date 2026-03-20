"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Logo from "./Logo";

interface NavBarProps {
  username?: string;
  onLogout?: () => void;
}

export default function NavBar({ username, onLogout }: NavBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profilePicUrl, setProfilePicUrl] = useState<string | null>(null);
  const avatarInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem("coronado_profile_pic_url");
    if (saved) setProfilePicUrl(saved);
  }, []);

  const handleAvatarSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result as string;
      localStorage.setItem("coronado_profile_pic_url", base64);
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
    { href: "/progress", label: "Progress" },
  ];

  const firstLetter = username ? username.charAt(0).toUpperCase() : "?";

  return (
    <nav className="sticky top-0 z-50 bg-jungle-deeper/90 backdrop-blur-md border-b border-jungle-border">
      <div className="container-app">
        <div className="flex items-center justify-between h-14 sm:h-16">
          {/* Logo */}
          <button onClick={() => router.push("/dashboard")} className="flex items-center">
            <Logo size="sm" />
          </button>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => {
              const active = pathname === link.href || pathname.startsWith(link.href + "/");
              return (
                <a
                  key={link.href}
                  href={link.href}
                  className={`px-3 py-2 text-sm rounded-lg transition-colors ${
                    active
                      ? "text-jungle-accent font-medium"
                      : "text-jungle-muted hover:text-jungle-accent"
                  }`}
                >
                  {link.label}
                </a>
              );
            })}
          </div>

          {/* User section */}
          <div className="hidden md:flex items-center gap-3">
            {username && (
              <span className="text-jungle-muted text-sm">{username}</span>
            )}

            {/* Avatar circle */}
            <button
              onClick={() => avatarInputRef.current?.click()}
              title="Click to change profile picture"
              className="relative w-8 h-8 rounded-full overflow-hidden border-2 border-jungle-border hover:border-jungle-accent transition-colors focus:outline-none focus:ring-2 focus:ring-jungle-accent/40"
            >
              {profilePicUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={profilePicUrl}
                  alt="Profile"
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="w-full h-full flex items-center justify-center bg-jungle-accent/20 text-jungle-accent text-sm font-bold">
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
              className={`px-3 py-1.5 text-sm bg-jungle-card border rounded-lg transition-colors ${
                pathname === "/settings" ? "border-jungle-accent text-jungle-accent" : "border-jungle-border hover:border-jungle-accent text-jungle-muted"
              }`}
            >
              Settings
            </a>
            {onLogout && (
              <button
                onClick={onLogout}
                className="px-3 py-1.5 text-sm bg-jungle-card border border-jungle-border rounded-lg hover:border-jungle-danger transition-colors"
              >
                Logout
              </button>
            )}
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-2 text-jungle-muted hover:text-jungle-accent"
            aria-label="Toggle menu"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              {mobileOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden pb-4 border-t border-jungle-border mt-2 pt-3 space-y-1">
            {navLinks.map((link) => {
              const active = pathname === link.href || pathname.startsWith(link.href + "/");
              return (
                <a
                  key={link.href}
                  href={link.href}
                  className={`block px-3 py-2.5 hover:bg-jungle-card rounded-lg transition-colors ${
                    active ? "text-jungle-accent font-medium" : "text-jungle-muted hover:text-jungle-accent"
                  }`}
                  onClick={() => setMobileOpen(false)}
                >
                  {link.label}
                </a>
              );
            })}
            <div className="border-t border-jungle-border mt-2 pt-2 px-3">
              <div className="flex items-center gap-3 mb-3">
                {/* Mobile avatar */}
                <button
                  onClick={() => avatarInputRef.current?.click()}
                  className="relative w-8 h-8 rounded-full overflow-hidden border-2 border-jungle-border hover:border-jungle-accent transition-colors"
                >
                  {profilePicUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={profilePicUrl} alt="Profile" className="w-full h-full object-cover" />
                  ) : (
                    <span className="w-full h-full flex items-center justify-center bg-jungle-accent/20 text-jungle-accent text-sm font-bold">
                      {firstLetter}
                    </span>
                  )}
                </button>
                {username && (
                  <p className="text-jungle-dim text-sm">{username}</p>
                )}
              </div>
              {onLogout && (
                <button
                  onClick={onLogout}
                  className="w-full py-2 text-sm text-jungle-danger bg-jungle-card border border-jungle-border rounded-lg"
                >
                  Logout
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
