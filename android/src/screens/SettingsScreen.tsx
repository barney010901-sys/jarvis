import React, { useEffect, useState } from 'react';
import { Alert, Pressable, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { colors, radii, spacing, typography } from '../theme/theme';
import { useSettings } from '../context/SettingsContext';
import { checkHealth } from '../api/client';

function Field({ label, ...props }: { label: string } & React.ComponentProps<typeof TextInput>) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        style={styles.input}
        placeholderTextColor={colors.textMuted}
        autoCapitalize="none"
        autoCorrect={false}
        {...props}
      />
    </View>
  );
}

export function SettingsScreen() {
  const { settings, update } = useSettings();
  const [httpUrl, setHttpUrl] = useState(settings.backendHttpUrl);
  const [wsUrl, setWsUrl] = useState(settings.backendWsUrl);
  const [token, setToken] = useState(settings.apiToken);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    setHttpUrl(settings.backendHttpUrl);
    setWsUrl(settings.backendWsUrl);
    setToken(settings.apiToken);
  }, [settings]);

  const save = async () => {
    await update({ backendHttpUrl: httpUrl.trim(), backendWsUrl: wsUrl.trim(), apiToken: token.trim() });
    Alert.alert('Saved', 'Backend connection settings updated.');
  };

  const testConnection = async () => {
    setChecking(true);
    try {
      const ok = await checkHealth({ backendHttpUrl: httpUrl.trim(), backendWsUrl: wsUrl.trim(), apiToken: token.trim() });
      Alert.alert(ok ? 'Connected' : 'Unreachable', ok ? 'Backend health check passed.' : 'Could not reach /health.');
    } finally {
      setChecking(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={typography.title}>Settings</Text>
        <Text style={styles.hint}>
          Jarvis is an interface only — it holds no AI logic. These settings just tell the app where
          the backend lives.
        </Text>

        <Field label="Backend HTTPS URL" value={httpUrl} onChangeText={setHttpUrl} placeholder="https://your-backend" />
        <Field label="Backend WebSocket URL" value={wsUrl} onChangeText={setWsUrl} placeholder="wss://your-backend/ws" />
        <Field label="API Token" value={token} onChangeText={setToken} placeholder="Bearer token" secureTextEntry />

        <Pressable style={styles.primaryButton} onPress={save}>
          <Text style={styles.primaryLabel}>Save</Text>
        </Pressable>
        <Pressable style={styles.secondaryButton} onPress={testConnection} disabled={checking}>
          <Text style={styles.secondaryLabel}>{checking ? 'Checking…' : 'Test connection'}</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md },
  hint: { ...typography.caption, marginBottom: spacing.sm },
  field: { gap: spacing.xs },
  fieldLabel: { ...typography.caption, color: colors.textSecondary, fontWeight: '600' },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.textPrimary,
  },
  primaryButton: {
    backgroundColor: colors.accent,
    borderRadius: radii.sm,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  primaryLabel: { color: colors.background, fontWeight: '700' },
  secondaryButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingVertical: spacing.sm,
    alignItems: 'center',
  },
  secondaryLabel: { color: colors.textPrimary, fontWeight: '600' },
});
