// Minimal stand-in for React in tests: effects run immediately, cleanups are collected.
const cleanups = [];

export function useEffect(effect) {
  const cleanup = effect();
  if (typeof cleanup === "function") cleanups.push(cleanup);
}

export function runCleanups() {
  while (cleanups.length) cleanups.pop()();
}
