function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function luminance(hex: string): number {
  const match = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match?.[1]) return 0;
  const n = parseInt(match[1], 16);
  return (
    0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255)
  );
}

/** Text colour that stays readable on the site's accent, whatever the owner picks. */
export function readableOn(hex: string): "#ffffff" | "#111315" {
  const l = luminance(hex);
  const contrastWhite = 1.05 / (l + 0.05);
  const contrastDark = (l + 0.05) / (luminance("#111315") + 0.05);
  return contrastWhite >= contrastDark ? "#ffffff" : "#111315";
}
