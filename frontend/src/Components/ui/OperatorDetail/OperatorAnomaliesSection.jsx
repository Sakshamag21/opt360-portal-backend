import React from 'react';
import { AlertTriangle, CheckCircle } from 'lucide-react';

const OperatorAnomaliesSection = ({
  riskDetailsData,
  loadingRiskData,
  selectedAnomalyCategory,
  setSelectedAnomalyCategory,
  handleShowSidsByCategory,
}) => {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Category Filter Buttons */}
      {riskDetailsData?.risk_metrics?.anomaly_category_score && (
        <div className="bg-white rounded-2xl shadow-lg p-6 border-2 border-gray-100">
          <h4 className="text-lg font-bold text-gray-900 mb-4">Filter by Category</h4>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => setSelectedAnomalyCategory(null)}
              className={`px-4 py-2 rounded-lg font-semibold transition-all duration-200 ${
                !selectedAnomalyCategory
                  ? 'bg-gradient-to-r from-purple-600 to-purple-700 text-white shadow-lg scale-105'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              All Categories
            </button>
            {riskDetailsData.risk_metrics.anomaly_category_score.map((category) => (
              <button
                key={category.category_code}
                onClick={() => setSelectedAnomalyCategory(category.category_name.toLowerCase())}
                className={`px-4 py-2 rounded-lg font-semibold transition-all duration-200 ${
                  selectedAnomalyCategory === category.category_name.toLowerCase()
                    ? 'bg-gradient-to-r from-red-600 to-red-700 text-white shadow-lg scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {category.category_name.charAt(0).toUpperCase() + category.category_name.slice(1)}
                <span className="ml-2 px-2 py-0.5 bg-white/20 rounded text-xs">
                  {(category.category_score * 100).toFixed(2)}%
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <div className="p-2 bg-red-100 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-red-600" />
            </div>
            {selectedAnomalyCategory
              ? `${selectedAnomalyCategory.charAt(0).toUpperCase() + selectedAnomalyCategory.slice(1)} Anomalies`
              : 'Detected Anomalies'}
          </h3>
          {selectedAnomalyCategory && (
            <button
              onClick={() => handleShowSidsByCategory(selectedAnomalyCategory)}
              className="px-4 py-2 rounded-lg font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-all duration-200 shadow-md hover:shadow-lg flex items-center gap-2"
              title={`Show SIDs for ${selectedAnomalyCategory}`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              Show SIDs
            </button>
          )}
        </div>

        {riskDetailsData?.risk_metrics?.anomaly_category_score ? (
          <div className="space-y-4">
            {riskDetailsData.risk_metrics.anomaly_category_score
              .filter(category => !selectedAnomalyCategory || category.category_name.toLowerCase() === selectedAnomalyCategory)
              .map((category) => (
                <div key={category.category_code} className="space-y-3">
                  {/* Category Header */}
                  {!selectedAnomalyCategory && (
                    <div className="bg-gradient-to-r from-gray-50 to-gray-100 p-4 rounded-lg border-l-4 border-purple-500 mb-2">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-3">
                          <h4 className="text-xl font-bold text-gray-900 capitalize">{category.category_name}</h4>
                          <button
                            onClick={() => handleShowSidsByCategory(category.category_name)}
                            className="px-3 py-1.5 rounded-lg font-semibold text-sm bg-blue-600 text-white hover:bg-blue-700 transition-all duration-200 shadow-md hover:shadow-lg flex items-center gap-1.5"
                            title={`Show SIDs for ${category.category_name}`}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                            </svg>
                            Show SIDs
                          </button>
                        </div>
                        <span className={`px-4 py-2 rounded-full text-sm font-extrabold shadow-md ${
                          category.category_score >= 0.7 ? 'bg-red-100 text-red-700 border-2 border-red-300' :
                          category.category_score >= 0.4 ? 'bg-yellow-100 text-yellow-700 border-2 border-yellow-300' :
                          'bg-green-100 text-green-700 border-2 border-green-300'
                        }`}>
                          {(category.category_score * 100).toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Individual Anomalies */}
                  {category.category_metrics.map((anomaly) => (
                    <div
                      key={anomaly.anomaly_code}
                      className={`p-5 rounded-xl border-l-4 hover:scale-102 transition-all duration-300 shadow-md ${
                        anomaly.anomaly_score >= 0.7 ? 'bg-red-50 border-red-500' :
                        anomaly.anomaly_score >= 0.4 ? 'bg-yellow-50 border-yellow-500' :
                        anomaly.anomaly_score > 0 ? 'bg-blue-50 border-blue-500' :
                        'bg-gray-50 border-gray-300'
                      }`}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <h5 className="font-bold text-lg text-gray-900">{anomaly.anomaly_name}</h5>
                            <span className={`px-3 py-1 rounded-lg text-xs font-bold text-white shadow-sm ${
                              category.category_name === 'biometrics' ? 'bg-purple-500' :
                              category.category_name === 'document' ? 'bg-indigo-500' :
                              category.category_name === 'suspicious' ? 'bg-orange-500' :
                              category.category_name === 'work' ? 'bg-teal-500' :
                              'bg-gray-600'
                            }`}>
                              {category.category_name}
                            </span>
                          </div>
                          <p className="text-xs text-gray-500 font-mono">{anomaly.anomaly_code}</p>
                        </div>
                        <span className={`px-4 py-2 rounded-full text-sm font-extrabold shadow-md ${
                          anomaly.anomaly_score >= 0.7 ? 'bg-red-100 text-red-700 border-2 border-red-300' :
                          anomaly.anomaly_score >= 0.4 ? 'bg-yellow-100 text-yellow-700 border-2 border-yellow-300' :
                          anomaly.anomaly_score > 0 ? 'bg-blue-100 text-blue-700 border-2 border-blue-300' :
                          'bg-gray-100 text-gray-700 border-2 border-gray-300'
                        }`}>
                          {(anomaly.anomaly_score * 100).toFixed(2)}%
                        </span>
                      </div>

                      {/* Description based on score */}
                      <p className="text-sm text-gray-700 leading-relaxed mt-3">
                        {anomaly.anomaly_score >= 0.7
                          ? `High ${category.category_name} anomaly detected. Immediate investigation required.`
                          : anomaly.anomaly_score >= 0.4
                          ? `Moderate ${category.category_name} anomaly detected. Monitor closely.`
                          : anomaly.anomaly_score > 0
                          ? `Low ${category.category_name} anomaly detected. Within acceptable range.`
                          : `No ${category.category_name} anomaly detected.`}
                      </p>
                    </div>
                  ))}
                </div>
              ))}
          </div>
        ) : loadingRiskData ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading anomaly data...</p>
          </div>
        ) : (
          <div className="text-center py-12 bg-gradient-to-br from-green-50 to-blue-50 rounded-xl">
            <CheckCircle className="w-20 h-20 mx-auto mb-4 text-green-500" />
            <p className="text-xl font-bold text-gray-900 mb-2">No anomaly data available</p>
            <p className="text-sm text-gray-600">Unable to fetch detailed anomaly information from the API</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default OperatorAnomaliesSection;
