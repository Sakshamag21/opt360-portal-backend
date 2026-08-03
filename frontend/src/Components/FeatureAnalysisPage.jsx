import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart2, AlertTriangle, Shield, Settings, Users, HelpCircle, Loader, RefreshCw, ExternalLink } from 'lucide-react';
import PageNavigation from './PageNavigation';
import PageWrapper from './ui/PageWrapper';
import { API_BASE_URL, getAuthHeaders } from '../config/apiConfig';
import { REGIONAL_OFFICES, GLOBAL_GROUPS } from '../constants';
import { useCurrentUser } from '../hooks/useCurrentUser';
import { getGlobalRO } from '../hooks/useGlobalRegionalOffice';
import featureAnalysisDummy from '../resources/featureAnalysis.json';
import operatorsDummy from '../resources/operatorsDummy.json';

const IS_DEV = process.env.REACT_APP_ENV === 'dev';

// Seeds this page's RO from the header's global RO selector (for
// TechCentre/HeadQuarters users) or the caller's own RO, instead of always
// defaulting to REGIONAL_OFFICES[0] regardless of who's logged in. The
// dropdown still lets any user view a different RO's features.
const defaultRo = (profile) => {
  const headerRO = getGlobalRO();
  if (headerRO) return headerRO;
  if (profile && !GLOBAL_GROUPS.includes(profile.regional_office)) return profile.regional_office;
  return REGIONAL_OFFICES[0];
};

const CATEGORY_META = {
  'Authentication':          { color: 'bg-blue-100 text-blue-700 border-blue-200',   icon: Shield,       bar: 'bg-blue-500'   },
  'Biometrics':              { color: 'bg-purple-100 text-purple-700 border-purple-200', icon: Users,     bar: 'bg-purple-500' },
  'Suspicious Transactions': { color: 'bg-red-100 text-red-700 border-red-200',       icon: AlertTriangle, bar: 'bg-red-500'  },
  'Work':                    { color: 'bg-orange-100 text-orange-700 border-orange-200', icon: Settings,  bar: 'bg-orange-500' },
  'Uncategorized':           { color: 'bg-gray-100 text-gray-700 border-gray-200',    icon: HelpCircle,   bar: 'bg-gray-400'   },
};

const fmt = (v) => (v === null || v === undefined ? '—' : typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 4 }) : v);

const OperatorIdLink = ({ operatorId, onNavigate }) => {
  if (!operatorId) return <span className="text-xs text-gray-400">—</span>;
  return (
    <button
      onClick={() => onNavigate(operatorId)}
      className="inline-flex items-center gap-1 text-xs font-mono font-semibold text-blue-600 hover:text-blue-800 hover:underline transition"
      title={`View operator ${operatorId}`}
    >
      {operatorId}
      <ExternalLink className="w-3 h-3 shrink-0" />
    </button>
  );
};

const StatCell = ({ label, value, operatorId, onNavigate }) => (
  <div className="text-center space-y-0.5">
    <p className="text-xs text-gray-500">{label}</p>
    <p className="text-sm font-semibold text-gray-800">{fmt(value)}</p>
    <OperatorIdLink operatorId={operatorId} onNavigate={onNavigate} />
  </div>
);

const FeatureRow = ({ feature, onNavigate }) => (
  <tr className="border-b border-gray-100 hover:bg-gray-50 transition">
    <td className="px-4 py-3">
      <p className="text-sm font-medium text-gray-900">{feature.featureName}</p>
      <p className="text-xs text-gray-500 mt-0.5 max-w-sm">{feature.description}</p>
      <p className="text-xs text-gray-400 mt-0.5 font-mono">{feature.featureId}</p>
    </td>
    <td className="px-4 py-3 text-center text-sm font-semibold text-gray-700">{fmt(feature.count)}</td>
    <td className="px-4 py-3"><StatCell label="Max" value={feature.max?.value} operatorId={feature.max?.operatorId} onNavigate={onNavigate} /></td>
    <td className="px-4 py-3"><StatCell label="Min" value={feature.min?.value} operatorId={feature.min?.operatorId} onNavigate={onNavigate} /></td>
    <td className="px-4 py-3"><StatCell label="Avg" value={feature.average?.value} operatorId={feature.average?.operatorId} onNavigate={onNavigate} /></td>
  </tr>
);

