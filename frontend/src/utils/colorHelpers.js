import React from 'react';
import { XCircle, AlertCircle, CheckCircle, Activity } from 'lucide-react';

export const getSeverityColor = (severity) => {
  switch (severity) {
    case 'high': return 'bg-red-100 text-red-800 border-red-300';
    case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    case 'positive': return 'bg-green-100 text-green-800 border-green-300';
    default: return 'bg-gray-100 text-gray-800 border-gray-300';
  }
};

export const getSeverityIcon = (severity) => {
  switch (severity) {
    case 'high': return <XCircle className="w-4 h-4" />;
    case 'medium': return <AlertCircle className="w-4 h-4" />;
    case 'positive': return <CheckCircle className="w-4 h-4" />;
    default: return <Activity className="w-4 h-4" />;
  }
};

export const getCategoryColor = (category) => {
  const colors = {
    fraud: 'bg-red-500',
    quality: 'bg-orange-500',
    velocity: 'bg-purple-500',
    geographic: 'bg-blue-500',
    technical: 'bg-gray-500',
    productivity: 'bg-yellow-500',
    pattern: 'bg-pink-500'
  };
  return colors[category] || 'bg-gray-500';
};

// Single source of truth for risk_bucket -> color, so "Critical" (or any future
// bucket opt_master starts returning) only needs updating here, not in every
// chart/badge that renders a risk level. Severity order: Critical > High >
// Medium > Low > No. Matching is case-insensitive since opt_master.risk_bucket
// casing isn't guaranteed; unrecognized values fall back to a neutral gray
// rather than defaulting to any particular severity.
const RISK_BUCKET_STYLES = {
  critical: { level: 'CRITICAL RISK', label: 'Critical', color: '#b91c1c', bgColor: '#fecaca' },
  high:     { level: 'HIGH RISK',     label: 'High',     color: '#ef4444', bgColor: '#fee2e2' },
  medium:   { level: 'MEDIUM RISK',   label: 'Medium',   color: '#f59e0b', bgColor: '#fef3c7' },
  low:      { level: 'LOW RISK',      label: 'Low',      color: '#10b981', bgColor: '#d1fae5' },
  no:       { level: 'NO RISK',       label: 'No Risk',  color: '#6b7280', bgColor: '#f3f4f6' },
};

const RISK_BUCKET_FALLBACK = { level: 'UNKNOWN', label: 'Unknown', color: '#6b7280', bgColor: '#f3f4f6' };

// getRiskBucketStyle returns { level, label, color, bgColor } for a risk_bucket
// string as returned by the backend (opt_master.risk_bucket, or null/undefined
// for "No Risk"). Always driven by the actual bucket value — never derive a
// risk level from a raw score/percentage threshold independently of this.
export const getRiskBucketStyle = (riskBucket) => {
  const key = (riskBucket || 'no').toString().trim().toLowerCase();
  return RISK_BUCKET_STYLES[key] || RISK_BUCKET_FALLBACK;
};
