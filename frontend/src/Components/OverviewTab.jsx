import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { AlertCircle, Loader, ChevronDown } from 'lucide-react';
import LoadingSpinner from './ui/LoadingSpinner';
import overviewDummy from '../resources/overviewDummy.json';
import operatorsDummy from '../resources/operatorsDummy.json';
import { API_BASE_URL, getAuthHeaders } from '../config/apiConfig';
import { REGIONAL_OFFICES } from '../constants';
import { getRiskBucketStyle } from '../utils/colorHelpers';
import { useGlobalRegionalOffice } from '../hooks/useGlobalRegionalOffice';
import { useCurrentUser } from '../hooks/useCurrentUser';
import { codeOf } from '../utils/nameCode';
import { GLOBAL_GROUPS } from '../constants';

const IS_DEV = process.env.REACT_APP_ENV === 'dev';

// Known severity order for display purposes only — this sorts whatever
// buckets are actually present in the data, it doesn't filter or invent any.
// Unrecognized bucket names (a future addition) sort after these, alphabetically.
const RISK_SEVERITY_ORDER = ['Critical', 'High', 'Medium', 'Low'];

// getPresentBuckets returns the risk-bucket keys actually present across a
// list of chart entries (RO rows, EA rows, ...), ordered by known severity.
// Buckets with no data for a given entry just don't appear for that entry —
// nothing here assumes a fixed High/Medium/Low/Critical set exists.
const getPresentBuckets = (entries, excludeKeys) => {
  const keys = new Set();
  (entries || []).forEach(entry => {
    Object.keys(entry).forEach(k => {
      if (!excludeKeys.includes(k)) keys.add(k);
    });
  });
  return Array.from(keys).sort((a, b) => {
    const ia = RISK_SEVERITY_ORDER.indexOf(a);
    const ib = RISK_SEVERITY_ORDER.indexOf(b);
    if (ia === -1 && ib === -1) return a.localeCompare(b);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
};

const OverviewTab = () => {
  const navigate = useNavigate();
  // TechCentre/HeadQuarters users' header RO override — '' means global (all
  // ROs), a specific RO scopes every fetch below down to it. No-op (always
  // '') for normal RO users, since the header selector only renders for
  // global-group users in the first place.
  const [globalRO] = useGlobalRegionalOffice();
  const { profile } = useCurrentUser();
  const isGlobalUser = !!(profile && GLOBAL_GROUPS.includes(profile.regional_office));
  const [kpiData, setKpiData] = useState(null);
  const [roRiskData, setRoRiskData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedRegionalOffice, setSelectedRegionalOffice] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isUpdatingRO, setIsUpdatingRO] = useState(false);
  const [highestRiskData, setHighestRiskData] = useState(null);
  const [selectedDistributionType, setSelectedDistributionType] = useState('ea'); // 'ea' or 'reg'
  const [isDistributionDropdownOpen, setIsDistributionDropdownOpen] = useState(false);
  
  // EA selection states
  const [availableEas, setAvailableEas] = useState([]);
  const [selectedEas, setSelectedEas] = useState([]);
  const [eaDistributionData, setEaDistributionData] = useState([]);
  const [isEaDropdownOpen, setIsEaDropdownOpen] = useState(false);
  const [loadingEaData, setLoadingEaData] = useState(false);

  // Registrar selection states
  const [availableRegistrars, setAvailableRegistrars] = useState([]);
  const [selectedRegistrars, setSelectedRegistrars] = useState([]);
  const [registrarDistributionData, setRegistrarDistributionData] = useState([]);
  const [isRegistrarDropdownOpen, setIsRegistrarDropdownOpen] = useState(false);
  const [loadingRegistrarData, setLoadingRegistrarData] = useState(false);

  const regionalOffices = REGIONAL_OFFICES;

  // Fetch top 10 EAs/Registrars and available EA/Registrar list
  // NOTE: eaDistributionData/registrarDistributionData entries always use
  // canonical bucket-name keys (e.g. "High", "Medium", "Low", "Critical" if
  // present) — never a fixed high_risk/med_risk/low_risk shape — so the
  // chart below can render whatever buckets are actually present, from
  // either this top-10 fetch or the "compare selected" flow below.
  const fetchTopDistributions = async () => {
    if (IS_DEV) {
      if (selectedDistributionType === 'ea') {
        const eaArray = Object.entries(overviewDummy.top10_ea.data.ea).map(([name, risks]) => ({
          name, code: codeOf(name), High: risks.high_risk_count || 0, Medium: risks.med_risk_count || 0, Low: risks.low_risk_count || 0
        }));
        setEaDistributionData(eaArray);
        setAvailableEas(overviewDummy.all_eas.eas);
      } else {
        const regArray = Object.entries(overviewDummy.top10_registrar.data.registrars).map(([name, risks]) => ({
          name, code: codeOf(name), High: risks.high_risk_count || 0, Medium: risks.med_risk_count || 0, Low: risks.low_risk_count || 0
        }));
        setRegistrarDistributionData(regArray);
        setAvailableRegistrars(overviewDummy.all_registrars.registrars);
      }
      return;
    }

    // Header RO override for TechCentre/HeadQuarters users — '' (global) omits
    // the param entirely, matching every other RO-scoped fetch in this file.
    const roQS = globalRO ? `?ro=${encodeURIComponent(globalRO)}` : '';

    try {
      if (selectedDistributionType === 'ea') {
        const topEaResponse = await fetch(`${API_BASE_URL}/api/top10eav1${roQS}`, {
          method: 'GET',
          headers: getAuthHeaders()
        });
        if (topEaResponse.ok) {
          const topEaData = await topEaResponse.json();
          let eaArray = [];
          if (topEaData.data?.ea && typeof topEaData.data.ea === 'object') {
            const eaCodes = topEaData.data.ea_codes || {};
            eaArray = Object.entries(topEaData.data.ea).map(([name, buckets]) => ({ name, code: eaCodes[name] || '', ...buckets }));
          }
          setEaDistributionData(eaArray);
        }
        const allEaResponse = await fetch(`${API_BASE_URL}/api/all_eas${roQS}`, { method: 'GET', headers: getAuthHeaders() });
        if (allEaResponse.ok) {
          const allEaData = await allEaResponse.json();
          setAvailableEas(allEaData.eas || []);
        } else {
          setAvailableEas([]);
        }
      } else if (selectedDistributionType === 'reg') {
        const topRegistrarResponse = await fetch(`${API_BASE_URL}/api/top10regv1${roQS}`, {
          method: 'GET',
          headers: getAuthHeaders()
        });
        if (topRegistrarResponse.ok) {
          const topRegistrarData = await topRegistrarResponse.json();
          let registrarArray = [];
          if (topRegistrarData.data?.registrars && typeof topRegistrarData.data.registrars === 'object') {
            const regCodes = topRegistrarData.data.reg_codes || {};
            registrarArray = Object.entries(topRegistrarData.data.registrars).map(([name, buckets]) => ({ name, code: regCodes[name] || '', ...buckets }));
          }
          setRegistrarDistributionData(registrarArray);
        }
        const allRegistrarResponse = await fetch(`${API_BASE_URL}/api/all_registrars${roQS}`, { method: 'GET', headers: getAuthHeaders() });
        if (allRegistrarResponse.ok) {
          const allRegistrarData = await allRegistrarResponse.json();
          setAvailableRegistrars(allRegistrarData.registrars || []);
        } else {
          setAvailableRegistrars([]);
        }
      }
    } catch (err) {
      console.error('Error fetching distribution data:', err);
    }
  };

  // Handle comparison button click for EA only
  const handleCompareSelected = async () => {
    if (selectedEas.length === 0) return;

    setLoadingEaData(true);

    if (IS_DEV) {
      await new Promise(r => setTimeout(r, 300));
      const allEa = overviewDummy.top10_ea.data.ea;
      const eaArray = selectedEas
        .filter(name => allEa[name])
        .map(name => ({ name, code: codeOf(name), High: allEa[name].high_risk_count || 0, Medium: allEa[name].med_risk_count || 0, Low: allEa[name].low_risk_count || 0 }));
      setEaDistributionData(eaArray);
      setIsEaDropdownOpen(false);
      setLoadingEaData(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/selected_eas`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ selected_eas: selectedEas, ro: globalRO })
      });
      if (response.ok) {
        const data = await response.json();
        let eaArray = [];
        // /api/selected_eas is still S3-backed and only ever returns
        // high_risk/med_risk/low_risk — no Critical bucket possible here.
        if (data.ea_distribution && typeof data.ea_distribution === 'object') {
          eaArray = Object.entries(data.ea_distribution).map(([name, risks]) => ({
            name, High: risks.high_risk || 0, Medium: risks.med_risk || 0, Low: risks.low_risk || 0,
          }));
        } else if (Array.isArray(data)) {
          eaArray = data;
        } else if (data.data) {
          eaArray = data.data;
        }
        setEaDistributionData(eaArray);
        setIsEaDropdownOpen(false);
      }
    } catch (err) {
      console.error('Error comparing EA distributions:', err);
    } finally {
      setLoadingEaData(false);
    }
  };

  // Handle comparison button click for Registrar
  const handleCompareSelectedRegistrars = async () => {
    if (selectedRegistrars.length === 0) return;

    setLoadingRegistrarData(true);

    if (IS_DEV) {
      await new Promise(r => setTimeout(r, 300));
      const allReg = overviewDummy.top10_registrar.data.registrars;
      const regArray = selectedRegistrars
        .filter(name => allReg[name])
        .map(name => ({ name, code: codeOf(name), High: allReg[name].high_risk_count || 0, Medium: allReg[name].med_risk_count || 0, Low: allReg[name].low_risk_count || 0 }));
      setRegistrarDistributionData(regArray);
      setIsRegistrarDropdownOpen(false);
      setLoadingRegistrarData(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/selected_registrars`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ selected_registrars: selectedRegistrars, ro: globalRO })
      });
      if (response.ok) {
        const data = await response.json();
        let registrarArray = [];
        // /api/selected_registrars is still S3-backed and only ever returns
        // high_risk/med_risk/low_risk — no Critical bucket possible here.
        if (data.reg_distribution && typeof data.reg_distribution === 'object') {
          registrarArray = Object.entries(data.reg_distribution).map(([name, risks]) => ({
            name, High: risks.high_risk || 0, Medium: risks.med_risk || 0, Low: risks.low_risk || 0,
          }));
        } else if (Array.isArray(data)) {
          registrarArray = data;
        } else if (data.data) {
          registrarArray = data.data;
        }
        setRegistrarDistributionData(registrarArray);
        setIsRegistrarDropdownOpen(false);
      }
    } catch (err) {
      console.error('Error comparing Registrar distributions:', err);
    } finally {
      setLoadingRegistrarData(false);
    }
  };

  // Reset to Top 10 EAs
  const handleResetToTop10 = async () => {
    setSelectedEas([]);
    await fetchTopDistributions();
  };

  // Reset to Top 10 Registrars
  const handleResetToTop10Registrars = async () => {
    setSelectedRegistrars([]);
    await fetchTopDistributions();
  };

  // Toggle EA selection
  const toggleEaSelection = (item) => {
    setSelectedEas(prev => 
      prev.includes(item) 
        ? prev.filter(ea => ea !== item)
        : [...prev, item]
    );
  };

  // Toggle Registrar selection
  const toggleRegistrarSelection = (item) => {
    setSelectedRegistrars(prev => 
      prev.includes(item) 
        ? prev.filter(reg => reg !== item)
        : [...prev, item]
    );
  };

  // Fetch KPI data from API
  const fetchKpiData = async () => {
    setLoading(true);
    setError(null);

    if (IS_DEV) {
      await new Promise(r => setTimeout(r, 400));
      setKpiData(overviewDummy.kpi);
      setHighestRiskData(overviewDummy.highest_risk_opt);
      // Dev fixture still uses the old fixed field names — map them onto
      // canonical bucket-name keys so the dynamic chart rendering below
      // works the same in dev and live mode.
      const transformedRoData = Object.entries(overviewDummy.ro_risk_dist.data).map(([roName, roData]) => {
        const buckets = {
          High: roData.high_risk_count || 0,
          Medium: roData.med_risk_count || 0,
          Low: roData.low_risk_count || 0,
        };
        const total = Object.values(buckets).reduce((sum, v) => sum + v, 0);
        return { ro: roName, ...buckets, total };
      });
      setRoRiskData(transformedRoData);
      setLoading(false);
      return;
    }

    // Header RO override for TechCentre/HeadQuarters users. /api/kpi has no
    // global/aggregate file (unlike ro_risk_dist/highest_risk_opt, which can
    // go global), so it 400s for a global user with no override — that's
    // handled as non-fatal below rather than thrown, same as the existing
    // soft-fail pattern for highest_risk_opt.
    const roQS = globalRO ? `?ro=${encodeURIComponent(globalRO)}` : '';

    try {
      const [kpiResponse, roRiskResponse, highestRiskResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/kpi${roQS}`, { method: 'GET', headers: getAuthHeaders() }),
        fetch(`${API_BASE_URL}/api/ro_risk_dist`, { method: 'GET', headers: getAuthHeaders() }),
        fetch(`${API_BASE_URL}/api/highest_risk_opt${roQS}`, { method: 'GET', headers: getAuthHeaders() })
      ]);

      if (!roRiskResponse.ok) throw new Error(`RO Risk API error: ${roRiskResponse.status} ${roRiskResponse.statusText}`);

      const roRiskData = await roRiskResponse.json();

      if (kpiResponse.ok) {
        const kpiData = await kpiResponse.json();
        setKpiData(kpiData);
      } else {
        setKpiData(null);
      }
      if (highestRiskResponse.ok) {
        const hrData = await highestRiskResponse.json();
        setHighestRiskData(hrData);
      }

      // /api/ro_risk_dist now returns { data: { <ro>: { <bucket>: count } } }
      // — bucket names are whatever opt_master actually has (Critical/High/
      // Medium/Low today), not a fixed set of fields.
      let transformedRoData = [];
      if (roRiskData?.data && typeof roRiskData.data === 'object') {
        transformedRoData = Object.entries(roRiskData.data).map(([roName, buckets]) => {
          const safeBuckets = buckets || {};
          const total = Object.values(safeBuckets).reduce((sum, v) => sum + (v || 0), 0);
          return { ro: roName, ...safeBuckets, total };
        });
      }
      setRoRiskData(transformedRoData);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKpiData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [globalRO]);

  // Fetch top distributions when distribution type changes, or when a
  // TechCentre/HeadQuarters user changes the header RO override.
  useEffect(() => {
    fetchTopDistributions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDistributionType, globalRO]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (isDropdownOpen && !event.target.closest('.dropdown-container')) {
        setIsDropdownOpen(false);
      }
      if (isDistributionDropdownOpen && !event.target.closest('.distribution-dropdown-container')) {
        setIsDistributionDropdownOpen(false);
      }
      if (isEaDropdownOpen && !event.target.closest('.ea-selection-dropdown')) {
        setIsEaDropdownOpen(false);
      }
      if (isRegistrarDropdownOpen && !event.target.closest('.registrar-selection-dropdown')) {
        setIsRegistrarDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isDropdownOpen, isDistributionDropdownOpen, isEaDropdownOpen, isRegistrarDropdownOpen]);

  // Handle regional office selection
  const handleRegionalOfficeChange = async (selectedRO) => {
    setIsUpdatingRO(true);

    if (IS_DEV) {
      await new Promise(r => setTimeout(r, 200));
      setSelectedRegionalOffice(selectedRO);
      setIsDropdownOpen(false);
      await fetchKpiData();
      await fetchTopDistributions();
      setIsUpdatingRO(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/update_ro`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ group: selectedRO })
      });
      if (!response.ok) throw new Error(`Failed to update regional office: ${response.status}`);
      setSelectedRegionalOffice(selectedRO);
      setIsDropdownOpen(false);
      await fetchKpiData();
      await fetchTopDistributions();
    } catch (error) {
      console.error('Error updating regional office:', error);
      setError(`Failed to update regional office: ${error.message}`);
    } finally {
      setIsUpdatingRO(false);
    }
  };

  // Pie chart data for user's RO group. TechCentre/HeadQuarters (global)
  // users viewing no specific RO have no single slice — /api/kpi 400s for
  // them (no aggregate S3 KPI file exists), so kpiData stays null and there's
  // no opt_ro/user_group to match against. /api/ro_risk_dist itself is
  // already unconditionally global (every RO, no ro filter), so in that case
  // sum its buckets across all ROs instead of failing to find a match.
  const userGroup = kpiData?.opt_ro || kpiData?.user_group || null;
  const isGlobalScope = !globalRO && !userGroup;

  // Find the matching RO entry from ro_risk_dist data
  const userRoEntry = isGlobalScope
    ? null
    : roRiskData.find(ro => ro.ro === (globalRO || userGroup));

  // Risk buckets actually present in the RO data — drives both the pie chart
  // and the stacked bar chart below. Whatever opt_master has (Critical
  // included, if present) shows up; nothing here assumes a fixed set.
  const roBucketKeys = React.useMemo(
    () => getPresentBuckets(roRiskData, ['ro', 'total']),
    [roRiskData]
  );

  const pieChartData = roBucketKeys.map(bucket => ({
    name: `${bucket} Risk`,
    value: isGlobalScope
      ? roRiskData.reduce((sum, ro) => sum + (ro[bucket] || 0), 0)
      : (userRoEntry?.[bucket] || 0),
    color: getRiskBucketStyle(bucket).color
  }));

  // Transform distribution data for chart with logarithmic scale (EA or REG)
  // Risk buckets actually present in the current EA/Registrar source data.
  const eaRegBucketKeys = React.useMemo(() => {
    const source = selectedDistributionType === 'ea' ? eaDistributionData : registrarDistributionData;
    return getPresentBuckets(source, ['name', 'ea_name', 'registrar_name', 'code']);
  }, [selectedDistributionType, eaDistributionData, registrarDistributionData]);

  const distributionData = React.useMemo(() => {
    const source = selectedDistributionType === 'ea' ? eaDistributionData : registrarDistributionData;
    if (!Array.isArray(source) || source.length === 0) return [];
    return source.map(item => {
      const entry = { name: item.name || item.ea_name || item.registrar_name, code: item.code || '' };
      eaRegBucketKeys.forEach(bucket => {
        // Log-scale Y axis can't render exact 0, so display uses a small
        // floor while the tooltip shows the real (possibly zero) count.
        entry[`${bucket}_display`] = item[bucket] || 0.1;
        entry[`${bucket}_actual`] = item[bucket] || 0;
      });
      return entry;
    });
  }, [selectedDistributionType, eaDistributionData, registrarDistributionData, eaRegBucketKeys]);

  // Custom Tooltip for Distribution Charts
  const DistributionCustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0]?.payload;
      const total = eaRegBucketKeys.reduce((sum, bucket) => sum + (data?.[`${bucket}_actual`] ?? 0), 0);

      return (
        <div className="bg-white p-4 border-2 border-blue-200 rounded-lg shadow-xl">
          <p className="font-bold text-gray-900 mb-2 text-base">{label}</p>
          <div className="border-t pt-2 space-y-1">
            <p className="text-sm font-semibold text-gray-700">Total: {total} operators</p>
            {payload.map((entry, index) => {
              const bucket = eaRegBucketKeys[index];
              const actualValue = data?.[`${bucket}_actual`] ?? 0;
              return (
                <div key={index} className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.fill }}></div>
                    <span className="text-sm font-medium" style={{ color: entry.fill }}>{bucket} Risk</span>
                  </div>
                  <span className="text-sm font-bold text-gray-900">
                    {actualValue} ({total > 0 ? ((actualValue / total) * 100).toFixed(1) : 0}%)
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      );
    }
    return null;
  };

  // Function to navigate to specific operator by fetching from API
  const navigateToOperator = async (optId) => {
    if (IS_DEV) {
      const operator = operatorsDummy.data.find(op => op.id === optId) || operatorsDummy.data[0];
      navigate('/viewoperators', { state: { initialOperatorData: [operator], searchedOptId: optId } });
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/operator_search`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: optId })
      });
      if (!response.ok) throw new Error(`Failed to fetch operator: ${response.status}`);
      const operatorData = await response.json();
      // /operator_search wraps results under `data`; when there's no match it's an empty
      // array — fall back to null (not the raw response object) so we don't push a
      // malformed "operator" with no opt_id into the operators list.
      const list = Array.isArray(operatorData) ? operatorData : (Array.isArray(operatorData.data) ? operatorData.data : null);
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
    } catch (error) {
      console.error('Error fetching operator details:', error);
      navigate('/viewoperators', { state: { searchedOptId: optId } });
    }
  };

  // EA/Registrar distribution bar click → View Operators, filtered to that
  // EA/registrar (by code, matching the typeahead filter) and that risk bucket.
  const navigateToFilteredOperators = (entry, bucket) => {
    const ro = highestRiskData?.regional_office || selectedRegionalOffice || '';
    const initialFilters = { ro, riskBucket: bucket, status: 'active' };
    if (selectedDistributionType === 'ea') {
      initialFilters.eaCode = entry.code || '';
    } else {
      initialFilters.regCode = entry.code || '';
    }
    navigate('/viewoperators', { state: { initialFilters } });
  };

  // Loading state
  if (loading) return <LoadingSpinner message="Loading KPI data..." />;

  // Error state
  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-2">
          <AlertCircle className="w-6 h-6 text-red-600" />
          <h3 className="text-lg font-bold text-red-900">Error Loading KPI Data</h3>
        </div>
        <p className="text-red-700">{error}</p>
        <button 
          onClick={() => window.location.reload()}
          className="mt-4 bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Regional Office Selector Dropdown — unlike every other RO picker in
          the portal (header, View Operators filter, Region Evaluation,
          Feature Analysis), this one calls /api/update_ro and permanently
          changes the account's own default RO/group, not just what this
          page is viewing. Labeled accordingly so it isn't mistaken for a
          session-only view filter. */}
      <div className="bg-white rounded-xl shadow-lg p-4 border-l-4 border-blue-500">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-gray-900">My Default Regional Office</h2>
            {isUpdatingRO && <Loader className="w-4 h-4 animate-spin text-blue-500" />}
          </div>
          
          <div className="relative dropdown-container">
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              disabled={isUpdatingRO}
              className="flex items-center gap-2 bg-blue-50 hover:bg-blue-100 text-blue-700 font-semibold py-2 px-4 rounded-lg border border-blue-200 transition-colors duration-200 min-w-[160px] justify-between disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span>{selectedRegionalOffice || 'Select Regional Office'}</span>
              <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${isDropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            
            {isDropdownOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto">
                <div className="py-1">
                  {regionalOffices.map((office) => (
                    <button
                      key={office}
                      onClick={() => handleRegionalOfficeChange(office)}
                      className={`w-full text-left px-4 py-2 hover:bg-blue-50 transition-colors duration-150 ${
                        selectedRegionalOffice === office 
                          ? 'bg-blue-100 text-blue-700 font-semibold' 
                          : 'text-gray-700 hover:text-blue-600'
                      }`}
                      disabled={isUpdatingRO}
                    >
                      {office}
                      {selectedRegionalOffice === office && (
                        <span className="ml-2 text-blue-500">✓</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        
        {selectedRegionalOffice && (
          <div className="mt-3 flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
            <span className="text-sm text-gray-600">
              Currently viewing data for <span className="font-semibold text-gray-800">{selectedRegionalOffice}</span>
            </span>
          </div>
        )}
        <p className="mt-1 text-xs text-gray-400">
          Changing this updates your account's default Regional Office everywhere — it's not a one-time view filter.
          {isGlobalUser && ' To view a different RO for this session only, use the selector in the page header instead.'}
        </p>
      </div>

      {/* Key Insights Summary */}
      <div className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-xl shadow-lg p-5 text-white">
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="bg-white bg-opacity-20 rounded-lg p-3 flex flex-col">
            <h3 className="font-semibold mb-1.5 text-base">Highest <span className="text-red-300">Risk</span> Operator</h3>
            <div className="flex-grow">
              <p className="text-lg font-semibold">
                {highestRiskData?.data?.name || 'N/A'}
              </p>
              <p className="text-sm opacity-90">
                Risk Score: {highestRiskData?.data?.risk_score
                  ? (highestRiskData.data.risk_score * 100).toFixed(1)
                  : '0.0'}%
              </p>
              <p className="text-sm opacity-75">
                {highestRiskData?.data?.id || ''}
              </p>
            </div>
            <button 
              onClick={() => {
                if (highestRiskData?.data?.id) {
                  navigateToOperator(highestRiskData.data.id);
                }
              }}
              className="mt-2 w-full bg-white text-blue-600 hover:bg-blue-50 font-semibold py-1.5 px-3 text-sm rounded-lg transition duration-200 shadow-md"
              disabled={!highestRiskData?.data?.id}
            >
              Investigate
            </button>
          </div>
          <div className="bg-white bg-opacity-20 rounded-lg p-3 flex flex-col hover:bg-opacity-30 transition-all">
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="text-2xl">🚨</span>
              <h3 className="font-bold text-base">Urgent Feedback Required</h3>
            </div>
            <div className="flex-grow">
              <div className="mb-2">
                <p className="text-2xl font-bold">
                  {highestRiskData?.data?.high_opt_count ?? 0}
                </p>
                <p className="text-sm opacity-90">operators need immediate attention</p>
              </div>
          
            </div>
            <button
              onClick={() => navigate('/viewoperators', {
                state: {
                  initialFilters: {
                    ro: highestRiskData?.regional_office || selectedRegionalOffice || '',
                    riskBucket: 'Critical',
                    status: 'active'
                  }
                }
              })}
              className="mt-2 w-full bg-white text-red-600 hover:bg-red-50 font-semibold py-1.5 px-3 text-sm rounded-lg transition duration-200 shadow-md"
            >
              Review Now
            </button>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* RO Risk Distribution - Vertical Stacked Bar Chart */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-lg p-6 border-t-4 border-blue-500">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-gray-900">Regional Office Risk Distribution</h2>
            <span className="text-xs bg-blue-100 text-blue-700 px-3 py-1 rounded-full font-semibold">
              {roRiskData.length} Regional Offices
            </span>
          </div>
          <ResponsiveContainer width="100%" height={450}>
            <BarChart data={roRiskData} margin={{ top: 20, right: 30, left: 20, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis 
                dataKey="ro" 
                angle={-45} 
                textAnchor="end" 
                height={100}
                tick={{ fontSize: 11, fill: '#374151' }}
                interval={0}
              />
              <YAxis 
                label={{ value: 'Number of Operators', angle: -90, position: 'insideLeft', style: { fontSize: 12, fill: '#6b7280' } }}
                tick={{ fontSize: 11, fill: '#374151' }}
              />
              <Tooltip 
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const total = payload.reduce((sum, item) => sum + item.value, 0);
                    return (
                      <div className="bg-white p-4 border-2 border-blue-200 rounded-lg shadow-xl">
                        <p className="font-bold text-gray-900 mb-2 text-base">{payload[0].payload.ro}</p>
                        <div className="border-t pt-2 space-y-1">
                          <p className="text-sm font-semibold text-gray-700">Total: {total} operators</p>
                          {payload.reverse().map((item, index) => (
                            <div key={index} className="flex items-center justify-between gap-4">
                              <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.fill }}></div>
                                <span className="text-sm font-medium" style={{ color: item.fill }}>{item.name}</span>
                              </div>
                              <span className="text-sm font-bold text-gray-900">
                                {item.value} ({total > 0 ? ((item.value / total) * 100).toFixed(1) : 0}%)
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Legend 
                wrapperStyle={{ paddingTop: '20px' }}
                iconType="circle"
              />
              {roBucketKeys.map((bucket, idx) => (
                <Bar
                  key={bucket}
                  dataKey={bucket}
                  stackId="a"
                  fill={getRiskBucketStyle(bucket).color}
                  name={`${bucket} Risk`}
                  radius={idx === roBucketKeys.length - 1 ? [8, 8, 0, 0] : [0, 0, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Risk Distribution - Pie Chart for User's RO Group */}
        <div className="bg-white rounded-xl shadow-lg p-6 border-t-4 border-purple-500">
          <h2 className="text-xl font-bold text-gray-900 mb-4">{isGlobalScope ? 'All Regional Offices' : userGroup} Risk Distribution</h2>
          <ResponsiveContainer width="100%" height={450}>
            <PieChart>
              <Pie
                data={pieChartData}
                cx="50%"
                cy="45%"
                labelLine={true}
                label={({ name, value, percent }) => `${value} (${(percent * 100).toFixed(0)}%)`}
                outerRadius={140}
                innerRadius={60}
                fill="#8884d8"
                dataKey="value"
                paddingAngle={3}
              >
                {pieChartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip 
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const total = pieChartData.reduce((sum, item) => sum + item.value, 0);
                    const percent = ((payload[0].value / total) * 100).toFixed(1);
                    return (
                      <div className="bg-white p-3 border-2 rounded-lg shadow-lg" style={{ borderColor: payload[0].payload.color }}>
                        <p className="font-bold text-gray-900">{payload[0].name}</p>
                        <p className="text-lg font-bold" style={{ color: payload[0].payload.color }}>
                          {payload[0].value} operators
                        </p>
                        <p className="text-sm text-gray-600">{percent}% of total</p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Legend 
                verticalAlign="bottom" 
                height={60}
                iconType="circle"
                wrapperStyle={{ paddingTop: '20px' }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

  
      </div>

      {/* Distribution Chart with Logarithmic Scale (EA/REG) */}
      <div className="bg-white rounded-xl shadow-lg p-6 border-t-4 border-green-500">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              {selectedDistributionType === 'ea' ? 'Enrollment Agency (EA)' : 'Registrar (REG)'} Risk Distribution
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {selectedDistributionType === 'ea' 
                ? (selectedEas.length > 0 
                    ? `Comparing ${selectedEas.length} selected enrollment agencies (Logarithmic Scale)` 
                    : 'Top 10 enrollment agencies by total operator count (Logarithmic Scale)')
                : (selectedRegistrars.length > 0
                    ? `Comparing ${selectedRegistrars.length} selected registrars (Logarithmic Scale)`
                    : 'Top 10 registrars by total operator count (Logarithmic Scale)')}
            </p>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs bg-green-100 text-green-700 px-3 py-1 rounded-full font-semibold">
              {distributionData.length} {selectedDistributionType === 'ea' ? 'Enrollment Agencies' : 'Registrars'}
            </span>
            
            {/* Distribution Type Dropdown */}
            <div className="relative distribution-dropdown-container">
              <button
                onClick={() => setIsDistributionDropdownOpen(!isDistributionDropdownOpen)}
                className="flex items-center gap-2 bg-green-50 hover:bg-green-100 text-green-700 font-semibold py-2 px-4 rounded-lg border border-green-200 transition-colors duration-200 min-w-[140px] justify-between"
              >
                <span>{selectedDistributionType === 'ea' ? 'EA Distribution' : 'REG Distribution'}</span>
                <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${isDistributionDropdownOpen ? 'rotate-180' : ''}`} />
              </button>
              
              {isDistributionDropdownOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
                  <div className="py-1">
                    <button
                      onClick={() => {
                        setSelectedDistributionType('ea');
                        setIsDistributionDropdownOpen(false);
                      }}
                      className={`w-full text-left px-4 py-2 hover:bg-green-50 transition-colors duration-150 ${
                        selectedDistributionType === 'ea' 
                          ? 'bg-green-100 text-green-700 font-semibold' 
                          : 'text-gray-700 hover:text-green-600'
                      }`}
                    >
                      EA Distribution
                      {selectedDistributionType === 'ea' && (
                        <span className="ml-2 text-green-500">✓</span>
                      )}
                    </button>
                    <button
                      onClick={() => {
                        setSelectedDistributionType('reg');
                        setIsDistributionDropdownOpen(false);
                      }}
                      className={`w-full text-left px-4 py-2 hover:bg-green-50 transition-colors duration-150 ${
                        selectedDistributionType === 'reg' 
                          ? 'bg-green-100 text-green-700 font-semibold' 
                          : 'text-gray-700 hover:text-green-600'
                      }`}
                    >
                      REG Distribution
                      {selectedDistributionType === 'reg' && (
                        <span className="ml-2 text-green-500">✓</span>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* EA Selection Dropdown - Only for EA Distribution */}
            {selectedDistributionType === 'ea' && (
              <>
                <div className="relative ea-selection-dropdown">
                  <button
                    onClick={() => setIsEaDropdownOpen(!isEaDropdownOpen)}
                    className="flex items-center gap-2 bg-blue-50 hover:bg-blue-100 text-blue-700 font-semibold py-2 px-4 rounded-lg border border-blue-200 transition-colors duration-200 justify-between"
                  >
                    <span>
                      Select EAs {selectedEas.length > 0 && `(${selectedEas.length})`}
                    </span>
                    <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${
                      isEaDropdownOpen ? 'rotate-180' : ''
                    }`} />
                  </button>
                  
                  {isEaDropdownOpen && (
                    <div className="absolute right-0 mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto">
                      <div className="p-3 border-b border-gray-200 bg-gray-50 sticky top-0">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold text-gray-700">
                            Select Enrollment Agencies
                          </span>
                          <button
                            onClick={handleResetToTop10}
                            className="text-xs text-red-600 hover:text-red-800 font-medium"
                          >
                            Clear All
                          </button>
                        </div>
                      </div>
                      <div className="py-1">
                        {availableEas.map((item, index) => (
                          <label
                            key={index}
                            className="flex items-center px-4 py-2 hover:bg-blue-50 cursor-pointer transition-colors duration-150"
                          >
                            <input
                              type="checkbox"
                              checked={selectedEas.includes(item)}
                              onChange={() => toggleEaSelection(item)}
                              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                            />
                            <span className="ml-3 text-sm text-gray-700">{item}</span>
                          </label>
                        ))}
                      </div>
                      {availableEas.length === 0 && (
                        <div className="px-4 py-3 text-sm text-gray-500 text-center">
                          No EAs available
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Compare Button - Only for EA */}
                <button
                  onClick={handleCompareSelected}
                  disabled={selectedEas.length === 0 || loadingEaData}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-2 px-4 rounded-lg transition-colors duration-200"
                >
                  {loadingEaData ? (
                    <>
                      <Loader className="w-4 h-4 animate-spin" />
                      <span>Loading...</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                      </svg>
                      <span>Show Comparison</span>
                    </>
                  )}
                </button>

                {/* Reset Button - Only for EA, shown when EAs are selected */}
                {selectedEas.length > 0 && (
                  <button
                    onClick={handleResetToTop10}
                    disabled={loadingEaData}
                    className="flex items-center gap-2 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-2 px-4 rounded-lg transition-colors duration-200"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                    </svg>
                    <span>Show Top 10</span>
                  </button>
                )}
              </>
            )}

            {/* Registrar Selection Dropdown - Only for REG Distribution */}
            {selectedDistributionType === 'reg' && (
              <>
                <div className="relative registrar-selection-dropdown">
                  <button
                    onClick={() => setIsRegistrarDropdownOpen(!isRegistrarDropdownOpen)}
                    className="flex items-center gap-2 bg-blue-50 hover:bg-blue-100 text-blue-700 font-semibold py-2 px-4 rounded-lg border border-blue-200 transition-colors duration-200 justify-between"
                  >
                    <span>
                      Select Registrars {selectedRegistrars.length > 0 && `(${selectedRegistrars.length})`}
                    </span>
                    <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${
                      isRegistrarDropdownOpen ? 'rotate-180' : ''
                    }`} />
                  </button>
                  
                  {isRegistrarDropdownOpen && (
                    <div className="absolute right-0 mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto">
                      <div className="p-3 border-b border-gray-200 bg-gray-50 sticky top-0">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold text-gray-700">
                            Select Registrars
                          </span>
                          <button
                            onClick={handleResetToTop10Registrars}
                            className="text-xs text-red-600 hover:text-red-800 font-medium"
                          >
                            Clear All
                          </button>
                        </div>
                      </div>
                      <div className="py-1">
                        {availableRegistrars.map((item, index) => (
                          <label
                            key={index}
                            className="flex items-center px-4 py-2 hover:bg-blue-50 cursor-pointer transition-colors duration-150"
                          >
                            <input
                              type="checkbox"
                              checked={selectedRegistrars.includes(item)}
                              onChange={() => toggleRegistrarSelection(item)}
                              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                            />
                            <span className="ml-3 text-sm text-gray-700">{item}</span>
                          </label>
                        ))}
                      </div>
                      {availableRegistrars.length === 0 && (
                        <div className="px-4 py-3 text-sm text-gray-500 text-center">
                          No Registrars available
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Compare Button - Only for Registrar */}
                <button
                  onClick={handleCompareSelectedRegistrars}
                  disabled={selectedRegistrars.length === 0 || loadingRegistrarData}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-2 px-4 rounded-lg transition-colors duration-200"
                >
                  {loadingRegistrarData ? (
                    <>
                      <Loader className="w-4 h-4 animate-spin" />
                      <span>Loading...</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                      </svg>
                      <span>Show Comparison</span>
                    </>
                  )}
                </button>

                {/* Reset Button - Only for Registrar, shown when Registrars are selected */}
                {selectedRegistrars.length > 0 && (
                  <button
                    onClick={handleResetToTop10Registrars}
                    disabled={loadingRegistrarData}
                    className="flex items-center gap-2 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-2 px-4 rounded-lg transition-colors duration-200"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                    </svg>
                    <span>Show Top 10</span>
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        <div className="mb-4">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-4 text-sm">
              {eaRegBucketKeys.map(bucket => (
                <div key={bucket} className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: getRiskBucketStyle(bucket).color }}></div>
                  <span>{bucket} Risk</span>
                </div>
              ))}
            </div>
            
            {/* Indicator for EA mode */}
            {selectedDistributionType === 'ea' && (
              <div className="flex items-center gap-2">
                {selectedEas.length > 0 ? (
                  <div className="flex items-center gap-2 text-sm bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full font-semibold">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                    </svg>
                    <span>Comparing {selectedEas.length} Selected EAs</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-sm bg-purple-100 text-purple-700 px-3 py-1 rounded-full font-semibold">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>
                    </svg>
                    <span>Showing Top 10 EAs</span>
                  </div>
                )}
              </div>
            )}

            {/* Indicator for Registrar mode */}
            {selectedDistributionType === 'reg' && (
              <div className="flex items-center gap-2">
                {selectedRegistrars.length > 0 ? (
                  <div className="flex items-center gap-2 text-sm bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full font-semibold">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                    </svg>
                    <span>Comparing {selectedRegistrars.length} Selected Registrars</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-sm bg-purple-100 text-purple-700 px-3 py-1 rounded-full font-semibold">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>
                    </svg>
                    <span>Showing Top 10 Registrars</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {distributionData.length > 0 ? (
          <>
            <ResponsiveContainer width="100%" height={500}>
              <BarChart 
                data={distributionData} 
                margin={{ top: 20, right: 30, left: 20, bottom: 120 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis 
                  dataKey="name" 
                  angle={-45}
                  textAnchor="end"
                  height={120}
                  tick={{ fontSize: 10, fill: '#374151' }}
                  interval={0}
                />
                <YAxis 
                  scale="log" 
                  domain={[0.1, 'auto']}
                  allowDataOverflow={false}
                  tickFormatter={(value) => {
                    if (value < 1) return '0';
                    return value >= 1000 ? `${(value/1000).toFixed(0)}k` : value.toFixed(0);
                  }}
                  label={{ 
                    value: 'Number of Operators (Log Scale)', 
                    angle: -90, 
                    position: 'insideLeft', 
                    style: { fontSize: 12, fill: '#6b7280' } 
                  }}
                  tick={{ fontSize: 11, fill: '#374151' }}
                />
                <Tooltip content={<DistributionCustomTooltip />} />

                {eaRegBucketKeys.map(bucket => (
                  <Bar
                    key={bucket}
                    dataKey={`${bucket}_display`}
                    name={`${bucket} Risk`}
                    fill={getRiskBucketStyle(bucket).color}
                    onClick={(data) => navigateToFilteredOperators(data?.payload || data, bucket)}
                    style={{ cursor: 'pointer' }}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>

            <div className="mt-4 p-3 bg-blue-50 rounded-lg">
              <div className="flex items-start gap-2 text-blue-700">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div className="text-sm">
                  <span className="font-medium">Note:</span> Y-axis uses logarithmic scale for better visualization. Hover over bars to see actual operator counts.
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-20 px-4">
            <div className="text-center max-w-md">
              <AlertCircle className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-bold text-gray-700 mb-2">No Data Available</h3>
              <p className="text-gray-500">
                No {selectedDistributionType === 'ea' ? 'enrollment agency' : 'registrar'} data is currently available. 
                {selectedDistributionType === 'ea' ? (
                  selectedEas.length > 0 
                    ? ' The selected enrollment agencies may not have data, or the API is unavailable.'
                    : ' Please try again later or contact support if the issue persists.'
                ) : (
                  selectedRegistrars.length > 0
                    ? ' The selected registrars may not have data, or the API is unavailable.'
                    : ' Please try again later or contact support if the issue persists.'
                )}
              </p>
            </div>
          </div>
        )}
      </div>

    </div>
  );
};

export default OverviewTab;
