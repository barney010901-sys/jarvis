import React, { useEffect, useState } from 'react';
import { Alert, Pressable, SafeAreaView, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { colors, radii, spacing, typography } from '../theme/theme';
import { Card } from '../components/Card';
import { StatusPill } from '../components/StatusPill';
import { useSettings } from '../context/SettingsContext';
import { checkHealth } from '../api/client';
import { useAsyncData } from '../hooks/useAsyncData';
import { createContact, getAutonomyLevel, getContacts, getSystemHealth, setAutonomyLevel } from '../api/phase3Client';

const AUTONOMY_LEVELS: { level: number; name: string; description: string }[] = [
  { level: 1, name: 'Suggest only', description: 'Jarvis proposes actions but never acts without approval.' },
  { level: 2, name: 'Prepare', description: 'Jarvis drafts actions (e.g. a reply) but always asks before doing them.' },
  { level: 3, name: 'Ask (default)', description: 'Safe read-only actions run automatically; anything else asks.' },
  { level: 4, name: 'Execute approved', description: 'Actions matching a policy you’ve pre-approved run automatically.' },
  { level: 5, name: 'Safe automation', description: 'Low/medium-risk reversible actions within limits run automatically.' },
];

function Field({ label, ...props }: { label: string } & React.ComponentProps<typeof TextInput>) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput style={styles.input} placeholderTextColor={colors.textMuted} autoCapitalize="none" autoCorrect={false} {...props} />
    </View>
  );
}

function ToggleRow({ label, hint, value, onValueChange, disabled }: { label: string; hint?: string; value: boolean; onValueChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <View style={styles.toggleRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.toggleLabel}>{label}</Text>
        {!!hint && <Text style={styles.toggleHint}>{hint}</Text>}
      </View>
      <Switch value={value} onValueChange={onValueChange} disabled={disabled} trackColor={{ true: colors.accentDim, false: colors.border }} thumbColor={value ? colors.accent : colors.textMuted} />
    </View>
  );
}

