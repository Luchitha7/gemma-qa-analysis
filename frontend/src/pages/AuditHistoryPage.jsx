import React, { useState, useEffect } from 'react';
import { useTenant } from '../context/TenantContext';
import { Clock, Eye } from 'lucide-react';
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

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Clock size={20} className="text-blue-600" /> QA Audit History ({selectedTenant})
          </h2>
          <p className="text-xs text-slate-500">Historical records stored in PostgreSQL table `evaluation_reports`. Click any row to view in-depth breakdown.</p>
        </div>
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
                <th className="p-4 text-right">Action</th>
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
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openHistoryDetail(row.id);
                        }}
                        className="flex items-center gap-1 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 px-2.5 py-1 rounded text-[11px] font-semibold transition ml-auto cursor-pointer"
                      >
                        <Eye size={12} /> View Details
                      </button>
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
      />
    </div>
  );
}
