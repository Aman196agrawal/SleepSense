import React from 'react';
import { createBottomTabNavigator, BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator, NativeStackNavigationProp } from '@react-navigation/native-stack';
import FloatingTabBar from './FloatingTabBar';

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

export default function MainNavigator() {
  return (
    <Tab.Navigator
      tabBar={(props) => <FloatingTabBar {...props} />}
      screenOptions={{ headerShown: false }}
    >
      <Tab.Screen name="Home"    component={HomeStack} />
      <Tab.Screen name="Log"     component={LifestyleLogScreen} />
      <Tab.Screen name="Record"  component={RecordScreen} />
      <Tab.Screen name="History" component={HistoryStack} />
      <Tab.Screen name="Profile" component={ProfileStack} />
    </Tab.Navigator>
  );
}
