import React, { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, radii, spacing, typography } from '../theme/theme';
import type { ConfirmationRequiredPayload } from '../api/events';

type Props = {
  request: ConfirmationRequiredPayload | null;
  onApprove: (confirmationId: string) => Promise<void>;
  onReject: (confirmationId: string) => Promise<void>;
};

/**
 * Rendered whenever a confirmation.required event arrives for a SENSITIVE
 * tool call (see docs/ARCHITECTURE.md, "Security model"). The task does
 * not proceed on the backend until this resolves one way or the other.
 */
export function ConfirmationDialog({ request, onApprove, onReject }: Props) {
  const [busy, setBusy] = useState(false);

  if (!request) return null;

  const handle = async (action: (id: string) => Promise<void>) => {
    setBusy(true);
    try {
      await action(request.confirmation_id);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal transparent animationType="fade" visible>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.badge}>CONFIRMATION REQUIRED</Text>
          <Text style={styles.tool}>{request.tool_name}</Text>
          <Text style={styles.description}>{request.description}</Text>

          <View style={styles.actions}>
            <Pressable
              disabled={busy}
              onPress={() => handle(onReject)}
              style={[styles.button, styles.rejectButton]}
            >
              <Text style={styles.rejectLabel}>Reject</Text>
            </Pressable>
            <Pressable
              disabled={busy}
              onPress={() => handle(onApprove)}
              style={[styles.button, styles.approveButton]}
            >
              <Text style={styles.approveLabel}>Approve</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(2, 4, 10, 0.82)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  card: {
    width: '100%',
    backgroundColor: colors.surfaceRaised,
    borderColor: colors.warning,
    borderWidth: 1,
    borderRadius: radii.md,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  badge: {
    color: colors.warning,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.5,
  },
  tool: { ...typography.heading, fontFamily: 'monospace' as const },
  description: { ...typography.body, color: colors.textSecondary },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  button: {
    flex: 1,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
    alignItems: 'center',
  },
  rejectButton: { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.danger },
  approveButton: { backgroundColor: colors.accent },
  rejectLabel: { color: colors.danger, fontWeight: '700' },
  approveLabel: { color: colors.background, fontWeight: '700' },
});
