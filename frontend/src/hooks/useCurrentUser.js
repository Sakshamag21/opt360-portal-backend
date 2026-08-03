import { useEffect, useState } from 'react';
import { API_BASE_URL, getAuthHeaders } from '../config/apiConfig';

const IS_DEV = process.env.REACT_APP_ENV === 'dev';

// Kept in sync with ProfilePage.jsx's DEV_PROFILE — role is "superadmin" so every
// dev-mode page renders with full-privilege header content for easy local testing.
export const DEV_PROFILE = {
  ad_id: 'dev-user',
  name: 'Local Dev User',
  regional_office: 'Delhi',
  role: 'superadmin',
  email: 'dev-user@localhost',
  status: 'active',
  last_login: new Date().toISOString()
};

// Module-level cache: POST /api/profile is called once per SPA session (first
// mount of whichever page loads first), not once per page navigation. This also
// means the last_login stamp (a side effect of that endpoint) only fires once per
// session rather than on every page view — see docs/RBAC_PLAN.md §4.
let cachedProfile = null;

/**
 * Shared current-user profile (name/regional_office/role/email) so every page's
 * header (via PageNavigation) renders the same authoritative info, sourced from
 * the backend rather than each page independently decoding sessionStorage.
 */
export const useCurrentUser = () => {
  const [profile, setProfile] = useState(cachedProfile);
  const [loading, setLoading] = useState(!cachedProfile);

  useEffect(() => {
    if (cachedProfile) return;
    let cancelled = false;

    const load = async () => {
      if (IS_DEV) {
        await new Promise(r => setTimeout(r, 100));
        if (!cancelled) {
          cachedProfile = DEV_PROFILE;
          setProfile(DEV_PROFILE);
          setLoading(false);
        }
        return;
      }
      try {
        const response = await fetch(`${API_BASE_URL}/api/profile`, { method: 'POST', headers: getAuthHeaders() });
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const data = await response.json();
        if (!cancelled) {
          cachedProfile = data;
          setProfile(data);
        }
      } catch (err) {
        console.error('Error fetching current user:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, []);

  return { profile, loading };
};
