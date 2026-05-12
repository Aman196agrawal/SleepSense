import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';

import HomeScreen          from '../screens/HomeScreen';
import RecordScreen        from '../screens/RecordScreen';
import HistoryScreen       from '../screens/HistoryScreen';
import ProfileScreen       from '../screens/ProfileScreen';
import SessionDetailScreen from '../screens/SessionDetailScreen';
import LifestyleLogScreen  from '../screens/LifestyleLogScreen';

const Tab   = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

function HomeStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="HomeMain"      component={HomeScreen} />
      <Stack.Screen name="SessionDetail" component={SessionDetailScreen} />
    </Stack.Navigator>
  );
}

function HistoryStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="HistoryMain"   component={HistoryScreen} />
      <Stack.Screen name="SessionDetail" component={SessionDetailScreen} />
    </Stack.Navigator>
  );
}

const TAB_ICONS: Record<string, { default: string; focused: string }> = {
  Home:      { default: 'home-outline',      focused: 'home' },
  Record:    { default: 'mic-outline',        focused: 'mic' },
  Log:       { default: 'leaf-outline',       focused: 'leaf' },
  History:   { default: 'bar-chart-outline',  focused: 'bar-chart' },
  Profile:   { default: 'person-outline',     focused: 'person' },
};

export default function MainNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: {
          backgroundColor: Colors.surface,
          borderTopColor: Colors.border,
          height: 62,
          paddingBottom: 8,
        },
        tabBarActiveTintColor: Colors.primary,
        tabBarInactiveTintColor: Colors.textMuted,
        tabBarLabelStyle: { fontSize: 10, marginTop: 2 },
        tabBarIcon: ({ color, focused }) => {
          const icons = TAB_ICONS[route.name];
          const name = focused ? icons?.focused : icons?.default;
          return <Ionicons name={(name ?? 'ellipse-outline') as any} size={22} color={color} />;
        },
      })}
    >
      <Tab.Screen name="Home"    component={HomeStack} />
      <Tab.Screen name="Record"  component={RecordScreen} />
      <Tab.Screen name="Log"     component={LifestyleLogScreen} options={{ title: 'Log' }} />
      <Tab.Screen name="History" component={HistoryStack} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}
