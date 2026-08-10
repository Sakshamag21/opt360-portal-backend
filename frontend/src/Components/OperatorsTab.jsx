import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { MapPin, AlertTriangle, Eye, ArrowUp, ArrowDown, Loader2, UserX } from 'lucide-react';
import OperatorDetailView from './OperatorDetailView';
import NameCodeTypeahead from './ui/NameCodeTypeahead';
import { OperatorListSkeleton } from './ui/OperatorCardSkeleton';
import { API_BASE_URL, getAuthHeaders } from '../config/apiConfig';
import { REGIONAL_OFFICES, GLOBAL_GROUPS } from '../constants';
import { useCurrentUser } from '../hooks/useCurrentUser';
import { codeOf } from '../utils/nameCode';
import operatorsDummy from '../resources/operatorsDummy.json';

const IS_DEV = process.env.REACT_APP_ENV === 'dev';

// Synthesizes reg_code/ea_code/status onto the dev-mode dummy dataset, which
// predates this redesign and doesn't carry those fields — see
// docs/VIEW_OPERATORS_REDESIGN_PLAN.md. Dev-only, not shipped to real data.
const DEV_OPERATORS = operatorsDummy.data.map(op => ({
  ...op,
  reg_code: codeOf(op.reg),
  ea_code: codeOf(op.ea),
  status: op.user_status === 1 ? 'active' : 'inactive'
}));
const DEV_FILTERS = {
  regional_offices: REGIONAL_OFFICES,
  registrars: [...new Map(DEV_OPERATORS.map(op => [op.reg_code, { name: op.reg, code: op.reg_code }])).values()],
  eas: [...new Map(DEV_OPERATORS.map(op => [op.ea_code, { name: op.ea, code: op.ea_code }])).values()],
  risk_buckets: ['Critical', 'High', 'Medium', 'Low', 'No'],
  states: [...new Set(DEV_OPERATORS.map(op => op.state))].filter(Boolean).sort(),
  districts: [...new Set(DEV_OPERATORS.map(op => op.district))].filter(Boolean).sort()
};

const SORT_OPTIONS = [
  { value: 'risk_score', label: 'Risk Score' },
  { value: 'last_sync', label: 'Last Sync' }
];

const defaultFilters = {
  ro: '',
  state: '',
  district: '',
  regCode: '',
  eaCode: '',
  status: '',
  riskBucket: '',
  sortBy: 'risk_score',
  sortDir: 'desc'
};

