import React, { useEffect, useState, useCallback } from 'react';
import { LogOut, UserPlus, Users, Mail, Shield, Pencil, Loader } from 'lucide-react';
import PageNavigation from './PageNavigation';
import PageWrapper from './ui/PageWrapper';
import LoadingSpinner from './ui/LoadingSpinner';
import authService from '../services/AuthService';
import { API_BASE_URL, getAuthHeaders } from '../config/apiConfig';
import { GROUPS, GLOBAL_GROUPS } from '../constants';
import { DEV_PROFILE } from '../hooks/useCurrentUser';
import { useGlobalRegionalOffice } from '../hooks/useGlobalRegionalOffice';

const IS_DEV = process.env.REACT_APP_ENV === 'dev';

const DEV_TEAM = [
  { ad_id: 'dev-user', name: 'Local Dev User', email: 'dev-user@localhost', regional_office: 'Delhi', role: 'superadmin', status: 'active', last_login: new Date().toISOString() },
  { ad_id: 'jdoe01', name: 'Jane Doe', email: 'jane.doe@example.com', regional_office: 'Delhi', role: 'admin', status: 'active', last_login: '2026-06-30T09:12:00Z' },
  { ad_id: 'asmith', name: 'Alex Smith', email: 'alex.smith@example.com', regional_office: 'Delhi', role: 'user', status: 'inactive', last_login: null }
];

const formatLastLogin = (value) => {
  if (!value) return 'Never';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? 'Never' : d.toLocaleString();
};

const StatusBadge = ({ status }) => (
  <span className={`text-xs px-2 py-1 rounded-full font-medium ${
    status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-600'
  }`}>
    {status === 'active' ? 'Active' : 'Inactive'}
  </span>
);

