import React, { useState } from 'react';
import { FlatList, RefreshControl, SafeAreaView, StyleSheet, Text, View, Pressable } from 'react-native';
import { colors, spacing, typography } from '../theme/theme';
import { Card } from '../components/Card';
import { StatusPill } from '../components/StatusPill';
import { EmptyState, NotConfiguredState } from '../components/EmptyState';
import { useAsyncData } from '../hooks/useAsyncData';
import { useSettings } from '../context/SettingsContext';
import { getProjectGoals, getProjects, type GoalSummary } from '../api/phase3Client';

/** Project Center + Goal Center (sections 11-12), combined: each project
 * expands to show its goals — "what am I working on, what's next" in one
 * place rather than two screens that always have to be cross-referenced. */
export function ProjectsScreen() {
  const { settings } = useSettings();
  const { data, loading, refresh } = useAsyncData(() => getProjects(settings), [settings.backendHttpUrl]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [goalsBySlug, setGoalsBySlug] = useState<Record<string, GoalSummary[]>>({});

  const toggle = async (slug: string) => {
    if (expanded === slug) {
      setExpanded(null);
      return;
    }
    setExpanded(slug);
    if (!goalsBySlug[slug]) {
      const response = await getProjectGoals(settings, slug);
      setGoalsBySlug((prev) => ({ ...prev, [slug]: response?.goals ?? [] }));
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={[typography.title, styles.header]}>Projects</Text>
      {data === null ? (
        <NotConfiguredState feature="Project tracking" />
      ) : (
        <FlatList
          contentContainerStyle={styles.list}
          data={data.projects}
          keyExtractor={(item) => item.slug}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={colors.accent} />}
          ListEmptyComponent={<EmptyState label="No projects yet — Jarvis creates one implicitly the first time you work on something." />}
          renderItem={({ item }) => (
            <Card>
              <Pressable onPress={() => toggle(item.slug)}>
                <View style={styles.rowBetween}>
                  <Text style={styles.itemTitle}>{item.name}</Text>
                  <StatusPill status={item.status} />
                </View>
                {!!item.technologies.length && <Text style={styles.meta}>{item.technologies.join(' · ')}</Text>}
              </Pressable>
              {expanded === item.slug && (
                <View style={styles.goals}>
                  {(goalsBySlug[item.slug] ?? []).length === 0 ? (
                    <Text style={styles.meta}>No goals recorded for this project.</Text>
                  ) : (
                    goalsBySlug[item.slug].map((g) => (
                      <View key={g.id} style={styles.goalRow}>
                        <StatusPill status={g.status} />
                        <Text style={styles.goalTitle} numberOfLines={2}>{g.title}</Text>
                      </View>
                    ))
                  )}
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
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  itemTitle: { ...typography.body, fontWeight: '700' },
  meta: { ...typography.caption, marginTop: 2 },
  goals: { marginTop: spacing.sm, gap: spacing.xs, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.sm },
  goalRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  goalTitle: { ...typography.caption, color: colors.textPrimary, flex: 1 },
});
