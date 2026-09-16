"use client";

import { useSyncExternalStore } from "react";

// Demo identity for the applicant portal: a company name remembered in this browser. Not authentication.
const KEY = "greenlight.installer";
const EVENT = "greenlight:installer";
export const SAMPLE_INSTALLER = "Redwood Valley Solar & Electric";

function read(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null; // storage unavailable (private mode): sign in again per visit
  }
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function write(value: string | null) {
  try {
    if (value) window.localStorage.setItem(KEY, value);
    else window.localStorage.removeItem(KEY);
  } catch {}
  window.dispatchEvent(new Event(EVENT));
}

export function useInstaller() {
  const installer = useSyncExternalStore(subscribe, read, () => null);
  const ready = useSyncExternalStore(subscribe, () => true, () => false);
  return { installer, ready, signIn: (v: string) => write(v.trim()), signOut: () => write(null) };
}
