import React, { useState, useEffect } from 'react';
import { useTenant } from '../context/TenantContext';
import { Clock, Eye, Trash2 } from 'lucide-react';
import AuditDetailModal from '../components/AuditDetailModal';

export default function AuditHistoryPage() {
  const { selectedTenant, API_BASE } = useTenant();
  const [historyData, setHistoryData] = useState([]);
  const [selectedHistoryItem, setSelectedHistoryItem] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/evaluations?tenant_id=${selectedTenant}`);
      const data = await res.json();
      setHistoryData(data);
    } catch (e) {
      console.error('Failed to fetch history:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedTenant) {
      fetchHistory();
    }
  }, [selectedTenant]);

  const openHistoryDetail = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/api/evaluations/${id}`);
      const data = await res.json();
      setSelectedHistoryItem(data);
    } catch (e) {
      console.error('Failed to fetch evaluation detail:', e);
    }
  };

  const handleDeleteEvaluation = async (id) => {
    if (!window.confirm(`Are you sure you want to delete this evaluation report (${id.slice(0, 8)}...)?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/evaluations/${id}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        if (selectedHistoryItem && selectedHistoryItem.id === id) {
          setSelectedHistoryItem(null);
        }
        fetchHistory();
      } else {
        alert('Failed to delete evaluation record.');
      }
    } catch (err) {
      alert('Delete error: ' + err.message);
    }
  };

  const handleClearAllHistory = async () => {
    if (!window.confirm(`Are you sure you want to delete ALL audit records for "${selectedTenant}"?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/evaluations?tenant_id=${selectedTenant}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setSelectedHistoryItem(null);
        fetchHistory();
      }
    } catch (err) {
      alert('Clear error: ' + err.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap justify-between items-center gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Clock size={20} className="text-blue-600" /> QA Audit History ({selectedTenant})
          </h2>
          <p className="text-xs text-slate-500">Historical evaluation records stored in PostgreSQL. Click any row to view in-depth breakdown or delete individual records.</p>
        </div>
        {historyData.length > 0 && (
          <button
            onClick={handleClearAllHistory}
            className="flex items-center gap-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg px-3 py-1.5 text-xs font-semibold transition cursor-pointer"
          >
            <Trash2 size={13} /> Clear All {selectedTenant} Logs
          </button>
        )}
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 text-slate-500 border-b border-slate-200 font-semibold">
                <th className="p-4">Report ID</th>
                <th className="p-4">Channel</th>
                <th className="p-4">Score</th>
                <th className="p-4">Status</th>
                <th className="p-4">Date & Time</th>
                <th className="p-4">Summary</th>
                <th className="p-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {historyData.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-10 text-slate-400 text-xs">
                    {loading ? 'Loading audit records...' : `No evaluation records found yet for ${selectedTenant}.`}
                  </td>
                </tr>
              ) : (
                historyData.map((row) => (
                  <tr 
                    key={row.id} 
                    onClick={() => openHistoryDetail(row.id)}
                    className="hover:bg-blue-50/40 cursor-pointer transition"
                  >
                    <td className="p-4 font-mono font-semibold text-blue-700">{row.id.slice(0, 8)}...</td>
                    <td className="p-4 text-slate-800 font-medium">{row.channel}</td>
                    <td className="p-4 font-bold text-sm text-slate-900">{row.final_score}</td>
                    <td className="p-4">
                      <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                        row.is_auto_fail
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      }`}>
                        {row.is_auto_fail ? 'AUTO-FAIL' : 'PASSED'}
                      </span>
                    </td>
                    <td className="p-4 text-slate-500">{new Date(row.created_at).toLocaleString()}</td>
                    <td className="p-4 text-slate-700 max-w-sm truncate">{row.summary}</td>
                    <td className="p-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            openHistoryDetail(row.id);
                          }}
                          className="flex items-center gap-1 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 px-2 py-1 rounded text-[11px] font-semibold transition cursor-pointer"
                        >
                          <Eye size={12} /> View
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteEvaluation(row.id);
                          }}
                          className="flex items-center gap-1 bg-white hover:bg-rose-50 text-rose-600 border border-slate-200 hover:border-rose-200 px-2 py-1 rounded text-[11px] font-semibold transition cursor-pointer"
                        >
                          <Trash2 size={12} /> Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <AuditDetailModal 
        item={selectedHistoryItem} 
        onClose={() => setSelectedHistoryItem(null)} 
        onDelete={handleDeleteEvaluation}
      />
    </div>
  );
}
