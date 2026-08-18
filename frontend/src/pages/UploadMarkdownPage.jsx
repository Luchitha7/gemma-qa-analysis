import React, { useState, useEffect } from 'react';
import { useTenant } from '../context/TenantContext';
import { FileText, Upload, Trash2, RefreshCw, BookOpen, Copy, AlertTriangle, CheckCircle } from 'lucide-react';

export default function UploadMarkdownPage() {
  const { selectedTenant, API_BASE } = useTenant();
  const [documents, setDocuments] = useState([]);
  const [markdownData, setMarkdownData] = useState({ markdown: '', filename: '' });
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);

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

  useEffect(() => {
    if (selectedTenant) {
      fetchDocuments();
      fetchMarkdown();
    }
  }, [selectedTenant]);

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
        setUploadStatus(`Success! Converted ${result.page_count} pages. Extracted criteria & indexed ${result.policy_chunks_count} policy chunks into Vector DB.`);
        fetchDocuments();
        fetchMarkdown();
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
        alert('Knowledge base cleared successfully.');
      }
    } catch (err) {
      alert('Clear failed: ' + err.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap justify-between items-center gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <FileText size={20} className="text-blue-600" /> Lossless PDF to Markdown Ingestion
          </h2>
          <p className="text-xs text-slate-500">
            Upload company QA guideline PDF documents. Tables, percentages, and spiels are extracted into Markdown and indexed into PostgreSQL and Vector DB.
          </p>
        </div>
        <button
          onClick={handleClearKnowledgeBase}
          className="flex items-center gap-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg px-3 py-1.5 text-xs font-semibold transition cursor-pointer"
        >
          <Trash2 size={13} /> Clear {selectedTenant} Knowledge Base
        </button>
      </div>

      {/* Upload Area */}
      <div className="border-2 border-dashed border-slate-300 hover:border-blue-500 bg-white rounded-xl p-8 text-center transition cursor-pointer relative shadow-sm">
        <input
          type="file"
          accept=".pdf"
          onChange={handleFileUpload}
          disabled={loading}
          className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
        />
        <div className="flex flex-col items-center justify-center gap-2.5">
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
            {loading ? <RefreshCw className="animate-spin" size={24} /> : <Upload size={24} />}
          </div>
          <div>
            <h3 className="font-semibold text-slate-800 text-sm">
              {loading ? 'Processing Document...' : `Click or Drag & Drop Guideline PDF for ${selectedTenant}`}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">Supports multi-page PDFs with tables, category weights, and SLAs</p>
          </div>
        </div>
      </div>

      {uploadStatus && (
        <div className={`p-4 rounded-lg text-xs flex items-center gap-3 border ${
          uploadStatus.startsWith('Error') 
            ? 'bg-rose-50 text-rose-800 border-rose-200'
            : 'bg-emerald-50 text-emerald-800 border-emerald-200'
        }`}>
          {uploadStatus.startsWith('Error') ? <AlertTriangle size={16} /> : <CheckCircle size={16} />}
          <span>{uploadStatus}</span>
        </div>
      )}

      {/* Uploaded Documents List */}
      {documents.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
          <h3 className="font-bold text-xs uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-2">
            <BookOpen size={14} className="text-blue-600" /> Uploaded Company Documents ({documents.length})
          </h3>
          <div className="divide-y divide-slate-100">
            {documents.map((doc) => (
              <div key={doc.id} className="py-3 flex justify-between items-center gap-4 text-xs">
                <div>
                  <strong className="text-slate-900 block text-sm font-semibold">{doc.filename}</strong>
                  <span className="text-slate-500 text-[11px]">
                    {doc.page_count} page(s) · {doc.char_count.toLocaleString()} characters · Uploaded {new Date(doc.uploaded_at).toLocaleString()}
                  </span>
                </div>
                <button
                  onClick={() => handleDeleteDocument(doc.id, doc.filename)}
                  className="flex items-center gap-1 bg-white hover:bg-rose-50 text-rose-600 border border-slate-200 hover:border-rose-200 px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer"
                >
                  <Trash2 size={12} /> Delete
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Markdown Viewer */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="bg-slate-50 px-5 py-3 border-b border-slate-200 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <BookOpen size={15} className="text-slate-700" />
            <span className="font-semibold text-xs text-slate-800">
              Converted Markdown ({markdownData.filename || 'No document selected'})
            </span>
          </div>
          <button
            onClick={() => navigator.clipboard.writeText(markdownData.markdown)}
            className="flex items-center gap-1 bg-white hover:bg-slate-100 text-slate-700 text-xs px-2.5 py-1 rounded border border-slate-200 font-medium cursor-pointer"
          >
            <Copy size={12} /> Copy Markdown
          </button>
        </div>
        <div className="p-6 max-h-[500px] overflow-y-auto bg-slate-900 text-slate-100 rounded-b-xl">
          {markdownData.markdown ? (
            <pre className="font-mono text-xs whitespace-pre-wrap leading-relaxed">
              {markdownData.markdown}
            </pre>
          ) : (
            <div className="text-center py-12 text-slate-400 text-xs">
              No Markdown content available yet. Upload a PDF guideline to inspect the extracted Markdown.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
