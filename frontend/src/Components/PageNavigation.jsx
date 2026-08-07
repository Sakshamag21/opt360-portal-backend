import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, ChevronRight, Home, UserCircle, Globe } from 'lucide-react';
import { useCurrentUser } from '../hooks/useCurrentUser';
import { useGlobalRegionalOffice } from '../hooks/useGlobalRegionalOffice';
import { REGIONAL_OFFICES, GLOBAL_GROUPS } from '../constants';

const TABS = [
  { key: 'overview',         label: 'Overview',               path: '/dashboard' },
  // Hidden for now — keeping for future re-enable.
  // { key: 'anomaly',          label: 'Anomaly Indicators',     path: '/anomalyindicators' },
  { key: 'region',           label: 'Region Evaluation',      path: '/regionevaluation' },
  { key: 'featureanalysis',  label: 'Feature Analysis',       path: '/featureanalysis' },
  { key: 'viewoperators',    label: 'View Operators',         path: '/viewoperators' },
  { key: 'search',           label: 'Search Packet Details',  path: '/searchpacketdetails' },
  { key: 'dynamicriskmap',   label: 'Dynamic Risk Map',       path: '/dynamicriskmap' }, // New tab added

  // Profile is reachable via the header button (top-right), not a tab — see below.
];

const BORDER_COLORS = {
  overview:        'border-red-500',
  anomaly:         'border-red-500',
  region:          'border-purple-500',
  featureanalysis: 'border-indigo-500',
  viewoperators:   'border-red-500',
  search:          'border-green-500',
  profile:         'border-blue-500',
  dynamicriskmap:  'border-teal-500', 

};

const PAGE_LABELS = {
  overview:        'Dashboard',
  anomaly:         'Anomaly Indicators',
  region:          'Region Evaluation',
  featureanalysis: 'Feature Analysis',
  viewoperators:   'View Operators',
  profile:         'Profile',
  search:          'Search Packet Details',
  dynamicriskmap:  'Dynamic Risk Map', 

};

const PageNavigation = ({ currentPage }) => {
  const navigate = useNavigate();
  const { profile } = useCurrentUser();
  const [globalRO, setGlobalRO] = useGlobalRegionalOffice();
  const borderColor = BORDER_COLORS[currentPage] || 'border-red-500';
  const isGlobalUser = profile && GLOBAL_GROUPS.includes(profile.regional_office);

  return (
    <>
      {/* Header */}
      <div className={`bg-white rounded-xl shadow-lg p-6 border-l-4 ${borderColor}`}>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <Shield className="w-8 h-8 text-red-500" />
              Operator 360
            </h1>
            {profile && (
              <div className="mt-2 flex items-center gap-3 flex-wrap">
                <p className="text-sm text-gray-600">
                  Welcome, <span className="font-semibold text-blue-600">{profile.name || profile.ad_id}</span>
                </p>
                {profile.regional_office && (
                  <span className="text-xs px-3 py-1 bg-purple-100 text-purple-700 rounded-full font-medium">
                    {profile.regional_office}
                  </span>
                )}
                {profile.role && (
                  <span className="text-xs px-3 py-1 bg-blue-100 text-blue-700 rounded-full font-medium capitalize">
                    {profile.role}
                  </span>
                )}
                {profile.email && (
                  <span className="text-xs text-gray-500">{profile.email}</span>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {isGlobalUser && (
              <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                <Globe className="w-4 h-4 text-gray-500" />
                <select
                  value={globalRO}
                  onChange={e => setGlobalRO(e.target.value)}
                  className="text-sm bg-transparent focus:outline-none text-gray-700 font-medium"
                  title="TechCentre/HeadQuarters see all Regional Offices by default — pick one to scope down."
                >
                  <option value="">All Regional Offices (Global)</option>
                  {REGIONAL_OFFICES.map(ro => <option key={ro} value={ro}>{ro}</option>)}
                </select>
                {globalRO && (
                  <button
                    onClick={() => setGlobalRO('')}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium whitespace-nowrap"
                  >
                    Reset to Global
                  </button>
                )}
              </div>
            )}
            <button
              onClick={() => navigate('/profile')}
              className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold shadow-lg hover:shadow-xl transition-all duration-200 ${
                currentPage === 'profile'
                  ? 'bg-white border-2 border-blue-500 text-blue-600'
                  : 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white'
              }`}
            >
              <UserCircle className="w-5 h-5" />
              <span>Profile</span>
            </button>
          </div>
        </div>
      </div>

      {/* Breadcrumb Navigation */}
      <div className="flex items-center gap-2 text-sm">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1 text-gray-600 hover:text-blue-600 transition"
        >
          <Home className="w-4 h-4" />
          <span>Home</span>
        </button>
        <ChevronRight className="w-4 h-4 text-gray-400" />
        {currentPage === 'overview' ? (
          <span className="text-blue-600 font-medium">Dashboard</span>
        ) : (
          <>
            <button
              onClick={() => navigate('/dashboard')}
              className="text-gray-600 hover:text-blue-600 transition"
            >
              Dashboard
            </button>
            <ChevronRight className="w-4 h-4 text-gray-400" />
            <span className="text-blue-600 font-medium">{PAGE_LABELS[currentPage]}</span>
          </>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="bg-white rounded-xl shadow-md p-2">
        <div className="flex gap-2 overflow-x-auto">
          {TABS.map(tab => (
            <button
              key={tab.key}
              onClick={() => navigate(tab.path)}
              className={`px-4 py-2 rounded-lg font-medium transition whitespace-nowrap ${
                currentPage === tab.key
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
    </>
  );
};

export default PageNavigation;
