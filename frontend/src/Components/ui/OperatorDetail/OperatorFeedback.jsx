import React from 'react';
import { MessageSquare, FileText, CheckCircle, XCircle, Check, AlertTriangle, BarChart3 } from 'lucide-react';

// Mirrors backend/handlers/OperatorDetailView/operatorFeedbackStats.go's
// feedbackCategories, plus which verdict value ("yes"/true) counts as the
// concerning one for that category -- verified_legitimate_operator is the
// only category where "yes" is the reassuring answer.
const CATEGORY_META = [
  { key: 'verified_fraud_operator', label: 'Verified Fraudulent', concerningValue: true },
  { key: 'verified_legitimate_operator', label: 'Verified Legitimate', concerningValue: false },
  { key: 'worked_with_cloned_machine', label: 'Cloned Machine Use', concerningValue: true },
  { key: 'unsystematic_biometric_capture', label: 'Unsystematic Biometric Capture', concerningValue: true },
  { key: 'packet_anomaly_identified', label: 'Packet Anomaly Identified', concerningValue: true },
];

const FeedbackStatsCard = ({ feedbackStats, loadingFeedbackStats, feedbackStatsError }) => {
  if (loadingFeedbackStats) {
    return (
      <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100 mb-6">
        <p className="text-sm text-gray-500">Loading feedback stats…</p>
      </div>
    );
  }

  if (feedbackStatsError) {
    return (
      <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100 mb-6">
        <p className="text-sm text-red-600">Failed to load feedback stats: {feedbackStatsError}</p>
      </div>
    );
  }

  const totalCount = feedbackStats?.total_feedback_count ?? 0;
  const categories = feedbackStats?.categories ?? {};

  return (
    <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100 mb-6">
      <h3 className="text-2xl font-bold text-gray-900 mb-2 flex items-center gap-3">
        <div className="p-2 bg-gradient-to-br from-[#e8dff2] to-[#d2c5e7] rounded-lg">
          <BarChart3 className="w-6 h-6 text-[#9b7bb5]" />
        </div>
        Feedback Stats
      </h3>
      <p className="text-sm text-gray-600 mb-6">
        Aggregated across every feedback submission on record for this operator ({totalCount} total).
      </p>

      {totalCount === 0 ? (
        <p className="text-sm text-gray-500">No feedback has been submitted for this operator yet.</p>
      ) : (
        <div className="space-y-4">
          {CATEGORY_META.map(({ key, label, concerningValue }) => {
            const stat = categories[key] || { yes: 0, no: 0, unset: 0 };
            const concerning = concerningValue ? stat.yes : stat.no;
            const clear = concerningValue ? stat.no : stat.yes;
            const unset = stat.unset;
            const total = concerning + clear + unset || 1;

            return (
              <div key={key}>
                <div className="flex justify-between items-baseline mb-1">
                  <span className="text-sm font-semibold text-gray-800">{label}</span>
                  <span className="text-xs text-gray-500">
                    {concerning} concerning · {clear} clear · {unset} not evaluated
                  </span>
                </div>
                <div className="w-full h-3 rounded-full overflow-hidden bg-gray-100 flex">
                  {concerning > 0 && (
                    <div
                      className="h-full bg-red-500"
                      style={{ width: `${(concerning / total) * 100}%` }}
                      title={`${concerning} concerning`}
                    />
                  )}
                  {clear > 0 && (
                    <div
                      className="h-full bg-green-500"
                      style={{ width: `${(clear / total) * 100}%` }}
                      title={`${clear} clear`}
                    />
                  )}
                  {unset > 0 && (
                    <div
                      className="h-full bg-gray-300"
                      style={{ width: `${(unset / total) * 100}%` }}
                      title={`${unset} not evaluated`}
                    />
                  )}
                </div>
              </div>
            );
          })}

          <div className="flex gap-4 pt-2 text-xs text-gray-500">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" /> Concerning</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" /> Clear</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-gray-300 inline-block" /> Not evaluated</span>
          </div>
        </div>
      )}
    </div>
  );
};

