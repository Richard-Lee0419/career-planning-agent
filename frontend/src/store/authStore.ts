import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AccountInfo, CurrentUserResponse } from '../api/types';
import { clearLegacyPrivateStorage } from '../utils/privateStorage';

interface AuthState {
  token: string | null;
  account: AccountInfo | null;
  userProfileSummary: CurrentUserResponse['data']['profile'] | null;
  setToken: (token: string | null) => void;
  setCurrentUser: (payload: CurrentUserResponse['data']) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      account: null,
      userProfileSummary: null,
      setToken: (token) => set({ token, account: null, userProfileSummary: null }),
      setCurrentUser: (payload) => {
        clearLegacyPrivateStorage();
        set({
          account: payload.account,
          userProfileSummary: payload.profile
        });
      },
      logout: () => {
        clearLegacyPrivateStorage();
        set({ token: null, account: null, userProfileSummary: null });
      }
    }),
    {
      name: 'ai-career-auth'
    }
  )
);
