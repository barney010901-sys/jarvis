import React from 'react';
import { RefreshControl, SafeAreaView, ScrollView, StyleSheet, Text, View } from 'react-native';
import { colors, spacing, typography } from '../theme/theme';
import { Card } from '../components/Card';
import { StatusPill } from '../components/StatusPill';
import { EmptyState, NotConfiguredState } from '../components/EmptyState';
import { useAsyncData } from '../hooks/useAsyncData';
import { useSettings } from '../context/SettingsContext';
import { getBusinessSummary, getCustomers, getOpportunities } from '../api/phase3Client';

/** Business Center (sections 46-52) — sustainability stage, ranked
 * opportunities (backend/app/business/scoring.py), and the customer
 * pipeline, in one screen. */
export function BusinessScreen() {
  const { settings } = useSettings();
  const summary = useAsyncData(() => getBusinessSummary(settings), [settings.backendHttpUrl]);
  const opportunities = useAsyncData(() => getOpportunities(settings), [settings.backendHttpUrl]);
  const customers = useAsyncData(() => getCustomers(settings), [settings.backendHttpUrl]);

  const loading = summary.loading || opportunities.loading || customers.loading;
  const refresh = () => {
    summary.refresh();
    opportunities.refresh();
    customers.refresh();
  };

  if (summary.data === null) {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={[typography.title, styles.header]}>Business</Text>
        <NotConfiguredState feature="The business engine" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={colors.accent} />}
      >
        <Text style={typography.title}>Business</Text>

        <Card title="Sustainability">
          <View style={styles.rowBetween}>
            <StatusPill status={summary.data.stage} label={summary.data.stage} />
            <Text style={styles.meta}>${summary.data.surplus_usd.toFixed(2)} surplus</Text>
          </View>
          <Text style={styles.meta}>${summary.data.revenue_total_usd.toFixed(2)} total revenue · ${summary.data.monthly_operating_cost_usd.toFixed(2)} this month's operating cost</Text>
        </Card>

        <Card title="Opportunities (ranked by expected value, risk-adjusted)">
          {(opportunities.data?.opportunities ?? []).length === 0 ? (
            <EmptyState label="No opportunities tracked yet." />
          ) : (
            opportunities.data!.opportunities.map((o) => (
              <View key={o.id} style={styles.itemRow}>
                <Text style={styles.itemTitle} numberOfLines={1}>{o.title}</Text>
                <Text style={styles.score}>{o.score.toFixed(0)}</Text>
              </View>
            ))
          )}
        </Card>

        <Card title="Customers">
          {(customers.data?.customers ?? []).length === 0 ? (
            <EmptyState label="No customers tracked yet." />
          ) : (
            customers.data!.customers.map((c) => (
              <View key={c.id} style={styles.itemRow}>
                <Text style={styles.itemTitle} numberOfLines={1}>{c.name}</Text>
                <StatusPill status={c.stage} />
              </View>
            ))
          )}
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { padding: spacing.lg, paddingBottom: 0 },
  content: { padding: spacing.lg, gap: spacing.md },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  meta: { ...typography.caption },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  itemTitle: { ...typography.body, flex: 1 },
  score: { ...typography.body, fontWeight: '700', color: colors.accent },
});
