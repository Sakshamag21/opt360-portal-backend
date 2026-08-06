import React from 'react';
import { User, MapPin, Mail, Phone, TrendingUp, Clock, AlertCircle, Zap, UserX, Package } from 'lucide-react';
import { getRiskBucketStyle } from '../../../utils/colorHelpers';

const OperatorDetailsSection = ({ apiOperatorData, loadingApiData }) => {
  const riskStyle = getRiskBucketStyle(apiOperatorData?.risk_bucket);

  return (
    <div className="space-y-6 animate-fade-in">
      {apiOperatorData && Object.keys(apiOperatorData).length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Operator Information Card */}
          <div className="bg-gradient-to-br from-indigo-50 to-white rounded-2xl p-6 shadow-xl border-2 border-indigo-100 hover:shadow-2xl transition-all duration-300">
            <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-3 border-b border-indigo-200 pb-4">
              <div className="p-2 bg-indigo-500 rounded-lg">
                <User className="w-5 h-5 text-white" />
              </div>
              Operator Information
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between items-start p-3 bg-white rounded-lg hover:bg-indigo-50 transition">
                <span className="text-gray-600 font-medium">Operator ID</span>
                <span className="font-bold text-gray-900 font-mono text-right text-sm">{apiOperatorData.id}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-white rounded-lg hover:bg-indigo-50 transition">
                <span className="text-gray-600 font-medium">Name</span>
                <span className="font-bold text-gray-900 text-right">{apiOperatorData.name}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-white rounded-lg hover:bg-indigo-50 transition">
                <span className="text-gray-600 font-medium">Status</span>
                <div className="flex items-center gap-2">
                  {apiOperatorData.dissociation_date && (
                    <span className="px-3 py-1 rounded-full text-xs font-bold bg-red-100 text-red-700 border-2 border-red-300">
                      ● Dissociated
                    </span>
                  )}
                  <span className={`px-3 py-1 rounded-full text-xs font-bold ${apiOperatorData.status === 'active' ? 'bg-green-100 text-green-700 border-2 border-green-300' : 'bg-red-100 text-red-700 border-2 border-red-300'}`}>
                    {apiOperatorData.status === 'active' ? '● Active' : '● Inactive'}
                  </span>
                </div>
              </div>
              <div className="flex justify-between items-start p-3 bg-white rounded-lg hover:bg-indigo-50 transition">
                <div className="flex items-center gap-2 text-gray-600">
                  <Mail className="w-4 h-4" />
                  <span className="font-medium">Email</span>
                </div>
                <span className="font-bold text-gray-900 text-sm text-right max-w-[60%] break-all">
                  {apiOperatorData.email || 'Not provided'}
                </span>
              </div>
              <div className="flex justify-between items-start p-3 bg-white rounded-lg hover:bg-indigo-50 transition">
                <div className="flex items-center gap-2 text-gray-600">
                  <Phone className="w-4 h-4" />
                  <span className="font-medium">Mobile</span>
                </div>
                <span className="font-bold text-gray-900 text-right">
                  {apiOperatorData.phone || 'Not provided'}
                </span>
              </div>
              <div className="flex justify-between items-start p-3 bg-white rounded-lg hover:bg-indigo-50 transition">
                <div className="flex items-center gap-2 text-gray-600">
                  <Clock className="w-4 h-4" />
                  <span className="font-medium">Last Sync</span>
                </div>
                <span className="font-bold text-gray-900 text-sm text-right">
                  {apiOperatorData.last_sync_timestamp ? new Date(apiOperatorData.last_sync_timestamp).toLocaleString() : 'N/A'}
                </span>
              </div>
              <div className="flex justify-between items-start p-3 bg-white rounded-lg hover:bg-indigo-50 transition">
                <div className="flex items-center gap-2 text-gray-600">
                  <Package className="w-4 h-4" />
                  <span className="font-medium">Last Packet Date</span>
                </div>
                <span className="font-bold text-gray-900 text-sm text-right">
                  {apiOperatorData.last_packet_date ? new Date(apiOperatorData.last_packet_date).toLocaleString() : 'N/A'}
                </span>
              </div>
            </div>
          </div>

          {/* Location & Organization Card */}
          <div className="bg-gradient-to-br from-green-50 to-white rounded-2xl p-6 shadow-xl border-2 border-green-100 hover:shadow-2xl transition-all duration-300">
            <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-3 border-b border-green-200 pb-4">
              <div className="p-2 bg-green-500 rounded-lg">
                <MapPin className="w-5 h-5 text-white" />
              </div>
              Location & Organization
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center p-3 bg-white rounded-lg hover:bg-green-50 transition">
                <span className="text-gray-600 font-medium">State</span>
                <span className="font-bold text-gray-900 text-right">{apiOperatorData.state}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-white rounded-lg hover:bg-green-50 transition">
                <span className="text-gray-600 font-medium">District</span>
                <span className="font-bold text-gray-900 text-right">{apiOperatorData.district}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-white rounded-lg hover:bg-green-50 transition">
                <span className="text-gray-600 font-medium">Regional Office</span>
                <span className="font-bold text-gray-900 text-right">{apiOperatorData.ro}</span>
              </div>
              <div className="flex justify-between items-start p-3 bg-white rounded-lg hover:bg-green-50 transition">
                <span className="text-gray-600 font-medium">Registrar</span>
                <span className="font-bold text-gray-900 text-right max-w-[60%] break-words">{apiOperatorData.reg}</span>
              </div>
              <div className="flex justify-between items-start p-3 bg-white rounded-lg hover:bg-green-50 transition">
                <span className="text-gray-600 font-medium">Enrolling Agency</span>
                <span className="font-bold text-gray-900 text-sm text-right max-w-[60%] break-words">{apiOperatorData.ea}</span>
              </div>
            </div>
          </div>

          {/* Performance & Risk Card */}
          <div className="bg-gradient-to-br from-purple-50 to-white rounded-2xl p-6 shadow-xl border-2 border-purple-100 hover:shadow-2xl transition-all duration-300">
            <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-3 border-b border-purple-200 pb-4">
              <div className="p-2 bg-purple-500 rounded-lg">
                <TrendingUp className="w-5 h-5 text-white" />
              </div>
              Risk
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between items-start p-3 bg-white rounded-lg hover:bg-purple-50 transition">
                <span className="text-gray-600 font-medium">Risk Score</span>
                <div className="text-right">
                  <span
                    className="px-4 py-2 rounded-full text-lg font-extrabold shadow-md"
                    style={{ backgroundColor: riskStyle.bgColor, color: riskStyle.color }}
                  >
                    {((apiOperatorData.risk_score || 0) * 100).toFixed(1)}%
                  </span>
                  <p className="text-xs text-gray-500 mt-1">{riskStyle.level}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Machine Details Card */}
          {apiOperatorData.machine_code && (
            <div className="bg-gradient-to-br from-orange-50 to-white rounded-2xl p-6 shadow-xl border-2 border-orange-100 hover:shadow-2xl transition-all duration-300">
              <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-3 border-b border-orange-200 pb-4">
                <div className="p-2 bg-orange-500 rounded-lg">
                  <Zap className="w-5 h-5 text-white" />
                </div>
                Machine Details
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between items-start p-3 bg-white rounded-lg hover:bg-orange-50 transition">
                  <span className="text-gray-600 font-medium">Machine Code</span>
                  <span className="font-bold text-gray-900 font-mono text-xs text-right max-w-[65%] break-all">
                    {apiOperatorData.machine_code}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Dissociation Card */}
          {apiOperatorData.dissociation_date && (
            <div className="bg-gradient-to-br from-red-50 to-white rounded-2xl p-6 shadow-xl border-2 border-red-200 hover:shadow-2xl transition-all duration-300">
              <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-3 border-b border-red-200 pb-4">
                <div className="p-2 bg-red-500 rounded-lg">
                  <UserX className="w-5 h-5 text-white" />
                </div>
                Dissociation
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center p-3 bg-white rounded-lg hover:bg-red-50 transition">
                  <span className="text-gray-600 font-medium">Dissociation Date</span>
                  <span className="font-bold text-red-700 text-right">
                    {new Date(apiOperatorData.dissociation_date).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex justify-between items-start p-3 bg-white rounded-lg hover:bg-red-50 transition">
                  <span className="text-gray-600 font-medium">Reason</span>
                  <span className="font-bold text-gray-900 text-sm text-right max-w-[60%] break-words">
                    {apiOperatorData.dissociation_reason || 'Not specified'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : loadingApiData ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading operator details...</p>
        </div>
      ) : (
        <div className="text-center py-12 bg-gradient-to-br from-gray-50 to-white rounded-xl border-2 border-gray-200">
          <AlertCircle className="w-20 h-20 mx-auto mb-4 text-gray-400" />
          <p className="text-xl font-bold text-gray-900 mb-2">No details available</p>
          <p className="text-sm text-gray-600">Unable to fetch operator details from the API</p>
        </div>
      )}
    </div>
  );
};

export default OperatorDetailsSection;
