"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      if (mode === "signup") {
        await api.signup(email, password);
      }
      const { access_token } = await api.login(email, password);
      window.localStorage.setItem("scenecraft_token", access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach the server. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-charcoal px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-signal">Take one</p>
          <h1 className="mt-2 text-3xl font-semibold text-chalk">SceneCraft</h1>
          <p className="mt-2 text-sm text-chalk/60">Script in. Working previs app out.</p>
        </div>

        <div className="mb-6 h-2 w-16 slate-stripe rounded-sm" aria-hidden="true" />

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="mb-1 block font-mono text-xs uppercase tracking-wide text-chalk/50">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="focus-ring w-full rounded-md border border-wire bg-charcoal2 px-3 py-2 text-chalk outline-none"
              placeholder="you@studio.com"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block font-mono text-xs uppercase tracking-wide text-chalk/50">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="focus-ring w-full rounded-md border border-wire bg-charcoal2 px-3 py-2 text-chalk outline-none"
              placeholder="At least 8 characters"
            />
          </div>

          {error && (
            <p role="alert" className="rounded-md border border-signal/40 bg-signal/10 px-3 py-2 text-sm text-signal">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="focus-ring w-full rounded-md bg-signal px-4 py-2 font-medium text-charcoal transition hover:brightness-95 disabled:opacity-50"
          >
            {isSubmitting ? "Working…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>

        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "signup" : "login")}
          className="focus-ring mt-4 font-mono text-xs uppercase tracking-wide text-chalk/50 underline decoration-wire underline-offset-4 hover:text-chalk"
        >
          {mode === "login" ? "New here? Create an account" : "Already have an account? Log in"}
        </button>
      </div>
    </main>
  );
}
