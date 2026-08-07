import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import PageWrapper from './ui/PageWrapper';
import PageNavigation from './PageNavigation';

// Map pathname prefixes to PageNavigation keys
const PATH_TO_KEY = {
  '/dashboard': 'overview',
  '/anomalyindicators': 'anomaly',
  '/regionevaluation': 'region',
  '/featureanalysis': 'featureanalysis',
  '/viewoperators': 'viewoperators',
  '/searchpacketdetails': 'search',
  '/dynamicriskmap': 'dynamicriskmap',
  '/riskheatmap': 'riskheatmap',
  '/profile': 'profile',
};

export default function ProtectedLayout() {
  const { pathname } = useLocation();
  // find the best match key for the current pathname
  const key = Object.keys(PATH_TO_KEY).find(p => pathname.startsWith(p)) || 'overview';
  const currentPage = PATH_TO_KEY[key] || 'overview';

  return (
    <PageWrapper>
      <PageNavigation currentPage={currentPage} />
      <Outlet />
    </PageWrapper>
  );
}
