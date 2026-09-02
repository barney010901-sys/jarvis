import React from 'react';
import { StyleSheet, Text, View, ViewProps } from 'react-native';
import { colors, radii, spacing, typography } from '../theme/theme';

type Props = ViewProps & {
  title?: string;
  right?: React.ReactNode;
};

/** The one card primitive every Phase 3 screen uses (section 65: "define
 * cards, buttons, ..."), so the dashboard/wallet/business/memory/etc.
 * screens all look like one system instead of five different ones. */
export function Card({ title, right, style, children, ...rest }: Props) {
  return (
    <View style={[styles.card, style]} {...rest}>
      {(title || right) && (
        <View style={styles.headerRow}>
          {!!title && <Text style={styles.title}>{title}</Text>}
          {right}
        </View>
      )}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { ...typography.caption, fontWeight: '700', letterSpacing: 1, textTransform: 'uppercase' },
});
