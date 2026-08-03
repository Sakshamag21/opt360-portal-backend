import React from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

function extractNumeric(val) {
  const n = Number(val);
  return Number.isFinite(n) ? n : 0;
}

const SERIES_COLORS = [
  '#ef4444', // red
  '#3b82f6', // blue
  '#10b981', // green
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#06b6d4', // cyan
  '#dc2626', // dark red
  '#16a34a', // dark green
  '#ea580c', // orange
];

function buildGraphData(feature) {
  const fg = feature?.feature_graph;
  if (fg && fg.graph_data && typeof fg.graph_data === 'object') {
    const entries = Object.entries(fg.graph_data);
    const sorted = entries.sort((a, b) => Number(a[0]) - Number(b[0]));
    // Build per-point combined objects: { x, series1: val, series2: val, timestamp_series1, timestamp_series2, ... }
    const points = sorted.map(([x, arr]) => {
      const list = Array.isArray(arr) ? arr : [];
      const combined = { x };
      list.forEach(obj => {
        if (obj && typeof obj === 'object') {
          let metricName = null;
          let timestampValue = null;
          
          Object.entries(obj).forEach(([key, value]) => {
            if (key === 'timestamp') {
              timestampValue = value;
            } else {
              metricName = key;
              combined[key] = extractNumeric(value);
            }
          });
          
          // Store timestamp with a special key for each metric
          if (metricName && timestampValue) {
            combined[`timestamp_${metricName}`] = timestampValue;
          }
        }
      });
      return combined;
    });
    return points;
  }
  // No feature_graph available
  return [];
}

// Custom tooltip to show timestamps
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-4 border rounded-lg shadow-lg">
        <p className="font-semibold text-gray-900 mb-2">Hour: {label}</p>
        <div className="space-y-2">
          {payload.map((entry, index) => {
            const metricName = entry.name;
            const timestampKey = `timestamp_${metricName}`;
            const timestamp = entry.payload[timestampKey];
            
            return (
              <div key={index} className="text-sm">
                <div className="flex items-center gap-2">
                  <div 
                    className="w-3 h-3 rounded"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="font-medium">{metricName}:</span>
                  <span className="font-bold">{entry.value}</span>
                </div>
                {timestamp && timestamp.trim() !== '' && (
                  <div className="ml-5 text-xs text-gray-600 mt-1">
                    {timestamp}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }
  return null;
};

const FeatureGraph = ({ feature }) => {
  const data = buildGraphData(feature);
  const featureType = feature?.feature_type || 'Value';
  // Determine series keys dynamically from data
  const seriesKeys = Array.from(
    new Set(
      (Array.isArray(data) ? data : [])
        .flatMap((row) => Object.keys(row))
        .filter((k) => k !== 'x' && !k.startsWith('timestamp_'))
    )
  );

  return (
    <div className="w-full">
      <div style={{ height: 320 }}>
        {data.length === 0 || seriesKeys.length === 0 ? (
          <div className="flex items-center justify-center h-full text-sm text-gray-600">No data available</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" label={{ value: 'Hour of Day', position: 'insideBottom', offset: -5 }} />
              <YAxis label={{ value: featureType, angle: -90, position: 'insideLeft' }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              {seriesKeys.map((key, idx) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={SERIES_COLORS[idx % SERIES_COLORS.length]}
                  name={key}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export default FeatureGraph;
