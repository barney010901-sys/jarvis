import React from 'react';
import { FlatList, RefreshControl, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { colors, spacing, typography } from '../theme/theme';
import { EmptyState } from '../components/EmptyState';
import { useAsyncData } from '../hooks/useAsyncData';
import { useSettings } from '../context/SettingsContext';
import { getAudit } from '../api/phase3Client';

/** The Audit Center (section 71) — every event the backend's AuditLogger
 * recorded (it's a wildcard EventBus subscriber — see
 * backend/app/audit/logger.py), so this list is exactly what actually
 * happened, not a curated summary. */
export function AuditScreen() {
  const { settings } = useSettings();
  const { data, loading, refresh } = useAsyncData(() => getAudit(settings), [settings.backendHttpUrl]);

  return (
    <SafeAreaView style={styles.container}>
      <Text style={[typography.title, styles.header]}>Audit</Text>
      <FlatList
        contentContainerStyle={styles.list}
        data={data?.entries ?? []}
        keyExtractor={(item, index) => `${item.created_at}-${index}`}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={colors.accent} />}
        ListEmptyComponent={<EmptyState label="No activity recorded yet." />}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text style={styles.action}>{item.action}</Text>
            <View style={styles.metaRow}>
              <Text style={styles.meta}>{item.component}</Text>
              {!!item.result && <Text style={styles.meta}> · {item.result}</Text>}
              {!!item.confirmation_state && <Text style={styles.meta}> · {item.confirmation_state}</Text>}
            </View>
            <Text style={styles.time}>{new Date(item.created_at).toLocaleString()}</Text>
          </View>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { padding: spacing.lg, paddingBottom: 0 },
  list: { padding: spacing.lg, gap: spacing.xs },
  row: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: spacing.sm,
  },
  action: { ...typography.mono, color: colors.textPrimary },
  metaRow: { flexDirection: 'row' },
  meta: { ...typography.caption },
  time: { ...typography.caption, color: colors.textMuted, marginTop: 2 },
});
