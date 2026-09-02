import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, radii } from '../theme/theme';

const TONE_COLOR: Record<string, string> = {
  good: colors.success,
  warning: colors.warning,
  bad: colors.danger,
  neutral: colors.textMuted,
  accent: colors.accent,
};

// Maps common backend status vocabularies (health, task lifecycle,
// verification, approvals) to one of five visual tones, so a new status
// string never needs a new color decision — see section 65.
const STATUS_TONE: Record<string, keyof typeof TONE_COLOR> = {
  HEALTHY: 'good', REAL: 'good', COMPLETED: 'good', APPROVED: 'good', EXECUTED: 'good', PAID: 'good', ACTIVE: 'good', GREEN: 'good',
  WARNING: 'warning', PARTIALLY_IMPLEMENTED: 'warning', PENDING: 'warning', RUNNING: 'warning', WAITING_FOR_CONFIRMATION: 'warning', YELLOW: 'warning', PROPOSED: 'warning',
  ERROR: 'bad', FAILED: 'bad', REJECTED: 'bad', CANCELLED: 'bad', TIMEOUT: 'bad', BLOCKED: 'bad', RED: 'bad',
  NOT_CONFIGURED: 'neutral', NOT_TESTED: 'neutral', MOCKED: 'neutral', CREATED: 'neutral', PLANNED: 'neutral', LEAD: 'neutral',
};

export function StatusPill({ status, label }: { status: string; label?: string }) {
  const tone = STATUS_TONE[status] ?? 'accent';
  const color = TONE_COLOR[tone];
  return (
    <View style={[styles.pill, { borderColor: color }]}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={[styles.text, { color }]}>{label ?? status}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1,
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
    alignSelf: 'flex-start',
  },
  dot: { width: 6, height: 6, borderRadius: 3 },
  text: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },
});
