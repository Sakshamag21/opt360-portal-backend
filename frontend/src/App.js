import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LandingPage from './Components/LandingPage';
import Callback from './Components/Callback';
import ProtectedRoute from './Components/ProtectedRoute';
import OperatorAnomalyDashboard from './Components/OperatorAnomalyDashboard';
import AnomalyIndicatorsPage from './Components/AnomalyIndicatorsPage';
import RegionEvaluationPage from './Components/RegionEvaluationPage';
import ViewOperatorsPage from './Components/ViewOperatorsPage';
import SearchPacketDetailsPage from './Components/SearchPacketDetailsPage';
import FeatureAnalysisPage from './Components/FeatureAnalysisPage';
import ProfilePage from './Components/ProfilePage';

function App() {
  return (
    <Router>
      <div className="flex flex-col min-h-screen">
        <main className="flex-grow">
          <Routes>
            {/* Public Routes */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/callback" element={<Callback />} />
            
            {/* Protected Dashboard Routes */}
            <Route 
              path="/dashboard" 
              element={
                <ProtectedRoute>
                  <OperatorAnomalyDashboard />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/anomalyindicators" 
              element={
                <ProtectedRoute>
                  <AnomalyIndicatorsPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/regionevaluation" 
              element={
                <ProtectedRoute>
                  <RegionEvaluationPage />
                </ProtectedRoute>
              } 
            />
            <Route
              path="/viewoperators"
              element={
                <ProtectedRoute>
                  <ViewOperatorsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/searchpacketdetails"
              element={
                <ProtectedRoute>
                  <SearchPacketDetailsPage />
                </ProtectedRoute>
              }
            />

            <Route
              path="/featureanalysis"
              element={
                <ProtectedRoute>
                  <FeatureAnalysisPage />
                </ProtectedRoute>
              }
            />

            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />

            {/* Redirect unknown routes to landing page */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
