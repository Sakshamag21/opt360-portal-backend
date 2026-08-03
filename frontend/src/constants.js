export const REGIONAL_OFFICES = [
  'Bangalore',
  'Mumbai',
  'Delhi',
  'Lucknow',
  'Hyderabad',
  'Ranchi',
  'Guwahati',
  'Chandigarh'
];

// RBAC "group" values (docs/RBAC_PLAN.md): the 8 ROs plus two non-RO groups.
// Used by the Profile/My Team feature (group filter, onboarding, reassignment).
// Kept separate from REGIONAL_OFFICES since TechCentre/HeadQuarters don't map to
// any RO-scoped S3 data path and shouldn't appear in operator-data RO selectors.
export const GROUPS = [...REGIONAL_OFFICES, 'TechCentre', 'HeadQuarters'];

// Groups that aren't a real Regional Office — these users see data across
// all ROs by default, with an optional header selector to scope down to one
// RO. Mirrors models.GlobalGroups on the backend (models/user.go).
export const GLOBAL_GROUPS = ['TechCentre', 'HeadQuarters'];