export function SettingsScreen() {
  const { settings, update } = useSettings();
  const [httpUrl, setHttpUrl] = useState(settings.backendHttpUrl);
  const [wsUrl, setWsUrl] = useState(settings.backendWsUrl);
  const [token, setToken] = useState(settings.apiToken);
  const [checking, setChecking] = useState(false);

  const [contactName, setContactName] = useState('');
  const contacts = useAsyncData(() => getContacts(settings), [settings.backendHttpUrl]);
  const autonomy = useAsyncData(() => getAutonomyLevel(settings), [settings.backendHttpUrl]);
  const health = useAsyncData(() => getSystemHealth(settings), [settings.backendHttpUrl]);

  useEffect(() => {
    setHttpUrl(settings.backendHttpUrl);
    setWsUrl(settings.backendWsUrl);
    setToken(settings.apiToken);
  }, [settings]);

  const save = async () => {
    await update({ ...settings, backendHttpUrl: httpUrl.trim(), backendWsUrl: wsUrl.trim(), apiToken: token.trim() });
    Alert.alert('Saved', 'Backend connection settings updated.');
  };

  const testConnection = async () => {
    setChecking(true);
    try {
      const ok = await checkHealth({ ...settings, backendHttpUrl: httpUrl.trim(), backendWsUrl: wsUrl.trim(), apiToken: token.trim() });
      Alert.alert(ok ? 'Connected' : 'Unreachable', ok ? 'Backend health check passed.' : 'Could not reach /health.');
    } finally {
      setChecking(false);
    }
  };

  const addContact = async () => {
    if (!contactName.trim()) return;
    await createContact(settings, { name: contactName.trim(), role: 'SECONDARY', channel: 'unknown' });
    setContactName('');
    contacts.refresh();
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={typography.title}>Settings</Text>

        <Card title="Connection">
          <Field label="Backend HTTPS URL" value={httpUrl} onChangeText={setHttpUrl} placeholder="https://your-backend" />
          <Field label="Backend WebSocket URL" value={wsUrl} onChangeText={setWsUrl} placeholder="wss://your-backend/ws" />
          <Field label="API Token" value={token} onChangeText={setToken} placeholder="Bearer token" secureTextEntry />
          <Pressable style={styles.primaryButton} onPress={save}>
            <Text style={styles.primaryLabel}>Save</Text>
          </Pressable>
          <Pressable style={styles.secondaryButton} onPress={testConnection} disabled={checking}>
            <Text style={styles.secondaryLabel}>{checking ? 'Checking…' : 'Test connection'}</Text>
          </Pressable>
        </Card>

        <Card title="Voice">
          <ToggleRow label="Speak Jarvis's replies (TTS)" hint="Real — uses on-device text-to-speech." value={settings.ttsEnabled} onValueChange={(v) => update({ ...settings, ttsEnabled: v })} />
          <ToggleRow label="Wake word" hint="Not implemented in this build — needs a native module + custom dev client." value={settings.wakeWordEnabled} onValueChange={(v) => update({ ...settings, wakeWordEnabled: v })} disabled />
        </Card>

        <Card title="Privacy & 24/7 mode">
          <ToggleRow label="Microphone" hint="Kill switch the push-to-talk button respects." value={settings.microphoneEnabled} onValueChange={(v) => update({ ...settings, microphoneEnabled: v })} />
          <ToggleRow label="24/7 background mode" hint="Not implemented — requires a foreground service + wake word, neither exists yet." value={settings.alwaysOnMode} onValueChange={(v) => update({ ...settings, alwaysOnMode: v })} disabled />
          <Text style={styles.hint}>Jarvis never records or transmits microphone audio unless you are actively holding the voice button.</Text>
        </Card>

        <Card title="Autonomy">
          <Text style={styles.hint}>How much Jarvis may do on its own before asking you (backend/app/policy).</Text>
          {autonomy.data ? (
            AUTONOMY_LEVELS.map((option) => (
              <Pressable
                key={option.level}
                style={[styles.autonomyOption, autonomy.data?.level === option.level && styles.autonomyOptionSelected]}
                onPress={async () => {
                  await setAutonomyLevel(settings, option.level);
                  autonomy.refresh();
                }}
              >
                <Text style={styles.autonomyName}>{option.name}</Text>
                <Text style={styles.hint}>{option.description}</Text>
              </Pressable>
            ))
          ) : (
            <Text style={styles.hint}>Not available — Postgres/Claude aren't configured on this backend.</Text>
          )}
        </Card>

        <Card title="Escalation contacts">
          <Text style={styles.hint}>Who Jarvis may notify if something important happens and you're unavailable — never anyone else.</Text>
          {(contacts.data?.contacts ?? []).map((c) => (
            <View key={c.id} style={styles.contactRow}>
              <Text style={styles.contactName}>{c.name}</Text>
              <StatusPill status={c.role} />
            </View>
          ))}
          <View style={styles.addContactRow}>
            <TextInput style={[styles.input, { flex: 1 }]} placeholder="Add a contact by name" placeholderTextColor={colors.textMuted} value={contactName} onChangeText={setContactName} />
            <Pressable onPress={addContact} style={styles.addButton}>
              <Text style={styles.primaryLabel}>Add</Text>
            </Pressable>
          </View>
        </Card>

        <Card title="System">
          <View style={styles.healthGrid}>
            {(health.data?.components ?? []).map((c) => (
              <StatusPill key={c.component} status={c.status} label={c.component} />
            ))}
          </View>
        </Card>

        <Card title="About">
          <Text style={styles.hint}>Jarvis — Phase 3 (final V1). See docs/PHASE_3.md in the repository for the full REAL/MOCKED/NOT_TESTED breakdown.</Text>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md },
  hint: { ...typography.caption },
  field: { gap: spacing.xs, marginBottom: spacing.xs },
  fieldLabel: { ...typography.caption, color: colors.textSecondary, fontWeight: '600' },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.textPrimary,
  },
  primaryButton: { backgroundColor: colors.accent, borderRadius: radii.sm, paddingVertical: spacing.sm, alignItems: 'center', marginTop: spacing.xs },
  primaryLabel: { color: colors.background, fontWeight: '700' },
  secondaryButton: { borderWidth: 1, borderColor: colors.border, borderRadius: radii.sm, paddingVertical: spacing.sm, alignItems: 'center' },
  secondaryLabel: { color: colors.textPrimary, fontWeight: '600' },
  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.xs },
  toggleLabel: { ...typography.body, fontWeight: '600' },
  toggleHint: { ...typography.caption, marginTop: 2 },
  autonomyOption: { borderWidth: 1, borderColor: colors.border, borderRadius: radii.sm, padding: spacing.sm, marginTop: spacing.xs },
  autonomyOptionSelected: { borderColor: colors.accent, backgroundColor: colors.accentSoft },
  autonomyName: { ...typography.body, fontWeight: '700' },
  contactRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: spacing.xs, borderBottomWidth: 1, borderBottomColor: colors.border },
  contactName: { ...typography.body },
  addContactRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  addButton: { backgroundColor: colors.accent, borderRadius: radii.sm, paddingHorizontal: spacing.md, alignItems: 'center', justifyContent: 'center' },
  healthGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
});
