import React from 'react';
import { FlatList, RefreshControl, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { colors, spacing, typography } from '../theme/theme';
import { Card } from '../components/Card';
import { StatusPill } from '../components/StatusPill';
import { EmptyState } from '../components/EmptyState';
import { useAsyncData } from '../hooks/useAsyncData';
import { useSettings } from '../context/SettingsContext';
import { getTasks } from '../api/phase3Client';

/** Task Center (section 13) — every task's lifecycle status
 * (backend/app/tasks), across sessions, not just the current chat. */
export function TasksScreen() {
  const { settings } = useSettings();
  const { data, loading, refresh } = useAsyncData(() => getTasks(settings), [settings.backendHttpUrl]);

  return (
    <SafeAreaView style={styles.container}>
      <Text style={[typography.title, styles.header]}>Tasks</Text>
      <FlatList
        contentContainerStyle={styles.list}
        data={data?.tasks ?? []}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={colors.accent} />}
        ListEmptyComponent={<EmptyState label="No tasks yet." />}
        renderItem={({ item }) => (
          <Card>
            <View style={styles.rowBetween}>
              <Text style={styles.itemTitle} numberOfLines={2}>{item.request}</Text>
              <StatusPill status={item.status} />
            </View>
            <Text style={styles.meta}>{item.project} · {new Date(item.created_at).toLocaleString()}</Text>
            {!!item.error && <Text style={styles.error} numberOfLines={2}>{item.error}</Text>}
          </Card>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { padding: spacing.lg, paddingBottom: 0 },
  list: { padding: spacing.lg, gap: spacing.sm },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
  itemTitle: { ...typography.body, fontWeight: '600', flex: 1 },
  meta: { ...typography.caption, marginTop: 2 },
  error: { ...typography.caption, color: colors.danger, marginTop: 2 },
});
