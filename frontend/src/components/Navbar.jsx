import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useTenant } from '../context/TenantContext';
import { FileText, Layers, Sparkles, Clock, Plus } from 'lucide-react';
import CreateTenantModal from './CreateTenantModal';

export default function Navbar() {
  const { tenants, selectedTenant, setSelectedTenant } = useTenant();
  const [showModal, setShowModal] = useState(false);

  const navLinkClass = ({ isActive }) =>
    `flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-semibold transition ${
      isActive
        ? 'bg-white text-slate-900 shadow-sm border border-slate-200/80'
        : 'text-slate-600 hover:text-slate-900'
    }`;

  return (
    <>
      <header className="border-b border-slate-200 bg-white sticky top-0 z-40 px-8 py-3.5 flex flex-wrap justify-between items-center gap-4 shadow-sm">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-slate-900 text-white flex items-center justify-center font-bold text-base shadow">
            QA
          </div>
          <div>
            <h1 className="font-bold text-base text-slate-900 leading-tight flex items-center gap-2">
              Automated QA Intelligence
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                PostgreSQL + MiniLM RAG
              </span>
            </h1>
            <p className="text-xs text-slate-500">Multi-Tenant Document Parser & Dynamic Gemma 3 4B Scorecard</p>
          </div>
        </div>

        {/* Company Selector */}
        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-500 font-medium">Company:</label>
          <select
            value={selectedTenant}
            onChange={(e) => setSelectedTenant(e.target.value)}
            className="bg-white text-slate-800 border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-sm"
          >
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.id})
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-semibold transition cursor-pointer"
          >
            <Plus size={13} /> New Company
          </button>
        </div>

        {/* Router Nav Links */}
        <nav className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200">
          <NavLink to="/" className={navLinkClass}>
            <FileText size={13} /> PDF & Markdown
          </NavLink>
          <NavLink to="/criteria" className={navLinkClass}>
            <Layers size={13} /> Criteria & Policies
          </NavLink>
          <NavLink to="/test" className={navLinkClass}>
            <Sparkles size={13} /> Live QA Test
          </NavLink>
          <NavLink to="/history" className={navLinkClass}>
            <Clock size={13} /> Audit History
          </NavLink>
        </nav>
      </header>

      <CreateTenantModal isOpen={showModal} onClose={() => setShowModal(false)} />
    </>
  );
}
