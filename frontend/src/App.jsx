import React, { useState, useEffect } from 'react';
import { 
  FileText, Upload, CheckCircle, AlertTriangle, XCircle, 
  Sparkles, Layers, ShieldAlert, BookOpen, Clock, Activity, 
  Database, RefreshCw, Plus, ChevronRight, Download, Copy, Play, Check, Trash2, FileMinus
} from 'lucide-react';

const API_BASE = 'http://localhost:8000';

export default function App() {
  const [tenants, setTenants] = useState([]);
  const [selectedTenant, setSelectedTenant] = useState('S-NET');
  const [activeTab, setActiveTab] = useState('upload'); // upload | criteria | test | history
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  
  // Data states
  const [documents, setDocuments] = useState([]);
  const [markdownData, setMarkdownData] = useState({ markdown: '', filename: '' });
  const [criteriaData, setCriteriaData] = useState(null);
  const [policiesData, setPoliciesData] = useState([]);
  const [historyData, setHistoryData] = useState([]);
  
  // Testing state
  const [channel, setChannel] = useState('Call');
  const [transcript, setTranscript] = useState('');
  const [evalResult, setEvalResult] = useState(null);
  const [evalLoading, setEvalLoading] = useState(false);

  // New Tenant Modal
  const [showNewTenantModal, setShowNewTenantModal] = useState(false);
  const [newTenantId, setNewTenantId] = useState('');
  const [newTenantName, setNewTenantName] = useState('');

  // Initial load
  useEffect(() => {
    fetchTenants();
  }, []);

  // When tenant changes, fetch its data
  useEffect(() => {
    if (selectedTenant) {
      fetchDocuments();
      fetchMarkdown();
      fetchCriteria();
      fetchPolicies();
      fetchHistory();
    }
  }, [selectedTenant]);

  const fetchTenants = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tenants`);
      const data = await res.json();
      setTenants(data);
      if (data.length > 0 && !selectedTenant) {
        setSelectedTenant(data[0].id);
      }
    } catch (e) {
      console.error('Failed to fetch tenants:', e);
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tenants/${selectedTenant}/documents`);
      const data = await res.json();
      setDocuments(data);
    } catch (e) {
      console.error('Failed to fetch documents:', e);
    }
  };

  const fetchMarkdown = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tenants/${selectedTenant}/markdown`);
      const data = await res.json();
      setMarkdownData(data);
    } catch (e) {
      console.error('Failed to fetch markdown:', e);
    }
  };

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

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/evaluations?tenant_id=${selectedTenant}`);
      const data = await res.json();
      setHistoryData(data);
    } catch (e) {
      console.error('Failed to fetch history:', e);
    }
  };

  const handleCreateTenant = async (e) => {
    e.preventDefault();
    if (!newTenantId || !newTenantName) return;
    try {
      await fetch(`${API_BASE}/api/tenants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: newTenantId.trim(), name: newTenantName.trim() }),
      });
      await fetchTenants();
      setSelectedTenant(newTenantId.trim());
      setShowNewTenantModal(false);
      setNewTenantId('');
      setNewTenantName('');
    } catch (err) {
      alert('Error creating company: ' + err.message);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setLoading(true);
    setUploadStatus('Uploading & Converting PDF to Lossless Markdown...');

    try {
      const res = await fetch(`${API_BASE}/api/tenants/${selectedTenant}/upload-pdf`, {
        method: 'POST',
        body: formData,
      });
      const result = await res.json();
      if (res.ok) {
        setUploadStatus(`Success! Converted ${result.page_count} pages. Extracted criteria & indexed ${result.policy_chunks_count} policy chunks.`);
        fetchDocuments();
        fetchMarkdown();
        fetchCriteria();
        fetchPolicies();
      } else {
        setUploadStatus('Error: ' + (result.detail || 'Upload failed'));
      }
    } catch (err) {
      setUploadStatus('Network error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDocument = async (docId, filename) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}"?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/tenants/${selectedTenant}/documents/${docId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        fetchDocuments();
        fetchMarkdown();
        fetchCriteria();
        fetchPolicies();
      }
    } catch (err) {
      alert('Delete failed: ' + err.message);
    }
  };

  const handleClearKnowledgeBase = async () => {
    if (!window.confirm(`Are you sure you want to completely CLEAR all documents and Vector KB for "${selectedTenant}"?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/tenants/${selectedTenant}/knowledge-base`, {
        method: 'DELETE',
      });
      if (res.ok) {
        fetchDocuments();
        fetchMarkdown();
        fetchCriteria();
        fetchPolicies();
        alert('Knowledge base cleared successfully.');
      }
    } catch (err) {
      alert('Clear failed: ' + err.message);
    }
  };

  const loadSample = (type) => {
    if (type === 'compliant_call') {
      setChannel('Call');
      setTranscript(
`[00:00] Client: Hello, my internet connection is completely down and I work from home!
[00:04] Agent: Thank you for calling S-NET Communications. My name is Alex, how can I help you today?
[00:10] Client: The internet light on my router is blinking red. My account is John Doe, Acme Corp at 104 North Avenue.
[00:18] Agent: Thank you for verifying your name and account details, John. I understand your internet is down and you have a blinking red light on the router. Let me run a line diagnostic right now.
[00:28] Agent: Please allow me 2 minutes to run a stability test on your line. May I put you on hold?
[00:32] Client: Sure, go ahead.
[00:35] [Hold: 1m 20s]
[01:55] Agent: Thank you for patiently waiting on the line. I found a line fault on our exchange side. Since you rent the router from S-NET, I will dispatch a technician at no cost to you today between 2 PM and 4 PM.
[02:15] Client: That is very fast and helpful, thank you so much!
[02:20] Agent: You are very welcome. I will transfer you to our brief 1-question survey regarding your call experience today. Thank you for Choosing S-NET and have a great day.`
      );
    } else if (type === 'hold_violation_call') {
      setChannel('Call');
      setTranscript(
`[00:00] Client: Hi, I need help with my phone bill.
[00:08] Agent: What is your number?
[00:12] Client: It is 555-0199.
[00:15] Agent: Hold on.
[00:20] [Hold: 4m 45s without any refresh or update]
[05:05] Agent: Okay, your bill is $95.
[05:10] [Dead Air: 35 seconds]
[05:45] Client: Hello? Are you still there?
[05:50] Agent: Yeah, you have to pay by Friday. Bye.`
      );
    } else if (type === 'autofail_call') {
      setChannel('Call');
      setTranscript(
`[00:00] Client: Why was I charged an extra $75 fee on my S-NET bill this month?
[00:05] Agent: You clearly didn't read your contract terms.
[00:10] Client: Excuse me? That is completely unacceptable. I want to speak to your supervisor right now!
[00:16] Agent: Supervisors do not take these calls, and asking for a manager will not change anything.
[00:24] Client: I am going to cancel my entire company subscription.
[00:29] Agent: Whatever, get lost then. I don't have time for this.`
      );
    } else if (type === 'compliant_email') {
      setChannel('Email');
      setTranscript(
`[10:00] Customer Email:
To: support@snet.com
Subject: Cannot access Zoho integration from office location

Hi Support,
Our team cannot connect to the Zoho phone integration since this morning. Error code 403.
Account: Acme Corp, Location: Chicago Office.
Contact: Sarah Miller (sarah@acme.com, 555-3211)

[10:08] Agent Response Email:
Dear Sarah Miller,

Thank you for reaching out to S-NET Communications Support.

I understand that your Chicago office team is unable to connect to the Zoho phone integration and is encountering Error 403. I have verified your account and location in our system.

I have refreshed your API token and whitelisted your Chicago office IP range per our standard ARE process. Please ask your team to restart the Zoho integration widget.

Ticket #SNET-88492 has been generated for tracking. We will follow up within 2 hours to ensure full resolution.

Thank you for Choosing S-NET and have a great day!

Best regards,
S-NET Technical Support Team`
      );
    } else if (type === 'compliant_chat') {
      setChannel('Chat');
      setTranscript(
`[00:00] Customer: Hi, our desk phones are not receiving incoming calls.
[00:18] Agent: Thank you for contacting S-NET Communications. My name is Sam, how can I assist you today?
[00:26] Customer: We are TechCorp, account #4992. I am David Brown (david@techcorp.com).
[00:40] Agent: Hello David, thank you for confirming TechCorp and your contact details. I understand your desk phones are not receiving inbound calls. Let me check the call forwarding rules right now.
[01:10] Agent: I found that call forwarding was accidentally toggled on to an inactive extension. I have restored standard routing. Could you test an inbound call now?
[01:35] Customer: Tested now and it rings on all desk phones! Thanks!
[01:45] Agent: Excellent! I will email your ticket reference #SNET-94812 shortly. Thank you for Choosing S-NET and have a great day!`
      );
    }
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
          agent_name: 'Agent'
        }),
      });
      const data = await res.json();
      setEvalResult(data);
      fetchHistory();
    } catch (err) {
      alert('Evaluation error: ' + err.message);
    } finally {
      setEvalLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0f17] text-slate-100 flex flex-col">
      {/* Top Navbar */}
      <header className="border-b border-[#24324f] bg-[#131b2e]/80 backdrop-blur-md sticky top-0 z-50 px-6 py-4 flex flex-wrap justify-between items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-400 to-blue-500 flex items-center justify-center font-black text-black text-xl shadow-lg shadow-teal-500/20">
            QA
          </div>
          <div>
            <h1 className="font-bold text-lg text-white leading-tight flex items-center gap-2">
              Multi-Tenant QA Service
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/20">
                PostgreSQL + RAG
              </span>
            </h1>
            <p className="text-xs text-slate-400">Layout-Aware PDF Converter, Vector RAG & Gemma 3 4B Evaluator</p>
          </div>
        </div>

        {/* Company / Tenant Selector */}
        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-400 font-medium">Active Company:</label>
          <div className="relative">
            <select
              value={selectedTenant}
              onChange={(e) => setSelectedTenant(e.target.value)}
              className="bg-[#1c273e] text-white border border-[#2e3d5b] rounded-lg px-3 py-1.5 text-sm font-semibold focus:outline-none focus:border-teal-400 pr-8 cursor-pointer"
            >
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.id})
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() => setShowNewTenantModal(true)}
            className="flex items-center gap-1.5 bg-teal-500/10 hover:bg-teal-500/20 text-teal-400 border border-teal-500/30 rounded-lg px-3 py-1.5 text-xs font-semibold transition"
          >
            <Plus size={14} /> New Company
          </button>
        </div>

        {/* Nav Tabs */}
        <nav className="flex items-center gap-1 bg-[#0b0f17] p-1 rounded-xl border border-[#24324f]">
          <button
            onClick={() => setActiveTab('upload')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === 'upload'
                ? 'bg-gradient-to-r from-teal-500 to-blue-500 text-black shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Upload size={14} /> PDF & Markdown
          </button>
          <button
            onClick={() => setActiveTab('criteria')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === 'criteria'
                ? 'bg-gradient-to-r from-teal-500 to-blue-500 text-black shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Layers size={14} /> Criteria & Policies
          </button>
          <button
            onClick={() => setActiveTab('test')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === 'test'
                ? 'bg-gradient-to-r from-teal-500 to-blue-500 text-black shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Sparkles size={14} /> Live QA Test
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === 'history'
                ? 'bg-gradient-to-r from-teal-500 to-blue-500 text-black shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Clock size={14} /> History ({historyData.length})
          </button>
        </nav>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl w-full mx-auto p-6 flex-1">
        {/* ========================================================================= */}
        {/* TAB 1: PDF INGESTION & MARKDOWN VIEWER */}
        {/* ========================================================================= */}
        {activeTab === 'upload' && (
          <div className="space-y-6 animate-fadeIn">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <FileText className="text-teal-400" /> Lossless PDF to Markdown Ingestion
                </h2>
                <p className="text-sm text-slate-400">
                  Upload company QA guideline PDF. Tables and spiels are extracted losslessly into Markdown, criteria is parsed to JSON, and policies are indexed into Vector DB.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleClearKnowledgeBase}
                  className="flex items-center gap-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-lg px-3 py-1.5 text-xs font-semibold transition"
                >
                  <Trash2 size={14} /> Clear {selectedTenant} Knowledge Base
                </button>
              </div>
            </div>

            {/* Upload Box */}
            <div className="border-2 border-dashed border-[#2e3d5b] hover:border-teal-400/50 bg-[#131b2e] rounded-2xl p-8 text-center transition cursor-pointer relative">
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileUpload}
                disabled={loading}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
              <div className="flex flex-col items-center justify-center gap-3">
                <div className="w-14 h-14 rounded-2xl bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400">
                  {loading ? <RefreshCw className="animate-spin" size={28} /> : <Upload size={28} />}
                </div>
                <div>
                  <h3 className="font-semibold text-white text-base">
                    {loading ? 'Processing Document...' : `Click or Drag & Drop QA Guideline PDF for ${selectedTenant}`}
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">Supports multi-page PDFs with tables, category weights, and SLAs</p>
                </div>
              </div>
            </div>

            {uploadStatus && (
              <div className={`p-4 rounded-xl text-xs flex items-center gap-3 border ${
                uploadStatus.startsWith('Error') 
                  ? 'bg-rose-500/10 text-rose-300 border-rose-500/30'
                  : 'bg-teal-500/10 text-teal-300 border-teal-500/30'
              }`}>
                {uploadStatus.startsWith('Error') ? <AlertTriangle size={16} /> : <CheckCircle size={16} />}
                <span>{uploadStatus}</span>
              </div>
            )}

            {/* Uploaded Documents List */}
            {documents.length > 0 && (
              <div className="bg-[#131b2e] border border-[#24324f] rounded-2xl p-5">
                <h3 className="font-bold text-sm text-white mb-3 flex items-center gap-2">
                  <BookOpen size={16} className="text-teal-400" /> Uploaded Company Documents ({documents.length})
                </h3>
                <div className="divide-y divide-[#24324f]">
                  {documents.map((doc) => (
                    <div key={doc.id} className="py-3 flex justify-between items-center gap-4 text-xs">
                      <div>
                        <strong className="text-white block text-sm">{doc.filename}</strong>
                        <span className="text-slate-400">
                          {doc.page_count} page(s) · {doc.char_count.toLocaleString()} characters · Uploaded {new Date(doc.uploaded_at).toLocaleString()}
                        </span>
                      </div>
                      <button
                        onClick={() => handleDeleteDocument(doc.id, doc.filename)}
                        className="flex items-center gap-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 px-3 py-1.5 rounded-lg text-xs font-semibold transition"
                      >
                        <Trash2 size={13} /> Delete File
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Converted Markdown Viewer */}
            <div className="bg-[#131b2e] border border-[#24324f] rounded-2xl overflow-hidden shadow-xl">
              <div className="bg-[#1c273e] px-6 py-3 border-b border-[#24324f] flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <BookOpen size={16} className="text-teal-400" />
                  <span className="font-bold text-sm text-white">
                    Converted Markdown ({markdownData.filename || 'No document selected'})
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => navigator.clipboard.writeText(markdownData.markdown)}
                    className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 text-xs px-3 py-1.5 rounded-md border border-slate-700 text-slate-300"
                  >
                    <Copy size={12} /> Copy MD
                  </button>
                </div>
              </div>
              <div className="p-6 max-h-[600px] overflow-y-auto">
                {markdownData.markdown ? (
                  <pre className="font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
                    {markdownData.markdown}
                  </pre>
                ) : (
                  <div className="text-center py-12 text-slate-500 text-sm">
                    No Markdown content available yet. Upload a PDF guideline to inspect the extracted Markdown.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: CRITERIA & POLICY INSPECTOR */}
        {/* ========================================================================= */}
        {activeTab === 'criteria' && (
          <div className="space-y-6 animate-fadeIn">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Layers className="text-teal-400" /> Parsed Criteria & Policy Knowledge Base
              </h2>
              <p className="text-sm text-slate-400">
                Extracted from the company's uploaded document. Criteria are injected into LLM evaluation prompts, while policies are indexed in Vector DB for RAG retrieval.
              </p>
            </div>

            {/* Category Weights Overview */}
            {criteriaData && criteriaData.category_weights && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {Object.entries(criteriaData.category_weights).map(([catName, weight]) => (
                  <div key={catName} className="bg-[#131b2e] border border-[#24324f] rounded-xl p-5 flex justify-between items-center">
                    <div>
                      <p className="text-xs text-slate-400 font-medium">Evaluation Category</p>
                      <h3 className="text-base font-bold text-white mt-0.5">{catName}</h3>
                    </div>
                    <div className="text-xl font-extrabold text-teal-400 bg-teal-500/10 border border-teal-500/20 px-3 py-1.5 rounded-lg">
                      {Math.round(weight * 100)}%
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Auto-Fail Triggers Card */}
            {criteriaData && criteriaData.auto_fail_rules && criteriaData.auto_fail_rules.length > 0 && (
              <div className="bg-rose-950/20 border border-rose-500/30 rounded-xl p-5">
                <h3 className="font-bold text-sm text-rose-300 flex items-center gap-2">
                  <ShieldAlert size={16} /> Auto-Fail Circuit Breakers (Instant 0 Score)
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  {criteriaData.auto_fail_rules.map((rule, idx) => (
                    <div key={idx} className="bg-[#131b2e]/60 p-3 rounded-lg border border-rose-500/20">
                      <strong className="text-xs text-rose-400 block">{rule.name}</strong>
                      <p className="text-xs text-slate-400 mt-1">{rule.description || rule.trigger}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Line Items List */}
            {criteriaData && criteriaData.categories && (
              <div className="bg-[#131b2e] border border-[#24324f] rounded-2xl p-6">
                <h3 className="font-bold text-base text-white mb-4 flex items-center gap-2">
                  <Activity size={18} className="text-teal-400" /> Line Items & Evaluation Criteria
                </h3>
                <div className="space-y-4">
                  {criteriaData.categories.map((cat, cIdx) => (
                    <div key={cIdx} className="border border-[#24324f] rounded-xl p-4 bg-[#1c273e]/40">
                      <h4 className="font-bold text-sm text-teal-400 mb-2">{cat.name} ({cat.weight_percentage}%)</h4>
                      <div className="space-y-2">
                        {(cat.line_items || []).map((item, iIdx) => (
                          <div key={iIdx} className="bg-[#0b0f17] p-3 rounded-lg border border-slate-800 text-xs">
                            <span className="font-semibold text-white block">{item.name}</span>
                            <p className="text-slate-400 mt-0.5">{item.description}</p>
                            {item.verbatim_spiels && item.verbatim_spiels.length > 0 && (
                              <div className="mt-2 text-teal-300 bg-teal-950/30 border border-teal-500/20 p-2 rounded">
                                <span className="font-semibold text-[11px] block">Required Verbatim Spiel:</span>
                                {item.verbatim_spiels.map((s, sIdx) => (
                                  <p key={sIdx} className="italic">"{s}"</p>
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
            <div className="bg-[#131b2e] border border-[#24324f] rounded-2xl p-6">
              <h3 className="font-bold text-base text-white mb-4 flex items-center gap-2">
                <Database size={18} className="text-teal-400" /> Vector Database Knowledge Chunks ({policiesData.length})
              </h3>
              {policiesData.length === 0 ? (
                <p className="text-xs text-slate-500">No policy chunks indexed yet for this tenant.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {policiesData.map((p, idx) => (
                    <div key={idx} className="bg-[#1c273e] border border-[#2e3d5b] p-4 rounded-xl text-xs">
                      <h4 className="font-bold text-teal-300 text-sm mb-1">{p.title}</h4>
                      <p className="text-slate-300 leading-relaxed">{p.content}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: LIVE QA TESTING PAGE */}
        {/* ========================================================================= */}
        {activeTab === 'test' && (
          <div className="space-y-6 animate-fadeIn">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Sparkles className="text-teal-400" /> Live QA Evaluation against Company Criteria & RAG
              </h2>
              <p className="text-sm text-slate-400">
                Paste a call, email, or chat transcript to run real-time evaluation using Gemma 3 4B, RoBERTa tone checks, and Vector RAG retrieval.
              </p>
            </div>

            {/* Presets & Channel Picker */}
            <div className="space-y-3 bg-[#131b2e] p-4 rounded-xl border border-[#24324f]">
              <div className="flex flex-wrap justify-between items-center gap-3">
                <div className="flex items-center gap-3">
                  <label className="text-xs font-semibold text-slate-400">Channel:</label>
                  <div className="flex gap-1 bg-[#0b0f17] p-1 rounded-lg border border-slate-800">
                    {['Call', 'Email', 'Chat'].map((c) => (
                      <button
                        key={c}
                        onClick={() => setChannel(c)}
                        className={`px-3 py-1 rounded text-xs font-semibold transition ${
                          channel === c ? 'bg-teal-500 text-black shadow' : 'text-slate-400 hover:text-white'
                        }`}
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400 font-medium">Quick Preset Transcripts:</span>
                </div>
              </div>

              {/* Sample Buttons Grid */}
              <div className="flex flex-wrap gap-2 pt-1 border-t border-[#24324f]">
                <button
                  onClick={() => loadSample('compliant_call')}
                  className="bg-emerald-950/40 hover:bg-emerald-900/60 text-xs px-3 py-1.5 rounded-lg border border-emerald-500/30 text-emerald-300 font-medium transition"
                >
                  📞 Call: 100% Compliant (Verbatim Spiels & SLA)
                </button>
                <button
                  onClick={() => loadSample('hold_violation_call')}
                  className="bg-amber-950/40 hover:bg-amber-900/60 text-xs px-3 py-1.5 rounded-lg border border-amber-500/30 text-amber-300 font-medium transition"
                >
                  📞 Call: Hold & Dead Air Violation
                </button>
                <button
                  onClick={() => loadSample('autofail_call')}
                  className="bg-rose-950/40 hover:bg-rose-900/60 text-xs px-3 py-1.5 rounded-lg border border-rose-500/30 text-rose-300 font-medium transition"
                >
                  ⚠ Call: Auto-Fail Breach (Discourtesy/Escalation Refusal)
                </button>
                <button
                  onClick={() => loadSample('compliant_email')}
                  className="bg-sky-950/40 hover:bg-sky-900/60 text-xs px-3 py-1.5 rounded-lg border border-sky-500/30 text-sky-300 font-medium transition"
                >
                  ✉️ Email: 10m SLA & Template Compliant
                </button>
                <button
                  onClick={() => loadSample('compliant_chat')}
                  className="bg-purple-950/40 hover:bg-purple-900/60 text-xs px-3 py-1.5 rounded-lg border border-purple-500/30 text-purple-300 font-medium transition"
                >
                  💬 Chat: Fast Response & Verification
                </button>
              </div>
            </div>

            {/* Transcript Textarea */}
            <div className="bg-[#131b2e] border border-[#24324f] rounded-2xl p-4">
              <textarea
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                placeholder="Paste transcript here (e.g., [00:00] Agent: Thank you for calling S-NET... / [00:05] Client: Hi...)"
                rows={10}
                className="w-full bg-[#0b0f17] border border-[#2e3d5b] rounded-xl p-4 text-xs font-mono text-slate-200 focus:outline-none focus:border-teal-400"
              />
              <div className="flex justify-between items-center mt-3">
                <span className="text-xs text-slate-500">
                  Target Company: <strong className="text-teal-400">{selectedTenant}</strong> · Model: <strong className="text-teal-400">gemma3:4b</strong>
                </span>
                <button
                  onClick={handleEvaluate}
                  disabled={evalLoading || !transcript.trim()}
                  className="flex items-center gap-2 bg-gradient-to-r from-teal-400 to-blue-500 hover:from-teal-300 hover:to-blue-400 disabled:opacity-50 text-black font-bold px-6 py-2.5 rounded-xl text-xs shadow-lg shadow-teal-500/20 transition cursor-pointer"
                >
                  {evalLoading ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
                  {evalLoading ? 'Evaluating with Gemma & RAG...' : 'Run Dynamic QA Analysis'}
                </button>
              </div>
            </div>

            {/* Evaluation Results Card */}
            {evalResult && (
              <div className="space-y-6 animate-fadeIn">
                {/* Score Banner */}
                <div className={`p-6 rounded-2xl border flex flex-wrap justify-between items-center gap-6 ${
                  evalResult.is_auto_fail 
                    ? 'bg-rose-950/30 border-rose-500/40 text-rose-200' 
                    : 'bg-[#131b2e] border-teal-500/30 text-white'
                }`}>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Overall QA Score</span>
                      {evalResult.is_auto_fail && (
                        <span className="px-2.5 py-0.5 rounded-full bg-rose-500 text-black font-black text-xs">
                          AUTO-FAIL TRIGGERED
                        </span>
                      )}
                    </div>
                    <div className="text-4xl font-black mt-1 flex items-baseline gap-2">
                      <span className={evalResult.is_auto_fail ? 'text-rose-400' : 'text-teal-400'}>
                        {evalResult.final_score}
                      </span>
                      <span className="text-sm text-slate-400">/ 100</span>
                    </div>
                    {evalResult.auto_fail_reason && (
                      <p className="text-xs text-rose-300 mt-2 font-medium">
                        ⚠ {evalResult.auto_fail_reason}
                      </p>
                    )}
                  </div>

                  {/* Category Scores */}
                  {evalResult.category_scores && (
                    <div className="flex flex-wrap gap-4">
                      {Object.entries(evalResult.category_scores).map(([cat, score]) => (
                        <div key={cat} className="bg-[#1c273e] px-4 py-2 rounded-xl border border-[#2e3d5b]">
                          <span className="text-[11px] text-slate-400 block">{cat}</span>
                          <span className="text-base font-bold text-white">{score} / 100</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Scorecard Line Items */}
                <div className="bg-[#131b2e] border border-[#24324f] rounded-2xl p-6">
                  <h3 className="font-bold text-base text-white mb-4">Gemma 3 4B Agent Scorecard Breakdown</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-[#24324f] text-slate-400 font-semibold">
                          <th className="pb-3">Line Item</th>
                          <th className="pb-3">Category</th>
                          <th className="pb-3">Rating</th>
                          <th className="pb-3">Score</th>
                          <th className="pb-3">Reason / Evidence</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#24324f]/60">
                        {(evalResult.scorecard || []).map((item, idx) => (
                          <tr key={idx} className="hover:bg-slate-800/30">
                            <td className="py-3 font-semibold text-white">{item.name}</td>
                            <td className="py-3 text-slate-400">{item.category}</td>
                            <td className="py-3">
                              <span className={`px-2.5 py-0.5 rounded-full font-bold text-[11px] ${
                                item.rating === 'PASS' 
                                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                  : item.rating === 'PARTIAL'
                                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              }`}>
                                {item.rating}
                              </span>
                            </td>
                            <td className="py-3 font-bold text-white">{item.score}</td>
                            <td className="py-3 text-slate-300">{item.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Summary & Suggestions Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-[#131b2e] border border-[#24324f] rounded-2xl p-5">
                    <h3 className="font-bold text-sm text-teal-400 mb-2">Call Summary</h3>
                    <p className="text-xs text-slate-300 leading-relaxed">{evalResult.summary}</p>
                  </div>

                  <div className="bg-[#131b2e] border border-[#24324f] rounded-2xl p-5">
                    <h3 className="font-bold text-sm text-teal-400 mb-2">Agent Coaching Suggestions</h3>
                    <div className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
                      {evalResult.suggestions}
                    </div>
                  </div>
                </div>

                {/* RAG Matched Policies */}
                {evalResult.matched_policies && evalResult.matched_policies.length > 0 && (
                  <div className="bg-[#131b2e] border border-[#24324f] rounded-2xl p-5">
                    <h3 className="font-bold text-sm text-teal-400 mb-3 flex items-center gap-2">
                      <Database size={16} /> RAG Retrieved Policies for Context
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {evalResult.matched_policies.map((p, idx) => (
                        <div key={idx} className="bg-[#1c273e] p-3 rounded-xl border border-[#2e3d5b] text-xs">
                          <div className="flex justify-between items-center mb-1">
                            <strong className="text-white">{p.title}</strong>
                            <span className="text-[10px] text-teal-400 font-mono">Sim: {p.similarity}</span>
                          </div>
                          <p className="text-slate-400">{p.content}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: EVALUATION HISTORY */}
        {/* ========================================================================= */}
        {activeTab === 'history' && (
          <div className="space-y-6 animate-fadeIn">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Clock className="text-teal-400" /> Evaluation Audit History ({selectedTenant})
              </h2>
              <p className="text-sm text-slate-400">Stored records in PostgreSQL table `evaluation_reports`.</p>
            </div>

            <div className="bg-[#131b2e] border border-[#24324f] rounded-2xl overflow-hidden shadow-xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="bg-[#1c273e] text-slate-400 border-b border-[#24324f] font-semibold">
                      <th className="p-4">Report ID</th>
                      <th className="p-4">Channel</th>
                      <th className="p-4">Final Score</th>
                      <th className="p-4">Status</th>
                      <th className="p-4">Date</th>
                      <th className="p-4">Summary</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#24324f]">
                    {historyData.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="text-center py-8 text-slate-500">
                          No evaluation records found yet.
                        </td>
                      </tr>
                    ) : (
                      historyData.map((row) => (
                        <tr key={row.id} className="hover:bg-slate-800/30">
                          <td className="p-4 font-mono text-teal-300">{row.id.slice(0, 8)}...</td>
                          <td className="p-4 text-white font-medium">{row.channel}</td>
                          <td className="p-4 font-bold text-sm text-white">{row.final_score}</td>
                          <td className="p-4">
                            <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                              row.is_auto_fail
                                ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                                : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            }`}>
                              {row.is_auto_fail ? 'AUTO-FAIL' : 'PASSED'}
                            </span>
                          </td>
                          <td className="p-4 text-slate-400">{new Date(row.created_at).toLocaleString()}</td>
                          <td className="p-4 text-slate-300 max-w-md truncate">{row.summary}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* New Company Modal */}
      {showNewTenantModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-[#131b2e] border border-[#24324f] rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white mb-1">Create New Company / Tenant</h3>
            <p className="text-xs text-slate-400 mb-4">Add a new company namespace for isolated criteria and vector RAG storage.</p>
            <form onSubmit={handleCreateTenant} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Company Code / ID (e.g. S-NET, AcmeCorp):</label>
                <input
                  type="text"
                  required
                  value={newTenantId}
                  onChange={(e) => setNewTenantId(e.target.value)}
                  placeholder="e.g. S-NET"
                  className="w-full bg-[#0b0f17] border border-[#2e3d5b] rounded-lg p-2.5 text-white focus:outline-none focus:border-teal-400"
                />
              </div>
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Company Display Name:</label>
                <input
                  type="text"
                  required
                  value={newTenantName}
                  onChange={(e) => setNewTenantName(e.target.value)}
                  placeholder="e.g. S-NET Communications"
                  className="w-full bg-[#0b0f17] border border-[#2e3d5b] rounded-lg p-2.5 text-white focus:outline-none focus:border-teal-400"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowNewTenantModal(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-teal-500 hover:bg-teal-400 text-black font-bold"
                >
                  Create Company
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="text-center py-6 text-slate-500 text-xs border-t border-[#24324f]">
        Automated Multi-Tenant QA Service · Powered by PostgreSQL, MiniLM RAG & Gemma 3 4B
      </footer>
    </div>
  );
}
