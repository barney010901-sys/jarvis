import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, radii, spacing, statusColors } from '../theme/theme';
import type { ConnectionStatus } from '../hooks/useJarvisSocket';

const LABEL: Record<ConnectionStatus, string> = {
  connected: 'CONNECTED',
  connecting: 'CONNECTING…',
  disconnected: 'OFFLINE',
};

export function ConnectionStatusBadge({ status }: { status: ConnectionStatus }) {
  const dotColor = statusColors[status];
  return (
    <View style={styles.container}>
      <View style={[styles.dot, { backgroundColor: dotColor, shadowColor: dotColor }]} />
      <Text style={styles.label}>{LABEL[status]}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    gap: spacing.xs,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    shadowOpacity: 0.9,
    shadowRadius: 4,
  },
  label: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 1,
  },
});
