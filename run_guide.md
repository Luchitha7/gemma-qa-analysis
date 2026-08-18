# 🚀 Complete Run & Testing Guide: Multi-Tenant QA Service

This guide provides step-by-step instructions to start, run, and test all components of the **Multi-Tenant Automated QA Service** (PostgreSQL Database, Vector RAG Store, Ollama Gemma 3 4B LLM, FastAPI Backend, and Vite + React + TailwindCSS Frontend).

---

## 📋 1. Prerequisites Checklist

Ensure the following tools are installed and available on your system:

| Component | Required Version | Status / Details |
| :--- | :--- | :--- |
| **Python** | Python 3.11 or 3.12 | Used for FastAPI, PyMuPDF, Sentence-Transformers, and RoBERTa |
| **Node.js & npm** | Node v18+ (tested on v22) | Used for Vite + React + TailwindCSS Frontend |
| **PostgreSQL** | PostgreSQL 17 | Running on `localhost:5432` (User: `postgres`, Password: `root`) |
| **Ollama** | Latest Ollama | Serving `gemma3:4b` locally |

---

## ⚙️ 2. One-Time Setup

If you are setting up for the first time, run these one-time installation commands in your terminal.

### A. Python Backend Setup
Open a PowerShell terminal in the project root folder `C:\Users\Lenovo\Desktop\qa-analysis-2\gemma-qa-analysis`:

```powershell
# 1. Install all backend dependencies
pip install -r requirements.txt
```

### B. Pull the Gemma 3 4B Model
```powershell
# 2. Pull the 4B Gemma model in Ollama
ollama pull gemma3:4b
```

### C. Frontend Setup
```powershell
# 3. Install frontend dependencies
cd frontend
npm install
cd ..
```

---

## 🖥️ 3. Starting the System (3 Simple Steps)

To run the entire system, open **3 separate terminal windows**:

### 🔹 Terminal 1: Start Ollama (Language Model Server)
```powershell
ollama serve
```
> *Keep this window open. Ollama listens on `http://localhost:11434`.*

---

### 🔹 Terminal 2: Start the Backend FastAPI Server
In the project root folder:
```powershell
python main.py
```
> *The backend will automatically connect to PostgreSQL on `localhost:5432`, ensure `qa_database` exists, create all tables, and start the API on **`http://localhost:8000`**.*

---

### 🔹 Terminal 3: Start the Vite Frontend Server
In the project root folder:
```powershell
cd frontend
npm run dev
```
> *The frontend will start and display your local URL: **`http://localhost:5173`**.*

---

## 🧪 4. Testing the System via Frontend Web UI

