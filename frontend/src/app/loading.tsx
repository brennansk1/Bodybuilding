import ViltrumLoader from "@/components/ViltrumLoader";

/**
 * Default loading fallback for any suspended route segment.
 * Next's App Router will mount this whenever a page or sub-layout is waiting
 * on async data — the Viltrum logo pulses until the target tree is ready.
 */
export default function Loading() {
  return <ViltrumLoader variant="fullscreen" />;
}
