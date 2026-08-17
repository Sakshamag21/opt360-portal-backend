import React, { useState, useEffect } from 'react';
import { X, MapPin, Mail, User, Building, Calendar, TrendingUp, AlertTriangle, CheckCircle, Activity, Clock, Zap, ArrowLeft, Shield, Award, Target, MessageSquare, Check, XCircle, FileText, Phone, Info, AlertCircle, Download } from 'lucide-react';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts';
import * as XLSX from 'xlsx';
import FeatureGraph from './FeatureGraph';

import sampleUser from '../resources/sampleUser.json';
import { API_BASE_URL, getAuthHeaders } from '../config/apiConfig';
import { getRiskBucketStyle } from '../utils/colorHelpers';
import OperatorDetailsSection from './ui/OperatorDetail/OperatorDetailsSection';
import OperatorKPISection from './ui/OperatorDetail/OperatorKPISection';
import OperatorRiskSection from './ui/OperatorDetail/OperatorRiskSection';
import OperatorAnomaliesSection from './ui/OperatorDetail/OperatorAnomaliesSection';
import OperatorPacketReview from './ui/OperatorDetail/OperatorPacketReview';
import OperatorFeedback from './ui/OperatorDetail/OperatorFeedback';

// ClickHouse's `comments` field is itself a JSON-encoded object (e.g.
// '{"error_category":"DE","field":"dob"}') — parse it so the reason modal
// can render real key/value rows instead of dumping the raw JSON string as
// a single value. Falls back to a single "comments" entry for plain text.
const parseCommentsAsReason = (comments) => {
  if (!comments) return null;
  if (typeof comments === 'object') return comments;
  try {
    const parsed = JSON.parse(comments);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed;
  } catch (e) {
    // Not JSON — fall through to plain-text handling below.
  }
  return { comments };
};

// ClickHouse's anomalous-packet read path only returns a flat
// anomaly_category string plus a free-text comments field — no anomaly_type
// array with per-item reason breakdowns. Without this, the "view reason"
// icon (gated on anomaly_type.length > 0) never renders for those packets.
// Synthesize a single-entry anomaly_type array from the flat fields so the
// existing reason-details modal has something to show.
const buildAnomalyType = (packet) => {
  const existing = packet.anomaly_type || packet.Anomaly_type;
  if (existing && existing.length > 0) return existing;
  const category = packet.anomaly_category || packet.Anomaly_category;
  const comments = packet.comments || packet.Comments;
  if (!category && !comments) return [];
  const reason = parseCommentsAsReason(comments);
  return [{
    anomaly_category: category,
    ...(reason ? { reason } : {})
  }];
};

