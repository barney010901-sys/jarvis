import React, { useState } from 'react';
import { FlatList, SafeAreaView, StyleSheet, Text, TextInput, View } from 'react-native';
import { colors, radii, spacing, typography } from '../theme/theme';
import { Card } from '../components/Card';
import { StatusPill } from '../components/StatusPill';
import { EmptyState, NotConfiguredState } from '../components/EmptyState';
import { useSettings } from '../context/SettingsContext';
import { searchMemory, type MemorySearchResult } from '../api/phase3Client';

/** Memory + knowledge search (section 72/10) — natural search across
 * long-term memory and the knowledge base (backend/app/knowledge), e.g.
 * "What did we learn about Android audio?" */
export function MemoryScreen() {
  const { settings } = useSettings();
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<MemorySearchResult | null>(null);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);

  const runSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const response = await searchMemory(settings, query.trim());
      setResult(response);
      setSearched(true);
    } finally {
      setLoading(false);
    }
  };

  const items = [
    ...((result?.knowledge ?? []).map((k) => ({ id: `k-${k.id}`, kind: 'knowledge' as const, title: k.title, detail: k.content, badge: k.category, confidence: k.confidence }))),
    ...((result?.memories ?? []).map((m) => ({ id: `m-${m.id}`, kind: 'memory' as const, title: m.content, detail: m.tags.join(', '), badge: 'MEMORY', confidence: undefined }))),
  ];

  return (
    <SafeAreaView style={styles.container}>
      <Text style={[typography.title, styles.header]}>Memory</Text>
      <View style={styles.searchRow}>
        <TextInput
          style={styles.input}
          placeholder="What did we learn about…?"
          placeholderTextColor={colors.textMuted}
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={runSearch}
          returnKeyType="search"
        />
      </View>

      {!searched && !loading && <EmptyState label="Search recent memory, decisions, and knowledge." />}
      {searched && result === null && <NotConfiguredState feature="Knowledge search" />}

      <FlatList
        contentContainerStyle={styles.list}
        data={items}
        keyExtractor={(item) => item.id}
        ListEmptyComponent={searched && result !== null ? <EmptyState label="Nothing found for that query." /> : null}
        renderItem={({ item }) => (
          <Card>
            <View style={styles.rowBetween}>
              <StatusPill status={item.badge} />
              {item.confidence != null && <Text style={styles.confidence}>{Math.round(item.confidence * 100)}% confidence</Text>}
            </View>
            <Text style={styles.itemTitle}>{item.title}</Text>
            {!!item.detail && <Text style={styles.detail} numberOfLines={3}>{item.detail}</Text>}
          </Card>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { padding: spacing.lg, paddingBottom: 0 },
  searchRow: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.textPrimary,
  },
  list: { padding: spacing.lg, gap: spacing.sm },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  itemTitle: { ...typography.body, fontWeight: '600', marginTop: spacing.xs },
  detail: { ...typography.caption, marginTop: 2 },
  confidence: { ...typography.caption },
});
