import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { getSeverityColor, getSeverityIcon, getCategoryColor } from '../utils/colorHelpers';
import { getGlobalRO } from '../hooks/useGlobalRegionalOffice';
import PageNavigation from './PageNavigation';
import OperatorsTab from './OperatorsTab';
import PageWrapper from './ui/PageWrapper';

const ViewOperatorsPage = () => {
  const { state } = useLocation();
  // Read synchronously so OperatorsTab gets the data on its first render,
  // preventing the auto-fetch from racing against the initialOperatorData effect.
  const [initialOperatorData] = useState(state?.initialOperatorData || null);
  const [searchedOptId] = useState(state?.searchedOptId || null);
  const [notFoundMessage] = useState(state?.notFoundMessage || null);
  // Explicit route-state filters (Review Now / EA-Reg tile clicks) win; else,
  // for a TechCentre/HeadQuarters user who's scoped the header to one RO,
  // default the filter panel to that RO instead of the global (no-RO) view.
  const [initialFilters] = useState(() => {
    if (state?.initialFilters) return state.initialFilters;
    const headerRO = getGlobalRO();
    return headerRO ? { ro: headerRO } : null;
  });
  const [selectedOperator, setSelectedOperator] = useState(null);

  return (
    <PageWrapper>
      <PageNavigation currentPage="viewoperators" />

      <OperatorsTab
        filteredOperators={[]}
        selectedOperator={selectedOperator}
        setSelectedOperator={setSelectedOperator}
        getSeverityColor={getSeverityColor}
        getSeverityIcon={getSeverityIcon}
        getCategoryColor={getCategoryColor}
        initialOperatorData={initialOperatorData}
        searchedOptId={searchedOptId}
        notFoundMessage={notFoundMessage}
        initialFilters={initialFilters}
      />
    </PageWrapper>
  );
};

export default ViewOperatorsPage;
