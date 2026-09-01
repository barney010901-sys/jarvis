import React, { useRef } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors } from '../theme/theme';

export type VoiceButtonState = 'idle' | 'listening' | 'processing';

const LABEL: Record<VoiceButtonState, string> = {
  idle: 'HOLD TO TALK',
  listening: 'LISTENING…',
  processing: 'PROCESSING…',
};

type Props = {
  state: VoiceButtonState;
  onPressIn: () => void;
  onPressOut: () => void;
};

/**
 * Push-to-talk affordance. Phase 1: visual state machine only — pressing
 * it does not record audio yet (STT capture is a Phase 2 change; see
 * docs/PHASE_1.md). The states this renders (idle/listening/processing)
 * are exactly what a real audio pipeline will drive later.
 */
export function VoiceButton({ state, onPressIn, onPressOut }: Props) {
  const scale = useRef(new Animated.Value(1)).current;

  const animateTo = (value: number) => {
    Animated.spring(scale, { toValue: value, useNativeDriver: true, friction: 5 }).start();
  };

  return (
    <View style={styles.wrapper}>
      <Animated.View
        style={[
          styles.ring,
          state === 'listening' && styles.ringListening,
          state === 'processing' && styles.ringProcessing,
          { transform: [{ scale }] },
        ]}
      >
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Push to talk to Jarvis"
          onPressIn={() => {
            animateTo(1.08);
            onPressIn();
          }}
          onPressOut={() => {
            animateTo(1);
            onPressOut();
          }}
          style={styles.button}
        >
          <View style={styles.core}>
            <Text style={styles.icon}>{state === 'processing' ? '◌' : '●'}</Text>
          </View>
        </Pressable>
      </Animated.View>
      <Text style={styles.label}>{LABEL[state]}</Text>
    </View>
  );
}

const SIZE = 176;

const styles = StyleSheet.create({
  wrapper: { alignItems: 'center', gap: 16 },
  ring: {
    width: SIZE,
    height: SIZE,
    borderRadius: SIZE / 2,
    borderWidth: 2,
    borderColor: colors.accentDim,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.accentSoft,
  },
  ringListening: {
    borderColor: colors.accent,
    shadowColor: colors.accent,
    shadowOpacity: 0.9,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 0 },
  },
  ringProcessing: {
    borderColor: colors.warning,
  },
  button: {
    width: SIZE - 24,
    height: SIZE - 24,
    borderRadius: (SIZE - 24) / 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  core: {
    width: SIZE - 48,
    height: SIZE - 48,
    borderRadius: (SIZE - 48) / 2,
    backgroundColor: colors.surfaceRaised,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  icon: { fontSize: 40, color: colors.accent },
  label: {
    color: colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
    letterSpacing: 2,
  },
});
