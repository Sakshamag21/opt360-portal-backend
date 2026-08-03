import React from 'react';

const PageWrapper = ({ children }) => (
  <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
    <div className="p-6">
      <div className="max-w-[1920px] mx-auto space-y-6">
        {children}
      </div>
    </div>
  </div>
);

export default PageWrapper;
