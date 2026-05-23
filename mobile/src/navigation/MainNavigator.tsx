import React from 'react';
import { createBottomTabNavigator, BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator, NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';

import HomeScreen          from '../screens/HomeScreen';
import RecordScreen        from '../screens/RecordScreen';
import HistoryScreen       from '../screens/HistoryScreen';
import ProfileScreen       from '../screens/ProfileScreen';
import SessionDetailScreen from '../screens/SessionDetailScreen';
import LifestyleLogScreen  from '../screens/LifestyleLogScreen';
import HealthProfileScreen from '../screens/HealthProfileScreen';
import GoalsScreen        from '../screens/GoalsScreen';
import CalendarScreen    from '../screens/CalendarScreen';

// ── Stack param types ────────────────────────────────────────────────────────

export type HomeStackParams = {
  HomeMain:      undefined;
  SessionDetail: { sessionId: string };
};

export type HistoryStackParams = {
  HistoryMain:   undefined;
  SessionDetail: { sessionId: string };
  Calendar:      undefined;
};

export type ProfileStackParams = {
  ProfileMain:   undefined;
  HealthProfile: undefined;
  Goals:         undefined;
};

export type MainTabParams = {
  Home:    undefined;
  Record:  undefined;
  Log:     undefined;
  History: undefined;
  Profile: undefined;
};

export type HomeStackNav    = NativeStackNavigationProp<HomeStackParams>;
export type HistoryStackNav = NativeStackNavigationProp<HistoryStackParams>;
export type ProfileStackNav = NativeStackNavigationProp<ProfileStackParams>;
export type MainTabNav      = BottomTabNavigationProp<MainTabParams>;

const Tab            = createBottomTabNavigator<MainTabParams>();
const HomeStackNav_  = createNativeStackNavigator<HomeStackParams>();
const HistoryStackNav_ = createNativeStackNavigator<HistoryStackParams>();
const ProfileStackNav_ = createNativeStackNavigator<ProfileStackParams>();

function HomeStack() {
  return (
    <HomeStackNav_.Navigator screenOptions={{ headerShown: false }}>
      <HomeStackNav_.Screen name="HomeMain"      component={HomeScreen} />
      <HomeStackNav_.Screen name="SessionDetail" component={SessionDetailScreen} />
    </HomeStackNav_.Navigator>
  );
}

function HistoryStack() {
  return (
    <HistoryStackNav_.Navigator screenOptions={{ headerShown: false }}>
      <HistoryStackNav_.Screen name="HistoryMain"   component={HistoryScreen} />
      <HistoryStackNav_.Screen name="SessionDetail" component={SessionDetailScreen} />
      <HistoryStackNav_.Screen name="Calendar"      component={CalendarScreen} />
    </HistoryStackNav_.Navigator>
  );
}

function ProfileStack() {
  return (
    <ProfileStackNav_.Navigator screenOptions={{ headerShown: false }}>
      <ProfileStackNav_.Screen name="ProfileMain"    component={ProfileScreen} />
      <ProfileStackNav_.Screen name="HealthProfile"  component={HealthProfileScreen} />
      <ProfileStackNav_.Screen name="Goals"          component={GoalsScreen} />
    </ProfileStackNav_.Navigator>
  );
}

const TAB_ICONS: Record<keyof MainTabParams, { default: string; focused: string }> = {
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
          const icons = TAB_ICONS[route.name as keyof MainTabParams];
          const name = focused ? icons?.focused : icons?.default;
          return <Ionicons name={(name ?? 'ellipse-outline') as any} size={22} color={color} />;
        },
      })}
    >
      <Tab.Screen name="Home"    component={HomeStack} />
      <Tab.Screen name="Record"  component={RecordScreen} />
      <Tab.Screen name="Log"     component={LifestyleLogScreen} />
      <Tab.Screen name="History" component={HistoryStack} />
      <Tab.Screen name="Profile" component={ProfileStack} />
    </Tab.Navigator>
  );
}
