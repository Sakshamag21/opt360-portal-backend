import { useEffect, useState } from 'react';

// Shared, cross-page "RO override" selection for TechCentre/HeadQuarters
// users — these groups see data across all ROs by default (empty string =
// global), but can pick a specific RO from the header to scope down, and
// revert back to global at any time. Persisted in sessionStorage so the
// selection survives a page refresh, and kept in sync across every
// component using this hook via a simple pub/sub (module-level state,
// mirroring useCurrentUser.js's caching pattern — this app doesn't have a
// React Context provider set up, so this is the lightest way to share one
// piece of state across pages that mount/unmount independently via routing).
const STORAGE_KEY = 'opt360_global_ro_override';

let currentRO = (() => {
  try {
    return sessionStorage.getItem(STORAGE_KEY) || '';
  } catch {
    return '';
  }
})();

const subscribers = new Set();

export const getGlobalRO = () => currentRO;

export const setGlobalRO = (ro) => {
  currentRO = ro || '';
  try {
    if (currentRO) {
      sessionStorage.setItem(STORAGE_KEY, currentRO);
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // sessionStorage unavailable (e.g. private browsing edge cases) — the
    // in-memory value still works for the rest of this session.
  }
  subscribers.forEach(fn => fn(currentRO));
};

// Returns [selectedRO, setSelectedRO] — selectedRO is '' for "global" (no
// RO filter). Every RO-scoped fetch in a global user's pages should read
// this and pass it as the `ro` override param/field when non-empty.
export const useGlobalRegionalOffice = () => {
  const [ro, setRo] = useState(currentRO);
  useEffect(() => {
    subscribers.add(setRo);
    return () => subscribers.delete(setRo);
  }, []);
  return [ro, setGlobalRO];
};