Open your web browser and navigate to:
👉 **[http://localhost:5173](http://localhost:5173)**

### 📍 Test 1: Uploading, Managing & Deleting Company Guidelines
1. In the top navigation bar, click on **PDF & Markdown**.
2. Select your active company (e.g. **S-NET**) or click **+ New Company** to add a new company namespace.
3. Drag & drop or click the upload box to upload a company QA Form Guideline PDF.
4. The system will:
   - Convert the PDF into clean, lossless **Markdown (`.md`)** preserving all table grids, percentages, and spiels.
   - Save the raw Markdown in the PostgreSQL `documents` table.
   - Use Gemma 3 4B to separate the document into **Criteria JSON** and **Policy Knowledge Chunks**.
   - Embed and store the policy chunks into the Vector DB.
5. **Managing & Deleting Files**:
   - Under **Uploaded Company Documents**, you can view all uploaded PDF files and click the **Delete File (Trash)** button to delete a specific guideline.
   - Click **Clear Knowledge Base** to completely wipe all documents and vector embeddings for that company.
6. Inspect the converted `.md` document in the live **Converted Markdown Viewer**. You can click **Copy MD** to copy the markdown text.

---

### 📍 Test 2: Inspecting Extracted Criteria & Vector RAG Policies
1. Click on the **Criteria & Policies** tab.
2. Verify:
   - **Category Weights**: e.g., Soft Skills (25%), Technical Knowledge (50%), Process Knowledge (25%).
   - **Auto-Fail Circuit Breakers**: Discourtesy, Call Avoidance, Fraud, Escalation Refusal.
   - **Line Items & Required Verbatim Spiels**: Greeting, Closing, and Survey spiels.
   - **Vector Database Knowledge Chunks**: Browse the indexed SOPs and procedural guidelines stored for RAG.

---

### 📍 Test 3: Running Live QA Evaluations with Sample Transcripts
1. Click on the **Live QA Test** tab.
2. Select your channel: **Call**, **Email**, or **Chat**.
3. Choose from 5 realistic preset interaction transcripts:
   - 📞 **Call: 100% Compliant**: Complete greeting, hold procedure with expectation & thanks, ARE troubleshooting, closing & survey IVR spiel.
   - 📞 **Call: Hold & Dead Air Violation**: Agent leaves customer on hold > 4 mins with no refresh, 35s dead air.
   - ⚠ **Call: Auto-Fail Breach**: Agent uses rude language, dismisses customer, refuses supervisor escalation.
   - ✉️ **Email: 10m SLA & Template Compliant**: Professional email greeting, account validation, clear ARE action steps, brand signature.
   - 💬 **Chat: Fast Response & Verification**: 1st response < 30s, correct customer verification, L1 troubleshooting.
4. Click **Run Dynamic QA Analysis**.
5. Inspect the evaluation results:
   - **Overall Score Banner**: Shows final score (0–100) or **AUTO-FAIL TRIGGERED (0.0 / 100)** if a violation occurred.
   - **Category Score Breakdown**: Individual scores for Soft Skills, Technical, and Process.
   - **Scorecard Line Items Table**: Displays `PASS`, `PARTIAL`, or `FAIL` ratings with Gemma's audit reason.
   - **RAG Retrieved Policies**: Shows which company policies were retrieved from the Vector DB as evidence.
   - **Call Summary & Coaching Suggestions**: Plain-language call summary and coaching tips for the agent.

---

### 📍 Test 4: Reviewing Evaluation Audit History
1. Click on the **History** tab.
2. View all past evaluation reports stored in PostgreSQL table `evaluation_reports` with report IDs, timestamps, scores, and status flags.

---

## 📡 5. Testing via REST API (`request.http`)

You can also test the API directly using the [`request.http`](file:///c:/Users/Lenovo/Desktop/qa-analysis-2/gemma-qa-analysis/request.http) file with the **VS Code REST Client extension**, IntelliJ HTTP Client, or `curl`:

### Example 1: List Tenants
```bash
curl -X GET http://localhost:8000/api/tenants
```

### Example 2: Run Dynamic QA Evaluation
```bash
curl -X POST http://localhost:8000/api/tenants/S-NET/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "Call",
    "agent_name": "Alex",
    "transcript": "[00:00] Client: My internet is down.\n[00:05] Agent: Thank you for calling S-NET Communications. My name is Alex, how can I help you today?\n[00:15] Agent: I will resolve this issue for you. Thank you for Choosing S-NET and have a great day."
  }'
```

### Example 3: Fetch Converted Markdown for a Tenant
```bash
curl -X GET http://localhost:8000/api/tenants/S-NET/markdown
```

---

## 🔧 6. Troubleshooting & FAQs

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **`Could not reach Ollama`** | Ollama service is not running | Run `ollama serve` in a terminal window. |
| **`Database connection error`** | PostgreSQL is stopped or password is wrong | Verify PostgreSQL is running on `localhost:5432` with password `root`. Set environment variables `DB_PASSWORD=root` if needed. |
| **`Port 8000 already in use`** | Another backend instance is running | Kill the existing process on port 8000 or change port in `main.py`. |
| **`Port 5173 already in use`** | Another Vite dev server is running | Vite will automatically switch to `http://localhost:5174`. |
| **`PDF upload returns empty`** | Scanned PDF without text layer | Upload a digital PDF with selectable text or tables. |
