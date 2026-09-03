"use client";

import { initializeApp, getApps, getApp } from "firebase/app";
import { getFirestore, doc, onSnapshot, type Unsubscribe } from "firebase/firestore";

// Firebase's client config (apiKey included) is not secret — it identifies
// the project, it doesn't authorize anything on its own. Real access
// control is infra/firestore/firestore.rules: public read scoped to
// exactly job_traces/{jobId}, write blocked for every client. See
// apps/api/src/core/firestore_client.py for the write side and why a
// public-read capability-URL is a deliberate tradeoff, not an oversight.
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

function firestoreConfigured(): boolean {
  return Boolean(firebaseConfig.apiKey && firebaseConfig.projectId);
}

function db() {
  const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
  return getFirestore(app);
}

export interface JobTraceStep {
  agent: string;
  status: string;
  at: string | null;
  completed: number | null;
  total: number | null;
  failed: number | null;
}

export interface JobTrace {
  id: string;
  status: string;
  steps: JobTraceStep[];
  deployed_app_url: string | null;
  error_detail: string | null;
}

/**
 * Live-subscribes to job_traces/{jobId} — PHASE-05-ITERATION-AND-TRACE-UI.md
 * SS7. Firestore pushes the update the instant apps/api writes it, so this
 * is real-time, not a poll loop. Falls back to null immediately (never
 * subscribes) when Firebase isn't configured — callers should fall back to
 * polling GET /jobs/{id} in that case, same data shape either way.
 */
export function subscribeToJobTrace(
  jobId: string,
  onUpdate: (trace: JobTrace | null) => void,
  onError: (error: Error) => void,
): Unsubscribe | null {
  if (!firestoreConfigured()) return null;
  return onSnapshot(
    doc(db(), "job_traces", jobId),
    (snapshot) => onUpdate(snapshot.exists() ? (snapshot.data() as JobTrace) : null),
    onError,
  );
}
