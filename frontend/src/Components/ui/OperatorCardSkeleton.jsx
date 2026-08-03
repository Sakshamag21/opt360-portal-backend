import React from 'react';

/**
 * Skeleton placeholder matching OperatorsTab's result-card layout, shown while
 * a live opt_master query is in flight (there's no cache — see
 * docs/VIEW_OPERATORS_REDESIGN_PLAN.md — so a good loading state matters more
 * here than in most of the app).
 */
const OperatorCardSkeleton = () => (
  <div className="border rounded-xl p-6 bg-white shadow-sm animate-pulse">
    <div className="flex items-center gap-4 mb-4">
      <div className="h-6 w-40 bg-gray-200 rounded" />
      <div className="h-6 w-24 bg-gray-200 rounded-full" />
      <div className="h-6 w-20 bg-gray-200 rounded-full" />
      <div className="ml-auto h-9 w-36 bg-gray-200 rounded-lg" />
    </div>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-4 w-28 bg-gray-100 rounded" />
      ))}
    </div>
  </div>
);

export const OperatorListSkeleton = ({ count = 5 }) => (
  <div className="space-y-4">
    {Array.from({ length: count }).map((_, i) => <OperatorCardSkeleton key={i} />)}
  </div>
);

export default OperatorCardSkeleton;
