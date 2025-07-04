import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { Toaster } from 'react-hot-toast';
import Header from './components/common/Header';
import Landing from './pages/Landing';
import Login from './components/auth/Login';
import Register from './components/auth/Register';
import DashboardLayout from './components/dashboard/DashboardLayout';
import Overview from './components/dashboard/Overview';
import Orders from './components/dashboard/Orders';
import Positions from './components/dashboard/Positions';
import ForgotPassword from './components/auth/ForgotPassword';
import VerifyOtpResetPassword from './components/auth/VerifyOtpResetPassword';
import ResetPassword from './components/auth/ResetPassword';
import PnL from './components/dashboard/PnL';
import BrokerConnection from './components/dashboard/BrokerConnection';
import { isAuthenticated } from './utils/auth';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return isAuthenticated() ? <>{children}</> : <Navigate to="/login" />;
};

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-dark-950">
        <Toaster 
          position="top-right"
          toastOptions={{
            style: {
              background: '#1a1a1a',
              color: '#8a9c70',
              border: '1px solid rgba(138, 156, 112, 0.2)',
            },
          }}
        />
        <Header />
        <AnimatePresence mode="wait">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/verify-otp-reset" element={<VerifyOtpResetPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Overview />} />
              <Route path="orders" element={<Orders />} />
              <Route path="positions" element={<Positions />} />
              <Route path="pnl" element={<PnL />} />
              <Route path="brokers" element={<BrokerConnection />} />
            </Route>
          </Routes>
        </AnimatePresence>
      </div>
    </Router>
  );
}

export default App;