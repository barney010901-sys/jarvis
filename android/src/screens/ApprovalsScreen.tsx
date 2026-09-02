import React, { useState } from 'react';
import { FlatList, RefreshControl, SafeAreaView, StyleSheet, Text, View, Pressable } from 'react-native';
import { colors, radii, spacing, typography } from '../theme/theme';
import { Card } from '../components/Card';
import { StatusPill } from '../components/StatusPill';
import { EmptyState, NotConfiguredState } from '../components/EmptyState';
import { useAsyncData } from '../hooks/useAsyncData';
import { useSettings } from '../context/SettingsContext';
import { getApprovals } from '../api/phase3Client';
import { approveConfirmation, rejectConfirmation } from '../api/client';

/** The Approval Center (section 70) — every ASK decision from the Policy
 * Engine (wallet spend, outgoing reply, capability install, destructive
 * op) in one inbox. Approve/reject reuse the existing confirmation
 * endpoints: an approval's id IS the underlying confirmation id. */
export function ApprovalsScreen() {
  const { settings } = useSettings();
  const [busyId, setBusyId] = useState<string | null>(null);
  const { data, loading, refresh } = useAsyncData(() => getApprovals(settings), [settings.backendHttpUrl]);

  const act = async (id: string, action: 'approve' | 'reject') => {
    setBusyId(id);
    try {
      await (action === 'approve' ? approveConfirmation(settings, id) : rejectConfirmation(settings, id));
      refresh();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={[typography.title, styles.header]}>Approvals</Text>
      {data === null ? (
        <NotConfiguredState feature="The approval center" />
      ) : (
        <FlatList
          contentContainerStyle={styles.list}
          data={data.approvals}
          keyExtractor={(item) => item.id}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={colors.accent} />}
          ListEmptyComponent={<EmptyState label="No approvals yet." />}
          renderItem={({ item }) => (
            <Card>
              <View style={styles.rowBetween}>
                <Text style={styles.itemTitle} numberOfLines={2}>{item.title}</Text>
                <StatusPill status={item.status} />
              </View>
              <Text style={styles.description} numberOfLines={3}>{item.description}</Text>
              <View style={styles.rowBetween}>
                <Text style={styles.meta}>{item.kind} · risk: {item.risk}{item.cost_usd != null ? ` · $${item.cost_usd.toFixed(2)}` : ''}</Text>
              </View>
              {item.status === 'PENDING' && (
                <View style={styles.actions}>
                  <Pressable disabled={busyId === item.id} onPress={() => act(item.id, 'reject')} style={[styles.button, styles.rejectButton]}>
                    <Text style={styles.rejectLabel}>Reject</Text>
                  </Pressable>
                  <Pressable disabled={busyId === item.id} onPress={() => act(item.id, 'approve')} style={[styles.button, styles.approveButton]}>
                    <Text style={styles.approveLabel}>Approve</Text>
                  </Pressable>
                </View>
              )}
            </Card>
          )}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { padding: spacing.lg, paddingBottom: 0 },
  list: { padding: spacing.lg, gap: spacing.sm },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
  itemTitle: { ...typography.body, fontWeight: '700', flex: 1 },
  description: { ...typography.caption },
  meta: { ...typography.mono },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xs },
  button: { flex: 1, paddingVertical: spacing.sm, borderRadius: radii.sm, alignItems: 'center' },
  rejectButton: { borderWidth: 1, borderColor: colors.danger },
  approveButton: { backgroundColor: colors.accent },
  rejectLabel: { color: colors.danger, fontWeight: '700' },
  approveLabel: { color: colors.background, fontWeight: '700' },
});
