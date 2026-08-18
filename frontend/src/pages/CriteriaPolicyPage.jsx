import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useTenant } from '../context/TenantContext';
import { Layers, ShieldAlert, Activity, Database, FileText, Upload } from 'lucide-react';

export default function CriteriaPolicyPage() {
  const { selectedTenant, API_BASE } = useTenant();
  const [criteriaData, setCriteriaData] = useState(null);
  const [policiesData, setPoliciesData] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchCriteria = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tenants/${selectedTenant}/criteria`);
      const data = await res.json();
      setCriteriaData(data);
    } catch (e) {
      console.error('Failed to fetch criteria:', e);
    }
  };

  const fetchPolicies = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tenants/${selectedTenant}/policies`);
      const data = await res.json();
      setPoliciesData(data);
    } catch (e) {
      console.error('Failed to fetch policies:', e);
    }
  };

  useEffect(() => {
    if (selectedTenant) {
      setLoading(true);
      Promise.all([fetchCriteria(), fetchPolicies()]).finally(() => setLoading(false));
    }
  }, [selectedTenant]);

  const hasCriteria = criteriaData && 
    criteriaData.has_criteria !== false && 
    criteriaData.categories && 
    criteriaData.categories.length > 0;

  if (loading) {
    return (
      <div className="text-center py-16 text-slate-400 text-xs">
        Loading criteria for {selectedTenant}...
      </div>
    );
  }

  if (!hasCriteria) {
    return (
      <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center shadow-sm space-y-4 max-w-2xl mx-auto my-8">
        <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 mx-auto">
          <FileText size={28} />
        </div>
        <div>
          <h3 className="font-bold text-slate-900 text-base">No Guideline Document Uploaded for {selectedTenant}</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
            Criteria, category weights, line items, and vector policies are dynamically extracted from your uploaded Markdown file. Upload a company PDF to extract and view them.
          </p>
        </div>
        <div className="pt-2">
          <Link
            to="/"
            className="inline-flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white font-semibold px-5 py-2.5 rounded-lg text-xs shadow transition cursor-pointer"
          >
            <Upload size={14} /> Upload Guideline PDF for {selectedTenant}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <Layers size={20} className="text-blue-600" /> Extracted Criteria & Policy Knowledge Base
        </h2>
        <p className="text-xs text-slate-500">
          Extracted directly from the company's uploaded Markdown document. Used dynamically for LLM prompt engineering and Vector RAG evaluation.
        </p>
      </div>

      {/* Category Weights Overview */}
      {criteriaData && criteriaData.category_weights && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(criteriaData.category_weights).map(([catName, weight]) => (
            <div key={catName} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm flex justify-between items-center">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Category Weight</p>
                <h3 className="text-sm font-bold text-slate-900 mt-0.5">{catName}</h3>
              </div>
              <div className="text-lg font-extrabold text-blue-700 bg-blue-50 border border-blue-100 px-3 py-1 rounded-lg">
                {Math.round(weight * 100)}%
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Auto-Fail Triggers Card */}
      {criteriaData && criteriaData.auto_fail_rules && criteriaData.auto_fail_rules.length > 0 && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-5">
          <h3 className="font-bold text-xs uppercase tracking-wider text-rose-800 flex items-center gap-1.5 mb-3">
            <ShieldAlert size={15} /> Auto-Fail Circuit Breakers (Instant 0 Score)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {criteriaData.auto_fail_rules.map((rule, idx) => (
              <div key={idx} className="bg-white p-3 rounded-lg border border-rose-200 shadow-2xs">
                <strong className="text-xs text-rose-900 block font-semibold">{rule.name}</strong>
                <p className="text-xs text-slate-600 mt-0.5">{rule.description || rule.trigger}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Line Items List */}
      {criteriaData && criteriaData.categories && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <h3 className="font-bold text-sm text-slate-900 mb-4 flex items-center gap-2">
            <Activity size={16} className="text-blue-600" /> Line Items & Evaluation Criteria
          </h3>
          <div className="space-y-4">
            {criteriaData.categories.map((cat, cIdx) => (
              <div key={cIdx} className="border border-slate-200 rounded-xl p-4 bg-slate-50/50">
                <h4 className="font-bold text-xs text-slate-800 mb-3 flex items-center justify-between">
                  <span>{cat.name}</span>
                  <span className="text-[11px] font-semibold bg-white border border-slate-200 px-2 py-0.5 rounded text-slate-600">
                    {cat.weight_percentage}%
                  </span>
                </h4>
                <div className="space-y-2">
                  {(cat.line_items || []).map((item, iIdx) => (
                    <div key={iIdx} className="bg-white p-3 rounded-lg border border-slate-200 text-xs shadow-2xs">
                      <span className="font-semibold text-slate-900 block">{item.name}</span>
                      <p className="text-slate-600 mt-0.5">{item.description}</p>
                      {item.verbatim_spiels && item.verbatim_spiels.length > 0 && (
                        <div className="mt-2 text-blue-900 bg-blue-50 border border-blue-100 p-2.5 rounded text-[11px]">
                          <span className="font-semibold block mb-0.5">Required Verbatim Spiel:</span>
                          {item.verbatim_spiels.map((s, sIdx) => (
                            <p key={sIdx} className="italic text-blue-800">"{s}"</p>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Vector DB Policy Chunks */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <h3 className="font-bold text-sm text-slate-900 mb-4 flex items-center gap-2">
          <Database size={16} className="text-blue-600" /> Vector Database Knowledge Chunks ({policiesData.length})
        </h3>
        {policiesData.length === 0 ? (
          <p className="text-xs text-slate-500">No policy chunks indexed yet for this tenant.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {policiesData.map((p, idx) => (
              <div key={idx} className="bg-slate-50 border border-slate-200 p-4 rounded-xl text-xs">
                <h4 className="font-bold text-slate-900 text-xs mb-1">{p.title}</h4>
                <p className="text-slate-600 leading-relaxed">{p.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
