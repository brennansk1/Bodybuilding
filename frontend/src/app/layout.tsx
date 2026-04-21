import type { Metadata, Viewport } from "next";
import { Contrail_One, Crimson_Pro, Inter } from "next/font/google";
import "./globals.css";
import ToastContainer from "@/components/Toast";

// Display — the Contrail One wordmark font, single weight.
const contrail = Contrail_One({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

// Body serif — Crimson Pro for coaching prose, descriptions, long-form copy.
const crimson = Crimson_Pro({
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
});

// UI — Inter for dense data, nav, labels, forms.
const inter = Inter({
  weight: ["400", "500", "600"],
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Viltrum",
  description: "All Is Ours.",
  manifest: "/manifest.json",
  icons: {
    icon: [
      { url: "/favicon.png", type: "image/png" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Viltrum",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#1A1816",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${contrail.variable} ${crimson.variable} ${inter.variable}`}
    >
      <body className="min-h-screen antialiased flex flex-col">
        <div className="flex-1">{children}</div>
        {/* Global footer — motto + wordmark, unobtrusive */}
        <footer className="border-t border-viltrum-ash bg-white/50 py-6 mt-12">
          <div className="container-app flex flex-col sm:flex-row items-center justify-between gap-3 text-viltrum-travertine">
            <span className="font-display uppercase tracking-[6px] text-[10px]">
              All Is Ours
            </span>
            <span className="font-display uppercase tracking-[4px] text-[10px]">
              Viltrum
            </span>
          </div>
        </footer>
        <ToastContainer />
      </body>
    </html>
  );
}
