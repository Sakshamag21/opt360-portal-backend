// src/Components/mockData.js

// LEVEL 1: State-wise aggregated data (Shown when zoomed out)
export const stateData = [
  { region_name: "Maharashtra", lat: 19.7515, lng: 75.7139, operator_count: 1250, high_risk_count: 340 },
  { region_name: "Karnataka", lat: 15.3173, lng: 75.7139, operator_count: 890, high_risk_count: 210 },
  { region_name: "Uttar Pradesh", lat: 26.8467, lng: 80.9462, operator_count: 1500, high_risk_count: 450 },
  { region_name: "Tamil Nadu", lat: 11.1271, lng: 78.6569, operator_count: 760, high_risk_count: 150 },
  { region_name: "West Bengal", lat: 22.9868, lng: 87.8550, operator_count: 650, high_risk_count: 180 },
];

// LEVEL 2: District-wise aggregated data (Shown when zoomed into a state)
export const districtData = [
  { region_name: "Pune", lat: 18.5204, lng: 73.8567, operator_count: 320, high_risk_count: 85 },
  { region_name: "Mumbai", lat: 19.0760, lng: 72.8777, operator_count: 450, high_risk_count: 120 },
  { region_name: "Nagpur", lat: 21.1458, lng: 79.0882, operator_count: 180, high_risk_count: 45 },
  { region_name: "Bengaluru Urban", lat: 12.9716, lng: 77.5946, operator_count: 410, high_risk_count: 90 },
  { region_name: "Mysuru", lat: 12.2958, lng: 76.6394, operator_count: 150, high_risk_count: 30 },
  { region_name: "Lucknow", lat: 26.8467, lng: 80.9462, operator_count: 280, high_risk_count: 70 },
  { region_name: "Kanpur", lat: 26.4499, lng: 80.3319, operator_count: 220, high_risk_count: 60 },
];

// LEVEL 3: Individual operator coordinates (Shown when zoomed into a district)
// Generating 5000+ dummy operators dynamically for performance testing
export const operatorData = Array.from({ length: 5000 }).map((_, index) => {
  const riskLevels = ["High", "Medium", "Low"];
  const randomRisk = riskLevels[Math.floor(Math.random() * riskLevels.length)];
  
  // Randomizing coordinates around Maharashtra and Karnataka for the dummy data
  const lat = 18 + Math.random() * 3; 
  const lng = 73 + Math.random() * 4;

  return {
    operator_id: `OP_${1000 + index}`,
    name: `Operator ${index + 1}`,
    lat: parseFloat(lat.toFixed(4)),
    lng: parseFloat(lng.toFixed(4)),
    risk_level: randomRisk
  };
});