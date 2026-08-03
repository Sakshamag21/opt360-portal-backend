import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { MapPin, ArrowLeft, BarChart3, Loader } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { API_BASE_URL, getAuthHeaders } from '../config/apiConfig';
import regionEvaluationDummy from '../resources/regionEvaluationDummy.json';
import { getRiskBucketStyle } from '../utils/colorHelpers';

const IS_DEV = process.env.REACT_APP_ENV === 'dev';

// This source (opt360Store/.../audit.json, via /api/region_evaluation_count)
// only has high_risk/med_risk/low_risk keys today, but if the pipeline
// starts writing a critical_risk key, it should just appear here — not be
// silently dropped, and not show as a fake zero when absent. Any key ending
// in _risk on a source item is treated as a bucket.
const RISK_KEY_ORDER = ['critical_risk', 'high_risk', 'med_risk', 'low_risk'];
const RISK_KEY_LABELS = { critical_risk: 'Critical', high_risk: 'High', med_risk: 'Medium', low_risk: 'Low' };

const riskKeyLabel = (key) =>
  RISK_KEY_LABELS[key] || key.replace(/_risk$/, '').split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

const riskKeyColor = (key) => getRiskBucketStyle(riskKeyLabel(key)).color;

const getRiskKeys = (items) => {
  const keys = new Set();
  (items || []).forEach(item => {
    Object.keys(item).forEach(k => {
      if (k.endsWith('_risk')) keys.add(k);
    });
  });
  return Array.from(keys).sort((a, b) => {
    const ia = RISK_KEY_ORDER.indexOf(a);
    const ib = RISK_KEY_ORDER.indexOf(b);
    if (ia === -1 && ib === -1) return a.localeCompare(b);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
};

const GeographicAnalysisTab = ({ selectedRo = 'Bangalore' }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedState, setSelectedState] = useState(null);
  const [drillLevel, setDrillLevel] = useState('state'); // 'state' or 'district'

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [displayData, setDisplayData] = useState([]);

  const riskKeys = React.useMemo(() => getRiskKeys(chartData), [chartData]);

  // Transform data for logarithmic display (replace 0 with 0.1 for visibility)
  const transformDataForLog = (data) => {
    const keys = getRiskKeys(data);
    return data.map(item => {
      const transformed = { ...item };
      keys.forEach(key => {
        transformed[`${key}_display`] = item[key] || 0.1;
        transformed[`${key}_actual`] = item[key] || 0;
      });
      return transformed;
    });
  };

  // Reset state and clear query params when regional office changes
  useEffect(() => {
    setSelectedState(null);
    setDrillLevel('state');
    const params = new URLSearchParams();
    setSearchParams(params, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRo]);

  // Sync initial state from query params (e.g., ?name=Tamil%20Nadu)
  useEffect(() => {
    const nameParam = searchParams.get('name');
    if (nameParam) {
      setSelectedState(nameParam);
      setDrillLevel('district');
    } else {
      // If no query param, ensure we're at state level
      setSelectedState(null);
      setDrillLevel('state');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Fetch data from API based on drill level
  useEffect(() => {
    // Guard: Skip fetch during state transitions
    // If drillLevel is 'state', selectedState MUST be null
    // If drillLevel is 'district', selectedState MUST have a value
    if (drillLevel === 'state' && selectedState !== null) return;
    if (drillLevel === 'district' && !selectedState) return;

    const fetchRegionData = async () => {
      setLoading(true);
      setError(null);

      if (IS_DEV) {
        await new Promise(r => setTimeout(r, 350));
        let responseData;
        if (drillLevel === 'district' && selectedState && regionEvaluationDummy.districts[selectedState]) {
          responseData = regionEvaluationDummy.districts[selectedState];
        } else {
          responseData = regionEvaluationDummy.states;
        }
        const apiData = responseData.data || responseData;
        const distribution = apiData.opt_distribution || {};
        if (drillLevel === 'state') {
          const stateData = Object.entries(distribution).map(([name, counts]) => ({ name, ...counts }));
          setChartData(stateData);
          setDisplayData(transformDataForLog(stateData));
        } else {
          const nested = selectedState && distribution[selectedState];
          const districtData = Object.entries(nested || distribution).map(([name, counts]) => ({ name, ...counts }));
          setChartData(districtData);
          setDisplayData(transformDataForLog(districtData));
        }
        setLoading(false);
        return;
      }

      try {
        const params = new URLSearchParams({ regional_office: selectedRo });
        if (drillLevel === 'district' && selectedState && selectedState.trim() !== '') {
          params.append('opt_state', selectedState);
        }

        const url = `${API_BASE_URL}/api/region_evaluation_count?${params.toString()}`;

        const response = await fetch(url, {
          method: 'GET',
          headers: getAuthHeaders()
        });

        if (!response.ok) throw new Error(`API error: ${response.status} ${response.statusText}`);

        const responseData = await response.json();

        // Process API response based on drill level
        const apiData = responseData.data || responseData;
        const distribution = apiData.opt_distribution || {};
        
        if (drillLevel === 'state') {
          // Process state-level data from opt_distribution
          const stateData = Object.entries(distribution).map(([stateName, counts]) => ({ name: stateName, ...counts }));

          setChartData(stateData);
          setDisplayData(transformDataForLog(stateData));
        } else if (drillLevel === 'district') {
          // For district level, opt_distribution is nested: { "StateName": { "DistrictName": {counts} } }
          // Extract the districts from the selected state
          let districtData = [];

          if (selectedState && distribution[selectedState]) {
            // Nested structure: districts are under the state key
            districtData = Object.entries(distribution[selectedState]).map(([districtName, counts]) => ({ name: districtName, ...counts }));
          } else {
            // Fallback: flat structure with district names as top-level keys
            districtData = Object.entries(distribution).map(([districtName, counts]) => ({ name: districtName, ...counts }));
          }

          setChartData(districtData);
          setDisplayData(transformDataForLog(districtData));
        }
      } catch (err) {
        console.error('Error fetching region evaluation data:', err);
        setError(err.message);
        setChartData([]);
      } finally {
        setLoading(false);
      }
    };

    fetchRegionData();
  }, [selectedRo, drillLevel, selectedState, searchParams]);

  const handleBarClick = (data) => {
    if (drillLevel !== 'state' || !data) return;
    const clickedName = data?.payload?.name || data?.name;
    if (!clickedName) return;
    setSelectedState(clickedName);
    setDrillLevel('district');
    const params = new URLSearchParams(searchParams);
    params.set('name', clickedName);
    setSearchParams(params, { replace: false });
  };

  const handleBackToStates = () => {
    setSelectedState(null);
    setDrillLevel('state');
    const params = new URLSearchParams(searchParams);
    params.delete('name');
    setSearchParams(params, { replace: false });
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0]?.payload;
      const total = riskKeys.reduce((sum, key) => sum + (data?.[`${key}_actual`] ?? 0), 0);

      return (
        <div className="bg-white p-4 border rounded-lg shadow-lg">
          <p className="font-semibold text-gray-900 mb-2">{label}</p>
          <div className="space-y-1">
            {payload.map((entry, index) => {
              const key = riskKeys[index];
              const actualValue = data?.[`${key}_actual`] ?? 0;
              return (
                <div key={index} className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded"
                      style={{ backgroundColor: entry.color }}
                    />
                    <span className="text-sm">{riskKeyLabel(key)} Risk:</span>
                  </div>
                  <span className="font-medium">{actualValue}</span>
                </div>
              );
            })}
            <hr className="my-2" />
            <div className="flex items-center justify-between font-semibold">
              <span>Total:</span>
              <span>{total}</span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <MapPin className="w-6 h-6 text-blue-500" />
            <div>
              <h2 className="text-xl font-bold text-gray-900">
                Region Evaluation - {selectedRo} RO
              </h2>
              <p className="text-gray-600">
                {drillLevel === 'state' 
                  ? `Risk distribution by states in ${selectedRo} region` 
                  : `Risk distribution by districts in ${selectedState}`
                }
              </p>
            </div>
          </div>
          
          {drillLevel === 'district' && (
            <button
              onClick={handleBackToStates}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to States
            </button>
          )}
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-96">
            <Loader className="w-8 h-8 animate-spin text-blue-500" />
            <span className="ml-3 text-gray-600">Loading data...</span>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-96">
            <div className="text-center">
              <p className="text-red-600 font-semibold mb-2">Error loading data</p>
              <p className="text-gray-600 text-sm">{error}</p>
            </div>
          </div>
        ) : (
          <>
            <div className="mb-4">
              <div className="flex items-center gap-4 text-sm">
                {riskKeys.map(key => (
                  <div key={key} className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded" style={{ backgroundColor: riskKeyColor(key) }}></div>
                    <span>{riskKeyLabel(key)} Risk</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={displayData}
                  margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="name"
                    angle={-45}
                    textAnchor="end"
                    height={80}
                    fontSize={12}
                  />
                  <YAxis
                    scale="log"
                    domain={[0.1, 'auto']}
                    allowDataOverflow={false}
                    tickFormatter={(value) => {
                      if (value < 1) return '0';
                      return value >= 1000 ? `${(value/1000).toFixed(0)}k` : value.toFixed(0);
                    }}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend
                    formatter={(value) => value.replace(' Display', '')}
                  />
                  {riskKeys.map(key => (
                    <Bar
                      key={key}
                      dataKey={`${key}_display`}
                      name={`${riskKeyLabel(key)} Risk Display`}
                      fill={riskKeyColor(key)}
                      onClick={handleBarClick}
                      style={{ cursor: drillLevel === 'state' ? 'pointer' : 'default' }}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
            
            {drillLevel === 'state' && (
              <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                <div className="flex items-center gap-2 text-blue-700">
                  <BarChart3 className="w-4 h-4" />
                  <span className="text-sm font-medium">Click on any state bar to view district-wise breakdown</span>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Summary Statistics */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-4">
          {drillLevel === 'state' ? 'State-wise Summary' : `${selectedState} Districts Summary`}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {chartData.map((item, index) => {
            const total = riskKeys.reduce((sum, key) => sum + (item[key] || 0), 0);
            return (
              <div key={index} className="border rounded-lg p-4">
                <h4 className="font-semibold text-gray-900 mb-2 truncate" title={item.name}>
                  {item.name}
                </h4>
                <div className="space-y-2">
                  {riskKeys.map(key => (
                    <div key={key} className="flex justify-between text-sm">
                      <span style={{ color: riskKeyColor(key) }}>{riskKeyLabel(key)} Risk:</span>
                      <span className="font-medium">{item[key] || 0}</span>
                    </div>
                  ))}
                  <hr />
                  <div className="flex justify-between text-sm font-semibold">
                    <span>Total:</span>
                    <span>{total}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default GeographicAnalysisTab;
