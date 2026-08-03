import React from 'react';
import { X, Activity, Info, AlertCircle, Award } from 'lucide-react';
import FeatureGraph from '../../FeatureGraph';

const OperatorKPISection = ({
  loadingKpiData,
  kpiError,
  kpis,
  featureRemarksModal,
  setFeatureRemarksModal,
  featureGraphModal,
  setFeatureGraphModal,
}) => {
  return (
    <div className="space-y-6">
      {loadingKpiData ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#9b7bb5]"></div>
          <span className="ml-3 text-gray-600">Loading KPI data...</span>
        </div>
      ) : kpiError ? (
        <div className="bg-red-50 rounded-2xl p-8 text-center border-2 border-red-200">
          <AlertCircle className="w-16 h-16 mx-auto mb-4 text-red-500" />
          <h3 className="text-2xl font-bold text-gray-900 mb-2">Error Loading KPI Data</h3>
          <p className="text-gray-600">{kpiError}</p>
        </div>
      ) : kpis.length === 0 ? (
        <div className="bg-yellow-50 rounded-2xl p-8 text-center border-2 border-yellow-200">
          <Info className="w-16 h-16 mx-auto mb-4 text-yellow-500" />
          <h3 className="text-2xl font-bold text-gray-900 mb-2">No KPI Data Available</h3>
          <p className="text-gray-600">There are no KPIs available for this operator at this time.</p>
        </div>
      ) : (
        kpis.map((categoryObj, idx) => (
          <div key={idx} className="mb-6">
            {Object.entries(categoryObj || {}).map(([categoryName, features]) => {
              if (!Array.isArray(features) || features.length === 0) return null;
              return (
                <div key={categoryName} className="mb-4">
                  <h3 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-3">
                    <div className="p-2 bg-[#e8dff2] rounded-lg">
                      <Award className="w-6 h-6 text-[#9b7bb5]" />
                    </div>
                    {categoryName}
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    {(Array.isArray(features) ? features : []).map((f) => (
                      <div key={f?.feature_id} className="border-l-4 rounded-xl p-5 shadow-md bg-gradient-to-br from-[#f5f2f8] to-[#e8dff2] border-[#d2c5e7]
                        ">
                            <div className={`flex items-center justify-between mb-2 text-[#9b7bb5]`}>
                              <div className="flex items-center gap-2">
                                <Activity className="w-5 h-5" />
                                <span className="text-xs font-bold uppercase tracking-wide">{f?.feature_name ?? ''}</span>
                                <button
                                  type="button"
                                  aria-label="Feature info"
                                  className="p-1 rounded-md hover:bg-white/60"
                                  onClick={(e) => { e.stopPropagation(); setFeatureRemarksModal({ open: true, feature: f }); }}
                                >
                                  <Info className="w-4 h-4" />
                                </button>
                              </div>

                              <div className="flex items-center gap-2">
                                {f.feature_graph && (f.feature_graph.graph_type=="line chart") && <button
                                  type="button"
                                  className="px-2 py-1 text-xs font-medium rounded-md border border-[#d2c5e7] bg-white/70 text-[#7a5f93] hover:bg-white"
                                  onClick={(e) => { e.stopPropagation(); setFeatureGraphModal({ open: true, feature: f }); }}
                                >
                                  Graph
                                </button>}

                              </div>
                            </div>
                            <div className="text-3xl font-extrabold text-[#7a5f93]">
                              {f?.feature_value ?? '0'}
                            </div>
                            <div className="text-xs font-medium mt-1 text-[#9b7bb5]">
                              {f?.feature_description ?? ''}
                            </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ))
      )}

      {featureRemarksModal.open && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setFeatureRemarksModal({ open: false, feature: null })} />
          <div className="absolute inset-0 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl border border-gray-200" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between p-4 border-b">
                <h3 className="text-lg font-semibold text-gray-900">{featureRemarksModal.feature?.feature_name ?? 'Feature Remarks'}</h3>
                <button
                  className="p-2 rounded-md hover:bg-gray-100"
                  aria-label="Close remarks"
                  onClick={() => setFeatureRemarksModal({ open: false, feature: null })}
                >
                  <X className="w-5 h-5 text-gray-600" />
                </button>
              </div>
              <div className="p-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {Object.keys(featureRemarksModal.feature?.remarks ?? {}).length === 0 ? (
                    <div className="text-gray-600">No remarks available for this feature.</div>
                  ) : (
                    Object.entries(featureRemarksModal.feature.remarks).map(([key, value]) => (
                      <div key={key} className="rounded-lg border border-gray-200 p-3">
                        <div className="text-xs font-semibold text-gray-700">{key}</div>
                        <div className="text-sm text-gray-900 mt-1">{String(value)}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
              <div className="flex justify-end gap-2 p-4 border-t">
                <button
                  className="px-3 py-2 text-sm rounded-md bg-gray-100 text-gray-800 hover:bg-gray-200"
                  onClick={() => setFeatureRemarksModal({ open: false, feature: null })}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {featureGraphModal.open && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setFeatureGraphModal({ open: false, feature: null })} />
          <div className="absolute inset-0 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl border border-gray-200" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between p-4 border-b">
                <h3 className="text-lg font-semibold text-gray-900">{featureGraphModal.feature?.feature_name ?? 'Feature Graph'}</h3>
                {console.log()}
                <button
                  className="p-2 rounded-md hover:bg-gray-100"
                  aria-label="Close graph"
                  onClick={() => setFeatureGraphModal({ open: false, feature: null })}
                >
                  <X className="w-5 h-5 text-gray-600" />
                </button>
              </div>
              <div className="p-4">
                <FeatureGraph feature={featureGraphModal.feature} />
              </div>
              <div className="flex justify-end gap-2 p-4 border-t">
                <button
                  className="px-3 py-2 text-sm rounded-md bg-gray-100 text-gray-800 hover:bg-gray-200"
                  onClick={() => setFeatureGraphModal({ open: false, feature: null })}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OperatorKPISection;
