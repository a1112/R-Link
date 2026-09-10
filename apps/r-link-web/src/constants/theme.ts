/**
 * 主题配置常量
 */

export const themeColors = {
  zinc: {
    950: "#09090b",
    900: "#18181b",
    800: "#27272a",
    700: "#3f3f46",
    600: "#52525b",
    500: "#71717a",
    400: "#a1a1aa",
    300: "#d4d4d8",
    200: "#e4e4e7",
    100: "#f4f4f5",
    50:  "#fafafa",
    white: "#ffffff",
    black: "#000000",
  },
  light: {
    950: "#ffffff",
    900: "#f4f4f5",
    800: "#e4e4e7",
    700: "#d4d4d8",
    600: "#a1a1aa",
    500: "#71717a",
    400: "#52525b",
    300: "#3f3f46",
    200: "#18181b",
    100: "#09090b",
    50:  "#000000",
    white: "#18181b",
    black: "#ffffff",
  }
};

export type ThemeName = keyof typeof themeColors;

/**
 * 将十六进制颜色转换为 RGBA */
export const hexToRgba = (hex: string, alpha: number): string => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

/**
 * 获取主题样式 */
export const getThemeStyles = (themeName: ThemeName): React.CSSProperties => {
  const palette = themeColors[themeName] || themeColors.zinc;
  const styles: Record<string, string> = {};

  // Base colors
  Object.entries(palette).forEach(([key, value]) => {
    styles[`--c-${key}`] = value;
  });

  const isLight = themeName === 'light';

  // Alphas
  styles['--c-950-85'] = hexToRgba(palette[950], isLight ? 0.60 : 0.85);
  styles['--c-950-80'] = hexToRgba(palette[950], isLight ? 0.60 : 0.80);
  styles['--c-950-50'] = hexToRgba(palette[950], 0.50);
  styles['--c-900-50'] = hexToRgba(palette[900], 0.50);
  styles['--c-800-90'] = hexToRgba(palette[800], 0.90);
  styles['--c-800-50'] = hexToRgba(palette[800], 0.50);
  styles['--c-800-30'] = hexToRgba(palette[800], 0.30);
  styles['--c-500-20'] = hexToRgba(palette[500], 0.20);
  styles['--c-500-5'] = hexToRgba(palette[500], 0.05);

  // Modal backdrop
  styles['--c-modal-overlay'] = isLight ? "rgba(0,0,0,0.2)" : "rgba(0,0,0,0.5)";

  return styles as React.CSSProperties;
};

/**
 * 主题配置列表 */
export const themes = [
  { id: "zinc" as ThemeName, name: "极致灰", primary: "bg-zinc-500", bg: "bg-zinc-900" },
  { id: "light" as ThemeName, name: "纯净白", primary: "bg-zinc-200", bg: "bg-zinc-100" },
];