const OperatorFeedback = ({
  feedback,
  handleSmartFeedback,
  remarks,
  handleRemarksChange,
  documents,
  handleDocumentUpload,
  feedbackHistory,
  submitFeedback,
  setFeedback,
  feedbackStats,
  loadingFeedbackStats,
  feedbackStatsError,
}) => {
  return (
    <div className="space-y-6 animate-fade-in">
      <FeedbackStatsCard
        feedbackStats={feedbackStats}
        loadingFeedbackStats={loadingFeedbackStats}
        feedbackStatsError={feedbackStatsError}
      />

      <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100">
        <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-[#e8dff2] to-[#d2c5e7] rounded-lg">
            <MessageSquare className="w-6 h-6 text-[#9b7bb5]" />
          </div>
          Operator Verification & Feedback
        </h3>
        <p className="text-sm text-gray-600 mb-6">
          Please review and provide feedback on the following verification parameters for this operator.
        </p>

        {/* Feedback History Section */}
        {feedbackHistory.length > 0 && (
          <div className="mb-8 p-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200">
            <h4 className="text-lg font-bold text-blue-900 mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Previous Feedback History
            </h4>
            <div className="space-y-4 max-h-60 overflow-y-auto">
              {feedbackHistory.map((historyItem, index) => (
                <div key={index} className="bg-white p-4 rounded-lg border border-blue-200 shadow-sm">
                  <div className="flex justify-between items-start mb-2">
                    <span className="font-semibold text-gray-900">Feedback #{feedbackHistory.length - index}</span>
                    <span className="text-xs text-gray-500">
                      {new Date(historyItem.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">
                    <strong>Submitted by:</strong> {historyItem.username}
                  </p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {Object.entries(historyItem.feedback).map(([key, value]) => {
                      if (value !== null) {
                        return (
                          <span key={key} className={`px-2 py-1 rounded ${
                            value === true ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                          }`}>
                            {key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}: {value ? 'Yes' : 'No'}
                          </span>
                        );
                      }
                      return null;
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-6">
          {/* 1. Has this operator been verified as fraudulent */}
          <div className="border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow duration-300 bg-gradient-to-r from-white to-gray-50">
            <h4 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center text-red-600 font-bold">1</div>
              Fraudulent Operator Verification
            </h4>
            <p className="text-sm text-gray-600 mb-4">Has this operator been verified as fraudulent?</p>
            <div className="flex gap-3 mb-4">
              <button
                onClick={() => handleSmartFeedback('verifiedFraudOperator', true)}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-300 ${
                  feedback.verifiedFraudOperator === true
                    ? 'bg-red-500 text-white shadow-lg scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-600 border border-gray-300'
                }`}
              >
                <XCircle className="w-5 h-5" />
                Yes - Fraudulent
              </button>
              <button
                onClick={() => handleSmartFeedback('verifiedFraudOperator', false)}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-300 ${
                  feedback.verifiedFraudOperator === false
                    ? 'bg-green-500 text-white shadow-lg scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-green-50 hover:text-green-600 border border-gray-300'
                }`}
              >
                <Check className="w-5 h-5" />
                No - Not Fraudulent
              </button>
            </div>

            {/* Document Upload and Remarks for Fraudulent */}
            {feedback.verifiedFraudOperator === true && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Upload Evidence (PDF - Optional)
                    </label>
                    <input
                      type="file"
                      accept=".pdf"
                      onChange={(e) => handleDocumentUpload('fraudulent', e.target.files[0])}
                      className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-red-50 file:text-red-700 hover:file:bg-red-100"
                    />
                    {documents.fraudulent && (
                      <p className="text-xs text-green-600 mt-1">✓ {documents.fraudulent.name}</p>
                    )}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Remarks (Optional)
                    </label>
                    <textarea
                      value={remarks.fraudulent}
                      onChange={(e) => handleRemarksChange('fraudulent', e.target.value)}
                      rows="3"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-red-500 focus:border-red-500"
                      placeholder="Add any additional remarks..."
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 2. Has the operator been verified as legitimate */}
          <div className="border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow duration-300 bg-gradient-to-r from-white to-gray-50">
            <h4 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center text-green-600 font-bold">2</div>
              Legitimate Operator Verification
            </h4>
            <p className="text-sm text-gray-600 mb-4">Has the operator been verified as legitimate?</p>
            <div className="flex gap-3 mb-4">
              <button
                onClick={() => handleSmartFeedback('verifiedLegitimateOperator', true)}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-300 ${
                  feedback.verifiedLegitimateOperator === true
                    ? 'bg-green-500 text-white shadow-lg scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-green-50 hover:text-green-600 border border-gray-300'
                }`}
              >
                <Check className="w-5 h-5" />
                Yes - Legitimate
              </button>
              <button
                onClick={() => handleSmartFeedback('verifiedLegitimateOperator', false)}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-300 ${
                  feedback.verifiedLegitimateOperator === false
                    ? 'bg-red-500 text-white shadow-lg scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-600 border border-gray-300'
                }`}
              >
                <XCircle className="w-5 h-5" />
                No - Not Verified
              </button>
            </div>

            {/* Remarks for Legitimate */}
            {(feedback.verifiedLegitimateOperator === true || feedback.verifiedLegitimateOperator === false) && (
              <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Remarks (Optional)
                </label>
                <textarea
                  value={remarks.legitimate}
                  onChange={(e) => handleRemarksChange('legitimate', e.target.value)}
                  rows="3"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-green-500 focus:border-green-500"
                  placeholder="Add any additional remarks about legitimacy verification..."
                />
              </div>
            )}
          </div>

          {/* 3. Has the operator worked with a cloned machine */}
          <div className="border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow duration-300 bg-gradient-to-r from-white to-gray-50">
            <h4 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center text-purple-600 font-bold">3</div>
              Machine Cloning Verification
            </h4>
            <p className="text-sm text-gray-600 mb-4">Has the operator worked with a cloned machine?</p>
            <div className="flex gap-3 mb-4">
              <button
                onClick={() => handleSmartFeedback('workedWithClonedMachine', true)}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-300 ${
                  feedback.workedWithClonedMachine === true
                    ? 'bg-red-500 text-white shadow-lg scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-600 border border-gray-300'
                }`}
              >
                <AlertTriangle className="w-5 h-5" />
                Yes - Used Cloned Machine
              </button>
              <button
                onClick={() => handleSmartFeedback('workedWithClonedMachine', false)}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-300 ${
                  feedback.workedWithClonedMachine === false
                    ? 'bg-green-500 text-white shadow-lg scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-green-50 hover:text-green-600 border border-gray-300'
                }`}
              >
                <Check className="w-5 h-5" />
                No - No Cloned Machine
              </button>
            </div>

            {/* Document Upload and Remarks for Cloned Machine */}
            {(feedback.workedWithClonedMachine === true || feedback.workedWithClonedMachine === false) && (
              <div className="mt-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Upload Evidence (PDF - Optional)
                    </label>
                    <input
                      type="file"
                      accept=".pdf"
                      onChange={(e) => handleDocumentUpload('clonedMachine', e.target.files[0])}
                      className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100"
                    />
                    {documents.clonedMachine && (
                      <p className="text-xs text-green-600 mt-1">✓ {documents.clonedMachine.name}</p>
                    )}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Remarks (Optional)
                    </label>
                    <textarea
                      value={remarks.clonedMachine}
                      onChange={(e) => handleRemarksChange('clonedMachine', e.target.value)}
                      rows="3"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-purple-500 focus:border-purple-500"
                      placeholder="Add any additional remarks about machine cloning..."
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 4. Has the operator done unsystematic biometric capture */}
          <div className="border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow duration-300 bg-gradient-to-r from-white to-gray-50">
            <h4 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center text-orange-600 font-bold">4</div>
              Biometric Capture Verification
            </h4>
            <p className="text-sm text-gray-600 mb-4">Has the operator done unsystematic biometric capture?</p>
            <div className="flex gap-3 mb-4">
              <button
                onClick={() => handleSmartFeedback('unsystematicBiometricCapture', true)}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-300 ${
                  feedback.unsystematicBiometricCapture === true
                    ? 'bg-red-500 text-white shadow-lg scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-600 border border-gray-300'
                }`}
              >
                <AlertTriangle className="w-5 h-5" />
                Yes - Unsystematic Capture
              </button>
              <button
                onClick={() => handleSmartFeedback('unsystematicBiometricCapture', false)}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-300 ${
                  feedback.unsystematicBiometricCapture === false
                    ? 'bg-green-500 text-white shadow-lg scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-green-50 hover:text-green-600 border border-gray-300'
                }`}
              >
                <Check className="w-5 h-5" />
                No - Systematic Capture
              </button>
            </div>

            {/* Document Upload and Remarks for Biometric Capture */}
            {(feedback.unsystematicBiometricCapture === true || feedback.unsystematicBiometricCapture === false) && (
              <div className="mt-4 p-4 bg-orange-50 border border-orange-200 rounded-lg">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Upload Evidence (PDF - Optional)
                    </label>
                    <input
                      type="file"
                      accept=".pdf"
                      onChange={(e) => handleDocumentUpload('biometricCapture', e.target.files[0])}
                      className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100"
                    />
                    {documents.biometricCapture && (
                      <p className="text-xs text-green-600 mt-1">✓ {documents.biometricCapture.name}</p>
                    )}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Remarks (Optional)
                    </label>
                    <textarea
                      value={remarks.biometricCapture}
                      onChange={(e) => handleRemarksChange('biometricCapture', e.target.value)}
                      rows="3"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-orange-500 focus:border-orange-500"
                      placeholder="Add any additional remarks about biometric capture..."
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 5. Has any anomaly been identified in the packets */}
          <div className="border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow duration-300 bg-gradient-to-r from-white to-gray-50">
            <h4 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold">5</div>
              Packet Anomaly Verification
            </h4>
            <p className="text-sm text-gray-600 mb-4">Has any anomaly been identified in the packets?</p>
            <div className="flex gap-3 mb-4">
              <button
                onClick={() => handleSmartFeedback('packetAnomalyIdentified', true)}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-300 ${
                  feedback.packetAnomalyIdentified === true
                    ? 'bg-red-500 text-white shadow-lg scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-600 border border-gray-300'
                }`}
              >
                <AlertTriangle className="w-5 h-5" />
                Yes - Anomaly Found
              </button>
              <button
                onClick={() => handleSmartFeedback('packetAnomalyIdentified', false)}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-300 ${
                  feedback.packetAnomalyIdentified === false
                    ? 'bg-green-500 text-white shadow-lg scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-green-50 hover:text-green-600 border border-gray-300'
                }`}
              >
                <Check className="w-5 h-5" />
                No - No Anomaly
              </button>
            </div>

            {/* Document Upload and Remarks for Packet Anomaly */}
            {(feedback.packetAnomalyIdentified === true || feedback.packetAnomalyIdentified === false) && (
              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Upload Evidence (PDF - Optional)
                    </label>
                    <input
                      type="file"
                      accept=".pdf"
                      onChange={(e) => handleDocumentUpload('packetAnomaly', e.target.files[0])}
                      className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                    />
                    {documents.packetAnomaly && (
                      <p className="text-xs text-green-600 mt-1">✓ {documents.packetAnomaly.name}</p>
                    )}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Remarks (Optional)
                    </label>
                    <textarea
                      value={remarks.packetAnomaly}
                      onChange={(e) => handleRemarksChange('packetAnomaly', e.target.value)}
                      rows="3"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Add any additional remarks about packet anomaly..."
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Submit Button */}
        <div className="mt-8 flex justify-end gap-4 border-t pt-6">
          <button
            onClick={() => setFeedback({
              verifiedFraudOperator: null,
              verifiedLegitimateOperator: null,
              workedWithClonedMachine: null,
              unsystematicBiometricCapture: null,
              packetAnomalyIdentified: null
            })}
            className="px-6 py-3 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg font-semibold transition-all duration-300"
          >
            Reset Feedback
          </button>
          <button
            onClick={submitFeedback}
            className="px-8 py-3 bg-gradient-to-r from-[#9b7bb5] to-[#d2c5e7] hover:from-[#7a5f93] hover:to-[#9b7bb5] text-white rounded-lg font-bold transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-105"
          >
            Submit Feedback
          </button>
        </div>
      </div>

      {/* Feedback Summary Card */}
      <div className="bg-gradient-to-br from-[#f5f2f8] to-[#e8dff2] rounded-2xl shadow-lg p-6 border border-[#d2c5e7]">
        <h4 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-[#9b7bb5]" />
          Feedback Summary
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div className="flex justify-between items-center p-3 bg-white rounded-lg">
            <span className="font-medium text-gray-700">Fraudulent:</span>
            <span className={`font-bold ${
              feedback.verifiedFraudOperator === true ? 'text-red-600' :
              feedback.verifiedFraudOperator === false ? 'text-green-600' :
              'text-gray-400'
            }`}>
              {feedback.verifiedFraudOperator === true ? 'Yes' :
               feedback.verifiedFraudOperator === false ? 'No' : 'Not Set'}
            </span>
          </div>
          <div className="flex justify-between items-center p-3 bg-white rounded-lg">
            <span className="font-medium text-gray-700">Legitimate:</span>
            <span className={`font-bold ${
              feedback.verifiedLegitimateOperator === true ? 'text-green-600' :
              feedback.verifiedLegitimateOperator === false ? 'text-red-600' :
              'text-gray-400'
            }`}>
              {feedback.verifiedLegitimateOperator === true ? 'Yes' :
               feedback.verifiedLegitimateOperator === false ? 'No' : 'Not Set'}
            </span>
          </div>
          <div className="flex justify-between items-center p-3 bg-white rounded-lg">
            <span className="font-medium text-gray-700">Cloned Machine:</span>
            <span className={`font-bold ${
              feedback.workedWithClonedMachine === true ? 'text-red-600' :
              feedback.workedWithClonedMachine === false ? 'text-green-600' :
              'text-gray-400'
            }`}>
              {feedback.workedWithClonedMachine === true ? 'Yes' :
               feedback.workedWithClonedMachine === false ? 'No' : 'Not Set'}
            </span>
          </div>
          <div className="flex justify-between items-center p-3 bg-white rounded-lg">
            <span className="font-medium text-gray-700">Unsystematic Biometric:</span>
            <span className={`font-bold ${
              feedback.unsystematicBiometricCapture === true ? 'text-red-600' :
              feedback.unsystematicBiometricCapture === false ? 'text-green-600' :
              'text-gray-400'
            }`}>
              {feedback.unsystematicBiometricCapture === true ? 'Yes' :
               feedback.unsystematicBiometricCapture === false ? 'No' : 'Not Set'}
            </span>
          </div>
          <div className="flex justify-between items-center p-3 bg-white rounded-lg md:col-span-2">
            <span className="font-medium text-gray-700">Packet Anomaly:</span>
            <span className={`font-bold ${
              feedback.packetAnomalyIdentified === true ? 'text-red-600' :
              feedback.packetAnomalyIdentified === false ? 'text-green-600' :
              'text-gray-400'
            }`}>
              {feedback.packetAnomalyIdentified === true ? 'Yes' :
               feedback.packetAnomalyIdentified === false ? 'No' : 'Not Set'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OperatorFeedback;
