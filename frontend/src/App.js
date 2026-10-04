import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { I18nProvider } from "@/i18n";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { SettingsProvider } from "@/context/SettingsContext";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import CustomerMenu from "@/pages/CustomerMenu";
import CashierDashboard from "@/pages/CashierDashboard";
import OwnerDashboard from "@/pages/OwnerDashboard";
import Invoice from "@/pages/Invoice";

function Protected({ children, role }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10 text-center text-neutral-500">...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to={user.role === "owner" ? "/owner" : "/cashier"} replace />;
  return children;
}

export default function App() {
  return (
    <I18nProvider>
      <AuthProvider>
        <SettingsProvider>
          <Toaster position="top-center" richColors />
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/t/:tableNumber" element={<CustomerMenu />} />
              <Route path="/invoice/:orderId" element={<Invoice />} />
              <Route path="/cashier" element={<Protected><CashierDashboard /></Protected>} />
              <Route path="/owner" element={<Protected role="owner"><OwnerDashboard /></Protected>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </SettingsProvider>
      </AuthProvider>
    </I18nProvider>
  );
}
