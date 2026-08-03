import React, { useMemo, useState, useEffect } from 'react';
import { Target, AlertTriangle, Shield, Settings, FileText, Users, Info } from 'lucide-react';
import { API_BASE_URL, getAuthHeaders } from '../config/apiConfig';
import infoData from '../resources/infoData.json';
import anomalyDummy from '../resources/anomalyDummy.json';

const IS_DEV = process.env.REACT_APP_ENV === 'dev';

const PatternAnalysisTab = () => {
  const [apiAnomalyData, setApiAnomalyData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hoveredInfo, setHoveredInfo] = useState(null);

  // Fetch anomaly indicators from API
  useEffect(() => {
    const fetchAnomalyIndicators = async () => {
      setLoading(true);
      setError(null);

      if (IS_DEV) {
        await new Promise(r => setTimeout(r, 400));
        setApiAnomalyData(anomalyDummy.data);
        setLoading(false);
        return;
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/anamoly_indicators`, {
          method: 'GET',
          headers: getAuthHeaders()
        });
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const result = await response.json();
        setApiAnomalyData(result.data || {});
      } catch (err) {
        console.error('Error fetching anomaly indicators:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchAnomalyIndicators();
  }, []);

  // Process anomaly data from the API into per-category totals.
  const anomalyData = useMemo(() => {
    const anomalyCategories = {
      'biometric': { name: 'Biometric', icon: Shield, color: 'bg-blue-500', apiCategory: 'Biometrics' },
      'document': { name: 'Document', icon: FileText, color: 'bg-green-500', apiCategory: 'Document' },
      'hardware': { name: 'Hardware', icon: Settings, color: 'bg-orange-500', apiCategory: 'Hardware' },
      'packet': { name: 'Packet', icon: Users, color: 'bg-purple-500', apiCategory: 'Suspicious' },
      'work': { name: 'Work', icon: AlertTriangle, color: 'bg-red-500', apiCategory: 'Work' }
    };

    if (!apiAnomalyData) {
      return { categoryStats: [], totalOperators: 0 };
    }

    const categoryStats = {};
    Object.keys(anomalyCategories).forEach(key => {
      categoryStats[anomalyCategories[key].name] = {
        name: anomalyCategories[key].name,
        categoryKey: key,
        high: 0,
        medium: 0,
        low: 0,
        total: 0,
        ...anomalyCategories[key]
      };
    });

    Object.values(apiAnomalyData).forEach(indicator => {
      const matchingCategory = Object.values(anomalyCategories).find(
        cat => cat.apiCategory === indicator.anomaly_category
      );
      if (matchingCategory) {
        const categoryName = matchingCategory.name;
        categoryStats[categoryName].high += indicator.high || 0;
        categoryStats[categoryName].medium += indicator.medium || 0;
        categoryStats[categoryName].low += indicator.low || 0;
        categoryStats[categoryName].total += (indicator.high || 0) + (indicator.medium || 0) + (indicator.low || 0);
      }
    });

    const totalOperators = Object.values(apiAnomalyData).reduce((sum, indicator) =>
      Math.max(sum, (indicator.high || 0) + (indicator.medium || 0) + (indicator.low || 0)), 0);

    return {
      categoryStats: Object.values(categoryStats),
      totalOperators
    };
  }, [apiAnomalyData]);

  return (
    <div className="space-y-6">
      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-purple-500 mb-4"></div>
            <p className="text-lg font-semibold text-gray-700">Loading anomaly data...</p>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-3" />
          <p className="text-red-700 font-medium">Error loading data: {error}</p>
        </div>
      )}

      {!loading && !error && (
      <>
      {/* Detailed Anomaly Types */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-6">Anomaly Types Breakdown</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {apiAnomalyData && Object.entries(apiAnomalyData).map(([key, indicator], idx) => {
            const total = (indicator.high || 0) + (indicator.medium || 0) + (indicator.low || 0);

            // Find matching category based on anomaly_category
            const categoryMapping = {
              'Biometrics': { name: 'Biometric', icon: Shield, color: 'bg-blue-500' },
              'Document': { name: 'Document', icon: FileText, color: 'bg-green-500' },
              'Hardware': { name: 'Hardware', icon: Settings, color: 'bg-orange-500' },
              'Suspicious': { name: 'Packet', icon: Users, color: 'bg-purple-500' },
              'Work': { name: 'Work', icon: AlertTriangle, color: 'bg-red-500' }
            };

            const category = categoryMapping[indicator.anomaly_category] || { name: 'Other', icon: Target, color: 'bg-gray-500' };
            const IconComponent = category.icon;

            return (
              <div key={idx} className="border rounded-lg p-4 hover:shadow-md transition-all duration-200 hover:border-purple-300">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg ${category.color} flex items-center justify-center`}>
                      <IconComponent className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-semibold text-gray-900 text-sm mb-1">
                        {indicator.anomaly_name}
                      </h4>
                      <div className="text-xs text-gray-600 mb-1 flex items-center gap-2">
                        <span className="font-mono bg-gray-200 px-2 py-1 rounded">
                          {indicator.anomaly_code}
                        </span>
                        {infoData[indicator.anomaly_code] && (
                          <div className="relative inline-flex">
                            <div className="group relative">
                              <Info
                                className="w-5 h-5 text-blue-500 hover:text-blue-600 cursor-help transition-colors duration-200 hover:scale-110 transform"
                                onMouseEnter={() => setHoveredInfo(indicator.anomaly_code)}
                                onMouseLeave={() => setHoveredInfo(null)}
                              />
                              {hoveredInfo === indicator.anomaly_code && (
                                <div className="absolute left-full ml-3 top-1/2 -translate-y-1/2 z-[100] w-72 transition-all duration-200 ease-out opacity-100 scale-100">
                                  <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-blue-300 text-gray-800 p-4 rounded-xl shadow-2xl backdrop-blur-sm">
                                    {/* Arrow pointing left */}
                                    <div className="absolute -left-2 top-1/2 -translate-y-1/2 w-0 h-0 border-t-8 border-t-transparent border-b-8 border-b-transparent border-r-8 border-r-blue-300"></div>
                                    <div className="absolute -left-[6px] top-1/2 -translate-y-1/2 w-0 h-0 border-t-[7px] border-t-transparent border-b-[7px] border-b-transparent border-r-[7px] border-r-blue-50"></div>

                                    {/* Content */}
                                    <div className="flex items-start gap-2">
                                      <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
                                      <p className="text-xs leading-relaxed text-gray-700 font-medium">
                                        {infoData[indicator.anomaly_code]}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                      <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded">
                        {category.name}
                      </span>
                    </div>

                  </div>
                  <div className="text-right">
                    <span className="text-lg font-bold text-purple-600">{total.toLocaleString()}</span>


                  </div>
                </div>

                {/* Mini progress indicators */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                      <span>High</span>
                    </div>
                    <span className="font-medium">{indicator.high || 0}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-1">
                    <div
                      className="bg-red-500 h-1 rounded-full"
                      style={{ width: `${total > 0 ? ((indicator.high || 0) / total) * 100 : 0}%` }}
                    ></div>
                  </div>

                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                      <span>Medium</span>
                    </div>
                    <span className="font-medium">{indicator.medium || 0}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-1">
                    <div
                      className="bg-yellow-500 h-1 rounded-full"
                      style={{ width: `${total > 0 ? ((indicator.medium || 0) / total) * 100 : 0}%` }}
                    ></div>
                  </div>

                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                      <span>Low</span>
                    </div>
                    <span className="font-medium">{indicator.low || 0}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-1">
                    <div
                      className="bg-blue-500 h-1 rounded-full"
                      style={{ width: `${total > 0 ? ((indicator.low || 0) / total) * 100 : 0}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Anomaly Structure Overview */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-6">Anomaly Structure by Category</h3>
        <div className="space-y-6">
          {apiAnomalyData && anomalyData.categoryStats.map((category) => {
            // Find all API indicators for this category
            const categoryIndicators = Object.entries(apiAnomalyData).filter(([key, indicator]) => {
              const categoryMapping = {
                'Biometrics': 'Biometric',
                'Document': 'Document',
                'Hardware': 'Hardware',
                'Suspicious': 'Packet',
                'Work': 'Work'
              };
              return categoryMapping[indicator.anomaly_category] === category.name;
            });

            if (categoryIndicators.length === 0) return null;

            const IconComponent = category.icon;

            return (
              <div key={category.name} className="border rounded-lg p-4">
                <div className="flex items-center gap-3 mb-4">
                  <div className={`w-10 h-10 rounded-lg ${category.color} flex items-center justify-center`}>
                    <IconComponent className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h4 className="text-lg font-semibold text-gray-900">{category.name} Category</h4>
                    <p className="text-sm text-gray-600">
                      {categoryIndicators.length} anomaly indicators • {category.total.toLocaleString()} total occurrences
                    </p>
                  </div>
                </div>

                {/* Anomaly Types List */}
                <div className="space-y-2">
                  <h5 className="font-medium text-gray-700 text-sm mb-3">Anomaly Types:</h5>
                  {categoryIndicators.map(([key, indicator], idx) => {
                    const total = (indicator.high || 0) + (indicator.medium || 0) + (indicator.low || 0);
                    return (
                      <div key={idx} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded text-sm hover:bg-gray-100 transition-colors">
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">{indicator.anomaly_name}</div>
                          <div className="text-xs text-gray-500 font-mono mt-1">{indicator.anomaly_code}</div>
                        </div>
                        <div className="text-right ml-4">
                          <div className="font-bold text-gray-900">{total.toLocaleString()}</div>
                          <div className="text-xs text-gray-500">
                            <span className="text-red-600">{indicator.high || 0}</span> /
                            <span className="text-yellow-600"> {indicator.medium || 0}</span> /
                            <span className="text-blue-600"> {indicator.low || 0}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      </>
      )}

    </div>
  );
};

export default PatternAnalysisTab;
