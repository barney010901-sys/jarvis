import React, { useState } from 'react';
import { RefreshControl, SafeAreaView, ScrollView, StyleSheet, Text, View, Pressable } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { colors, radii, spacing, typography } from '../theme/theme';
import { ConnectionStatusBadge } from '../components/ConnectionStatusBadge';
import { JarvisCore } from '../components/JarvisCore';
import { ConfirmationDialog } from '../components/ConfirmationDialog';
import { TaskProgressPanel } from '../components/TaskProgressPanel';
import { Card } from '../components/Card';
import { StatusPill } from '../components/StatusPill';
import { useJarvisSocket } from '../hooks/useJarvisSocket';
import { usePendingConfirmation } from '../hooks/usePendingConfirmation';
import { useChatMessages } from '../hooks/useChatMessages';
import { useAssistantSpeech } from '../hooks/useAssistantSpeech';
import { useJarvisState } from '../state/jarvisState';
import { useAsyncData } from '../hooks/useAsyncData';
import { useSettings } from '../context/SettingsContext';
import { approveConfirmation, rejectConfirmation } from '../api/client';
import { getDashboard } from '../api/phase3Client';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Home'>;

const SESSION_ID = 'android-home';

/** The command center (section 3/64): Jarvis's presence, what's happening
 * right now, and what needs attention — one screen, not a chatbot with a
 * few buttons. */
export function HomeScreen({ navigation }: Props) {
  const { settings } = useSettings();
  const { status, events, sendUserMessage } = useJarvisSocket();
  const pendingConfirmation = usePendingConfirmation(events);
  const messages = useChatMessages(events);
  const { isSpeaking } = useAssistantSpeech(messages, settings.ttsEnabled);
  const [isRecording, setIsRecording] = useState(false);
  const jarvisState = useJarvisState(events, status, { hasPendingConfirmation: !!pendingConfirmation, isRecording, isSpeaking });

  const { data: dashboard, loading, refresh } = useAsyncData(
    () => getDashboard(settings),
    [settings.backendHttpUrl, settings.apiToken, events.length]
  );

  // Phase 3: push-to-talk still doesn't capture real audio — no wake
  // word/VAD/STT pipeline ships in this build (see docs/PHASE_3.md,
  // "NOT_IMPLEMENTED"). Holding JarvisCore sends a fixed demo message so
  // the full context -> planner -> Claude -> tools -> response pipeline
  // can be observed end to end; swapping in real capture only changes
  // these two handlers.
  const handlePressIn = () => setIsRecording(true);
  const handlePressOut = () => {
    setIsRecording(false);
    sendUserMessage({ sessionId: SESSION_ID, text: 'What is the status of my current project?' });
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={colors.accent} />}
      >
        <View style={styles.header}>
          <Text style={typography.title}>JARVIS</Text>
          <ConnectionStatusBadge status={status} />
        </View>

        <JarvisCore state={jarvisState} onPressIn={handlePressIn} onPressOut={handlePressOut} />

        {!!dashboard?.pending_approvals.length && (
          <Card title="Needs your approval">
            {dashboard.pending_approvals.slice(0, 3).map((a) => (
              <Text key={a.id} style={styles.rowText} numberOfLines={1}>• {a.title}</Text>
            ))}
            <Pressable onPress={() => navigation.navigate('Approvals')}>
              <Text style={styles.link}>Review all ({dashboard.pending_approvals.length}) →</Text>
            </Pressable>
          </Card>
        )}

        {!!dashboard?.suggestions.length && (
          <Card title="Suggestions">
            {dashboard.suggestions.slice(0, 3).map((s) => (
              <Text key={s.id} style={styles.rowText} numberOfLines={2}>• {s.title}</Text>
            ))}
          </Card>
        )}

        <View style={styles.statusRow}>
          {dashboard?.wallet && (
            <Card title="Wallet" style={styles.statusCard}>
              <Pressable onPress={() => navigation.navigate('Wallet')}>
                <Text style={styles.bigNumber}>${dashboard.wallet.balance_usd.toFixed(2)}</Text>
                <Text style={styles.rowText}>${dashboard.wallet.weekly_spent.toFixed(2)} / ${dashboard.wallet.weekly_limit.toFixed(2)} this week</Text>
              </Pressable>
            </Card>
          )}
          {dashboard?.business && (
            <Card title="Business" style={styles.statusCard}>
              <Pressable onPress={() => navigation.navigate('Business')}>
                <Text style={styles.bigNumber}>{dashboard.business.stage}</Text>
                <Text style={styles.rowText}>${dashboard.business.surplus_usd.toFixed(2)} surplus</Text>
              </Pressable>
            </Card>
          )}
        </View>

        <Card title="System health">
          <View style={styles.healthGrid}>
            {(dashboard?.system_health ?? []).map((c) => (
              <StatusPill key={c.component} status={c.status} label={c.component} />
            ))}
          </View>
        </Card>

        <Card title="Task activity">
          <TaskProgressPanel events={events} />
        </Card>

        <View style={styles.nav}>
          {(
            [
              ['Chat', 'Chat'],
              ['Memory', 'Memory'],
              ['Projects', 'Projects'],
              ['Tasks', 'Tasks'],
              ['Wallet', 'Wallet'],
              ['Business', 'Business'],
              ['Audit', 'Audit'],
              ['Settings', 'Settings'],
            ] as const
          ).map(([label, route]) => (
            <Pressable key={route} style={styles.navButton} onPress={() => navigation.navigate(route)}>
              <Text style={styles.navButtonText}>{label}</Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>

      <ConfirmationDialog
        request={pendingConfirmation}
        onApprove={(id) => approveConfirmation(settings, id)}
        onReject={(id) => rejectConfirmation(settings, id)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  scrollContent: { padding: spacing.lg, gap: spacing.md },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  rowText: { ...typography.caption, color: colors.textSecondary },
  link: { ...typography.caption, color: colors.accent, fontWeight: '700', marginTop: spacing.xs },
  statusRow: { flexDirection: 'row', gap: spacing.sm },
  statusCard: { flex: 1 },
  bigNumber: { ...typography.heading, color: colors.textPrimary },
  healthGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
  nav: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  navButton: {
    flexGrow: 1,
    minWidth: '30%',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  navButtonText: { color: colors.textPrimary, fontWeight: '600' },
});
