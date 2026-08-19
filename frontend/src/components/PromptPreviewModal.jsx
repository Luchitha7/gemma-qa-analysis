import React, { useState } from 'react';
import { X, Copy, Check, Sparkles, Database, ShieldAlert, Cpu, CheckCircle } from 'lucide-react';

export default function PromptPreviewModal({
  isOpen,
  onClose,
  previewData,
  onApproveAndRun,
  evalLoading
}) {
  if (!isOpen || !previewData) return null;

  const [promptText, setPromptText] = useState(previewData.prompt || '');
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(promptText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn">
      <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[92vh] flex flex-col shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-base text-slate-900 flex items-center gap-2">
                <Cpu size={18} className="text-blue-600" /> LLM Prompt Builder & Inspection
              </h3>
              <span className="px-2 py-0.5 rounded-full font-bold text-[10px] bg-blue-50 text-blue-700 border border-blue-200">
                Gemma 3 4B Ingestion
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Review and approve the exact prompt built from your company guideline, RAG policies, and RoBERTa tone markers.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Injected Metadata Stats */}
        <div className="px-6 py-3 bg-slate-100/70 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-3">
            <span className="bg-white border border-slate-200 px-2.5 py-1 rounded-md text-slate-700 font-semibold flex items-center gap-1.5">
              <Database size={13} className="text-blue-600" /> RAG Policies Injected: {previewData.matched_policies ? previewData.matched_policies.length : 0}
            </span>
            <span className="bg-white border border-slate-200 px-2.5 py-1 rounded-md text-slate-700 font-semibold flex items-center gap-1.5">
              <Sparkles size={13} className="text-indigo-600" /> Line Items: {previewData.line_items_count || 0}
            </span>
            <span className="bg-white border border-slate-200 px-2.5 py-1 rounded-md text-slate-700 font-semibold flex items-center gap-1.5">
              <ShieldAlert size={13} className="text-rose-600" /> Tense Turns Flagged: {previewData.intense_moments ? previewData.intense_moments.length : 0}
            </span>
          </div>

          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-600 hover:text-slate-900 bg-white border border-slate-200 hover:bg-slate-50 px-2.5 py-1 rounded-md transition cursor-pointer"
          >
            {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
            {copied ? 'Copied Prompt' : 'Copy Prompt'}
          </button>
        </div>

        {/* Scrollable Editable Prompt Area */}
        <div className="p-6 overflow-y-auto space-y-3 flex-1 flex flex-col">
          <label className="text-xs font-semibold text-slate-700 block">
            Final Assembled Prompt String (Editable):
          </label>
          <textarea
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
            rows={18}
            className="w-full flex-1 bg-slate-950 text-emerald-400 font-mono text-xs p-4 rounded-xl border border-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 leading-relaxed resize-y"
            placeholder="Assembled prompt..."
          />
        </div>

        {/* Modal Footer Actions */}
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex justify-between items-center">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-100 text-slate-700 font-semibold text-xs transition cursor-pointer"
          >
            Cancel / Edit Transcript
          </button>

          <button
            onClick={() => onApproveAndRun(promptText)}
            disabled={evalLoading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-md transition cursor-pointer disabled:opacity-50"
          >
            {evalLoading ? (
              <>Running Analysis with Gemma...</>
            ) : (
              <>
                <CheckCircle size={15} /> Approve & Run Analysis
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
