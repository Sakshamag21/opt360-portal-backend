import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Loader, CheckCircle, XCircle, AlertCircle, ExternalLink } from 'lucide-react';
import PageNavigation from './PageNavigation';
import PageWrapper from './ui/PageWrapper';
import { API_BASE_URL, getAuthHeaders } from '../config/apiConfig';
import dummyData from '../resources/sidSearchDummy.json';
import operatorsDummy from '../resources/operatorsDummy.json';

const IS_DEV = process.env.REACT_APP_ENV === 'dev';

const Field = ({ label, value }) => (
  <div>
    <p className="text-xs text-gray-500 mb-0.5">{label}</p>
    <p className="text-sm font-medium text-gray-800 break-all">
      {value !== null && value !== undefined && value !== '' ? String(value) : <span className="text-gray-400">—</span>}
    </p>
  </div>
);

const Section = ({ title, children }) => (
  <div>
    <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">{title}</h4>
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {children}
    </div>
  </div>
);

const parseResult = (data) => {
  const result = data.results?.[0];
  if (!result) return null;

  const operatorArray = result.response?.data?.operator;

  if (!result.success || !Array.isArray(operatorArray) || operatorArray.length === 0) {
    return {
      success: false,
      sid: result.sid,
      error: result.error || `HTTP ${result.status_code}`,
    };
  }

  const op = operatorArray[0];
  return {
    success: true,
    sid:         result.sid,
    pktType:     op.pktType,
    idType:      op.idType,
    optId:       op.optId,
    name:        op.name,
    email:       op.email,
    ea:          op.ea,
    eaCode:      op.eaCode,
    reg:         op.reg,
    regCode:     op.regCode,
    district:    op.district,
    state:       op.state,
    ro:          op.ro,
    pincode:     op.pincode,
    machineCode: op.machineCode,
    riskScore:   op.riskScore,
  };
};

