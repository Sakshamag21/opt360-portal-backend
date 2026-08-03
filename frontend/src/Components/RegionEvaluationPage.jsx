import React, { useState } from 'react';
import PageNavigation from './PageNavigation';
import GeographicAnalysisTab from './GeographicAnalysisTab';
import PageWrapper from './ui/PageWrapper';
import { REGIONAL_OFFICES, GLOBAL_GROUPS } from '../constants';
import { useCurrentUser } from '../hooks/useCurrentUser';
import { getGlobalRO } from '../hooks/useGlobalRegionalOffice';

// Seeds this page's RO from the header's global RO selector (for
// TechCentre/HeadQuarters users) or the caller's own RO — instead of a
// hardcoded 'Bangalore' that showed the wrong RO's data by default for
// almost everyone. The button-grid below still lets any user view a
// different RO on this page (viewing is unrestricted), it's just no longer
// the *only* way to land on the right one.
const defaultRo = (profile) => {
  const headerRO = getGlobalRO();
  if (headerRO) return headerRO;
  if (profile && !GLOBAL_GROUPS.includes(profile.regional_office)) return profile.regional_office;
  return REGIONAL_OFFICES[0];
};

const RegionEvaluationPage = () => {
  const { profile } = useCurrentUser();
  const [selectedRo, setSelectedRo] = useState(() => defaultRo(profile));

  // profile loads asynchronously after mount — re-seed once it's available
  // (only if the user hasn't already picked something themselves).
  const seededFromProfile = React.useRef(false);
  React.useEffect(() => {
    if (profile && !seededFromProfile.current) {
      seededFromProfile.current = true;
      setSelectedRo(defaultRo(profile));
    }
  }, [profile]);

  return (
    <PageWrapper>
      <PageNavigation currentPage="region" />

      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Select Regional Office</h3>
        <div className="flex flex-wrap gap-3">
          {REGIONAL_OFFICES.map((ro) => (
            <button
              key={ro}
              onClick={() => { seededFromProfile.current = true; setSelectedRo(ro); }}
              className={`px-4 py-2 rounded-lg font-medium transition ${
                selectedRo === ro
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {ro}
            </button>
          ))}
        </div>
      </div>

      <GeographicAnalysisTab selectedRo={selectedRo} />
    </PageWrapper>
  );
};

export default RegionEvaluationPage;
