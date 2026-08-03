import React from 'react';
import PageNavigation from './PageNavigation';
import PatternAnalysisTab from './PatternAnalysisTab';
import PageWrapper from './ui/PageWrapper';

const AnomalyIndicatorsPage = () => (
  <PageWrapper>
    <PageNavigation currentPage="anomaly" />
    <PatternAnalysisTab />
  </PageWrapper>
);

export default AnomalyIndicatorsPage;
