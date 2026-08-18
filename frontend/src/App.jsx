import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { TenantProvider } from './context/TenantContext';
import Navbar from './components/Navbar';

// Pages
import UploadMarkdownPage from './pages/UploadMarkdownPage';
import CriteriaPolicyPage from './pages/CriteriaPolicyPage';
import LiveQAPage from './pages/LiveQAPage';
import AuditHistoryPage from './pages/AuditHistoryPage';

export default function App() {
  return (
    <TenantProvider>
      <Router>
        <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
          {/* Header Navigation */}
          <Navbar />

          {/* Main Route Content */}
          <main className="max-w-7xl w-full mx-auto p-8 flex-1">
            <Routes>
              <Route path="/" element={<UploadMarkdownPage />} />
              <Route path="/criteria" element={<CriteriaPolicyPage />} />
              <Route path="/test" element={<LiveQAPage />} />
              <Route path="/history" element={<AuditHistoryPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>

          {/* Footer */}
          <footer className="text-center py-6 text-slate-400 text-xs border-t border-slate-200 bg-white">
            Automated Multi-Tenant QA Service · Powered by PostgreSQL, MiniLM RAG & Gemma 3 4B
          </footer>
        </div>
      </Router>
    </TenantProvider>
  );
}
