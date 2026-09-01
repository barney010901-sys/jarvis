import React, { useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, SafeAreaView, StyleSheet, Text, TextInput, View } from 'react-native';
import { colors, radii, spacing, typography } from '../theme/theme';
import { ConnectionStatusBadge } from '../components/ConnectionStatusBadge';
import { ConfirmationDialog } from '../components/ConfirmationDialog';
import { useJarvisSocket } from '../hooks/useJarvisSocket';
import { useChatMessages } from '../hooks/useChatMessages';
import { usePendingConfirmation } from '../hooks/usePendingConfirmation';
import { useSettings } from '../context/SettingsContext';
import { approveConfirmation, rejectConfirmation } from '../api/client';

const SESSION_ID = 'android-chat';

export function ChatScreen() {
  const { settings } = useSettings();
  const { status, events, sendUserMessage } = useJarvisSocket();
  const messages = useChatMessages(events);
  const pendingConfirmation = usePendingConfirmation(events);
  const [draft, setDraft] = useState('');

  const send = () => {
    const text = draft.trim();
    if (!text) return;
    const delivered = sendUserMessage({ sessionId: SESSION_ID, text });
    if (delivered) setDraft('');
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={typography.heading}>Chat</Text>
        <ConnectionStatusBadge status={status} />
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={80}
      >
        <FlatList
          style={styles.flex}
          data={messages}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.messages}
          renderItem={({ item }) => (
            <View
              style={[
                styles.bubble,
                item.role === 'user' ? styles.bubbleUser : styles.bubbleAssistant,
                item.isError && styles.bubbleError,
              ]}
            >
              <Text style={item.role === 'user' ? styles.bubbleTextUser : styles.bubbleTextAssistant}>
                {item.text}
                {item.pending ? ' ▍' : ''}
              </Text>
            </View>
          )}
        />

        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            placeholder="Message Jarvis…"
            placeholderTextColor={colors.textMuted}
            value={draft}
            onChangeText={setDraft}
            onSubmitEditing={send}
            returnKeyType="send"
          />
          <Pressable style={styles.sendButton} onPress={send}>
            <Text style={styles.sendLabel}>Send</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>

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
  flex: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.lg,
  },
  messages: { padding: spacing.md, gap: spacing.sm },
  bubble: {
    maxWidth: '85%',
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.xs,
  },
  bubbleUser: {
    alignSelf: 'flex-end',
    backgroundColor: colors.accent,
  },
  bubbleAssistant: {
    alignSelf: 'flex-start',
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.border,
  },
  bubbleError: {
    borderColor: colors.danger,
  },
  bubbleTextUser: { color: colors.background, fontWeight: '600' },
  bubbleTextAssistant: { color: colors.textPrimary },
  inputRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  input: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    color: colors.textPrimary,
  },
  sendButton: {
    backgroundColor: colors.accent,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendLabel: { color: colors.background, fontWeight: '700' },
});
