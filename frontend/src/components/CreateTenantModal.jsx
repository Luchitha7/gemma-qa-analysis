import React, { useState } from 'react';
import { useTenant } from '../context/TenantContext';
import { X } from 'lucide-react';

export default function CreateTenantModal({ isOpen, onClose }) {
  const { fetchTenants, setSelectedTenant, API_BASE } = useTenant();
  const [newTenantId, setNewTenantId] = useState('');
  const [newTenantName, setNewTenantName] = useState('');
  const [creating, setCreating] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!newTenantId || !newTenantName) return;
    setCreating(true);
    try {
      const res = await fetch(`${API_BASE}/api/tenants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: newTenantId.trim(), name: newTenantName.trim() }),
      });
      if (res.ok) {
        await fetchTenants();
        setSelectedTenant(newTenantId.trim());
        setNewTenantId('');
        setNewTenantName('');
        onClose();
      } else {
        const err = await res.json();
        alert('Failed: ' + (err.detail || 'Error creating company'));
      }
    } catch (err) {
      alert('Error creating company: ' + err.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn">
      <div className="bg-white border border-slate-200 rounded-2xl max-w-md w-full p-6 shadow-2xl">
        <div className="flex justify-between items-center mb-1">
          <h3 className="text-base font-bold text-slate-900">Create New Company / Tenant</h3>
          <button onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-slate-700">
            <X size={18} />
          </button>
        </div>
        <p className="text-xs text-slate-500 mb-4">Add a new company namespace for isolated criteria and vector RAG storage.</p>
        
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-700 font-semibold mb-1">Company Code / ID (e.g. S-NET, AcmeCorp):</label>
            <input
              type="text"
              required
              value={newTenantId}
              onChange={(e) => setNewTenantId(e.target.value)}
              placeholder="e.g. S-NET"
              className="w-full bg-white border border-slate-300 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-slate-700 font-semibold mb-1">Company Display Name:</label>
            <input
              type="text"
              required
              value={newTenantName}
              onChange={(e) => setNewTenantName(e.target.value)}
              placeholder="e.g. S-NET Communications"
              className="w-full bg-white border border-slate-300 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={creating}
              className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold"
            >
              {creating ? 'Creating...' : 'Create Company'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
