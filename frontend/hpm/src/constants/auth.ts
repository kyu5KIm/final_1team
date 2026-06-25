import { create } from 'zustand';

export const AUTH_ERRORS = {
  EMAIL_REQUIRED: "이메일을 입력해주세요.",
  PASSWORD_REQUIRED: "비밀번호를 입력해주세요.",
  INVALID_LOGIN: "이메일 또는 비밀번호가 올바르지 않습니다.",
} as const;



interface AuthStore {
  isLoginModalOpen: boolean;
  openLoginModal: () => void;
  closeLoginModal: () => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  isLoginModalOpen: false,
  openLoginModal: () => set({ isLoginModalOpen: true }),
  closeLoginModal: () => set({ isLoginModalOpen: false }),
}));