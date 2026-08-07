// src/heatmapMockData.js

// Helper to generate multiple points around a center to create a "blob"
const generateClusterPoints = (centerLat, centerLng, count, baseIntensity) => {
  const points = [];
  for (let i = 0; i < count; i++) {
    // Spread points around the center
    const lat = centerLat + (Math.random() - 0.5) * 1.5;
    const lng = centerLng + (Math.random() - 0.5) * 1.5;
    points.push([lat, lng, baseIntensity]);
  }
  return points;
};

// LEVEL 1: State-wise Heat Data
export const stateHeatData = [
  ...generateClusterPoints(19.7515, 75.7139, 50, 0.9), // Maharashtra (High Risk)
  ...generateClusterPoints(15.3173, 75.7139, 30, 0.5), // Karnataka (Medium Risk)
  ...generateClusterPoints(26.8467, 80.9462, 60, 1.0), // UP (Critical Risk)
  ...generateClusterPoints(11.1271, 78.6569, 20, 0.3), // Tamil Nadu (Low Risk)
  ...generateClusterPoints(22.9868, 87.8550, 25, 0.4), // West Bengal (Low-Med Risk)
];

// LEVEL 2: District-wise Heat Data
export const districtHeatData = [
  ...generateClusterPoints(18.5204, 73.8567, 20, 0.8), // Pune
  ...generateClusterPoints(19.0760, 72.8777, 30, 1.0), // Mumbai
  ...generateClusterPoints(21.1458, 79.0882, 10, 0.3), // Nagpur
  ...generateClusterPoints(12.9716, 77.5946, 25, 0.7), // Bengaluru
  ...generateClusterPoints(12.2958, 76.6394, 5, 0.2),  // Mysuru
  ...generateClusterPoints(26.8467, 80.9462, 15, 0.9), // Lucknow
  ...generateClusterPoints(26.4499, 80.3319, 10, 0.6), // Kanpur
];