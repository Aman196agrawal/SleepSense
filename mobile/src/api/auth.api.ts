import { authClient } from './client';

export const register = (email: string, password: string, display_name: string) =>
  authClient.post('/auth/register', { email, password, display_name });

export const login = (email: string, password: string) =>
  authClient.post('/auth/login', { email, password });

export const refreshToken = (refresh_token: string) =>
  authClient.post('/auth/refresh', { refresh_token });

export const logout = (refresh_token: string) =>
  authClient.post('/auth/logout', { refresh_token });

export const getMe = () => authClient.get('/users/me');

export const updateMe = (data: Record<string, string>) =>
  authClient.patch('/users/me', data);
