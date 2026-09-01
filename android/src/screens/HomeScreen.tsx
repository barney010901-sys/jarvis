import React, { useState } from 'react';
import { SafeAreaView, StyleSheet, Text, View, Pressable } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { colors, spacing, typography } from '../theme/theme';
import { ConnectionStatusBadge } from '../components/ConnectionStatusBadge';
import { VoiceButton, type VoiceButtonState } from '../components/VoiceButton';
import { ConfirmationDialog } from '../components/ConfirmationDialog';
import { TaskProgressPanel } from '../components/TaskProgressPanel';
import { useJarvisSocket } from '../hooks/useJarvisSocket';
import { usePendingConfirmation } from '../hooks/usePendingConfirmation';
import { useSettings } from '../context/SettingsContext';
import { approveConfirmation, rejectConfirmation } from '../api/client';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Home'>;

const SESSION_ID = 'android-home';

export function HomeScreen({ navigation }: Props) {
  const { settings } = useSettings();
  const { status, events, sendUserMessage } = useJarvisSocket();
  const pendingConfirmation = usePendingConfirmation(events);
  const [voiceState, setVoiceState] = useState<VoiceButtonState>('idle');

  // Phase 1: push-to-talk does not capture real audio yet (see
  // docs/PHASE_1.md). Holding the button sends a fixed demo message so the
  // full event pipeline (task.created -> ... -> task.completed) can be
  // observed end to end; wiring real STT capture here is a Phase 2 change
  // that will replace this handler's body, not the button itself.
  const handlePressIn = () => {
    setVoiceState('listening');
  };

  const handlePressOut = () => {
    setVoiceState('processing');
    sendUserMessage({ sessionId: SESSION_ID, text: 'What is the status of my current project?' });
    setTimeout(() => setVoiceState('idle'), 600);
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={typography.title}>JARVIS</Text>
        <ConnectionStatusBadge status={status} />
      </View>

      <View style={styles.voiceArea}>
        <VoiceButton state={voiceState} onPressIn={handlePressIn} onPressOut={handlePressOut} />
      </View>

      <View style={styles.progressArea}>
        <Text style={styles.sectionLabel}>TASK ACTIVITY</Text>
        <TaskProgressPanel events={events} />
      </View>

      <View style={styles.nav}>
        <Pressable style={styles.navButton} onPress={() => navigation.navigate('Chat')}>
          <Text style={styles.navButtonText}>Chat</Text>
        </Pressable>
        <Pressable style={styles.navButton} onPress={() => navigation.navigate('Settings')}>
          <Text style={styles.navButtonText}>Settings</Text>
        </Pressable>
      </View>

      <ConfirmationDialog
        request={pendingConfirmation}
        onApprove={(id) => approveConfirmation(settings, id)}
        onReject={(id) => rejectConfirmation(settings, id)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing.lg, gap: spacing.lg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  voiceArea: { alignItems: 'center', paddingVertical: spacing.lg },
  progressArea: { flex: 1, gap: spacing.sm },
  sectionLabel: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.5,
  },
  nav: { flexDirection: 'row', gap: spacing.sm },
  navButton: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  navButtonText: { color: colors.textPrimary, fontWeight: '600' },
});
