import { create } from 'zustand';
import * as AuthAPI from '../api/auth.api';
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from '../api/tokenStore';

interface User {
  id: string;
  email: string;
  display_name?: string;
  timezone: string;
  bedtime_reminder_time?: string;
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  socialLoginGoogle: (id_token: string) => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  resetPassword: (token: string, new_password: string) => Promise<void>;
  updateProfile: (data: Record<string, any>) => Promise<void>;
  logout: () => Promise<void>;
  hydrate: () => Promise<void>;
}

// Token storage lives in the device keychain/keystore (see ../api/tokenStore.ts)
// and is consumed by the axios interceptor (see ../api/client.ts). We deliberately
// don't mirror the tokens into Zustand state — nothing in the UI re-renders on
// token rotation, so keeping them in a reactive store would just be dead weight.

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,

  hydrate: async () => {
    const token = await getAccessToken();
    if (token) {
      try {
        const res = await AuthAPI.getMe();
        set({ user: res.data, isLoading: false });
      } catch {
        await clearTokens();
        set({ isLoading: false });
      }
    } else {
      set({ isLoading: false });
    }
  },

  login: async (email, password) => {
    const res = await AuthAPI.login(email, password);
    await setTokens(res.data.access_token, res.data.refresh_token);
    const me = await AuthAPI.getMe();
    set({ user: me.data });
  },

  register: async (email, password, name) => {
    const res = await AuthAPI.register(email, password, name);
    await setTokens(res.data.access_token, res.data.refresh_token);
    const me = await AuthAPI.getMe();
    set({ user: me.data });
  },

  socialLoginGoogle: async (id_token) => {
    const res = await AuthAPI.socialLoginGoogle(id_token);
    await setTokens(res.data.access_token, res.data.refresh_token);
    const me = await AuthAPI.getMe();
    set({ user: me.data });
  },

  forgotPassword: async (email) => {
    await AuthAPI.forgotPassword(email);
  },

  resetPassword: async (token, new_password) => {
    await AuthAPI.resetPassword(token, new_password);
  },

  updateProfile: async (data) => {
    await AuthAPI.updateMe(data);
    const me = await AuthAPI.getMe();
    set({ user: me.data });
  },

  logout: async () => {
    const rt = await getRefreshToken();
    if (rt) await AuthAPI.logout(rt).catch(() => {});
    await clearTokens();
    set({ user: null });
  },
}));
