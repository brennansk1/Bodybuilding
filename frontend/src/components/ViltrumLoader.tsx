"use client";

/**
 * Backwards-compat shim — `ViltrumLoader` was the original loader; per the
 * Claude Design handoff the platform-wide loader is now `OilOrbsLoader`
 * (matte-black orbs orbiting a slowly rotating logo with viscous physics).
 *
 * This file re-exports OilOrbsLoader as the default so every existing
 * `import ViltrumLoader from "@/components/ViltrumLoader"` keeps working
 * without touching every call site. Same `variant` + `label` prop API.
 */

import OilOrbsLoader from "./OilOrbsLoader";

export default OilOrbsLoader;
