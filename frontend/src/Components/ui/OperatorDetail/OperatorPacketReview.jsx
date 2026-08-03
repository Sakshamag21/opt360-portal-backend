import React from 'react';
import { X, AlertTriangle, FileText, User, Activity, Clock, MapPin, Building, Zap, Calendar, Info } from 'lucide-react';

const OperatorPacketReview = ({
  packetData,
  loadingPackets,
  packetError,
  filterDate,
  setFilterDate,
  searchSid,
  setSearchSid,
  filterEnrollmentType,
  setFilterEnrollmentType,
  filterAnomalyType,
  setFilterAnomalyType,
  pageSize,
  handlePageSizeChange,
  currentPage,
  totalRecords,
  totalPages,
  handlePageChange,
  clearFilters,
  searchPackets,
  anomalyData,
  handleMarkAnomaly,
  showAnomalyModal,
  setShowAnomalyModal,
  selectedPacket,
  anomalyRemarks,
  setAnomalyRemarks,
  submitAnomalyReport,
  showAnomalyDetailsModal,
  setShowAnomalyDetailsModal,
  selectedAnomalyDetails,
  setSelectedAnomalyDetails,
  hideFilters = false,
  hideMarkAnomalyButton = false,
}) => {
  return (
    <div className="space-y-6 animate-fade-in" data-section="packet-review">
      <div className="bg-white rounded-2xl p-8 shadow-2xl border-2 border-gray-100 hover:shadow-3xl transition-all duration-500">
        <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-[#e8dff2] to-[#d2c5e7] rounded-lg">
            <FileText className="w-6 h-6 text-[#9b7bb5]" />
          </div>
          Packet Review Dashboard
        </h3>

        {/* Filter Section */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 mb-6 border border-blue-100 shadow-sm">
          {!hideFilters && (
          <>
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.707A1 1 0 013 7V4z"></path>
              </svg>
              Filter Packets
            </h4>
            <button
              onClick={clearFilters}
              className="px-3 py-1 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors duration-200"
            >
              Clear All
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Date</label>
              <input
                type="date"
                value={filterDate}
                onChange={e => setFilterDate(e.target.value)}
                min={new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}
                max={new Date().toISOString().split('T')[0]}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
              />
              <p className="flex items-center gap-1 text-xs text-amber-600">
                <Info className="w-3 h-3 shrink-0" />
                Search is limited to the last 30 days
              </p>
            </div>
{/* 
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Search SID</label>
              <input
                type="text"
                value={searchSid}
                onChange={e => setSearchSid(e.target.value)}
                placeholder="Enter SID to search"
                disabled={!filterDate}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            </div> */}

            {/* <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Enrollment Type</label>
              <select
                value={filterEnrollmentType}
                onChange={e => setFilterEnrollmentType(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
              >
                <option value="">All Types</option>
                <option value="new_enrollment">New Enrollment</option>
                <option value="update">Update</option>
              </select>
            </div> */}

            {/* <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Anomaly Type</label>
              <input
                type="text"
                value={filterAnomalyType}
                onChange={e => setFilterAnomalyType(e.target.value)}
                placeholder="e.g., Work"
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
              />
            </div> */}
          </div>
          </>
          )}

          <div className="mt-4 flex justify-between items-center">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-gray-700">Page Size:</label>
                <select
                  value={pageSize}
                  onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                  className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="10">10</option>
                  <option value="25">25</option>
                  <option value="50">50</option>
                  <option value="100">100</option>
                </select>
              </div>
              <div className="text-sm text-gray-600">
                Showing {Math.min((currentPage - 1) * pageSize + 1, totalRecords)} - {Math.min(currentPage * pageSize, totalRecords)} of {totalRecords} records
              </div>
            </div>
            {!hideFilters && (
              <button
                onClick={searchPackets}
                disabled={!filterDate && !filterEnrollmentType && !filterAnomalyType}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-medium rounded-lg shadow-sm transition-all duration-200 flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                </svg>
                Search Packets
              </button>
            )}
          </div>
        </div>

        {/* Pagination Controls */}
        {!loadingPackets && !packetError && totalRecords > 0 && (
          <div className="bg-white rounded-xl p-4 mb-4 border border-gray-200 flex justify-between items-center">
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1 || loadingPackets}
              className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7"></path>
              </svg>
              Previous
            </button>

            <div className="flex items-center gap-2">
              {[...Array(Math.min(5, totalPages))].map((_, idx) => {
                let pageNum;
                if (totalPages <= 5) {
                  pageNum = idx + 1;
                } else if (currentPage <= 3) {
                  pageNum = idx + 1;
                } else if (currentPage >= totalPages - 2) {
                  pageNum = totalPages - 4 + idx;
                } else {
                  pageNum = currentPage - 2 + idx;
                }

                return (
                  <button
                    key={pageNum}
                    onClick={() => handlePageChange(pageNum)}
                    className={`w-10 h-10 rounded-lg font-medium transition-all duration-200 ${
                      currentPage === pageNum
                        ? 'bg-blue-600 text-white shadow-md'
                        : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              })}
              {totalPages > 5 && currentPage < totalPages - 2 && (
                <>
                  <span className="text-gray-500">...</span>
                  <button
                    onClick={() => handlePageChange(totalPages)}
                    className="w-10 h-10 rounded-lg font-medium bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors duration-200"
                  >
                    {totalPages}
                  </button>
                </>
              )}
            </div>

            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={totalRecords > 0 && currentPage >= totalPages || loadingPackets}
              className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 flex items-center gap-2"
            >
              Next
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
              </svg>
            </button>
          </div>
        )}

        {loadingPackets ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-purple-500 mb-4"></div>
              <p className="text-lg font-semibold text-gray-700">Loading packet data...</p>
            </div>
          </div>
        ) : packetError ? (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
            <p className="text-red-700 font-medium">No SIDs exist for the selected date. Please update search filter</p>
          </div>
        ) : packetData.length > 0 ? (
          <>
            {/* Packet Statistics */}
            {/* Only a true total (from the API's pagination count) is shown here.
                The former "New Enrollments"/"Updates"/"Last 24h" cards computed
                counts from packetData.filter(...).length — the current page only,
                not an operator-wide total — which misrepresented per-page counts
                as totals. Removed rather than shipping a wrong number; a correct
                version needs a backend aggregate endpoint, not a page-scoped filter. */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <div className="bg-gradient-to-r from-blue-50 to-blue-100 rounded-xl p-4 border border-blue-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-blue-600 text-sm font-medium">Total Packets</p>
                    <p className="text-2xl font-bold text-blue-900">{totalRecords}</p>
                  </div>
                  <FileText className="w-8 h-8 text-blue-500" />
                </div>
              </div>
            </div>

            {/* Packet List */}
            <div className="space-y-4">
              <h4 className="text-lg font-semibold text-gray-900 mb-4">Recent Packets</h4>
              <div className="bg-white rounded-2xl shadow-xl border border-gray-200 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                      <tr>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200">
                          Packet EID
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200">
                          Type
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200">
                          Created Date
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200">
                          Station ID
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200">
                          Machine Code
                        </th>
                        {/* <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200">
                          Source
                        </th> */}
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200">
                          Anomaly Type
                        </th>
                        {!hideMarkAnomalyButton && (
                          <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200">
                            Actions
                          </th>
                        )}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                      {packetData
                        .sort((a, b) => new Date(b.pkt_created_ts) - new Date(a.pkt_created_ts))
                        .map((packet, index) => (
                        <tr key={index} className="hover:bg-gradient-to-r hover:from-blue-50 hover:to-purple-50 transition-all duration-300 group">
                          <td className="px-6 py-4 whitespace-nowrap text-sm">
                            <div className="flex items-center gap-2">
                              <div className="font-mono text-blue-600 truncate max-w-[200px]" title={packet.pkt_eid}>
                                {packet.pkt_eid}
                              </div>
                              <div className="relative group/info">
                                <Info className="w-4 h-4 text-gray-400 hover:text-blue-600 cursor-pointer transition-colors" />
                                <div className="absolute left-0 top-6 z-50 hidden group-hover/info:block w-80 bg-white border border-gray-300 rounded-lg shadow-2xl p-4">
                                  <div className="space-y-2 text-xs">
                                    <div className="font-semibold text-gray-900 border-b pb-2 mb-2">Packet EID Details</div>
                                    <div className="flex flex-col gap-1">
                                      <div className="flex justify-between gap-2">
                                        <span className="font-medium text-gray-600">EID:</span>
                                        <span className="text-gray-900 text-right break-all font-mono">
                                          {packet.pkt_eid || packet.Eid || 'N/A'}
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${
                              packet.pkt_type === 'N'
                                ? 'bg-green-100 text-green-800 border border-green-200'
                                : 'bg-orange-100 text-orange-800 border border-orange-200'
                            }`}>
                              <div className={`w-2 h-2 rounded-full mr-2 ${
                                packet.pkt_type === 'N' ? 'bg-green-500' : 'bg-orange-500'
                              }`}></div>
                              {packet.pkt_type === 'N' ? 'New Enrollment' : 'Update'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            <div className="flex items-center">
                              <Calendar className="w-4 h-4 text-gray-400 mr-2" />
                              <div>
                                <div className="font-medium">
                                  {new Date(packet.pkt_created_ts).toLocaleDateString()}
                                </div>
                                <div className="text-xs text-gray-500">
                                  {new Date(packet.pkt_created_ts).toLocaleTimeString()}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center">
                              <MapPin className="w-4 h-4 text-gray-400 mr-2" />
                              <span className="text-sm font-mono text-gray-700 bg-gray-100 px-2 py-1 rounded">
                                {packet.station_no || packet.station_id || packet.pkt_station_id}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <Building className="w-4 h-4 text-gray-400 mr-2" />
                              <span className="text-sm font-mono text-gray-700 bg-gray-100 px-2 py-1 rounded truncate max-w-[300px]" title={packet.station_machine_code || packet.machine_code || packet.pkt_machine_code}>
                                {packet.station_machine_code || packet.machine_code || packet.pkt_machine_code}
                              </span>
                              <div className="relative group/info">
                                <Info className="w-4 h-4 text-gray-400 hover:text-blue-600 cursor-pointer transition-colors" />
                                <div className="absolute left-0 top-6 z-50 hidden group-hover/info:block w-[500px] bg-white border border-gray-300 rounded-lg shadow-2xl p-4">
                                  <div className="space-y-2 text-xs">
                                    <div className="font-semibold text-gray-900 border-b pb-2 mb-2">Machine Code Details</div>
                                    <div className="flex flex-col gap-1">
                                      <div className="flex justify-between gap-2">
                                        <span className="font-medium text-gray-600">Machine Code:</span>
                                        <span className="text-gray-900 text-right break-all font-mono">
                                          {packet.station_machine_code || packet.machine_code || packet.pkt_machine_code || 'N/A'}
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </td>
                          {/* <td className="px-6 py-4 whitespace-nowrap">
                            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 border border-indigo-200">
                              <Zap className="w-3 h-3 mr-1" />
                              {packet.pkt_source}
                            </span>
                          </td> */}
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              {packet.anomaly_category ? (
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
                                  <AlertTriangle className="w-3 h-3 mr-1" />
                                  {packet.anomaly_category}
                                </span>
                              ) : packet.anomaly_type && packet.anomaly_type.length > 0 ? (
                                <div className="flex flex-wrap gap-1">
                                  {packet.anomaly_type.map((anomaly, idx) => (
                                    <span key={idx} className="inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
                                      <AlertTriangle className="w-3 h-3 mr-1" />
                                      {typeof anomaly === 'object' ? anomaly.anomaly_category || anomaly.anomaly_name : anomaly}
                                    </span>
                                  ))}
                                </div>
                              ) : (
                                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800 border border-green-200">
                                  <div className="w-2 h-2 rounded-full bg-green-500 mr-1"></div>
                                  Non-Anomalous
                                </span>
                              )}
                              {packet.anomaly_type && packet.anomaly_type.length > 0 && (
                                <button
                                  onClick={() => {
                                    setSelectedAnomalyDetails(packet.anomaly_type);
                                    setShowAnomalyDetailsModal(true);
                                  }}
                                  className="p-1 rounded-full hover:bg-red-100 transition-colors"
                                  title="View anomaly details"
                                >
                                  <Info className="w-4 h-4 text-gray-400 hover:text-red-600 cursor-pointer transition-colors" />
                                </button>
                              )}
                            </div>
                          </td>
                          {!hideMarkAnomalyButton && (
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="flex items-center space-x-2">
                                {anomalyData[packet.pkt_eid] ? (
                                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
                                    <AlertTriangle className="w-3 h-3 mr-1" />
                                    Anomaly Reported
                                  </span>
                                ) : (
                                  <button
                                    onClick={() => handleMarkAnomaly(packet)}
                                    className="inline-flex items-center px-4 py-2 rounded-lg text-xs font-semibold bg-red-500 text-white hover:bg-red-600 shadow-md hover:shadow-lg transition-all duration-200"
                                  >
                                    <AlertTriangle className="w-3 h-3 mr-1" />
                                    Mark Anomaly
                                  </button>
                                )}
                              </div>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="text-center py-12">
            <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h4 className="text-lg font-semibold text-gray-600 mb-2">No Packet Data Available</h4>
            <p className="text-gray-500">No packet review data found for this operator.</p>
          </div>
        )}
      </div>

      {/* Anomaly Reporting Modal */}
      {showAnomalyModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                <AlertTriangle className="w-6 h-6 text-red-500" />
                Report Packet Anomaly
              </h3>
              <button
                onClick={() => setShowAnomalyModal(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {selectedPacket && (
              <div className="mb-6">
                <div className="bg-gray-50 rounded-lg p-4 mb-4">
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Packet Details:</h4>
                  <div className="space-y-1 text-sm text-gray-600">
                    <div><span className="font-medium">EID:</span> {selectedPacket.pkt_eid}</div>
                    <div><span className="font-medium">Type:</span> {selectedPacket.pkt_type === 'N' ? 'New Enrollment' : 'Update'}</div>
                    <div><span className="font-medium">Created:</span> {new Date(selectedPacket.pkt_created_ts).toLocaleString()}</div>
                    <div><span className="font-medium">Station:</span> {selectedPacket.pkt_station_id}</div>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Anomaly Remarks <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={anomalyRemarks}
                    onChange={(e) => setAnomalyRemarks(e.target.value)}
                    rows="4"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-red-500 focus:border-red-500 resize-none"
                    placeholder="Describe the anomaly you've identified in this packet..."
                  />
                </div>
              </div>
            )}

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowAnomalyModal(false)}
                className="px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={submitAnomalyReport}
                className="px-6 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-semibold"
              >
                Report Anomaly
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Anomaly Details Modal */}
      {showAnomalyDetailsModal && selectedAnomalyDetails && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 max-w-3xl w-full mx-4 shadow-2xl max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                <AlertTriangle className="w-6 h-6 text-red-500" />
                Anomaly Type Details
              </h3>
              <button
                onClick={() => {
                  setShowAnomalyDetailsModal(false);
                  setSelectedAnomalyDetails(null);
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="space-y-4">
              {selectedAnomalyDetails.map((anomaly, idx) => (
                <div key={idx} className="bg-red-50 p-5 rounded-xl border border-red-200">
                  <div className="flex flex-col gap-3">
                    <div className="flex justify-between items-start gap-4">
                      <span className="font-semibold text-gray-700">Category:</span>
                      <span className="text-gray-900 font-bold text-right">{anomaly.anomaly_category || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between items-start gap-4">
                      <span className="font-semibold text-gray-700">Code:</span>
                      <span className="text-gray-900 font-mono text-sm bg-white px-3 py-1 rounded border border-red-300">{anomaly.anomaly_code || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between items-start gap-4">
                      <span className="font-semibold text-gray-700">Name:</span>
                      <span className="text-gray-900 font-medium text-right">{anomaly.anomaly_name || 'N/A'}</span>
                    </div>
                    {anomaly.reason && Object.keys(anomaly.reason).length > 0 && (
                      <div className="mt-3 pt-3 border-t border-red-300">
                        <div className="font-semibold text-gray-700 mb-3">Reason Details:</div>
                        <div className="space-y-2 bg-white rounded-lg p-4 border border-red-200">
                          {Object.entries(anomaly.reason).map(([key, value]) => (
                            <div key={key} className="flex justify-between items-center gap-4 py-2 border-b border-gray-200 last:border-b-0">
                              <span className="text-gray-700 font-medium capitalize">
                                {key.replace(/_/g, ' ')}:
                              </span>
                              <span className={`font-bold px-3 py-1 rounded-full text-sm ${
                                typeof value === 'boolean'
                                  ? value
                                    ? 'bg-red-100 text-red-700 border border-red-300'
                                    : 'bg-green-100 text-green-700 border border-green-300'
                                  : 'bg-gray-100 text-gray-700 border border-gray-300'
                              }`}>
                                {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : value || 'N/A'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end mt-6">
              <button
                onClick={() => {
                  setShowAnomalyDetailsModal(false);
                  setSelectedAnomalyDetails(null);
                }}
                className="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OperatorPacketReview;
