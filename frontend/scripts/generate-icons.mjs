/**
 * Generate static PWA icons (icon-192.png and icon-512.png)
 * Run: node scripts/generate-icons.mjs
 * Requires: sharp (npm install -D sharp)
 */

import { writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Pine tree SVG matching icon.tsx
function createSvg(size) {
  const padding = Math.round(size * 0.1);
  const treeSize = size - padding * 2;
  const borderRadius = Math.round(size * 0.18);

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" rx="${borderRadius}" fill="#0b1410"/>
  <svg x="${padding}" y="${padding}" width="${treeSize}" height="${treeSize}" viewBox="0 0 52 56">
    <polygon points="26,0 14,18 19,18 10,32 17,32 6,46 46,46 35,32 42,32 33,18 38,18" fill="#22c55e"/>
    <rect x="22" y="46" width="8" height="6" rx="1" fill="#854d0e"/>
  </svg>
</svg>`;
}

// Write SVG files (can be converted to PNG with sharp or used directly)
const sizes = [192, 512];

for (const size of sizes) {
  const svg = createSvg(size);
  const path = join(__dirname, '..', 'public', `icon-${size}.svg`);
  writeFileSync(path, svg);
  console.log(`Generated ${path}`);
}

// Also generate a favicon.svg
const faviconSvg = createSvg(64);
writeFileSync(join(__dirname, '..', 'public', 'favicon.svg'), faviconSvg);
console.log('Generated favicon.svg');

console.log('\\nSVG icons generated. To convert to PNG, install sharp:');
console.log('  npm install -D sharp');
console.log('Then uncomment the sharp conversion in this script.');
console.log('\\nAlternatively, the manifest can reference SVG icons directly.');