const SearchPacketDetailsPage = () => {
  const navigate = useNavigate();
  const [sid, setSid] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [operatorSearchWarning, setOperatorSearchWarning] = useState(null);

  const navigateToOperator = async (optId, ro) => {
    if (!optId || !optId.trim()) return;
    setOperatorSearchWarning(null);

    if (!ro) {
      setOperatorSearchWarning('Regional office is missing for this packet — operator cannot be searched.');
      return;
    }

    if (IS_DEV) {
      const operator = operatorsDummy.data.find(op => op.id === optId) || { id: optId, name: optId };
      navigate('/viewoperators', { state: { initialOperatorData: [operator], searchedOptId: optId } });
      return;
    }

    try {
      // FIX 1: Missing parentheses around the template-literal URL
      const response = await fetch(`${API_BASE_URL}/api/operator_search`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: optId, ro })
      });
      const data = await response.json();

      const list = Array.isArray(data) ? data : (Array.isArray(data.data) ? data.data : null);
      const operator = list && list.length > 0 ? list[0] : null;

      navigate('/viewoperators', {
        state: {
          initialOperatorData: operator ? [operator] : [],
          searchedOptId: optId,
          notFoundMessage: operator ? null : `Operator ${optId} not found in regional office ${ro}.`
        }
      });
    } catch {
      navigate('/viewoperators', { state: { searchedOptId: optId } });
    }
  };

  const handleSearch = async () => {
    const trimmed = sid.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      let data;
      if (IS_DEV) {
        await new Promise(r => setTimeout(r, 400));
        data = dummyData;
      } else {
        // FIX 2: Missing parentheses around the template-literal URL
        const response = await fetch(`${API_BASE_URL}/api/sid/batch_get`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify([trimmed]),
        });
        // FIX 3: `new Error` was called with a template literal instead of parentheses
        if (!response.ok) throw new Error(`Request failed: ${response.status} ${response.statusText}`);
        data = await response.json();
      }
      setResult(parseResult(data));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageWrapper>
      <PageNavigation currentPage="search" />

      {/* Search Form */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-xl font-bold text-gray-900">Search by Packet EID/SID</h2>
          {IS_DEV && (
            <span className="text-xs px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full font-medium border border-yellow-200">
              DEV — dummy data
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500 mb-5">
          Enter a Packet Enrolment Id (EID) or Session ID (SID) to retrieve the operator who created the packet.
        </p>
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={sid}
            onChange={e => setSid(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="e.g. S132222983161020260418055209"
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !sid.trim()}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition whitespace-nowrap"
          >
            {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </div>

      {/* Network error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 shrink-0" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {/* Operator search warning */}
      {operatorSearchWarning && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-amber-500 shrink-0" />
          <p className="text-amber-700 text-sm">{operatorSearchWarning}</p>
        </div>
      )}

      {/* Result card */}
      {result && (
        <div className="bg-white rounded-xl shadow-md overflow-hidden">
          {/* Card header */}
          {/* FIX 4: className was a bare template literal — needs to be in curly braces */}
          <div className={`px-6 py-4 flex items-center gap-3 ${result.success ? 'bg-green-50 border-b border-green-100' : 'bg-red-50 border-b border-red-100'}`}>
            {result.success
              ? <CheckCircle className="w-5 h-5 text-green-500 shrink-0" />
              : <XCircle className="w-5 h-5 text-red-500 shrink-0" />}
            <div>
              <p className="text-xs text-gray-500">SID</p>
              <p className="font-mono text-sm font-semibold text-gray-800">{result.sid}</p>
            </div>
            {result.success && (
              <div className="ml-6 flex items-center gap-4">
                <span className="text-xs px-2 py-1 bg-white border border-gray-200 rounded-full text-gray-600 font-medium">
                  {result.pktType === 'U' ? 'Update' : result.pktType === 'E' ? 'Enrolment' : result.pktType}
                </span>
                <span className="text-xs px-2 py-1 bg-white border border-gray-200 rounded-full text-gray-600 uppercase font-medium">
                  {result.idType}
                </span>
              </div>
            )}
            {!result.success && (
              <p className="ml-4 text-sm text-red-600">{result.error}</p>
            )}
          </div>

          {/* Detail sections */}
          {result.success && (
            <div className="p-6 space-y-6">
              <Section title="Operator">
                <div>
                  <p className="text-xs text-gray-500 mb-0.5">Operator ID</p>
                  {result.optId ? (
                    <button
                      onClick={() => navigateToOperator(result.optId, result.ro)}
                      className="inline-flex items-center gap-1.5 text-sm font-semibold font-mono text-blue-600 hover:text-blue-800 hover:underline transition"
                      // FIX 5: title was a bare template literal — needs curly braces
                      title={`View operator ${result.optId}`}
                    >
                      {result.optId}
                      <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                    </button>
                  ) : (
                    <span className="text-sm text-gray-400">—</span>
                  )}
                </div>
                <Field label="Name"       value={result.name} />
                <Field label="Email"      value={result.email} />
                <Field label="Risk Score" value={result.riskScore} />
              </Section>

              <div className="border-t border-gray-100" />

              <Section title="Organisation">
                <Field label="EA"        value={result.ea} />
                <Field label="EA Code"   value={result.eaCode} />
                <Field label="Registrar" value={result.reg} />
                <Field label="Reg Code"  value={result.regCode} />
              </Section>

              <div className="border-t border-gray-100" />

              <Section title="Location">
                <Field label="District" value={result.district} />
                <Field label="State"    value={result.state} />
                <Field label="RO"       value={result.ro} />
                <Field label="Pincode"  value={result.pincode} />
              </Section>

              <div className="border-t border-gray-100" />

              <Section title="Device">
                <Field label="Machine Code" value={result.machineCode} />
              </Section>
            </div>
          )}
        </div>
      )}
    </PageWrapper>
  );
};

export default SearchPacketDetailsPage;
