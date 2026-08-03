import React from 'react';
import { Shield, AlertTriangle, CheckCircle } from 'lucide-react';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts';

const OperatorRiskSection = ({
  riskScore,
  riskPercentage,
  riskLevel,
  animatedRiskAngle,
  riskRadarData,
  setSelectedAnomalyCategory,
  setActiveSection,
}) => {
  return (
    <div className="space-y-6 animate-fade-in">
      {riskScore > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Enhanced Risk Meter */}
          <div className="bg-white rounded-2xl p-8 shadow-2xl border-2 border-gray-100 hover:shadow-3xl transition-all duration-500 relative overflow-hidden pulse-glow">
            <div className="absolute top-0 right-0 w-40 h-40 bg-gradient-to-br from-purple-400 to-pink-400 opacity-10 rounded-full blur-3xl"></div>
            <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-3 relative z-10">
              <div className="p-2 bg-indigo-100 rounded-lg">
                <Shield className="w-6 h-6 text-indigo-600" />
              </div>
              Risk Assessment
            </h3>

            {/* Semi-circle meter */}
            <div className="relative w-full h-52 mx-auto mb-4">
              <svg viewBox="0 0 320 180" className="w-full h-full drop-shadow-lg">
                <defs>
                  <linearGradient id="riskGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" style={{ stopColor: '#10b981', stopOpacity: 1 }} />
                    <stop offset="50%" style={{ stopColor: '#f59e0b', stopOpacity: 1 }} />
                    <stop offset="100%" style={{ stopColor: '#ef4444', stopOpacity: 1 }} />
                  </linearGradient>
                  <filter id="glow">
                    <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
                    <feMerge>
                      <feMergeNode in="coloredBlur"/>
                      <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                  </filter>
                </defs>
                <path d="M 40 140 A 120 120 0 0 1 280 140" fill="none" stroke="#e5e7eb" strokeWidth="28" strokeLinecap="round" />
                <path d="M 40 140 A 120 120 0 0 1 280 140" fill="none" stroke="url(#riskGradient)" strokeWidth="28" strokeLinecap="round" opacity="0.3" />
                <path
                  d="M 40 140 A 120 120 0 0 1 280 140"
                  fill="none"
                  stroke={riskLevel.color}
                  strokeWidth="28"
                  strokeLinecap="round"
                  strokeDasharray={`${(animatedRiskAngle / 180) * 377.0} 377.0`}
                  filter="url(#glow)"
                  style={{ transition: 'stroke-dasharray 0.1s ease-out' }}
                />
                <line
                  x1="160"
                  y1="140"
                  x2={160 + Math.cos((Math.PI - (animatedRiskAngle * Math.PI / 180))) * 100}
                  y2={140 - Math.sin((Math.PI - (animatedRiskAngle * Math.PI / 180))) * 100}
                  stroke={riskLevel.color}
                  strokeWidth="6"
                  strokeLinecap="round"
                  style={{ transition: 'all 0.025s ease-out' }}
                />
                <circle cx="160" cy="140" r="8" fill={riskLevel.color} filter="url(#glow)" />
              </svg>
            </div>

            <div className="text-center relative z-10">
              <div className="text-5xl font-extrabold mb-3 drop-shadow" style={{ color: riskLevel.color }}>
                {riskPercentage.toFixed(1)}%
              </div>
              <div className="inline-block px-6 py-3 rounded-full font-bold text-base shadow-lg" style={{ backgroundColor: riskLevel.bgColor, color: riskLevel.color }}>
                {riskLevel.level}
              </div>
            </div>
          </div>

          {/* Risk Radar Chart */}
          <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100 hover:shadow-2xl transition-shadow duration-300">
            <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-3">
              <div className="p-2 bg-red-100 rounded-lg">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              Risk Analysis Radar
            </h3>
            <ResponsiveContainer width="100%" height={400}>
              <RadarChart
                data={riskRadarData.length > 0 && riskRadarData.some(d => d.score > 0) ? riskRadarData : [
                  { metric: 'Hardware Security', score: 30, fullMark: 100 },
                  { metric: 'Work Pattern', score: 25, fullMark: 100 },
                  { metric: 'Document Quality', score: 40, fullMark: 100 },
                  { metric: 'Biometrics Error', score: 20, fullMark: 100 },
                  { metric: 'Suspicious Txn', score: 35, fullMark: 100 },
                  { metric: 'Authentication Risk', score: 28, fullMark: 100 }
                ]}
              >
                <PolarGrid stroke="#e5e7eb" strokeWidth={2} />
                <PolarAngleAxis
                  dataKey="metric"
                  tick={(props) => {
                    const { payload, x, y, cx, cy } = props;
                    const categoryName = payload.value;

                    // Calculate position relative to center
                    const angle = Math.atan2(y - cy, x - cx);
                    const distance = 15;
                    const adjustedX = x + Math.cos(angle) * distance;
                    const adjustedY = y + Math.sin(angle) * distance;

                    return (
                      <g>
                        <foreignObject
                          x={adjustedX - 60}
                          y={adjustedY - 15}
                          width={120}
                          height={30}
                          style={{ overflow: 'visible' }}
                        >
                          <div
                            onClick={() => {
                              const metricToCategoryMap = {
                                'hardware': 'hardware',
                                'hardware security': 'hardware',
                                'work': 'work',
                                'work pattern': 'work',
                                'document': 'document',
                                'document quality': 'document',
                                'biometric': 'biometrics',
                                'biometrics': 'biometrics',
                                'biometrics error': 'biometrics',
                                'suspicious': 'suspicious',
                                'suspicious txn': 'suspicious',
                                'authentication': 'authentication',
                                'authentication risk': 'authentication',
                              };

                              const categoryNameLower = categoryName.toLowerCase();
                              // Try exact match first, then try matching the first word of the label
                              const mappedCategory = metricToCategoryMap[categoryNameLower]
                                || metricToCategoryMap[categoryNameLower.split(' ')[0]]
                                || categoryNameLower;

                              setSelectedAnomalyCategory(mappedCategory);
                              setActiveSection('anomalies');

                              setTimeout(() => {
                                window.scrollTo({ top: 0, behavior: 'smooth' });
                              }, 100);
                            }}
                            style={{
                              cursor: 'pointer',
                              padding: '6px 12px',
                              backgroundColor: '#ffffff',
                              color: '#374151',
                              borderRadius: '8px',
                              fontSize: '12px',
                              fontWeight: '600',
                              textAlign: 'center',
                              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.15)',
                              transition: 'all 0.2s ease',
                              border: '2px solid #e5e7eb',
                              whiteSpace: 'nowrap',
                              display: 'inline-block'
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = '#3b82f6';
                              e.currentTarget.style.color = '#ffffff';
                              e.currentTarget.style.borderColor = '#2563eb';
                              e.currentTarget.style.transform = 'scale(1.05)';
                              e.currentTarget.style.boxShadow = '0 4px 12px rgba(59, 130, 246, 0.4)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = '#ffffff';
                              e.currentTarget.style.color = '#374151';
                              e.currentTarget.style.borderColor = '#e5e7eb';
                              e.currentTarget.style.transform = 'scale(1)';
                              e.currentTarget.style.boxShadow = '0 2px 6px rgba(0, 0, 0, 0.15)';
                            }}
                          >
                            {categoryName}
                          </div>
                        </foreignObject>
                      </g>
                    );
                  }}
                />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 13 }} />
                <Radar name="Risk Score" dataKey="score" stroke="#ef4444" fill="#ef4444" fillOpacity={0.6} strokeWidth={3} />
                <Tooltip contentStyle={{ backgroundColor: '#fff', border: '2px solid #ef4444', borderRadius: '12px', padding: '12px' }} formatter={(value) => [`${value.toFixed(1)}%`, 'Risk Score']} />
              </RadarChart>
            </ResponsiveContainer>
            <div className="text-center text-sm text-gray-600 mt-4 bg-red-50 p-3 rounded-lg border border-red-200">
              ⚠️ Higher scores indicate higher risk levels
            </div>
          </div>
        </div>
      )}

      {/* Show message when risk score is 0 */}
      {riskScore === 0 && (
        <div className="bg-gradient-to-br from-green-50 to-blue-50 rounded-2xl p-8 text-center border-2 border-green-200 animate-fade-in">
          <CheckCircle className="w-16 h-16 mx-auto mb-4 text-green-500" />
          <h3 className="text-2xl font-bold text-gray-900 mb-2">No Risk Analysis Available</h3>
          <p className="text-gray-600">This operator has a risk score of 0 and requires no risk analysis at this time.</p>
        </div>
      )}
    </div>
  );
};

export default OperatorRiskSection;
