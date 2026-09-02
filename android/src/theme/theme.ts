/**
 * Centralized design tokens — every screen/component should read colors,
 * spacing, and type from here rather than hard-coding values, so the
 * "dark futuristic" look stays consistent as new screens are added.
 */
export const colors = {
  background: '#05070d',
  surface: '#0d121f',
  surfaceRaised: '#141b2e',
  border: '#1f2a44',
  accent: '#38f2ff',
  accentDim: '#1a7f8c',
  accentSoft: 'rgba(56, 242, 255, 0.12)',
  danger: '#ff4d6d',
  warning: '#ffb020',
  success: '#3ddc84',
  textPrimary: '#eaf2ff',
  textSecondary: '#8a96b3',
  textMuted: '#5b6480',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export const radii = {
  sm: 8,
  md: 16,
  lg: 24,
  pill: 999,
} as const;

export const typography = {
  title: { fontSize: 28, fontWeight: '700' as const, color: colors.textPrimary },
  heading: { fontSize: 18, fontWeight: '600' as const, color: colors.textPrimary },
  body: { fontSize: 15, fontWeight: '400' as const, color: colors.textPrimary },
  caption: { fontSize: 13, fontWeight: '400' as const, color: colors.textSecondary },
  mono: { fontSize: 12, fontFamily: 'monospace' as const, color: colors.textSecondary },
};

export const statusColors = {
  connected: colors.success,
  connecting: colors.warning,
  disconnected: colors.danger,
} as const;

/** JarvisState -> color, shared by JarvisCore and anything else that needs
 * to render "what Jarvis is doing right now" consistently. */
export const jarvisStateColors = {
  IDLE: colors.accentDim,
  LISTENING: colors.accent,
  THINKING: colors.accent,
  PROCESSING: colors.accent,
  USING_TOOL: colors.warning,
  WAITING_FOR_CONFIRMATION: colors.warning,
  SPEAKING: colors.success,
  ERROR: colors.danger,
  OFFLINE: colors.textMuted,
} as const;