const FeatureAnalysisPage = () => {
  const navigate = useNavigate();
  const { profile } = useCurrentUser();
  const [features, setFeatures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedRo, setSelectedRo] = useState(() => defaultRo(profile));
  const [filterCategory, setFilterCategory] = useState('');
  const [operatorSearchWarning, setOperatorSearchWarning] = useState(null);

  // profile loads asynchronously after mount — re-seed once available,
  // unless the user has already picked a RO themselves.
  const seededFromProfile = React.useRef(false);
  useEffect(() => {
    if (profile && !seededFromProfile.current) {
      seededFromProfile.current = true;
      setSelectedRo(defaultRo(profile));
    }
  }, [profile]);

  const navigateToOperator = async (optId) => {
    if (!optId || !optId.trim()) return;
    setOperatorSearchWarning(null);

    // The operator may belong to a different RO than the caller's own — pick up the
    // RO from the currently selected dropdown (the RO whose feature data we're viewing).
    if (!selectedRo) {
      setOperatorSearchWarning('Regional office is missing for this view — operator cannot be searched.');
      return;
    }

    if (IS_DEV) {
      const operator = operatorsDummy.data.find(op => op.id === optId) || { id: optId, name: optId };
      navigate('/viewoperators', { state: { initialOperatorData: [operator], searchedOptId: optId } });
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/operator_search`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: optId, ro: selectedRo })
      });
      const data = await response.json();
      // /operator_search wraps results under `data`; when there's no match it's an empty
      // array — fall back to null (not the raw response object) so we don't push a
      // malformed "operator" with no opt_id into the operators list.
      const list = Array.isArray(data) ? data : (Array.isArray(data.data) ? data.data : null);
      const operator = list && list.length > 0 ? list[0] : null;
      navigate('/viewoperators', {
        state: {
          initialOperatorData: operator ? [operator] : [],
          searchedOptId: optId,
          // /operator_search defaults to the caller's own regional office when no
          // `ro` is supplied — a 0-match result usually means this operator is
          // mapped to a different RO.
          notFoundMessage: operator ? null : `Operator ${optId} not found — it may be mapped to a different regional office than yours.`
        }
      });
    } catch {
      navigate('/viewoperators', { state: { searchedOptId: optId } });
    }
  };

  const fetchFeatures = async (ro) => {
    setLoading(true);
    setError(null);

    if (IS_DEV) {
      await new Promise(r => setTimeout(r, 350));
      setFeatures(featureAnalysisDummy);
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/featureAnalysis?RO=${encodeURIComponent(ro)}`, {
        method: 'GET',
        headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error(`API error: ${response.status}`);
      const data = await response.json();
      setFeatures(Array.isArray(data) ? data : (data.data || []));
    } catch (err) {
      console.error('Error fetching feature analysis:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchFeatures(selectedRo); }, [selectedRo]);

  const categories = useMemo(() => [...new Set(features.map(f => f.category))].sort(), [features]);

  const grouped = useMemo(() => {
    const filtered = filterCategory ? features.filter(f => f.category === filterCategory) : features;
    const map = {};
    filtered.forEach(f => {
      if (!map[f.category]) map[f.category] = [];
      map[f.category].push(f);
    });
    return map;
  }, [features, filterCategory]);

  const summaryCounts = useMemo(() => {
    const counts = {};
    features.forEach(f => { counts[f.category] = (counts[f.category] || 0) + 1; });
    return counts;
  }, [features]);

  return (
    <PageWrapper>
      <PageNavigation currentPage="featureanalysis" />

      {/* Header */}
      <div className="bg-white rounded-xl shadow-lg p-6 border-l-4 border-indigo-500">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
              <BarChart2 className="w-7 h-7 text-indigo-500" />
              Feature Analysis
            </h2>
            <p className="text-sm text-gray-500 mt-1">Risk feature distribution across operators for the selected regional office</p>
          </div>

          {/* RO selector */}
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-gray-600">Regional Office:</label>
            <select
              value={selectedRo}
              onChange={e => { seededFromProfile.current = true; setSelectedRo(e.target.value); }}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            >
              {REGIONAL_OFFICES.map(ro => <option key={ro} value={ro}>{ro}</option>)}
            </select>
            <button
              onClick={() => fetchFeatures(selectedRo)}
              className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </div>

        {/* Summary cards */}
        {!loading && !error && (
          <div className="mt-5 flex flex-wrap gap-3">
            {Object.entries(summaryCounts).map(([cat, count]) => {
              const meta = CATEGORY_META[cat] || CATEGORY_META['Uncategorized'];
              const Icon = meta.icon;
              return (
                <button
                  key={cat}
                  onClick={() => setFilterCategory(prev => prev === cat ? '' : cat)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition ${
                    filterCategory === cat ? meta.color + ' ring-2 ring-offset-1 ring-indigo-400' : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {cat}
                  <span className="ml-1 px-1.5 py-0.5 bg-white bg-opacity-60 rounded-full text-xs font-bold">{count}</span>
                </button>
              );
            })}
            {filterCategory && (
              <button
                onClick={() => setFilterCategory('')}
                className="px-3 py-2 rounded-lg border border-dashed border-gray-300 text-sm text-gray-500 hover:text-gray-700 transition"
              >
                Show all
              </button>
            )}
          </div>
        )}
      </div>

      {operatorSearchWarning && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />
          <p className="text-amber-700 text-sm">{operatorSearchWarning}</p>
        </div>
      )}

      {/* Loading / Error */}
      {loading && (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <Loader className="w-10 h-10 animate-spin text-indigo-500 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">Loading feature analysis…</p>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-5 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-red-500 shrink-0" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {/* Feature tables by category */}
      {!loading && !error && Object.entries(grouped).map(([category, items]) => {
        const meta = CATEGORY_META[category] || CATEGORY_META['Uncategorized'];
        const Icon = meta.icon;
        return (
          <div key={category} className="bg-white rounded-xl shadow-md overflow-hidden">
            <div className={`px-6 py-4 flex items-center gap-3 border-b ${meta.color} border-opacity-50`}>
              <Icon className="w-5 h-5" />
              <h3 className="text-base font-bold">{category}</h3>
              <span className="ml-auto text-xs font-semibold px-2 py-0.5 rounded-full bg-white bg-opacity-60">
                {items.length} feature{items.length !== 1 ? 's' : ''}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    <th className="px-4 py-3 w-2/5">Feature</th>
                    <th className="px-4 py-3 text-center">Operator Count</th>
                    <th className="px-4 py-3 text-center">Max</th>
                    <th className="px-4 py-3 text-center">Min</th>
                    <th className="px-4 py-3 text-center">Average</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(f => <FeatureRow key={f.featureId} feature={f} onNavigate={navigateToOperator} />)}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}

      {!loading && !error && Object.keys(grouped).length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <BarChart2 className="w-14 h-14 mb-4" />
          <p className="text-lg font-medium">No features found</p>
          <p className="text-sm">Try selecting a different regional office</p>
        </div>
      )}
    </PageWrapper>
  );
};

export default FeatureAnalysisPage;
