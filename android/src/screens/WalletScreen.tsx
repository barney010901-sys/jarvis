import React, { useState } from 'react';
import { Alert, RefreshControl, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { colors, radii, spacing, typography } from '../theme/theme';
import { Card } from '../components/Card';
import { StatusPill } from '../components/StatusPill';
import { EmptyState, NotConfiguredState } from '../components/EmptyState';
import { useAsyncData } from '../hooks/useAsyncData';
import { useSettings } from '../context/SettingsContext';
import { getWallet, updateWalletLimits } from '../api/phase3Client';

/** Wallet Center (sections 40-45, 62). CRITICAL, per the backend's own
 * architecture (backend/app/wallet/models.py): this is a real internal
 * ledger with enforced limits — there is no real bank/card/crypto rail
 * behind it. Every number here reflects that ledger, not a live account. */
export function WalletScreen() {
  const { settings } = useSettings();
  const { data, loading, refresh } = useAsyncData(() => getWallet(settings), [settings.backendHttpUrl]);
  const [weeklyLimit, setWeeklyLimit] = useState('');
  const [saving, setSaving] = useState(false);

  const saveLimit = async () => {
    const value = Number(weeklyLimit);
    if (!Number.isFinite(value) || value <= 0) {
      Alert.alert('Invalid amount', 'Enter a positive weekly limit.');
      return;
    }
    setSaving(true);
    try {
      await updateWalletLimits(settings, { weekly_limit_usd: value });
      setWeeklyLimit('');
      refresh();
    } finally {
      setSaving(false);
    }
  };

  if (data === null) {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={[typography.title, styles.header]}>Wallet</Text>
        <NotConfiguredState feature="The operational wallet" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={colors.accent} />}
      >
        <Text style={typography.title}>Wallet</Text>

        <Card title="Balance">
          <Text style={styles.balance}>${data.balance_usd.toFixed(2)}</Text>
        </Card>

        <View style={styles.limitRow}>
          <Card title="This week" style={styles.limitCard}>
            <Text style={styles.limitValue}>${data.weekly_spent_usd.toFixed(2)} / ${data.weekly_limit_usd.toFixed(2)}</Text>
          </Card>
          <Card title="This month" style={styles.limitCard}>
            <Text style={styles.limitValue}>${data.monthly_spent_usd.toFixed(2)} / ${data.monthly_limit_usd.toFixed(2)}</Text>
          </Card>
        </View>

        <Card title="Categories">
          <Text style={styles.label}>Approved</Text>
          <Text style={styles.meta}>{data.approved_categories.join(', ') || 'none configured'}</Text>
          <Text style={[styles.label, { marginTop: spacing.xs }]}>Blocked (never auto-executed)</Text>
          <Text style={styles.meta}>{data.blocked_categories.join(', ')}</Text>
        </Card>

        <Card title="Adjust weekly limit">
          <View style={styles.editRow}>
            <TextInput
              style={styles.input}
              placeholder={`Current: $${data.weekly_limit_usd.toFixed(2)}`}
              placeholderTextColor={colors.textMuted}
              keyboardType="decimal-pad"
              value={weeklyLimit}
              onChangeText={setWeeklyLimit}
            />
            <Text onPress={saving ? undefined : saveLimit} style={[styles.saveButton, saving && styles.saveButtonDisabled]}>
              {saving ? 'Saving…' : 'Save'}
            </Text>
          </View>
        </Card>

        <Card title="Recent transactions">
          {data.transactions.length === 0 ? (
            <EmptyState label="No transactions yet." />
          ) : (
            data.transactions.map((t) => (
              <View key={t.id} style={styles.txRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.txVendor}>{t.vendor}</Text>
                  <Text style={styles.meta}>{t.category} · {t.purpose}</Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={styles.txAmount}>${t.amount_usd.toFixed(2)}</Text>
                  <StatusPill status={t.status} />
                </View>
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
  balance: { fontSize: 36, fontWeight: '800', color: colors.textPrimary },
  limitRow: { flexDirection: 'row', gap: spacing.sm },
  limitCard: { flex: 1 },
  limitValue: { ...typography.body, fontWeight: '700' },
  label: { ...typography.caption, fontWeight: '700', color: colors.textSecondary },
  meta: { ...typography.caption },
  editRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'center' },
  input: {
    flex: 1,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.textPrimary,
  },
  saveButton: { color: colors.accent, fontWeight: '700', paddingHorizontal: spacing.md },
  saveButtonDisabled: { color: colors.textMuted },
  txRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  txVendor: { ...typography.body, fontWeight: '600' },
  txAmount: { ...typography.body, fontWeight: '700' },
});