const OperatorDetailView = ({ operator, onBack, getSeverityColor, getCategoryColor }) => {
  const [isLoaded, setIsLoaded] = useState(false);
  const [activeSection, setActiveSection] = useState('details');
  const [apiOperatorData, setApiOperatorData] = useState(null);
  const [loadingApiData, setLoadingApiData] = useState(true);
  const [apiError, setApiError] = useState(null);
  const [riskDetailsData, setRiskDetailsData] = useState(null);
  const [loadingRiskData, setLoadingRiskData] = useState(true);
  const [selectedAnomalyCategory, setSelectedAnomalyCategory] = useState(null);
  const [animatedRiskAngle, setAnimatedRiskAngle] = useState(0);
  const [kpiData, setKpiData] = useState(null);
  const [loadingKpiData, setLoadingKpiData] = useState(true);
  const [kpiError, setKpiError] = useState(null);
  
  const kpis = Array.isArray(kpiData?.kpis) ? kpiData.kpis : [];

  // Feedback state
  const [feedback, setFeedback] = useState({
    verifiedFraudOperator: null, // true/false
    verifiedLegitimateOperator: null, // true/false
    workedWithClonedMachine: null, // true/false
    unsystematicBiometricCapture: null, // true/false
    packetAnomalyIdentified: null // true/false
  });

  // Document upload and remarks state
  const [documents, setDocuments] = useState({
    fraudulent: null,
    clonedMachine: null,
    biometricCapture: null,
    packetAnomaly: null
  });

  const [remarks, setRemarks] = useState({
    fraudulent: '',
    legitimate: '',
    clonedMachine: '',
    biometricCapture: '',
    packetAnomaly: ''
  });

  // Feedback history state
  const [feedbackHistory, setFeedbackHistory] = useState([]);

  // Feedback stats (ClickHouse-backed aggregate across every past submission)
  const [feedbackStats, setFeedbackStats] = useState(null);
  const [loadingFeedbackStats, setLoadingFeedbackStats] = useState(true);
  const [feedbackStatsError, setFeedbackStatsError] = useState(null);
  
  // Packet review data state
  const [packetData, setPacketData] = useState([]);
  const [loadingPackets, setLoadingPackets] = useState(false);
  const [packetError, setPacketError] = useState(null);
  const [anomalyData, setAnomalyData] = useState({});
  const [showAnomalyModal, setShowAnomalyModal] = useState(false);
  const [selectedPacket, setSelectedPacket] = useState(null);
  const [anomalyRemarks, setAnomalyRemarks] = useState('');
  const [showAnomalyDetailsModal, setShowAnomalyDetailsModal] = useState(false);
  const [selectedAnomalyDetails, setSelectedAnomalyDetails] = useState(null);
  const [featureRemarksModal, setFeatureRemarksModal] = useState({ open: false, feature: null });
  const [featureGraphModal, setFeatureGraphModal] = useState({ open: false, feature: null });
  
  // Packet filter states
  const [filterDate, setFilterDate] = useState('');
  // When set (and different from filterDate), searchPackets sends
  // start_date/end_date instead of a single date — see fetchPacketsWithFilters.
  const [filterEndDate, setFilterEndDate] = useState('');
  const [filterEnrollmentType, setFilterEnrollmentType] = useState('');
  const [filterPacketSource, setFilterPacketSource] = useState('');
  const [filterAnomalyType, setFilterAnomalyType] = useState('');
  const [filterStationNo, setFilterStationNo] = useState('');
  const [searchSid, setSearchSid] = useState('');
  const [filterAnomalyCategory, setFilterAnomalyCategory] = useState('');
  
  // Pagination states
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalRecords, setTotalRecords] = useState(0);

  // Anomalous Packets tab state (replaces the old Anomalies tab)
  const [anomalousPacketsData, setAnomalousPacketsData] = useState([]);
  const [loadingAnomalousPackets, setLoadingAnomalousPackets] = useState(false);
  const [anomalousPacketsError, setAnomalousPacketsError] = useState(null);
  const [anomalousCurrentPage, setAnomalousCurrentPage] = useState(1);
  const [anomalousPageSize, setAnomalousPageSize] = useState(50);
  const [anomalousTotalRecords, setAnomalousTotalRecords] = useState(0);
  const [anomalyGroupOptions, setAnomalyGroupOptions] = useState([]);
  const [loadingAnomalyGroups, setLoadingAnomalyGroups] = useState(false);
  const [filterAnomalyGroup, setFilterAnomalyGroup] = useState('');
  const [downloadingAnomalousPackets, setDownloadingAnomalousPackets] = useState(false);

  useEffect(() => {
    setTimeout(() => setIsLoaded(true), 50);
    window.scrollTo(0, 0);
    loadOperatorDetails();
    loadOperatorRiskDetails();
    loadOperatorFeatures();
    loadFeedbackHistory();
    loadFeedbackStats();
  }, []);

  // Load operator details from API
  const loadOperatorDetails = async () => {
    try {
      setLoadingApiData(true);
      setApiError(null);

      // /operator_details resolves the S3 path via opt_master.data_path looked up
      // by opt_id alone — opt_state/opt_district are no longer accepted.
      const params = new URLSearchParams({
        opt_id: operator.opt_id || operator.Opt_id || ''
      });

      const url = `${API_BASE_URL}/api/operator_details?${params.toString()}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const responseData = await response.json();
      
      // Handle different response structures
      let operatorData;
      if (responseData.data) {
        // Check if data is an array or object
        if (Array.isArray(responseData.data)) {
          operatorData = responseData.data.length > 0 ? responseData.data[0] : null;
        } else {
          // data is an object
          operatorData = responseData.data;
        }
      } else {
        // Response itself is the data
        operatorData = responseData;
      }
      
      setApiOperatorData(operatorData);
    } catch (err) {
      console.error('Error loading operator details:', err);
      setApiError(err.message);
      // Use the passed operator data as fallback
      setApiOperatorData(null);
    } finally {
      setLoadingApiData(false);
    }
  };

  // Load operator risk details from API
  const loadOperatorRiskDetails = async () => {
    try {
      setLoadingRiskData(true);

      // /operator_risk_details resolves the S3 path via opt_master.data_path looked up
      // by opt_id alone — opt_state/opt_district are no longer accepted.
      const params = new URLSearchParams({
        opt_id: operator.opt_id || operator.Opt_id || ''
      });

      const url = `${API_BASE_URL}/api/operator_risk_details?${params.toString()}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const responseData = await response.json();
      
      // Extract data
      const riskData = responseData.data || responseData;
      setRiskDetailsData(riskData);
    } catch (err) {
      console.error('Error loading operator risk details:', err);
      setRiskDetailsData(null);
    } finally {
      setLoadingRiskData(false);
    }
  };

  // Load operator features (KPIs) from API
  const loadOperatorFeatures = async () => {
    try {
      setLoadingKpiData(true);
      setKpiError(null);

      // /operator_features resolves the S3 path via opt_master.data_path looked up
      // by opt_id alone — opt_state/opt_district are no longer accepted.
      const params = new URLSearchParams({
        opt_id: operator.opt_id || operator.Opt_id || ''
      });

      const url = `${API_BASE_URL}/api/operator_features?${params.toString()}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      // /operator_features returns the transformed object unwrapped — it is NOT
      // nested under a `data` key.
      const featuresData = await response.json();
      setKpiData(featuresData);
    } catch (err) {
      console.error('Error loading operator features:', err);
      setKpiError(err.message);
      setKpiData(null);
    } finally {
      setLoadingKpiData(false);
    }
  };

  // Load existing feedback history
  const loadFeedbackHistory = () => {
    try {
      const existingFeedback = localStorage.getItem(`feedback_${operator.opt_id || operator.operator_id}`);
      if (existingFeedback) {
        const parsedFeedback = JSON.parse(existingFeedback);
        setFeedbackHistory(Array.isArray(parsedFeedback) ? parsedFeedback : [parsedFeedback]);
      }
    } catch (error) {
      console.error('Error loading feedback history:', error);
    }
  };

  // Load feedback stats + full submission history from ClickHouse (every
  // feedback ever submitted for this operator, not just what's cached in
  // this browser's localStorage).
  const loadFeedbackStats = async () => {
    try {
      setLoadingFeedbackStats(true);
      setFeedbackStatsError(null);

      const params = new URLSearchParams({
        opt_id: operator.opt_id || operator.Opt_id || ''
      });

      const url = `${API_BASE_URL}/api/operator_feedback_stats?${params.toString()}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const statsData = await response.json();
      setFeedbackStats(statsData);
    } catch (err) {
      console.error('Error loading feedback stats:', err);
      setFeedbackStatsError(err.message);
      setFeedbackStats(null);
    } finally {
      setLoadingFeedbackStats(false);
    }
  };

  // Load packet data from API
  const loadPacketData = async () => {
    try {
      setLoadingPackets(true);
      setPacketError(null);

      // /anamolous_sids resolves the S3 path via opt_master.data_path looked up
      // by opt_id alone — opt_state/opt_district are no longer accepted.
      const params = new URLSearchParams({
        opt_id: mergedOperator.opt_id || mergedOperator.Opt_id || '',
        page: currentPage.toString(),
        page_size: pageSize.toString()
      });

      // Add anomaly category filter if set
      if (filterAnomalyCategory) {
        params.append('anomaly_category', filterAnomalyCategory);
      }

      const url = `${API_BASE_URL}/api/anamolous_sids?${params.toString()}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const responseData = await response.json();
      
      // Extract data array and pagination info from response
      const packets = responseData.data || [];
      const pagination = responseData.pagination || {};
      const total = pagination.total_records || packets.length;
      setTotalRecords(total);
      
      // Map API field names to component field names
      const mappedPackets = packets.map(packet => {
        return {
          ...packet,
          pkt_eid: packet.sid || packet.eid || packet.pkt_eid || packet.Eid,
          pkt_type: packet.enrolment_type || packet.enrolnment_type || packet.Enrolnment_type || packet.pkt_type,
          pkt_subtype: packet.pkt_subtype,
          pkt_source: packet.pkt_source || packet.Pkt_source,
          pkt_updt_type: packet.pkt_updt_type || packet.Pkt_updt_type || [],
          anomaly_type: buildAnomalyType(packet),
          anomaly_category: packet.anomaly_category || packet.Anomaly_category,
          pkt_created_ts: packet.date_created || packet.Date_created || packet.created_date ?
            (packet.date_created || packet.created_date || (packet.Date_created ? new Date(packet.Date_created / 1000000).toISOString() : null)) :
            packet.pkt_created_ts,
          enrolment_type: packet.enrolment_type || packet.enrolnment_type || packet.Enrolnment_type,
          station_id: packet.station_no || packet.Station_no || packet.station_id,
          station_no: packet.station_no || packet.Station_no || packet.station_id,
          machine_code: packet.station_machine_code || packet.Station_machine_code || packet.machine_code,
          station_machine_code: packet.station_machine_code || packet.Station_machine_code || packet.machine_code,
          packet_type: packet.packet_type,
          date: packet.date,
          opt_id: packet.opt_id || packet.Opt_id || packet.operator_id
        };
      });
      
      setPacketData(mappedPackets);
    } catch (err) {
      console.error('Error loading packet data:', err);
      setPacketError(err.message);
      setPacketData([]);
    } finally {
      setLoadingPackets(false);
    }
  };

  // Search packets with filters — always resets to page 1
  const searchPackets = async () => {
    setCurrentPage(1);
    await fetchPacketsWithFilters(1, pageSize);
  };

  // Single source of truth for all packet fetches — preserves filters across pagination and page-size changes
  const fetchPacketsWithFilters = async (page, size, filters = {}) => {
    try {
      setLoadingPackets(true);
      setPacketError(null);

      const date           = 'date'           in filters ? filters.date           : filterDate;
      const endDate        = 'endDate'        in filters ? filters.endDate        : filterEndDate;
      const sid            = 'sid'            in filters ? filters.sid            : searchSid;
      const enrollType     = 'enrollType'     in filters ? filters.enrollType     : filterEnrollmentType;
      const pktSource      = 'pktSource'      in filters ? filters.pktSource      : filterPacketSource;
      const anomalyType    = 'anomalyType'    in filters ? filters.anomalyType    : filterAnomalyType;
      const stationNo      = 'stationNo'      in filters ? filters.stationNo      : filterStationNo;

      // /search_operator_packets resolves the S3 path via opt_master.data_path looked up
      // by opt_id alone — opt_state/opt_district are no longer accepted.
      const params = new URLSearchParams({
        opt_id:       mergedOperator.opt_id   || mergedOperator.Opt_id   || '',
        page:         page.toString(),
        page_size:    size.toString(),
      });
      // A real range (end date given and different from start) sends
      // start_date/end_date; otherwise stick to the single 'date' param so
      // single-day searches keep hitting the backend's fast single-date path.
      if (endDate && endDate !== date) {
        params.append('start_date', date);
        params.append('end_date',   endDate);
      } else if (date) {
        params.append('date', date);
      }
      if (sid)         params.append('sid',             sid);
      if (enrollType)  params.append('enrollment_type', enrollType);
      if (pktSource)   params.append('pkt_source',      pktSource.replace(/ /g, '_'));
      if (anomalyType) params.append('anomaly_filter',  anomalyType);
      if (stationNo)   params.append('station_no',      stationNo);

      const response = await fetch(`${API_BASE_URL}/api/search_operator_packets?${params.toString()}`, {
        method: 'GET', headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error(`API error: ${response.status}`);

      const responseData = await response.json();
      const packets = responseData.data || [];
      const pagination = responseData.pagination || {};
      setTotalRecords(pagination.total_records || packets.length);
      setCurrentPage(page);

      setPacketData(packets.map(packet => ({
        ...packet,
        pkt_eid:              packet.sid || packet.eid || packet.Eid || packet.pkt_eid,
        pkt_type:             packet.enrollment_type || packet.enrolment_type || packet.enrolnment_type || packet.Enrolnment_type || packet.pkt_type,
        pkt_subtype:          packet.pkt_subtype,
        pkt_source:           packet.pkt_source || packet.Pkt_source,
        pkt_updt_type:        packet.pkt_updt_type || packet.Pkt_updt_type || [],
        anomaly_type:         buildAnomalyType(packet),
        anomaly_category:     packet.anomaly_category || packet.Anomaly_category,
        pkt_created_ts:       packet.date_created || packet.Date_created || packet.created_date || packet.date || packet.pkt_created_ts,
        enrolment_type:       packet.enrollment_type || packet.enrolment_type || packet.enrolnment_type || packet.Enrolnment_type,
        station_id:           packet.station_no || packet.Station_no || packet.station_id,
        station_no:           packet.station_no || packet.Station_no || packet.station_id,
        machine_code:         packet.station_machine_code || packet.Station_machine_code || packet.machine_code,
        station_machine_code: packet.station_machine_code || packet.Station_machine_code || packet.machine_code,
        packet_type:          packet.packet_type,
        date:                 packet.date,
        opt_id:               packet.opt_id || packet.Opt_id || packet.operator_id,
      })));
    } catch (err) {
      console.error('Error fetching packets:', err);
      setPacketError(err.message);
      setPacketData([]);
    } finally {
      setLoadingPackets(false);
    }
  };

  // Default load: yesterday's date, no other filters
  const loadDefaultPackets = async (date) => {
    setFilterDate(date || '');
    await fetchPacketsWithFilters(1, pageSize, {
      date, sid: '', enrollType: '', pktSource: '', anomalyType: '', stationNo: ''
    });
  };

  // Clear filters back to the default date view
  const clearFilters = () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const dateStr = yesterday.toISOString().split('T')[0];
    setFilterDate(dateStr);
    setFilterEndDate('');
    setFilterEnrollmentType('');
    setFilterPacketSource('');
    setFilterAnomalyType('');
    setFilterStationNo('');
    setSearchSid('');
    setFilterAnomalyCategory('');
    setCurrentPage(1);
    fetchPacketsWithFilters(1, pageSize, {
      date: dateStr, sid: '', enrollType: '', pktSource: '', anomalyType: '', stationNo: ''
    });
  };

  // Handle showing SIDs by anomaly category
  const handleShowSidsByCategory = async (categoryName) => {
    try {
      // Set the anomaly category filter
      setFilterAnomalyCategory(categoryName.toLowerCase());
      
      // Clear other filters
      setFilterDate('');
      setFilterEndDate('');
      setFilterEnrollmentType('');
      setFilterPacketSource('');
      setFilterAnomalyType('');
      setFilterStationNo('');
      setSearchSid('');
      setCurrentPage(1);
      
      // Switch to enrollment review section
      setActiveSection('enrollmentReview');
      
      // Load packet data with category filter
      await loadPacketDataByCategory(categoryName.toLowerCase());
      
      // Scroll to packet review section
      setTimeout(() => {
        const element = document.querySelector('[data-section="packet-review"]');
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
    } catch (error) {
      console.error('Error loading SIDs by category:', error);
    }
  };

  // Load packet data by anomaly category
  const loadPacketDataByCategory = async (category) => {
    try {
      setLoadingPackets(true);
      setPacketError(null);

      // /anamolous_sids resolves the S3 path via opt_master.data_path looked up
      // by opt_id alone — opt_state/opt_district are no longer accepted.
      const params = new URLSearchParams({
        opt_id: mergedOperator.opt_id || mergedOperator.Opt_id || '',
        anomaly_category: category,
        page: '1',
        page_size: pageSize.toString()
      });

      const url = `${API_BASE_URL}/api/anamolous_sids?${params.toString()}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const responseData = await response.json();
      
      const packets = responseData.data || [];
      const pagination = responseData.pagination || {};
      const total = pagination.total_records || packets.length;
      
      setTotalRecords(total);
      setCurrentPage(1);

      const mappedPackets = packets.map(packet => ({
        ...packet,
        pkt_eid: packet.sid || packet.eid || packet.Eid || packet.pkt_eid,
        pkt_type: packet.enrolment_type || packet.enrollment_type || packet.enrolment_type || packet.enrolnment_type || packet.Enrolnment_type || packet.pkt_type,
        pkt_subtype: packet.pkt_subtype,
        pkt_source: packet.pkt_source || packet.Pkt_source,
        pkt_updt_type: packet.pkt_updt_type || packet.Pkt_updt_type || [],
        anomaly_type: buildAnomalyType(packet),
        anomaly_category: packet.anomaly_category || packet.Anomaly_category,
        pkt_created_ts: packet.date_created || packet.Date_created || packet.created_date || packet.date || packet.pkt_created_ts,
        enrolment_type: packet.enrolment_type || packet.enrollment_type || packet.enrolment_type || packet.enrolnment_type || packet.Enrolnment_type,
        station_id: packet.station_no || packet.Station_no || packet.station_id,
        station_no: packet.station_no || packet.Station_no || packet.station_id,
        machine_code: packet.station_machine_code || packet.Station_machine_code || packet.machine_code,
        station_machine_code: packet.station_machine_code || packet.Station_machine_code || packet.machine_code,
        packet_type: packet.packet_type,
        date: packet.date,
        opt_id: packet.opt_id || packet.Opt_id || packet.operator_id
      }));
      
      setPacketData(mappedPackets);
    } catch (err) {
      console.error('Error loading packet data by category:', err);
      setPacketError(err.message);
      setPacketData([]);
    } finally {
      setLoadingPackets(false);
    }
  };

  // Load anomalous packets for the operator (no anomaly_category filter — i.e.
  // every category) for the "Anomalous Packets" tab, which replaces the old
  // Anomalies tab. Optionally scoped by feature_group via filterAnomalyGroup.
  const loadAnomalousPackets = async (page = 1, size = anomalousPageSize, group = filterAnomalyGroup) => {
    try {
      setLoadingAnomalousPackets(true);
      setAnomalousPacketsError(null);

      // /anamolous_sids resolves the S3 path via opt_master.data_path looked up
      // by opt_id alone — opt_state/opt_district are no longer accepted.
      // anomaly_category is intentionally omitted (null) to fetch every category.
      const params = new URLSearchParams({
        opt_id: mergedOperator.opt_id || mergedOperator.Opt_id || '',
        page: page.toString(),
        page_size: size.toString()
      });
      if (group) params.append('feature_group', group);

      const url = `${API_BASE_URL}/api/anamolous_sids?${params.toString()}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const responseData = await response.json();

      const packets = responseData.data || [];
      const pagination = responseData.pagination || {};
      const total = pagination.total_records || packets.length;

      setAnomalousTotalRecords(total);
      setAnomalousCurrentPage(page);
      setAnomalousPageSize(size);

      const mappedPackets = packets.map(packet => ({
        ...packet,
        pkt_eid: packet.sid || packet.eid || packet.Eid || packet.pkt_eid,
        pkt_type: packet.enrolment_type || packet.enrollment_type || packet.enrolnment_type || packet.Enrolnment_type || packet.pkt_type,
        pkt_subtype: packet.pkt_subtype,
        pkt_source: packet.pkt_source || packet.Pkt_source,
        pkt_updt_type: packet.pkt_updt_type || packet.Pkt_updt_type || [],
        anomaly_type: buildAnomalyType(packet),
        anomaly_category: packet.anomaly_category || packet.Anomaly_category,
        pkt_created_ts: packet.date_created || packet.Date_created || packet.created_date || packet.date || packet.pkt_created_ts,
        enrolment_type: packet.enrolment_type || packet.enrollment_type || packet.enrolnment_type || packet.Enrolnment_type,
        station_id: packet.station_no || packet.Station_no || packet.station_id,
        station_no: packet.station_no || packet.Station_no || packet.station_id,
        machine_code: packet.station_machine_code || packet.Station_machine_code || packet.machine_code,
        station_machine_code: packet.station_machine_code || packet.Station_machine_code || packet.machine_code,
        packet_type: packet.packet_type,
        date: packet.date,
        opt_id: packet.opt_id || packet.Opt_id || packet.operator_id
      }));

      setAnomalousPacketsData(mappedPackets);
    } catch (err) {
      console.error('Error loading anomalous packets:', err);
      setAnomalousPacketsError(err.message);
      setAnomalousPacketsData([]);
    } finally {
      setLoadingAnomalousPackets(false);
    }
  };

  const handleAnomalousPageChange = (newPage) => loadAnomalousPackets(newPage, anomalousPageSize);
  const handleAnomalousPageSizeChange = (newSize) => loadAnomalousPackets(1, newSize);
  const anomalousTotalPages = Math.max(1, Math.ceil(anomalousTotalRecords / anomalousPageSize));

  // Load the distinct feature_group values behind this operator's anomalous
  // packets, to populate the Anomalous Packets tab's group filter dropdown.
  const loadAnomalyGroups = async () => {
    try {
      setLoadingAnomalyGroups(true);
      const params = new URLSearchParams({
        opt_id: mergedOperator.opt_id || mergedOperator.Opt_id || ''
      });
      const url = `${API_BASE_URL}/api/anomaly_groups?${params.toString()}`;
      const response = await fetch(url, { method: 'GET', headers: getAuthHeaders() });
      if (!response.ok) throw new Error(`API error: ${response.status}`);
      const data = await response.json();
      setAnomalyGroupOptions(data.anomaly_groups || []);
    } catch (err) {
      console.error('Error loading anomaly groups:', err);
      setAnomalyGroupOptions([]);
    } finally {
      setLoadingAnomalyGroups(false);
    }
  };

  // Anomaly group filter changed — reset to page 1 and refetch with the new group
  const handleAnomalyGroupChange = (group) => {
    setFilterAnomalyGroup(group);
    loadAnomalousPackets(1, anomalousPageSize, group);
  };

  // Download the anomalous packets for this operator (respecting the current
  // feature_group filter, ignoring on-screen pagination) as an .xlsx file.
  // Capped at ANOMALOUS_EXPORT_CAP EIDs (most recent first, per the API's
  // created_date DESC ordering) so the export stays a single request.
  const ANOMALOUS_EXPORT_CAP = 100;
  const downloadAnomalousPacketsExcel = async () => {
    const optId = mergedOperator.opt_id || mergedOperator.Opt_id || '';
    if (!optId) return;

    try {
      setDownloadingAnomalousPackets(true);

      const params = new URLSearchParams({
        opt_id: optId,
        page: '1',
        page_size: ANOMALOUS_EXPORT_CAP.toString()
      });
      if (filterAnomalyGroup) params.append('feature_group', filterAnomalyGroup);

      const response = await fetch(`${API_BASE_URL}/api/anamolous_sids?${params.toString()}`, {
        method: 'GET',
        headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error(`API error: ${response.status} ${response.statusText}`);
      const responseData = await response.json();

      const allPackets = responseData.data || [];
      const totalRecords = responseData.pagination?.total_records ?? allPackets.length;

      if (allPackets.length === 0) {
        alert('No anomalous packets to export.');
        return;
      }

      const rows = allPackets.map(packet => {
        const anomalyType = buildAnomalyType(packet);
        const anomalyLabels = Array.isArray(anomalyType)
          ? anomalyType.map(a => (typeof a === 'object' ? (a.anomaly_category || a.anomaly_name) : a)).join(', ')
          : '';
        return {
          'Packet EID': packet.sid || packet.eid || packet.Eid || packet.pkt_eid || '',
          'Type': (packet.enrolment_type || packet.enrollment_type || packet.pkt_type) === 'N' ? 'New Enrollment' : 'Update',
          'Created Date': packet.date_created || packet.Date_created || packet.created_date || packet.date || '',
          'Station ID': packet.station_no || packet.Station_no || packet.station_id || '',
          'Machine Code': packet.station_machine_code || packet.Station_machine_code || packet.machine_code || '',
          'Anomaly Category': packet.anomaly_category || packet.Anomaly_category || '',
          'Anomaly Type': anomalyLabels,
          'Feature Group': packet.feature_group || packet.Feature_group || '',
          'Comments': packet.comments || packet.Comments || ''
        };
      });

      const worksheet = XLSX.utils.json_to_sheet(rows);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Anomalous Packets');

      const groupSuffix = filterAnomalyGroup ? `_${filterAnomalyGroup}` : '';
      const dateStr = new Date().toISOString().split('T')[0];
      XLSX.writeFile(workbook, `anomalous_packets_${optId}${groupSuffix}_${dateStr}.xlsx`);

      if (totalRecords > allPackets.length) {
        alert(`This operator has ${totalRecords} anomalous packets. Only the ${allPackets.length} most recent were exported (export cap: ${ANOMALOUS_EXPORT_CAP}).`);
      }
    } catch (err) {
      console.error('Error downloading anomalous packets:', err);
      alert('Failed to download anomalous packets. Please try again.');
    } finally {
      setDownloadingAnomalousPackets(false);
    }
  };
  

  // Pagination handlers — preserve all current filters, just change page/size
  const handlePageChange = (newPage) => fetchPacketsWithFilters(newPage, pageSize);

  const handlePageSizeChange = (newSize) => {
    setPageSize(newSize);
    fetchPacketsWithFilters(1, newSize);
  };
  
  // Calculate total pages
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  
  // Debug logging for pagination

  // Helper function to calculate days since last sync
  const calculateDaysSince = (syncTime) => {
    if (!syncTime) return 'N/A';
    try {
      const now = new Date();
      const sync = new Date(syncTime);
      const diffTime = Math.abs(now - sync);
      const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
      return diffDays;
    } catch (error) {
      return 'N/A';
    }
  };

  // Merge API data (now opt_master-sourced, lowercase field names — see
  // handlers/OperatorDetailView/operatorDetails.go's OperatorDetailsData) with
  // the passed operator data. pkt_per_day and the 5 per-category anomaly
  // scores are gone — opt_master has no column for either.
  const mergedOperator = apiOperatorData ? {
    ...operator,
    ...apiOperatorData,
    opt_id: apiOperatorData.id || operator.opt_id,
    opt_name: apiOperatorData.name || operator.opt_name,
    state: apiOperatorData.state || operator.state,
    district: apiOperatorData.district || operator.district,
    opt_ro: apiOperatorData.ro || operator.opt_ro,
    opt_ea: apiOperatorData.ea || operator.opt_ea,
    opt_reg: apiOperatorData.reg || operator.opt_reg,
    active_status: apiOperatorData.status || operator.active_status,
    last_sync_time: apiOperatorData.last_sync_timestamp || operator.last_sync_time,
    risk_score: apiOperatorData.risk_score ?? operator.risk_score,
    risk_bucket: apiOperatorData.risk_bucket || operator.risk_bucket,
  } : operator;

  // Helper function to format sync duration
  const formatSyncDuration = (seconds) => {
    if (!seconds || seconds === 0) return 'N/A';
    const numSeconds = parseInt(seconds);
    if (isNaN(numSeconds)) return 'N/A';
    if (numSeconds < 60) return `${numSeconds} sec`;
    if (numSeconds < 3600) return `${Math.round(numSeconds / 60)} min`;
    if (numSeconds < 86400) return `${Math.round(numSeconds / 3600)} hr`;
    return `${Math.round(numSeconds / 86400)} days`;
  };

  // Smart feedback handler with logical validation
  const handleSmartFeedback = (key, value) => {
    setFeedback(prev => {
      const newFeedback = { ...prev, [key]: value };
      
      // Smart validation logic
      if (key === 'verifiedFraudOperator' && value === true) {
        // If marked as fraudulent, cannot be legitimate
        newFeedback.verifiedLegitimateOperator = false;
      } else if (key === 'verifiedLegitimateOperator' && value === true) {
        // If marked as legitimate, cannot be fraudulent
        newFeedback.verifiedFraudOperator = false;
      }
      
      return newFeedback;
    });
  };

  // Handle document upload
  const handleDocumentUpload = (category, file) => {
    if (file && file.type === 'application/pdf') {
      setDocuments(prev => ({ ...prev, [category]: file }));
    } else {
      alert('Please upload only PDF files.');
    }
  };

  // Handle remarks change
  const handleRemarksChange = (category, value) => {
    setRemarks(prev => ({ ...prev, [category]: value }));
  };

  // Submit feedback with JSON creation
  const submitFeedback = async () => {
    try {
      // Get user profile from sessionStorage
      const userProfileStr = sessionStorage.getItem('user_profile');
      let adId = sampleUser.adId; // Default fallback
      let username = sampleUser.username; // Default fallback
      
      if (userProfileStr) {
        const userProfile = JSON.parse(userProfileStr);
        adId = userProfile.ad_id || userProfile.sub || sampleUser.adId;
        username = userProfile.username || adId;
      }

      // Prepare feedback data matching API structure
      const feedbackPayload = {
        opt_state: mergedOperator.state || apiOperatorData?.State || operator.state || '',
        opt_district: mergedOperator.district || apiOperatorData?.District || operator.district || '',
        opt_id: mergedOperator.opt_id || apiOperatorData?.Opt_id || operator.opt_id || operator.operator_id || '',
        submitted_by: username,
        timestamp: new Date().toISOString(),
        operator_name: mergedOperator.opt_name || apiOperatorData?.Opt_name || operator.opt_name || operator.name || '',
        ad_id: adId,
        feedback: {
          verified_fraud_operator: {
            verdict: feedback.verifiedFraudOperator,
            remarks: remarks.fraudulent || ''
          },
          verified_legitimate_operator: {
            verdict: feedback.verifiedLegitimateOperator,
            remarks: remarks.legitimate || ''
          },
          worked_with_cloned_machine: {
            verdict: feedback.workedWithClonedMachine,
            remarks: remarks.clonedMachine || ''
          },
          unsystematic_biometric_capture: {
            verdict: feedback.unsystematicBiometricCapture,
            remarks: remarks.biometricCapture || ''
          },
          packet_anomaly_identified: {
            verdict: feedback.packetAnomalyIdentified,
            remarks: remarks.packetAnomaly || ''
          }
        }
      };


      const accessToken = sessionStorage.getItem('access_token');

      // Evidence files (documents state) are sent as multipart, each under
      // an "evidence_<category>" field, alongside the feedback JSON as a
      // "feedback" field — the backend uploads each to S3 and includes
      // every path in the feedback record + Kafka event.
      const evidenceEntries = Object.entries(documents).filter(([, file]) => file);
      let fetchOptions;
      if (evidenceEntries.length > 0) {
        const formData = new FormData();
        formData.append('feedback', JSON.stringify(feedbackPayload));
        evidenceEntries.forEach(([category, file]) => {
          formData.append(`evidence_${category}`, file);
        });
        fetchOptions = {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${accessToken}` },
          body: formData
        };
      } else {
        fetchOptions = {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
          },
          body: JSON.stringify(feedbackPayload)
        };
      }

      // Send POST request to feedback API
      const response = await fetch(`${API_BASE_URL}/api/feedback`, fetchOptions);

      if (!response.ok) {
        throw new Error(`Failed to submit feedback: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      
      alert('Feedback submitted successfully!');
      
      // Reset form
      setFeedback({
        verifiedFraudOperator: null,
        verifiedLegitimateOperator: null,
        workedWithClonedMachine: null,
        unsystematicBiometricCapture: null,
        packetAnomalyIdentified: null
      });
      setRemarks({
        fraudulent: '',
        legitimate: '',
        clonedMachine: '',
        biometricCapture: '',
        packetAnomaly: ''
      });
      setDocuments({
        fraudulent: null,
        clonedMachine: null,
        biometricCapture: null,
        packetAnomaly: null
      });
      
      // Reload feedback history + stats
      loadFeedbackHistory();
      loadFeedbackStats();
    } catch (error) {
      console.error('Error submitting feedback:', error);
      alert('Error submitting feedback. Please try again.');
    }
  };

  // Handle anomaly marking
  const handleMarkAnomaly = (packet) => {
    setSelectedPacket(packet);
    setAnomalyRemarks('');
    setShowAnomalyModal(true);
  };

  const submitAnomalyReport = async () => {
    if (!anomalyRemarks.trim()) {
      alert('Please provide remarks before submitting the anomaly report.');
      return;
    }

    // Prepare anomaly data in the required format for database
    const anomalyPayload = {
      anomaly_category: selectedPacket.anomaly_category || "Document",
      anomaly_type: selectedPacket.anomaly_type || [
        {
          anomaly_category: selectedPacket.anomaly_category || "Document",
          anomaly_code: "document_qc_error",
          anomaly_name: "QC Error",
          reason: {
            error_category: "DE"
          }
        }
      ],
      date_created: selectedPacket.pkt_created_ts || selectedPacket.date_created || new Date().toISOString().replace('T', ' ').substring(0, 19),
      eid: selectedPacket.pkt_eid || selectedPacket.eid || selectedPacket.sid,
      enrolnment_type: selectedPacket.pkt_type || selectedPacket.enrolment_type || selectedPacket.enrolnment_type || "U",
      operator_id: operator.opt_id || operator.operator_id || selectedPacket.opt_id,
      opt_id: operator.opt_id || operator.operator_id || selectedPacket.opt_id,
      pkt_source: selectedPacket.pkt_source || "ECMP",
      pkt_updt_type: selectedPacket.pkt_updt_type || [],
      remarks: anomalyRemarks.trim() ? [anomalyRemarks.trim()] : [],
      sid: selectedPacket.pkt_eid || selectedPacket.sid || selectedPacket.eid,
      station_machine_code: selectedPacket.station_machine_code || selectedPacket.machine_code || "",
      station_no: selectedPacket.station_no || selectedPacket.station_id || ""
    };

    // Console log the JSON payload

    try {
      // Send anomaly to database via API endpoint
      await sendAnomalyToDatabase(anomalyPayload);

      // Store anomaly data locally (existing functionality)
      const anomalyReport = {
        packetId: selectedPacket.pkt_eid,
        operatorId: operator.opt_id || operator.operator_id,
        remarks: anomalyRemarks,
        reportedBy: 'Current User', // Replace with actual user
        reportedAt: new Date().toISOString(),
        packetDetails: selectedPacket,
        databasePayload: anomalyPayload
      };

      // Store anomaly data
      const newAnomalyData = {
        ...anomalyData,
        [selectedPacket.pkt_eid]: anomalyReport
      };
      setAnomalyData(newAnomalyData);

      // Save to localStorage
      localStorage.setItem(`anomalies_${operator.opt_id || operator.operator_id}`, JSON.stringify(newAnomalyData));

      alert('Anomaly reported successfully!');
      
      setShowAnomalyModal(false);
      setSelectedPacket(null);
      setAnomalyRemarks('');
    } catch (error) {
      console.error('Failed to report anomaly:', error);
      alert(`Failed to report anomaly: ${error.message}. Please try again.`);
    }
  };

  // Function to send anomaly data to database (ready to use when endpoint is available)
  const sendAnomalyToDatabase = async (payload) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/report_anomaly`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`Failed to report anomaly: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error sending anomaly to database:', error);
      throw error;
    }
  };


  // Risk radar chart: category-level breakdown, still S3-backed
  // (risk_details.json) — opt_master has no per-category columns, only the
  // overall risk_score/risk_bucket. No fallback data when the S3 file is
  // missing; showing fabricated zero-value categories would be misleading.
  const riskRadarData = riskDetailsData?.risk_metrics?.anomaly_category_score
    ? riskDetailsData.risk_metrics.anomaly_category_score.map(category => ({
        metric: category.category_name.charAt(0).toUpperCase() + category.category_name.slice(1),
        score: Math.max(0, Math.min(100, (category.category_score || 0) * 100)),
        fullMark: 100
      }))
    : [];

  // Risk score and risk level: opt_master only (risk_score / risk_bucket),
  // never risk_details.json and never a locally-invented percentage
  // threshold — risk_bucket is the single source of truth for severity.
  const riskScore = parseFloat(mergedOperator.risk_score) || 0;

  // Risk meter calculation
  const riskPercentage = riskScore * 100;
  const riskAngle = (riskPercentage / 100) * 180;

  const riskLevel = getRiskBucketStyle(mergedOperator.risk_bucket);

  // Animate risk meter needle when performance section is active
  useEffect(() => {
    if (activeSection === 'performance') {
      setAnimatedRiskAngle(0);
      const targetAngle = (riskScore * 100 / 100) * 180;
      const duration = 1500; // 1.5 seconds
      const steps = 60;
      const increment = targetAngle / steps;
      let currentStep = 0;

      const animationInterval = setInterval(() => {
        currentStep++;
        if (currentStep <= steps) {
          setAnimatedRiskAngle(increment * currentStep);
        } else {
          setAnimatedRiskAngle(targetAngle);
          clearInterval(animationInterval);
        }
      }, duration / steps);

      return () => clearInterval(animationInterval);
    }
  }, [activeSection, riskScore]);

  // Show loading indicator while API data is being fetched
  if (loadingApiData) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-purple-500 mb-4"></div>
          <p className="text-xl font-semibold text-gray-700">Loading operator details...</p>
          {apiError && (
            <p className="text-sm text-red-600 mt-2">Using cached data: {apiError}</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 transition-opacity duration-700 ${isLoaded ? 'opacity-100' : 'opacity-0'}`}>
      <style jsx>{`
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fade-in 0.6s ease-out forwards;
        }
        @keyframes pulse-glow {
          0%, 100% { box-shadow: 0 0 20px rgba(139, 92, 246, 0.3); }
          50% { box-shadow: 0 0 40px rgba(139, 92, 246, 0.6); }
        }
        .pulse-glow {
          animation: pulse-glow 3s ease-in-out infinite;
        }
      `}</style>

      <div className="max-w-[1920px] mx-auto">
      
        <div className="bg-gradient-to-r from-[#d2c5e7] via-[#e3d9f0] to-white text-gray-800 shadow-2xl backdrop-blur-sm">
          <div className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center gap-4 mb-4">
                  <button 
                    onClick={onBack}
                    className="group bg-white/80 hover:bg-white rounded-xl px-5 py-2.5 transition-all duration-300 flex items-center gap-2 hover:scale-105 hover:shadow-lg border border-[#d2c5e7]"
                  >
                    <ArrowLeft className="w-5 h-5 group-hover:-translate-x-1 transition-transform text-[#9b7bb5]" />
                    <span className="font-semibold text-[#9b7bb5]">Back to List</span>
                  </button>
            
                </div>
                <div className="space-y-3">
                  <h1 className="text-3xl font-semibold tracking-tight drop-shadow-lg animate-fade-in text-gray-800">
                    {mergedOperator.opt_name}
                  </h1>
                  <div className="flex flex-wrap items-center gap-4 text-sm backdrop-blur-sm bg-white/60 rounded-xl px-5 py-3 w-fit border border-[#d2c5e7] text-gray-700">
                    <span className="flex items-center gap-2">
                      <User className="w-4 h-4" />
                      <span className="font-mono font-semibold">{mergedOperator.opt_uid || mergedOperator.opt_id}</span>
                    </span>
                    <span className="text-[#d2c5e7]">|</span>
                    <span className="flex items-center gap-2">
                      <Building className="w-4 h-4" />
                      <span>{mergedOperator.optEa || mergedOperator.opt_ea || 'N/A'}</span>
                    </span>
                    <span className="text-[#d2c5e7]">|</span>
                    <span className="flex items-center gap-2">
                      <MapPin className="w-4 h-4" />
                      <span>{mergedOperator.district || 'Unknown'}, {mergedOperator.state || 'Unknown'}</span>
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-2 mt-6 border-t border-[#d2c5e7] border-opacity-60 pt-4 flex-wrap">
              {[
                { id: 'details', label: 'Details', icon: User },
                { id: 'kpi', label: 'KPI', icon: Shield },
                { id: 'performance', label: 'Risk Analysis', icon: TrendingUp },
                // Hidden for now — keeping for future re-enable.
                // { id: 'anomalies', label: 'Anomalies', icon: AlertTriangle },
                { id: 'anomalousPackets', label: 'Anomalous Packets', icon: AlertTriangle },
                { id: 'enrollmentReview', label: `Packet Review`, icon: FileText },
                { id: 'feedback', label: 'Feedback', icon: MessageSquare }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveSection(tab.id);
                    if (tab.id === 'enrollmentReview' && packetData.length === 0) {
                      const yesterday = new Date();
                      yesterday.setDate(yesterday.getDate() - 1);
                      const dateStr = yesterday.toISOString().split('T')[0];
                      setFilterDate(dateStr);
                      loadDefaultPackets(dateStr);
                    }
                    if (tab.id === 'anomalousPackets' && anomalousPacketsData.length === 0) {
                      loadAnomalousPackets(1, anomalousPageSize);
                      loadAnomalyGroups();
                    }
                  }}
                  className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold transition-all duration-300 ${
                    activeSection === tab.id 
                      ? 'bg-white text-[#9b7bb5] shadow-lg scale-105 border-2 border-[#d2c5e7]' 
                      : 'bg-[#e8dff2] hover:bg-[#d2c5e7] text-[#9b7bb5] hover:scale-102 border border-[#d2c5e7]'
                  }`}
                >
                  <tab.icon className="w-5 h-5" />
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Performance Section */}
          {activeSection === 'performance' && (
            <OperatorRiskSection
              riskScore={riskScore}
              riskPercentage={riskPercentage}
              riskLevel={riskLevel}
              animatedRiskAngle={animatedRiskAngle}
              riskRadarData={riskRadarData}
              setSelectedAnomalyCategory={setSelectedAnomalyCategory}
              setActiveSection={setActiveSection}
            />
          )}

              {/* KPIs for Overview */}
              {activeSection === 'kpi' && (
                <OperatorKPISection
                  loadingKpiData={loadingKpiData}
                  kpiError={kpiError}
                  kpis={kpis}
                  featureRemarksModal={featureRemarksModal}
                  setFeatureRemarksModal={setFeatureRemarksModal}
                  featureGraphModal={featureGraphModal}
                  setFeatureGraphModal={setFeatureGraphModal}
                />
              )}



          {/* Details Section */}
          {activeSection === 'details' && (
            <OperatorDetailsSection
              apiOperatorData={apiOperatorData}
              loadingApiData={loadingApiData}
            />
          )}

          {/* Anomalies Section — hidden for now — keeping for future re-enable.
          {activeSection === 'anomalies' && (
            <OperatorAnomaliesSection
              riskDetailsData={riskDetailsData}
              loadingRiskData={loadingRiskData}
              selectedAnomalyCategory={selectedAnomalyCategory}
              setSelectedAnomalyCategory={setSelectedAnomalyCategory}
              handleShowSidsByCategory={handleShowSidsByCategory}
            />
          )}
          */}

          {/* Anomalous Packets Section — replaces the Anomalies tab.
              Calls /api/anamolous_sids with no anomaly_category (i.e. every category)
              and renders it with the same structure as Packet Review, minus the
              Mark Anomaly action. Its own group filter (feature_group, via
              /api/anomaly_groups) is rendered here rather than inside
              OperatorPacketReview, since that component's built-in filter bar
              is date/sid-oriented and used by the unrelated Packet Review tab. */}
          {activeSection === 'anomalousPackets' && (
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 mb-6 border border-blue-100 shadow-sm flex items-center gap-4 flex-wrap justify-between">
              <div className="flex items-center gap-4 flex-wrap">
                <label className="text-sm font-medium text-gray-700">Anomaly Group:</label>
                <select
                  value={filterAnomalyGroup}
                  onChange={(e) => handleAnomalyGroupChange(e.target.value)}
                  disabled={loadingAnomalyGroups}
                  className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 disabled:opacity-50 min-w-[220px]"
                >
                  <option value="">All Groups</option>
                  {anomalyGroupOptions.map(group => (
                    <option key={group} value={group}>{group}</option>
                  ))}
                </select>
                {loadingAnomalyGroups && <span className="text-xs text-gray-500">Loading groups...</span>}
              </div>
              <button
                onClick={downloadAnomalousPacketsExcel}
                disabled={downloadingAnomalousPackets || anomalousTotalRecords === 0}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg shadow-sm transition-all duration-200 flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                {downloadingAnomalousPackets ? 'Preparing...' : 'Download Excel'}
              </button>
            </div>
          )}
          {activeSection === 'anomalousPackets' && (
            <OperatorPacketReview
              packetData={anomalousPacketsData}
              loadingPackets={loadingAnomalousPackets}
              packetError={anomalousPacketsError}
              hideFilters
              hideMarkAnomalyButton
              pageSize={anomalousPageSize}
              handlePageSizeChange={handleAnomalousPageSizeChange}
              currentPage={anomalousCurrentPage}
              totalRecords={anomalousTotalRecords}
              totalPages={anomalousTotalPages}
              handlePageChange={handleAnomalousPageChange}
              clearFilters={() => {}}
              searchPackets={() => {}}
              anomalyData={anomalyData}
              handleMarkAnomaly={handleMarkAnomaly}
              showAnomalyModal={showAnomalyModal}
              setShowAnomalyModal={setShowAnomalyModal}
              selectedPacket={selectedPacket}
              anomalyRemarks={anomalyRemarks}
              setAnomalyRemarks={setAnomalyRemarks}
              submitAnomalyReport={submitAnomalyReport}
              showAnomalyDetailsModal={showAnomalyDetailsModal}
              setShowAnomalyDetailsModal={setShowAnomalyDetailsModal}
              selectedAnomalyDetails={selectedAnomalyDetails}
              setSelectedAnomalyDetails={setSelectedAnomalyDetails}
            />
          )}

          {/* Enrollment Review Section */}
          {activeSection === 'enrollmentReview' && (
            <OperatorPacketReview
              packetData={packetData}
              loadingPackets={loadingPackets}
              packetError={packetError}
              filterDate={filterDate}
              setFilterDate={setFilterDate}
              filterEndDate={filterEndDate}
              setFilterEndDate={setFilterEndDate}
              searchSid={searchSid}
              setSearchSid={setSearchSid}
              filterEnrollmentType={filterEnrollmentType}
              setFilterEnrollmentType={setFilterEnrollmentType}
              filterAnomalyType={filterAnomalyType}
              setFilterAnomalyType={setFilterAnomalyType}
              pageSize={pageSize}
              handlePageSizeChange={handlePageSizeChange}
              currentPage={currentPage}
              totalRecords={totalRecords}
              totalPages={totalPages}
              handlePageChange={handlePageChange}
              clearFilters={clearFilters}
              searchPackets={searchPackets}
              anomalyData={anomalyData}
              handleMarkAnomaly={handleMarkAnomaly}
              showAnomalyModal={showAnomalyModal}
              setShowAnomalyModal={setShowAnomalyModal}
              selectedPacket={selectedPacket}
              anomalyRemarks={anomalyRemarks}
              setAnomalyRemarks={setAnomalyRemarks}
              submitAnomalyReport={submitAnomalyReport}
              showAnomalyDetailsModal={showAnomalyDetailsModal}
              setShowAnomalyDetailsModal={setShowAnomalyDetailsModal}
              selectedAnomalyDetails={selectedAnomalyDetails}
              setSelectedAnomalyDetails={setSelectedAnomalyDetails}
            />
          )}

          {/* Feedback Section */}
          {activeSection === 'feedback' && (
            <OperatorFeedback
              feedback={feedback}
              handleSmartFeedback={handleSmartFeedback}
              remarks={remarks}
              handleRemarksChange={handleRemarksChange}
              documents={documents}
              handleDocumentUpload={handleDocumentUpload}
              feedbackHistory={feedbackHistory}
              submitFeedback={submitFeedback}
              setFeedback={setFeedback}
              feedbackStats={feedbackStats}
              loadingFeedbackStats={loadingFeedbackStats}
              feedbackStatsError={feedbackStatsError}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default OperatorDetailView;
