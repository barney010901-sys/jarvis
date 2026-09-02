import React from 'react';
import { NavigationContainer, DarkTheme, Theme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { HomeScreen } from '../screens/HomeScreen';
import { ChatScreen } from '../screens/ChatScreen';
import { SettingsScreen } from '../screens/SettingsScreen';
import { ApprovalsScreen } from '../screens/ApprovalsScreen';
import { AuditScreen } from '../screens/AuditScreen';
import { MemoryScreen } from '../screens/MemoryScreen';
import { ProjectsScreen } from '../screens/ProjectsScreen';
import { TasksScreen } from '../screens/TasksScreen';
import { WalletScreen } from '../screens/WalletScreen';
import { BusinessScreen } from '../screens/BusinessScreen';
import { colors } from '../theme/theme';

export type RootStackParamList = {
  Home: undefined;
  Chat: undefined;
  Settings: undefined;
  Approvals: undefined;
  Audit: undefined;
  Memory: undefined;
  Projects: undefined;
  Tasks: undefined;
  Wallet: undefined;
  Business: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

const jarvisNavTheme: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.surface,
    text: colors.textPrimary,
    border: colors.border,
    primary: colors.accent,
  },
};

export function RootNavigator() {
  return (
    <NavigationContainer theme={jarvisNavTheme}>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: colors.surface },
          headerTintColor: colors.textPrimary,
          contentStyle: { backgroundColor: colors.background },
        }}
      >
        <Stack.Screen name="Home" component={HomeScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Chat" component={ChatScreen} />
        <Stack.Screen name="Approvals" component={ApprovalsScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Audit" component={AuditScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Memory" component={MemoryScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Projects" component={ProjectsScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Tasks" component={TasksScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Wallet" component={WalletScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Business" component={BusinessScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Settings" component={SettingsScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
