import React from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';
import { colors, radii, spacing, typography } from '../theme/theme';
import type { JarvisEvent } from '../api/events';

const ICON: Record<string, string> = {
  'user.message': '›',
  'task.created': '◆',
  'task.planned': '☰',
  'task.started': '▶',
  'tool.started': '⚙',
  'tool.completed': '✓',
  'confirmation.required': '⚠',
  'confirmation.approved': '✓',
  'confirmation.rejected': '✕',
  'task.failed': '✕',
  'task.completed': '●',
  'voice.transcription.completed': '"',
};

function colorFor(type: string): string {
  if (type === 'task.failed' || type === 'confirmation.rejected') return colors.danger;
  if (type === 'confirmation.required') return colors.warning;
  if (type === 'task.completed' || type === 'confirmation.approved') return colors.success;
  return colors.accent;
}

function summarize(event: JarvisEvent): string {
  switch (event.type) {
    case 'tool.started':
    case 'tool.completed':
      return String(event.payload.tool_name ?? '');
    case 'task.planned':
      return Array.isArray(event.payload.steps) ? `${event.payload.steps.length} step(s) planned` : '';
    case 'task.failed':
      return String(event.payload.error ?? '');
    case 'confirmation.required':
      return String(event.payload.tool_name ?? '');
    default:
      return '';
  }
}

/** Live log of backend Events — "task status" and "tool execution status". */
export function TaskProgressPanel({ events }: { events: JarvisEvent[] }) {
  if (events.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>No activity yet.</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={[...events].reverse()}
      keyExtractor={(item) => item.id}
      style={styles.list}
      renderItem={({ item }) => (
        <View style={styles.row}>
          <Text style={[styles.icon, { color: colorFor(item.type) }]}>{ICON[item.type] ?? '•'}</Text>
          <View style={styles.rowText}>
            <Text style={styles.type}>{item.type}</Text>
            {!!summarize(item) && <Text style={styles.detail}>{summarize(item)}</Text>}
          </View>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { flex: 1 },
  empty: { padding: spacing.lg, alignItems: 'center' },
  emptyText: { ...typography.caption },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
    borderRadius: radii.sm,
    marginBottom: spacing.xs,
  },
  icon: { fontSize: 16, width: 20, textAlign: 'center' },
  rowText: { flex: 1 },
  type: { ...typography.mono, color: colors.textPrimary },
  detail: { ...typography.caption, marginTop: 2 },
});
