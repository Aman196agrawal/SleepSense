import React, { useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import { View, ActivityIndicator } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useAuthStore } from './src/store/authStore';
import AuthNavigator from './src/navigation/AuthNavigator';
import MainNavigator from './src/navigation/MainNavigator';
import { Colors } from './src/theme/colors';

export default function App() {
  const user      = useAuthStore(s => s.user);
  const isLoading = useAuthStore(s => s.isLoading);
  const hydrate   = useAuthStore(s => s.hydrate);

  useEffect(() => { hydrate(); }, [hydrate]);

  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <StatusBar style="light" />
        {isLoading ? (
          <View style={{ flex: 1, backgroundColor: Colors.bg, justifyContent: 'center', alignItems: 'center' }}>
            <ActivityIndicator color={Colors.primary} size="large" />
          </View>
        ) : user ? (
          <MainNavigator />
        ) : (
          <AuthNavigator />
        )}
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
