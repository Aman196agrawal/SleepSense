import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import OnboardingScreen       from '../screens/OnboardingScreen';
import LoginScreen            from '../screens/LoginScreen';
import RegisterScreen         from '../screens/RegisterScreen';
import ForgotPasswordScreen   from '../screens/ForgotPasswordScreen';
import ResetPasswordScreen    from '../screens/ResetPasswordScreen';
import ApiSettingsScreen      from '../screens/ApiSettingsScreen';

export type AuthStackParams = {
  Onboarding:     undefined;
  Login:          undefined;
  Register:       undefined;
  ForgotPassword: undefined;
  ResetPassword:  undefined;
  // Also reachable before sign-in on purpose: if the backend URL is wrong you
  // cannot log in, and the copy of this screen inside ProfileStack sits behind
  // the login wall — so the only way to fix the URL would be a rebuild.
  ApiSettings:    undefined;
};

const Stack = createNativeStackNavigator<AuthStackParams>();

export default function AuthNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Onboarding"     component={OnboardingScreen} />
      <Stack.Screen name="Login"          component={LoginScreen} />
      <Stack.Screen name="Register"       component={RegisterScreen} />
      <Stack.Screen name="ForgotPassword" component={ForgotPasswordScreen} />
      <Stack.Screen name="ResetPassword"  component={ResetPasswordScreen} />
      <Stack.Screen name="ApiSettings"    component={ApiSettingsScreen} />
    </Stack.Navigator>
  );
}
