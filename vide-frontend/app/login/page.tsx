"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";

import { login } from "@/lib/api";
import { setToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const data = (await login(email, password)) as { token: string };
      setToken(data.token);
      router.replace("/dashboard");
    } catch {
      setError("Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#0f0f0f] px-4 py-8">
      <div className="w-full max-w-md rounded-2xl border border-white/5 bg-[#1a1a1a] p-8 shadow-2xl shadow-black/30">
        <div className="mb-8 text-center">
          <div className="bg-gradient-to-r from-violet-400 via-purple-500 to-fuchsia-500 bg-clip-text text-3xl font-semibold tracking-[0.24em] text-transparent">
            ILMORA STUDIOS
          </div>
          <p className="mt-3 text-sm uppercase tracking-[0.3em] text-zinc-400">
            Admin Dashboard
          </p>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit}>
          <div>
            <label
              className="mb-2 block text-sm font-medium text-zinc-200"
              htmlFor="email"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              suppressHydrationWarning={true}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-xl border border-transparent bg-[#2a2a2a] px-4 py-3 text-white outline-none transition focus:border-[#7c3aed] focus:ring-2 focus:ring-[#7c3aed]/30"
              placeholder="admin@ilmora.ai"
              required
            />
          </div>

          <div>
            <label
              className="mb-2 block text-sm font-medium text-zinc-200"
              htmlFor="password"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              suppressHydrationWarning={true}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-transparent bg-[#2a2a2a] px-4 py-3 text-white outline-none transition focus:border-[#7c3aed] focus:ring-2 focus:ring-[#7c3aed]/30"
              placeholder="Enter your password"
              required
            />
          </div>

          {error ? (
            <p className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={loading}
            suppressHydrationWarning={true}
            className="flex w-full items-center justify-center rounded-xl bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 px-4 py-3 text-sm font-semibold text-white transition hover:from-violet-500 hover:via-purple-500 hover:to-fuchsia-500 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {loading ? (
              <span className="flex items-center gap-3">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Signing in...
              </span>
            ) : (
              "Login"
            )}
          </button>
        </form>
      </div>
    </main>
  );
}
