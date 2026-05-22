import { authClient } from './client';

export const register = (email: string, password: string, display_name: string) =>
  authClient.post('/auth/register', { email, password, display_name });

export const login = (email: string, password: string) =>
  authClient.post('/auth/login', { email, password });

export const refreshToken = (refresh_token: string) =>
  authClient.post('/auth/refresh', { refresh_token });

export const logout = (refresh_token: string) =>
  authClient.post('/auth/logout', { refresh_token });

export const socialLoginGoogle = (id_token: string) =>
  authClient.post('/auth/social/google', { id_token });

export const forgotPassword = (email: string) =>
  authClient.post('/auth/forgot-password', { email });

export const resetPassword = (token: string, new_password: string) =>
  authClient.post('/auth/reset-password', { token, new_password });

export const getMe = () => authClient.get('/users/me');

export const updateMe = (data: Record<string, string>) =>
  authClient.patch('/users/me', data);

export const getHealthProfile = () =>
  authClient.get('/users/me/health-profile');

export const putHealthProfile = (data: Record<string, any>) =>
  authClient.put('/users/me/health-profile', data);

export const deleteAccount = () => authClient.delete('/users/me');
