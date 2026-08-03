import React from 'react';
import { Loader } from 'lucide-react';

const LoadingSpinner = ({ message = 'Loading...' }) => (
  <div className="flex items-center justify-center h-96">
    <div className="text-center">
      <Loader className="w-12 h-12 animate-spin text-blue-500 mx-auto mb-4" />
      <p className="text-gray-600 font-medium">{message}</p>
    </div>
  </div>
);

export default LoadingSpinner;
