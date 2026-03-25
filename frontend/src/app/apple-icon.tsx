import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 180,
          height: 180,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0b1410",
          borderRadius: 36,
        }}
      >
        <svg width="140" height="150" viewBox="0 0 52 56">
          <polygon points="26,0 14,18 19,18 10,32 17,32 6,46 46,46 35,32 42,32 33,18 38,18" fill="#22c55e" />
          <rect x="22" y="46" width="8" height="6" rx="1" fill="#854d0e" />
        </svg>
      </div>
    ),
    { ...size }
  );
}