const OperatorsTab = ({
  selectedOperator,
  setSelectedOperator,
  getSeverityColor,
  getCategoryColor,
  initialOperatorData,
  searchedOptId,
  notFoundMessage,
  initialFilters
}) => {
  const { profile } = useCurrentUser();
  const isGlobalUser = !!(profile && GLOBAL_GROUPS.includes(profile.regional_office));
  const [detailedViewOperator, setDetailedViewOperator] = useState(null);
  const [operators, setOperators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [emptyMessage, setEmptyMessage] = useState('');

  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalOperators, setTotalOperators] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  const [searchId, setSearchId] = useState('');
  // initialFilters (e.g. from the Overview page's "Review Now"/EA-Reg-tile
  // clicks, carried via route state) seeds both filters and draft so the
  // first fetch already reflects them and the filter controls show the
  // right selection, without needing a separate effect/re-fetch on mount.
  const [filters, setFilters] = useState(() => ({ ...defaultFilters, ...initialFilters }));
  // Draft filters let the user change several controls before hitting "Apply" —
  // `filters` (the state actually fetched with) only updates on Apply/pagination.
  const [draft, setDraft] = useState(() => ({ ...defaultFilters, ...initialFilters }));

  const [filterOptions, setFilterOptions] = useState({ regional_offices: REGIONAL_OFFICES, registrars: [], eas: [], risk_buckets: [], states: [], districts: [] });
  const hasInitialData = useRef(false);

  // ── Filter dropdown data (registrar/EA typeahead lists, risk buckets) ──────
  // Registrars are scoped to the selected RO; EAs are scoped to the selected
  // RO and/or registrar (either narrows independently, so picking a
  // registrar with no RO selected still narrows EAs for an all-RO search).
  // Refetches whenever draft.ro/draft.regCode change, so the dropdowns stay
  // cascaded as the user picks filters, not just on initial mount.
  useEffect(() => {
    if (IS_DEV) {
      setFilterOptions(DEV_FILTERS);
      return;
    }
    let cancelled = false;
    const fetchFilters = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/operator_filters`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ ro: draft.ro, reg_code: draft.regCode })
        });
        if (!response.ok || cancelled) return;
        const data = await response.json();
        if (cancelled) return;
        setFilterOptions(prev => ({
          regional_offices: data.regional_offices || prev.regional_offices || REGIONAL_OFFICES,
          registrars: data.registrars || [],
          eas: data.eas || [],
          risk_buckets: data.risk_buckets || [],
          states: data.states || [],
          districts: data.districts || []
        }));
      } catch (err) {
        console.error('Error fetching operator filter options:', err);
      }
    };
    fetchFilters();
    return () => { cancelled = true; };
  }, [draft.ro, draft.regCode]);

  // ── Core fetch — every filter/search/sort/page combination goes through this ──
  const fetchOperators = useCallback(async (page, activeFilters, id) => {
    setLoading(true);
    setError(null);

    if (IS_DEV) {
      await new Promise(r => setTimeout(r, 350));
      let rows = DEV_OPERATORS.filter(op => {
        if (id && !op.id.toLowerCase().includes(id.toLowerCase()) && !op.name.toLowerCase().includes(id.toLowerCase())) return false;
        if (activeFilters.ro && op.ro !== activeFilters.ro) return false;
        if (activeFilters.state && op.state !== activeFilters.state) return false;
        if (activeFilters.district && op.district !== activeFilters.district) return false;
        if (activeFilters.regCode && op.reg_code !== activeFilters.regCode) return false;
        if (activeFilters.eaCode && op.ea_code !== activeFilters.eaCode) return false;
        if (activeFilters.status && op.status !== activeFilters.status) return false;
        if (activeFilters.riskBucket && op.risk_bucket !== activeFilters.riskBucket) return false;
        return true;
      });
      rows.sort((a, b) => {
        const field = activeFilters.sortBy === 'last_sync' ? 'last_sync_timestamp' : 'risk_score';
        const av = field === 'last_sync_timestamp' ? new Date(a[field]).getTime() : a[field];
        const bv = field === 'last_sync_timestamp' ? new Date(b[field]).getTime() : b[field];
        return activeFilters.sortDir === 'asc' ? av - bv : bv - av;
      });
      const start = (page - 1) * pageSize;
      setOperators(rows.slice(start, start + pageSize));
      setTotalOperators(rows.length);
      setTotalPages(Math.max(1, Math.ceil(rows.length / pageSize)));
      setEmptyMessage(rows.length === 0 ? 'No operators found for the selected criteria.' : '');
      setLoading(false);
      return;
    }

    try {
      const body = {
        page,
        page_size: pageSize,
        sort_by: activeFilters.sortBy,
        sort_dir: activeFilters.sortDir
      };
      if (id) body.id = id;
      // Operator IDs are globally unique — searching by id should never be
      // scoped to a single RO, even if one is pre-selected (e.g. seeded
      // from the header's global RO picker). See operatorSearch.go.
      if (activeFilters.ro && !id) body.ro = activeFilters.ro;
      if (activeFilters.state) body.state = activeFilters.state;
      if (activeFilters.district) body.district = activeFilters.district;
      if (activeFilters.regCode) body.reg_code = activeFilters.regCode;
      if (activeFilters.eaCode) body.ea_code = activeFilters.eaCode;
      if (activeFilters.status) body.status = activeFilters.status;
      if (activeFilters.riskBucket) body.risk_bucket = activeFilters.riskBucket;

      const response = await fetch(`${API_BASE_URL}/api/operator_search`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(body)
      });
      if (!response.ok) throw new Error(`API error: ${response.status} ${response.statusText}`);

      const data = await response.json();
      const rows = data.data || [];
      setOperators(rows);
      setTotalOperators(data.total ?? rows.length);
      setTotalPages(data.total_pages ?? 1);
      setEmptyMessage(rows.length === 0 ? 'No operators found for the selected criteria.' : '');
    } catch (err) {
      console.error('Error fetching operators:', err);
      setError(err.message);
      setOperators([]);
      setTotalOperators(0);
      setTotalPages(1);
    } finally {
      setLoading(false);
    }
  }, [pageSize]);

  // ── Handle arriving here with a single pre-fetched operator (from Overview/Search/FeatureAnalysis) ──
  useEffect(() => {
    if (initialOperatorData && !hasInitialData.current) {
      const rows = Array.isArray(initialOperatorData) ? initialOperatorData : [initialOperatorData];
      setOperators(rows);
      setTotalOperators(rows.length);
      setTotalPages(1);
      setLoading(false);
      hasInitialData.current = true;
      if (searchedOptId) setSearchId(searchedOptId);
      if (rows.length === 0) {
        setEmptyMessage(notFoundMessage || (searchedOptId ? `Operator ${searchedOptId} not found.` : 'No operators found for the selected criteria.'));
      }
      return;
    }
    if (!hasInitialData.current) {
      fetchOperators(1, filters, '');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleApply = () => {
    setFilters(draft);
    setCurrentPage(1);
    fetchOperators(1, draft, searchId.trim());
  };

  const handlePageChange = (page) => {
    if (page < 1 || page > totalPages || page === currentPage) return;
    setCurrentPage(page);
    fetchOperators(page, filters, searchId.trim());
  };

  const handlePageSizeChange = (size) => {
    setPageSize(size);
    setCurrentPage(1);
    // pageSize is read from state inside fetchOperators via useCallback dep,
    // but that closure hasn't updated yet on this render — pass explicitly instead.
  };
  useEffect(() => {
    // Re-fetch when page size changes (after the state above has committed).
    if (hasInitialData.current && operators.length === 0 && totalOperators === 0) return;
    fetchOperators(1, filters, searchId.trim());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageSize]);

  const handleClear = () => {
    setDraft(defaultFilters);
    setFilters(defaultFilters);
    setSearchId('');
    setCurrentPage(1);
    fetchOperators(1, defaultFilters, '');
  };

  const toggleSortDir = () => setDraft(d => ({ ...d, sortDir: d.sortDir === 'asc' ? 'desc' : 'asc' }));

  const processedOperators = useMemo(() => {
    const formatIST = (value) => {
      if (!value) return 'N/A';
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return 'N/A';
      return date.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
      });
    };
    return operators.map(op => {
      return {
        ...op,
        opt_id: op.id,
        opt_name: op.name,
        risk_score: parseFloat(op.risk_score || 0),
        last_sync_time: formatIST(op.last_sync_timestamp),
        last_packet_date_display: formatIST(op.last_packet_date),
        opt_ro: op.ro,
        registrar_name: op.reg,
        ea_name: op.ea,
        status_label: op.status === 'active' ? 'Active' : (op.status === 'inactive' ? 'Inactive' : 'Unknown')
      };
    });
  }, [operators]);

  useEffect(() => {
    if (selectedOperator) {
      setDetailedViewOperator(selectedOperator);
      setSelectedOperator(null);
    }
  }, [selectedOperator, setSelectedOperator]);

  if (detailedViewOperator) {
    return (
      <OperatorDetailView
        operator={detailedViewOperator}
        onBack={() => setDetailedViewOperator(null)}
        getSeverityColor={getSeverityColor}
        getCategoryColor={getCategoryColor}
      />
    );
  }

  const hasActiveFilters = !!(searchId || filters.ro || filters.state || filters.district || filters.regCode || filters.eaCode || filters.status || filters.riskBucket);
  const isRefetching = loading && processedOperators.length > 0;
  const isFirstLoad = loading && processedOperators.length === 0;

  if (error && processedOperators.length === 0) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-2">
          <AlertTriangle className="w-6 h-6 text-red-600" />
          <h3 className="text-lg font-bold text-red-900">Error Loading Operators</h3>
        </div>
        <p className="text-red-700">{error}</p>
        <button
          onClick={() => fetchOperators(currentPage, filters, searchId.trim())}
          className="mt-4 bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Operators</h2>
            <div className="text-sm text-gray-600 mt-1 flex items-center gap-2">
              <p>Showing {processedOperators.length} of {totalOperators} operators (Page {currentPage} of {Math.max(totalPages, 1)})</p>
              {isRefetching && <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />}
            </div>
          </div>
          {hasActiveFilters && (
            <span className="text-xs text-blue-600 font-medium bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
              Filtered results
            </span>
          )}
        </div>

        {/* Filters and Search */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 mb-6 border border-blue-100 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-800">Filters & Search</h3>
            <button
              onClick={handleClear}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition ${
                hasActiveFilters
                  ? 'bg-red-600 text-white border-2 border-red-700 hover:bg-red-700 shadow'
                  : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'
              }`}
            >
              Clear All
            </button>
          </div>

          {/* Operator ID search — combinable with every filter below */}
          <div className="mb-6">
            <div className="flex gap-2">
              <input
                type="text"
                value={searchId}
                onChange={e => setSearchId(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleApply()}
                placeholder="Search by Operator ID..."
                className="flex-1 max-w-md px-4 py-3 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleApply}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg shadow-sm transition"
              >
                Search / Apply
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Regional Office</label>
              <select
                value={draft.ro}
                onChange={e => setDraft(d => ({ ...d, ro: e.target.value, regCode: '', eaCode: '' }))}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">{isGlobalUser ? 'All Regional Offices (Global)' : 'My Regional Office'}</option>
                {filterOptions.regional_offices.map(ro => <option key={ro} value={ro}>{ro}</option>)}
              </select>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">State</label>
              <select
                value={draft.state}
                onChange={e => setDraft(d => ({ ...d, state: e.target.value }))}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All States</option>
                {filterOptions.states.map(state => <option key={state} value={state}>{state}</option>)}
              </select>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">District</label>
              <select
                value={draft.district}
                onChange={e => setDraft(d => ({ ...d, district: e.target.value }))}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Districts</option>
                {filterOptions.districts.map(district => <option key={district} value={district}>{district}</option>)}
              </select>
            </div>

            <NameCodeTypeahead
              label="Registrar"
              options={filterOptions.registrars}
              value={draft.regCode}
              onChange={code => setDraft(d => ({ ...d, regCode: code, eaCode: '' }))}
            />

            <NameCodeTypeahead
              label="EA"
              options={filterOptions.eas}
              value={draft.eaCode}
              onChange={code => setDraft(d => ({ ...d, eaCode: code }))}
            />

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Status</label>
              <select
                value={draft.status}
                onChange={e => setDraft(d => ({ ...d, status: e.target.value }))}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Statuses</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Risk Category</label>
              <select
                value={draft.riskBucket}
                onChange={e => setDraft(d => ({ ...d, riskBucket: e.target.value }))}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Risk Categories</option>
                {filterOptions.risk_buckets.map(rb => <option key={rb} value={rb}>{rb}</option>)}
              </select>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Sort By</label>
              <div className="flex gap-1">
                <select
                  value={draft.sortBy}
                  onChange={e => setDraft(d => ({ ...d, sortBy: e.target.value }))}
                  className="flex-1 px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {SORT_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
                <button
                  type="button"
                  onClick={toggleSortDir}
                  title={draft.sortDir === 'asc' ? 'Ascending' : 'Descending'}
                  className="px-3 py-2 bg-white border border-gray-300 rounded-lg shadow-sm hover:bg-gray-50"
                >
                  {draft.sortDir === 'asc' ? <ArrowUp className="w-4 h-4 text-gray-600" /> : <ArrowDown className="w-4 h-4 text-gray-600" />}
                </button>
              </div>
            </div>
          </div>

          <div className="mt-4 flex justify-end">
            <button
              onClick={handleApply}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg shadow-sm transition"
            >
              Apply Filters
            </button>
          </div>
        </div>

        {/* Results */}
        {isFirstLoad ? (
          <OperatorListSkeleton count={pageSize > 5 ? 5 : pageSize} />
        ) : (
          <div className={`space-y-4 transition-opacity ${isRefetching ? 'opacity-50 pointer-events-none' : ''}`}>
            {processedOperators.length === 0 && (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <p className="text-lg font-semibold text-gray-500">
                  {emptyMessage || 'No operators found for the selected criteria.'}
                </p>
                <p className="text-sm text-gray-400 mt-1">Try changing the filters or clearing them.</p>
              </div>
            )}
            {processedOperators.map(operator => (
              <div
                key={operator.opt_id}
                className="border rounded-xl p-6 bg-gradient-to-br from-white via-blue-50 to-blue-100 shadow-lg hover:shadow-xl transition duration-200"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-4 mb-3 flex-wrap">
                      <h3 className="text-2xl font-bold text-blue-900">{operator.opt_name}</h3>
                      <span className="px-4 py-1 rounded-full text-sm font-semibold bg-red-100 text-red-700 border border-red-200 shadow">
                        Risk: {(operator.risk_score * 100).toFixed(1)}%
                      </span>
                      <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                        operator.status === 'active' ? 'bg-green-100 text-green-700 border border-green-200' : 'bg-gray-100 text-gray-700 border border-gray-200'
                      }`}>
                        Status: {operator.status_label}
                      </span>
                      {operator.dissociation_date && (
                        <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-700 border border-red-200">
                          <UserX className="w-3.5 h-3.5" /> Dissociated
                        </span>
                      )}
                      <button
                        onClick={() => setDetailedViewOperator(operator)}
                        className="ml-auto px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition flex items-center gap-2 shadow-md"
                      >
                        <Eye className="w-4 h-4" />
                        View Full Details
                      </button>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-base text-gray-700 mb-4">
                      <div className="flex items-center gap-2"><MapPin className="w-5 h-5 text-cyan-400" /><span className="font-semibold">Operator ID:</span> <span>{operator.opt_id}</span></div>
                      <div className="flex items-center gap-2"><MapPin className="w-5 h-5 text-blue-400" /><span className="font-semibold">Regional Office:</span> <span>{operator.opt_ro}</span></div>
                      <div className="flex items-center gap-2"><AlertTriangle className="w-5 h-5 text-yellow-400" /><span className="font-semibold">Registrar:</span> <span>{operator.registrar_name}</span></div>
                      <div className="flex items-center gap-2"><AlertTriangle className="w-5 h-5 text-green-400" /><span className="font-semibold">EA Name:</span> <span>{operator.ea_name}</span></div>
                      <div className="flex items-center gap-2"><span className="font-semibold">Last Sync:</span> <span>{operator.last_sync_time}</span></div>
                      <div className="flex items-center gap-2"><span className="font-semibold">Last Packet Date:</span> <span>{operator.last_packet_date_display}</span></div>
                      {operator.dissociation_date && (
                        <div className="flex items-center gap-2 col-span-2 md:col-span-4">
                          <UserX className="w-5 h-5 text-red-500" />
                          <span className="font-semibold text-red-700">Dissociated:</span>
                          <span className="text-red-700">{new Date(operator.dissociation_date).toLocaleDateString()}</span>
                          {operator.dissociation_reason && (
                            <span className="text-gray-500 italic">— {operator.dissociation_reason}</span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        <div className="mt-6 flex items-center justify-between bg-gray-50 px-4 py-3 rounded-lg">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-700">Show:</span>
            <select
              value={pageSize}
              onChange={e => handlePageSizeChange(Number(e.target.value))}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            >
              {[10, 20, 50, 100].map(size => <option key={size} value={size}>{size}</option>)}
            </select>
            <span className="text-sm text-gray-700">per page</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => handlePageChange(1)} disabled={currentPage === 1} className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100">First</button>
            <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1} className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100">Previous</button>
            <span className="text-sm">Page {currentPage} of {Math.max(totalPages, 1)}</span>
            <button onClick={() => handlePageChange(currentPage + 1)} disabled={!totalPages || currentPage >= totalPages} className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100">Next</button>
            <button onClick={() => handlePageChange(totalPages)} disabled={!totalPages || currentPage >= totalPages} className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100">Last</button>
          </div>
          <div className="text-sm text-gray-700">Total: {totalOperators} operators</div>
        </div>
      </div>
    </div>
  );
};

export default OperatorsTab;
