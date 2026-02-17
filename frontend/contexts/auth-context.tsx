"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { apiClient, setAuthTokenGetter } from "../lib/api";
import { setRuntimeToken } from "../lib/evaluations";

type User = {
  id: string;
  email: string;
  has_profile: boolean;
};

type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

type AuthContextValue = {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  signup: (email: string, password: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  markProfileComplete: () => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function getPostAuthPath(user: User): string {
  return user.has_profile ? "/evaluate" : "/profile/setup";
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    setAuthTokenGetter(() => token);
    setRuntimeToken(token);
  }, [token]);

  async function signup(email: string, password: string): Promise<void> {
    const { data } = await apiClient.post<AuthResponse>("/api/auth/signup", { email, password });
    setToken(data.access_token);
    setUser(data.user);
    router.push(getPostAuthPath(data.user));
  }

  async function login(email: string, password: string): Promise<void> {
    const { data } = await apiClient.post<AuthResponse>("/api/auth/login", { email, password });
    setToken(data.access_token);
    setUser(data.user);
    router.push(getPostAuthPath(data.user));
  }

  function logout(): void {
    setToken(null);
    setUser(null);
    router.push("/login");
  }

  function markProfileComplete(): void {
    setUser((prev) => (prev ? { ...prev, has_profile: true } : prev));
  }

  const value = useMemo(
    () => ({ token, user, isAuthenticated: token !== null, signup, login, markProfileComplete, logout }),
    [token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
