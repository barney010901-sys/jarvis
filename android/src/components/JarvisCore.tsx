import React, { useEffect, useRef } from 'react';
import { Animated, Easing, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, jarvisStateColors } from '../theme/theme';
import type { JarvisState } from '../state/jarvisState';

const LABEL: Record<JarvisState, string> = {
  IDLE: 'HOLD TO TALK',
  LISTENING: 'LISTENING…',
  THINKING: 'THINKING…',
  PROCESSING: 'PROCESSING…',
  USING_TOOL: 'USING A TOOL…',
  WAITING_FOR_CONFIRMATION: 'NEEDS YOUR APPROVAL',
  SPEAKING: 'SPEAKING…',
  ERROR: 'SOMETHING WENT WRONG',
  OFFLINE: 'OFFLINE',
};

// States with continuous motion vs. a static ring. Kept short so the
// animation reads as "state", not decoration (section 4/66).
const PULSING_STATES = new Set<JarvisState>(['LISTENING', 'THINKING', 'PROCESSING', 'USING_TOOL', 'SPEAKING']);

type Props = {
  state: JarvisState;
  onPressIn: () => void;
  onPressOut: () => void;
};

/**
 * The single, elegant visual identity for "is Jarvis alive and what is it
 * doing" (section 3/4) — one component, nine distinguishable states, no
 * separate widgets per screen. Every screen that shows Jarvis's presence
 * (Home, Chat) renders this same component so the identity is consistent.
 */
export function JarvisCore({ state, onPressIn, onPressOut }: Props) {
  const pressScale = useRef(new Animated.Value(1)).current;
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    pulse.stopAnimation();
    pulse.setValue(0);
    if (!PULSING_STATES.has(state)) return;

    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 900, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 900, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [state, pulse]);

  const color = jarvisStateColors[state];
  const glowOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.25, 0.8] });
  const glowScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.12] });

  return (
    <View style={styles.wrapper}>
      <Animated.View
        pointerEvents="none"
        style={[styles.glow, { borderColor: color, opacity: glowOpacity, transform: [{ scale: glowScale }] }]}
      />
      <Animated.View style={[styles.ring, { borderColor: color, transform: [{ scale: pressScale }] }]}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Push to talk to Jarvis"
          disabled={state === 'OFFLINE'}
          onPressIn={() => {
            Animated.spring(pressScale, { toValue: 1.08, useNativeDriver: true, friction: 5 }).start();
            onPressIn();
          }}
          onPressOut={() => {
            Animated.spring(pressScale, { toValue: 1, useNativeDriver: true, friction: 5 }).start();
            onPressOut();
          }}
          style={styles.button}
        >
          <View style={[styles.core, { borderColor: color }]}>
            <Text style={[styles.icon, { color }]}>{state === 'USING_TOOL' ? '⚙' : state === 'WAITING_FOR_CONFIRMATION' ? '⚠' : '●'}</Text>
          </View>
        </Pressable>
      </Animated.View>
      <Text style={[styles.label, { color }]}>{LABEL[state]}</Text>
    </View>
  );
}

const SIZE = 176;

const styles = StyleSheet.create({
  wrapper: { alignItems: 'center', gap: 16 },
  glow: {
    position: 'absolute',
    top: 0,
    width: SIZE,
    height: SIZE,
    borderRadius: SIZE / 2,
    borderWidth: 2,
  },
  ring: {
    width: SIZE,
    height: SIZE,
    borderRadius: SIZE / 2,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceRaised,
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
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
  },
  icon: { fontSize: 40 },
  label: { fontSize: 13, fontWeight: '600', letterSpacing: 2 },
});