const ProfilePage = () => {
  const [profile, setProfile] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [globalRO] = useGlobalRegionalOffice();

  const [emailDraft, setEmailDraft] = useState('');
  const [editingEmail, setEditingEmail] = useState(false);
  const [savingEmail, setSavingEmail] = useState(false);
  const [emailMessage, setEmailMessage] = useState(null);

  const [team, setTeam] = useState([]);
  const [loadingTeam, setLoadingTeam] = useState(true);
  const [teamGroupFilter, setTeamGroupFilter] = useState('');
  const [teamMessage, setTeamMessage] = useState(null);

  const [showOnboardForm, setShowOnboardForm] = useState(false);
  const [onboardForm, setOnboardForm] = useState({ ad_id: '', name: '', email: '', role: 'user', group: '' });
  const [onboarding, setOnboarding] = useState(false);
  const [onboardMessage, setOnboardMessage] = useState(null);

  const [updatingId, setUpdatingId] = useState(null);

  const isAdmin = profile?.role === 'admin';
  const isSuperadmin = profile?.role === 'superadmin';
  const canManageTeam = isAdmin || isSuperadmin;
  const isGlobalUser = profile && GLOBAL_GROUPS.includes(profile.regional_office);

  // First load (no data yet) shows the full-panel spinner; once the table has
  // data, subsequent fetches (group switch, post-onboard/update refresh) just
  // dim the existing table instead of replacing it with a spinner — avoids the
  // whole team list flashing away for a single-row change.
  const isTeamFirstLoad = loadingTeam && team.length === 0;
  const isTeamRefetching = loadingTeam && team.length > 0;

  const fetchProfile = useCallback(async () => {
    setLoadingProfile(true);
    if (IS_DEV) {
      await new Promise(r => setTimeout(r, 200));
      setProfile(DEV_PROFILE);
      setEmailDraft(DEV_PROFILE.email);
      setLoadingProfile(false);
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/profile`, { method: 'POST', headers: getAuthHeaders() });
      if (!response.ok) throw new Error(`API error: ${response.status}`);
      const data = await response.json();
      setProfile(data);
      setEmailDraft(data.email || '');
    } catch (err) {
      console.error('Error fetching profile:', err);
    } finally {
      setLoadingProfile(false);
    }
  }, []);

  const fetchTeam = useCallback(async (group) => {
    setLoadingTeam(true);
    setTeamMessage(null);
    if (IS_DEV) {
      await new Promise(r => setTimeout(r, 200));
      const g = group || DEV_PROFILE.regional_office;
      setTeam(DEV_TEAM.filter(m => m.regional_office === g));
      setLoadingTeam(false);
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/team`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(group ? { group } : {})
      });
      if (!response.ok) throw new Error(`API error: ${response.status}`);
      const data = await response.json();
      setTeam(data.data || []);
    } catch (err) {
      console.error('Error fetching team:', err);
      setTeamMessage({ type: 'error', text: 'Failed to load team.' });
    } finally {
      setLoadingTeam(false);
    }
  }, []);

  useEffect(() => { fetchProfile(); }, [fetchProfile]);

  useEffect(() => {
    if (!profile) return;
    // TechCentre/HeadQuarters are global groups, not real RO team filters —
    // default the team list to whichever RO is currently being viewed via
    // the header's global RO selector (or all ROs, when none is picked).
    const isGlobal = GLOBAL_GROUPS.includes(profile.regional_office);
    const defaultGroup = isGlobal ? globalRO : profile.regional_office;
    setTeamGroupFilter(defaultGroup);
    fetchTeam(defaultGroup);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile, fetchTeam]);

  const handleGroupFilterChange = (group) => {
    setTeamGroupFilter(group);
    fetchTeam(group);
  };

  const handleSaveEmail = async () => {
    setSavingEmail(true);
    setEmailMessage(null);
    if (IS_DEV) {
      await new Promise(r => setTimeout(r, 200));
      setProfile(p => ({ ...p, email: emailDraft }));
      setEditingEmail(false);
      setSavingEmail(false);
      setEmailMessage({ type: 'success', text: 'Email updated (dev mode, not persisted).' });
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/profile/update_email`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ email: emailDraft })
      });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || `API error: ${response.status}`);
      }
      setProfile(p => ({ ...p, email: emailDraft }));
      setEditingEmail(false);
      setEmailMessage({ type: 'success', text: 'Email updated.' });
    } catch (err) {
      setEmailMessage({ type: 'error', text: err.message });
    } finally {
      setSavingEmail(false);
    }
  };

  const handleOnboard = async (e) => {
    e.preventDefault();
    setOnboarding(true);
    setOnboardMessage(null);
    const body = { ad_id: onboardForm.ad_id.trim(), name: onboardForm.name.trim(), email: onboardForm.email.trim() };
    if (isSuperadmin) {
      body.role = onboardForm.role;
      body.group = onboardForm.group || profile.regional_office;
    }
    if (IS_DEV) {
      await new Promise(r => setTimeout(r, 200));
      setTeam(t => [...t, {
        ad_id: body.ad_id, name: body.name, email: body.email,
        regional_office: body.group || profile.regional_office,
        role: body.role || 'user', status: 'active', last_login: null
      }]);
      setOnboardMessage({ type: 'success', text: 'User onboarded (dev mode, not persisted).' });
      setOnboardForm({ ad_id: '', name: '', email: '', role: 'user', group: '' });
      setOnboarding(false);
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/team/onboard`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(body)
      });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || `API error: ${response.status}`);
      }
      setOnboardMessage({ type: 'success', text: 'User onboarded successfully.' });
      setOnboardForm({ ad_id: '', name: '', email: '', role: 'user', group: '' });
      fetchTeam(teamGroupFilter);
    } catch (err) {
      setOnboardMessage({ type: 'error', text: err.message });
    } finally {
      setOnboarding(false);
    }
  };

  const updateMember = async (adId, patch) => {
    setUpdatingId(adId);
    setTeamMessage(null);
    if (IS_DEV) {
      await new Promise(r => setTimeout(r, 150));
      setTeam(t => t.map(m => (m.ad_id === adId ? { ...m, ...patch, regional_office: patch.group || m.regional_office } : m)));
      setUpdatingId(null);
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/team/update`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ ad_id: adId, ...patch })
      });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || `API error: ${response.status}`);
      }
      fetchTeam(teamGroupFilter);
    } catch (err) {
      setTeamMessage({ type: 'error', text: err.message });
    } finally {
      setUpdatingId(null);
    }
  };

  if (loadingProfile) return <LoadingSpinner message="Loading profile..." />;

  return (
    <PageWrapper>
      <PageNavigation currentPage="profile" />

      {/* Own profile card */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{profile.name}</h2>
            <p className="text-sm text-gray-500">{profile.ad_id}</p>
          </div>
          <button
            onClick={() => authService.logout()}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-lg font-semibold shadow"
          >
            <LogOut className="w-4 h-4" /> Logout
          </button>
        </div>

        <div className={`mt-5 grid grid-cols-1 sm:grid-cols-3 ${isGlobalUser ? 'lg:grid-cols-4' : ''} gap-4`}>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">Group</p>
            <p className="font-semibold text-gray-900">{profile.regional_office}</p>
          </div>
          {isGlobalUser && (
            <div className="bg-gray-50 rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-1">Currently Viewing</p>
              <p className="font-semibold text-gray-900">{globalRO || 'All Regional Offices (Global)'}</p>
            </div>
          )}
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">Role</p>
            <p className="font-semibold text-gray-900 capitalize flex items-center gap-1">
              <Shield className="w-4 h-4 text-purple-500" /> {profile.role}
            </p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1 flex items-center gap-1"><Mail className="w-3 h-3" /> Email</p>
            {editingEmail ? (
              <div className="flex items-center gap-2">
                <input
                  type="email"
                  value={emailDraft}
                  onChange={(e) => setEmailDraft(e.target.value)}
                  disabled={savingEmail}
                  className="border border-gray-300 rounded px-2 py-1 text-sm w-full disabled:opacity-50"
                  placeholder="you@example.com"
                />
                <button
                  onClick={handleSaveEmail}
                  disabled={savingEmail}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white rounded font-medium disabled:opacity-50"
                >
                  {savingEmail && <Loader className="w-3 h-3 animate-spin" />}
                  {savingEmail ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={() => { setEditingEmail(false); setEmailDraft(profile.email || ''); }}
                  disabled={savingEmail}
                  className="text-xs px-3 py-1.5 bg-gray-200 hover:bg-gray-300 rounded font-medium disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <p className="font-semibold text-gray-900">{profile.email || '—'}</p>
                <button onClick={() => setEditingEmail(true)} className="text-gray-400 hover:text-blue-500">
                  <Pencil className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        </div>
        {emailMessage && (
          <p className={`mt-3 text-sm ${emailMessage.type === 'error' ? 'text-red-600' : 'text-green-600'}`}>
            {emailMessage.text}
          </p>
        )}
      </div>

      {/* My Team */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="flex items-center justify-between flex-wrap gap-4 mb-4">
          <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Users className="w-5 h-5 text-blue-500" /> My Team
            {isTeamRefetching && <Loader className="w-4 h-4 text-blue-500 animate-spin" />}
          </h3>
          <div className="flex items-center gap-3">
            {isSuperadmin && (
              <select
                value={teamGroupFilter}
                onChange={(e) => handleGroupFilterChange(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                {GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            )}
            {canManageTeam && (
              <button
                onClick={() => setShowOnboardForm(s => !s)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg text-sm font-medium"
              >
                <UserPlus className="w-4 h-4" /> Onboard User
              </button>
            )}
          </div>
        </div>

        {showOnboardForm && canManageTeam && (
          <form onSubmit={handleOnboard} className="mb-5 p-4 bg-gray-50 rounded-lg grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
          <fieldset disabled={onboarding} className="contents disabled:opacity-60">
            <div>
              <label className="text-xs text-gray-500 block mb-1">ADID</label>
              <input required value={onboardForm.ad_id} onChange={(e) => setOnboardForm(f => ({ ...f, ad_id: e.target.value }))} className="border border-gray-300 rounded px-2 py-1.5 text-sm w-full" />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Name</label>
              <input required value={onboardForm.name} onChange={(e) => setOnboardForm(f => ({ ...f, name: e.target.value }))} className="border border-gray-300 rounded px-2 py-1.5 text-sm w-full" />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Email</label>
              <input required type="email" value={onboardForm.email} onChange={(e) => setOnboardForm(f => ({ ...f, email: e.target.value }))} className="border border-gray-300 rounded px-2 py-1.5 text-sm w-full" />
            </div>
            {isSuperadmin && (
              <>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Role</label>
                  <select value={onboardForm.role} onChange={(e) => setOnboardForm(f => ({ ...f, role: e.target.value }))} className="border border-gray-300 rounded px-2 py-1.5 text-sm w-full">
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                    <option value="superadmin">superadmin</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Group</label>
                  <select value={onboardForm.group || profile.regional_office} onChange={(e) => setOnboardForm(f => ({ ...f, group: e.target.value }))} className="border border-gray-300 rounded px-2 py-1.5 text-sm w-full">
                    {GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                </div>
              </>
            )}
            <div className="sm:col-span-2 lg:col-span-5">
              <button type="submit" disabled={onboarding} className="flex items-center gap-1.5 px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                {onboarding && <Loader className="w-3.5 h-3.5 animate-spin" />}
                {onboarding ? 'Onboarding...' : 'Create User'}
              </button>
              {onboardMessage && (
                <span className={`ml-3 text-sm ${onboardMessage.type === 'error' ? 'text-red-600' : 'text-green-600'}`}>
                  {onboardMessage.text}
                </span>
              )}
            </div>
          </fieldset>
          </form>
        )}

        {teamMessage && (
          <p className={`mb-3 text-sm ${teamMessage.type === 'error' ? 'text-red-600' : 'text-green-600'}`}>{teamMessage.text}</p>
        )}

        {isTeamFirstLoad ? (
          <LoadingSpinner message="Loading team..." />
        ) : (
          <div className={`overflow-x-auto transition-opacity ${isTeamRefetching ? 'opacity-50 pointer-events-none' : ''}`}>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">ADID</th>
                  <th className="py-2 pr-4">Email</th>
                  <th className="py-2 pr-4">Role</th>
                  <th className="py-2 pr-4">Last Login</th>
                  <th className="py-2 pr-4">Status</th>
                  {canManageTeam && <th className="py-2 pr-4">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {team.map(member => (
                  <tr key={member.ad_id} className={`border-b last:border-0 transition-opacity ${updatingId === member.ad_id ? 'opacity-60' : ''}`}>
                    <td className="py-2 pr-4 font-medium text-gray-900">{member.name}</td>
                    <td className="py-2 pr-4 text-gray-600">{member.ad_id}</td>
                    <td className="py-2 pr-4 text-gray-600">{member.email || '—'}</td>
                    <td className="py-2 pr-4 capitalize text-gray-600">
                      {isSuperadmin ? (
                        <select
                          value={member.role}
                          disabled={updatingId === member.ad_id}
                          onChange={(e) => updateMember(member.ad_id, { role: e.target.value })}
                          className="border border-gray-300 rounded px-1.5 py-1 text-xs disabled:opacity-50"
                        >
                          <option value="user">user</option>
                          <option value="admin">admin</option>
                          <option value="superadmin">superadmin</option>
                        </select>
                      ) : member.role}
                    </td>
                    <td className="py-2 pr-4 text-gray-600">{formatLastLogin(member.last_login)}</td>
                    <td className="py-2 pr-4"><StatusBadge status={member.status} /></td>
                    {canManageTeam && (
                      <td className="py-2 pr-4">
                        <div className="flex items-center gap-2">
                          <button
                            disabled={updatingId === member.ad_id}
                            onClick={() => updateMember(member.ad_id, { status: member.status === 'active' ? 'inactive' : 'active' })}
                            className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded font-medium bg-gray-100 hover:bg-gray-200 text-gray-700 disabled:opacity-50"
                          >
                            {updatingId === member.ad_id && <Loader className="w-3 h-3 animate-spin" />}
                            {member.status === 'active' ? 'Deactivate' : 'Activate'}
                          </button>
                          {isSuperadmin && (
                            <select
                              value={member.regional_office}
                              disabled={updatingId === member.ad_id}
                              onChange={(e) => updateMember(member.ad_id, { group: e.target.value })}
                              className="border border-gray-300 rounded px-1.5 py-1 text-xs disabled:opacity-50"
                            >
                              {GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
                            </select>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
                {team.length === 0 && (
                  <tr>
                    <td colSpan={canManageTeam ? 7 : 6} className="py-6 text-center text-gray-400">No team members found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageWrapper>
  );
};

export default ProfilePage;
