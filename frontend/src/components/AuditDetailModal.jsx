import React from 'react';
import { X, Database, CheckCircle, AlertTriangle, Trash2 } from 'lucide-react';

export default function AuditDetailModal({ item, onClose, onDelete }) {
  if (!item) return null;

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn">
      <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-200 overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-base text-slate-900">In-Depth QA Audit Breakdown</h3>
              <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                item.is_auto_fail
                  ? 'bg-rose-50 text-rose-700 border border-rose-200'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              }`}>
                {item.is_auto_fail ? 'AUTO-FAIL' : 'PASSED'}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Report ID: <span className="font-mono text-slate-700">{item.id}</span> · Date: {new Date(item.created_at).toLocaleString()}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Scrollable Content */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-800">
          {/* Total Score & Auto-Fail Banner */}
          <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl flex justify-between items-center">
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Total Audit Score</span>
              <div className="text-3xl font-extrabold text-slate-900 mt-0.5">
                {item.final_score} <span className="text-xs font-normal text-slate-500">/ 100</span>
              </div>
              {item.is_auto_fail && (
                <p className="text-xs text-rose-600 mt-1 font-medium">Auto-fail rule breach detected during audit.</p>
              )}
            </div>
            <div className="text-right">
              <span className="text-[11px] text-slate-400 block">Channel / Agent</span>
              <span className="font-bold text-sm text-slate-800">{item.channel} · {item.agent_name || 'Agent'}</span>
            </div>
          </div>

          {/* Analyzed Transcript */}
          <div>
            <h4 className="font-bold text-xs uppercase tracking-wider text-slate-500 mb-2">Original Interaction Transcript</h4>
            <pre className="bg-slate-900 text-slate-100 p-4 rounded-xl font-mono text-[11px] whitespace-pre-wrap leading-relaxed max-h-52 overflow-y-auto">
              {item.transcript}
            </pre>
          </div>

          {/* Line-by-Line Scorecard */}
          <div>
            <h4 className="font-bold text-xs uppercase tracking-wider text-slate-500 mb-2">Line-by-Line QA Scorecard</h4>
            <div className="border border-slate-200 rounded-xl overflow-hidden">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                    <th className="p-3">Line Item</th>
                    <th className="p-3">Category</th>
                    <th className="p-3">Rating</th>
                    <th className="p-3">Score</th>
                    <th className="p-3">Audit Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(item.scorecard || []).map((line, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/50">
                      <td className="p-3 font-semibold text-slate-900">{line.name}</td>
                      <td className="p-3 text-slate-500">{line.category}</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                          line.rating === 'PASS' 
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : line.rating === 'PARTIAL'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}>
                          {line.rating}
                        </span>
                      </td>
                      <td className="p-3 font-bold text-slate-900">{line.score}</td>
                      <td className="p-3 text-slate-700">{line.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Summary & Suggestions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
              <h4 className="font-bold text-xs uppercase tracking-wider text-slate-500 mb-1.5">Executive Summary</h4>
              <p className="text-slate-700 leading-relaxed">{item.summary}</p>
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
              <h4 className="font-bold text-xs uppercase tracking-wider text-slate-500 mb-1.5">Coaching Tips</h4>
              <p className="text-slate-700 whitespace-pre-wrap leading-relaxed">{item.suggestions}</p>
            </div>
          </div>

          {/* Matched Policies */}
          {item.matched_policies && item.matched_policies.length > 0 && (
            <div>
              <h4 className="font-bold text-xs uppercase tracking-wider text-slate-500 mb-2">Matched Company Policies (RAG Evidence)</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {item.matched_policies.map((p, idx) => (
                  <div key={idx} className="bg-slate-50 border border-slate-200 p-3 rounded-lg">
                    <strong className="text-slate-900 block font-semibold">{p.title}</strong>
                    <p className="text-slate-600 mt-1 text-[11px]">{p.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-between items-center">
          {onDelete ? (
            <button
              onClick={() => onDelete(item.id)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 font-semibold text-xs transition cursor-pointer"
            >
              <Trash2 size={13} /> Delete Audit Record
            </button>
          ) : <div />}
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs shadow-sm cursor-pointer"
          >
            Close Audit View
          </button>
        </div>
      </div>
    </div>
  );
}
