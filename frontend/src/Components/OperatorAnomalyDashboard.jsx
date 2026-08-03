import React from 'react';
import OverviewTab from './OverviewTab';
import PageNavigation from './PageNavigation';
import PageWrapper from './ui/PageWrapper';

// This is the shell for the /dashboard route (PageNavigation's "Overview"
// tab). It used to be a 4-way in-page tab switcher (overview/patterns/
// geographic/operators), but PageNavigation is route-based — nothing ever
// called the setActiveTab that would reach the other 3 branches, so they
// were unreachable dead code. Patterns, Geographic, and Operators are all
// still live, just via their own routes (/anomalyindicators,
// /regionevaluation, /viewoperators respectively), not through here.
const OperatorAnomalyDashboard = () => (
  <PageWrapper>
    <PageNavigation currentPage="overview" />
    <OverviewTab />
  </PageWrapper>
);

export default OperatorAnomalyDashboard;
