import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, spacing, typography } from '../theme/theme';

export function EmptyState({ label }: { label: string }) {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>{label}</Text>
    </View>
  );
}

export function NotConfiguredState({ feature }: { feature: string }) {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>{feature} isn't available yet — Postgres and/or Claude aren't configured on this backend.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.lg, alignItems: 'center' },
  text: { ...typography.caption, textAlign: 'center', color: colors.textMuted },
});
