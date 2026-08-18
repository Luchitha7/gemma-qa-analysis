import React, { useState, useEffect } from 'react';
import { useTenant } from '../context/TenantContext';
import { Sparkles, FileCode, Upload, Play, RefreshCw, Database } from 'lucide-react';

export default function LiveQAPage() {
  const { selectedTenant, API_BASE } = useTenant();
  const [sampleFiles, setSampleFiles] = useState([]);
  const [selectedSampleFile, setSelectedSampleFile] = useState('');
  const [selectedSampleMeta, setSelectedSampleMeta] = useState(null);

  const [channel, setChannel] = useState('Call');
  const [agentName, setAgentName] = useState('Alex');
  const [transcript, setTranscript] = useState('');
  const [evalResult, setEvalResult] = useState(null);
  const [evalLoading, setEvalLoading] = useState(false);

  const fetchSamples = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/samples`);
      const data = await res.json();
      setSampleFiles(data);
    } catch (e) {
      console.error('Failed to fetch samples:', e);
    }
  };

  useEffect(() => {
    fetchSamples();
  }, []);

  const handleSelectSampleJSON = (filename) => {
    setSelectedSampleFile(filename);
    const sample = sampleFiles.find(s => s.filename === filename);
    if (sample) {
      setTranscript(sample.transcript || '');
      setChannel(sample.channel || 'Call');
      setAgentName(sample.agent_name || 'Agent');
      setSelectedSampleMeta(sample);
    }
  };

  const handleCustomJSONUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const parsed = JSON.parse(evt.target.result);
        setTranscript(parsed.transcript || evt.target.result);
        if (parsed.channel) setChannel(parsed.channel);
        if (parsed.agent_name) setAgentName(parsed.agent_name);
        setSelectedSampleFile(file.name);
        setSelectedSampleMeta(parsed);
      } catch (err) {
        setTranscript(evt.target.result);
        setSelectedSampleFile(file.name);
      }
    };
    reader.readAsText(file);
  };

  const handleEvaluate = async () => {
    if (!transcript.trim()) return;
    setEvalLoading(true);
    setEvalResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/tenants/${selectedTenant}/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcript: transcript,
          channel: channel,
          agent_name: agentName
        }),
      });
      const data = await res.json();
      setEvalResult(data);
    } catch (err) {
      alert('Evaluation error: ' + err.message);
    } finally {
      setEvalLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <Sparkles size={20} className="text-blue-600" /> Live QA Interaction Analysis
        </h2>
        <p className="text-xs text-slate-500">
          Select a sample JSON file from <code className="text-slate-800 bg-slate-200 px-1 py-0.5 rounded font-mono">inputs/</code>, upload a custom JSON, or paste any transcript to evaluate.
        </p>
      </div>

      {/* Interaction Input Configuration Card */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* 1. Select Sample JSON from inputs/ */}
          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1.5 flex items-center gap-1.5">
              <FileCode size={14} className="text-blue-600" /> Select Sample File (inputs/):
            </label>
            <select
              value={selectedSampleFile}
              onChange={(e) => handleSelectSampleJSON(e.target.value)}
              className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-2xs"
            >
              <option value="">-- Choose from inputs/ folder --</option>
              {sampleFiles.map((s) => (
                <option key={s.filename} value={s.filename}>
                  {s.title} ({s.filename})
                </option>
              ))}
            </select>
          </div>

          {/* 2. Upload Custom JSON file */}
          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1.5 flex items-center gap-1.5">
              <Upload size={14} className="text-blue-600" /> Or Upload Custom JSON File:
            </label>
            <input
              type="file"
              accept=".json"
              onChange={handleCustomJSONUpload}
              className="w-full text-xs text-slate-500 file:mr-2 file:py-1.5 file:px-3 file:rounded-lg file:border file:border-slate-300 file:text-xs file:font-semibold file:bg-slate-50 file:text-slate-700 hover:file:bg-slate-100 cursor-pointer"
            />
          </div>

          {/* 3. Channel Selector */}
          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1.5">Channel:</label>
            <div className="flex gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200">
              {['Call', 'Email', 'Chat'].map((c) => (
                <button
                  key={c}
                  onClick={() => setChannel(c)}
                  className={`flex-1 py-1 rounded text-xs font-semibold transition cursor-pointer ${
                    channel === c ? 'bg-white text-slate-900 shadow-sm border border-slate-200' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Sample Meta Banner */}
        {selectedSampleMeta && (
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs flex justify-between items-center gap-4">
            <div>
              <span className="font-bold text-slate-900 block">{selectedSampleMeta.title}</span>
              <span className="text-slate-600">{selectedSampleMeta.description}</span>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 bg-white border border-slate-300 rounded text-slate-700 shrink-0">
              {selectedSampleMeta.filename || 'custom.json'}
            </span>
          </div>
        )}
      </div>

      {/* Transcript Textarea Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
        <textarea
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          placeholder="Paste transcript here (e.g., [00:00] Agent: Thank you for calling S-NET... / [00:05] Client: Hi...)"
          rows={10}
          className="w-full bg-slate-50 border border-slate-200 rounded-lg p-4 text-xs font-mono text-slate-900 focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500"
        />
        <div className="flex justify-between items-center mt-4">
          <span className="text-xs text-slate-500">
            Target Company: <strong className="text-slate-800">{selectedTenant}</strong> · Evaluator: <strong className="text-slate-800">Gemma 3 4B</strong>
          </span>
          <button
            onClick={handleEvaluate}
            disabled={evalLoading || !transcript.trim()}
            className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-semibold px-6 py-2.5 rounded-lg text-xs shadow transition cursor-pointer"
          >
            {evalLoading ? <RefreshCw className="animate-spin" size={15} /> : <Play size={15} />}
            {evalLoading ? 'Evaluating with Gemma & RAG...' : 'Run Dynamic QA Analysis'}
          </button>
        </div>
      </div>

      {/* Evaluation Results Breakdown */}
      {evalResult && (
        <div className="space-y-6">
          {/* Score Summary Card */}
          <div className={`p-6 rounded-xl border shadow-sm flex flex-wrap justify-between items-center gap-6 ${
            evalResult.is_auto_fail 
              ? 'bg-rose-50 border-rose-200 text-rose-950' 
              : 'bg-white border-slate-200 text-slate-900'
          }`}>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Overall QA Score</span>
                {evalResult.is_auto_fail && (
                  <span className="px-2 py-0.5 rounded-full bg-rose-600 text-white font-bold text-[10px]">
                    AUTO-FAIL TRIGGERED
                  </span>
                )}
              </div>
              <div className="text-4xl font-extrabold mt-1 flex items-baseline gap-2">
                <span className={evalResult.is_auto_fail ? 'text-rose-600' : 'text-slate-900'}>
                  {evalResult.final_score}
                </span>
                <span className="text-sm text-slate-400 font-normal">/ 100</span>
              </div>
              {evalResult.auto_fail_reason && (
                <p className="text-xs text-rose-700 mt-2 font-medium">
                  ⚠ {evalResult.auto_fail_reason}
                </p>
              )}
            </div>

            {/* Category Scores */}
            {evalResult.category_scores && (
              <div className="flex flex-wrap gap-3">
                {Object.entries(evalResult.category_scores).map(([cat, score]) => (
                  <div key={cat} className="bg-slate-50 px-4 py-2.5 rounded-lg border border-slate-200 text-center">
                    <span className="text-[11px] text-slate-500 block font-medium">{cat}</span>
                    <span className="text-sm font-bold text-slate-900">{score} / 100</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Scorecard Table */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
            <h3 className="font-bold text-sm text-slate-900 mb-4">Gemma 3 4B Scorecard Breakdown</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500 font-semibold bg-slate-50">
                    <th className="p-3">Line Item</th>
                    <th className="p-3">Category</th>
                    <th className="p-3">Rating</th>
                    <th className="p-3">Score</th>
                    <th className="p-3">Audit Reason & Evidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(evalResult.scorecard || []).map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/80">
                      <td className="p-3 font-semibold text-slate-900">{item.name}</td>
                      <td className="p-3 text-slate-500">{item.category}</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                          item.rating === 'PASS' 
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : item.rating === 'PARTIAL'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}>
                          {item.rating}
                        </span>
                      </td>
                      <td className="p-3 font-bold text-slate-900">{item.score}</td>
                      <td className="p-3 text-slate-700">{item.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Summary & Suggestions Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
              <h3 className="font-bold text-xs uppercase tracking-wider text-slate-500 mb-2">Interaction Summary</h3>
              <p className="text-xs text-slate-700 leading-relaxed">{evalResult.summary}</p>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
              <h3 className="font-bold text-xs uppercase tracking-wider text-slate-500 mb-2">Agent Coaching Suggestions</h3>
              <div className="text-xs text-slate-700 whitespace-pre-wrap leading-relaxed">
                {evalResult.suggestions}
              </div>
            </div>
          </div>

          {/* RAG Matched Policies */}
          {evalResult.matched_policies && evalResult.matched_policies.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
              <h3 className="font-bold text-xs uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-2">
                <Database size={15} className="text-blue-600" /> RAG Retrieved Policies for Context
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {evalResult.matched_policies.map((p, idx) => (
                  <div key={idx} className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs">
                    <div className="flex justify-between items-center mb-1">
                      <strong className="text-slate-900 font-semibold">{p.title}</strong>
                      <span className="text-[10px] text-blue-700 font-mono bg-blue-50 border border-blue-100 px-1.5 py-0.5 rounded">
                        Sim: {p.similarity}
                      </span>
                    </div>
                    <p className="text-slate-600">{p.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
