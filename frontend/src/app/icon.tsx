import { ImageResponse } from "next/og";

export const size = { width: 64, height: 64 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 64,
          height: 64,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0b1410",
          borderRadius: 12,
        }}
      >
        <svg width="52" height="56" viewBox="0 0 52 56">
          <polygon points="26,0 14,18 19,18 10,32 17,32 6,46 46,46 35,32 42,32 33,18 38,18" fill="#22c55e" />
          <rect x="22" y="46" width="8" height="6" rx="1" fill="#854d0e" />
        </svg>
      </div>
    ),
    { ...size }
  );
}
