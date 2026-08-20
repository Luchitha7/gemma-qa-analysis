# 🛠️ Dynamic LLM Prompt Builder Guide (Rule-Based & Data-Driven)

This document explains the technical architecture, mathematical mechanics, and rule-based algorithms behind how **Automated QA Intelligence** dynamically constructs context-rich, guardrailed prompts for **Gemma 3 4B** to perform multi-tenant call, email, and chat evaluations with **zero hardcoding**.

---

## 🏗️ Prompt Construction Pipeline Overview

The system uses a **7-Stage Dynamic Rule-Based Assembly Pipeline** before sending any prompt to Gemma 3 4B:

![Prompt Builder Overview](resources/prompt-builder-overview.png)

---

## 📑 The 7 Stages of the Rule-Based Dynamic Algorithm

### 1. Speaker & Turn Normalization
- **Algorithm**: Regular expression matching standardizes dialogue prefixes (`[00:05] Agent:`, `(01:20) Support:`, `Caller:`, `Customer:`) into clean `(Speaker, Text)` tuples.
- **Latency & Hold Timing**: Extracts ISO/clock timestamps (e.g. `[04:45]`) to compute hold duration and silence/dead-air delays without manual intervention.

### 2. RoBERTa Emotion & Tone Intensity Injection
- **Model**: `cardiffnlp/twitter-roberta-base-sentiment-latest`
- **Algorithm**: Analyzes polarity and negative intensity per turn.
- **Dynamic Injections**:
  - `FLAGGED TENSE MOMENTS`: Dialogue turns where customer frustration exceeds the dynamic threshold (\(\le -0.4\)).
  - `HARSH/NEGATIVE AGENT LINES`: Turns where agent statements exhibit negative sentiment, injected as strict evidence for tone penalties.

### 3. ChromaDB Vector RAG Policy Evidence Injection
- **Model**: `all-MiniLM-L6-v2` dense embeddings with cosine similarity.
- **Algorithm**: Dynamically queries the vector store using customer inquiries to retrieve only the relevant company SOP chunks (e.g., Hold SLA, Verification standards, Supervisor Escalation).
- **Format**:
  ```text
  COMPANY POLICY CONTEXT (Retrieved from Knowledge Base):
  • S-NET Communications - Hold & Silence Management SLA: S-NET Communications Policy: Hold times must NOT exceed 3 minutes...
  • S-NET Communications - Customer Verification Standard: S-NET Communications Standard: Validate Caller name, Company name, Email, Callback Phone...
  ```

### 4. Dynamic Category Weights & Line Items Injection
- **Source**: Dynamically retrieved from PostgreSQL `criteria_configs` (derived from the company's uploaded Markdown document).
- **Zero-Hardcoding**: Category weights, line items, and required verbatim spiels are injected dynamically based on the active company:
  ```text
  COMPANY EVALUATION CATEGORIES & WEIGHTS:
  • Soft Skills: 25.0% of total QA score
  • Technical Knowledge: 50.0% of total QA score
  • Process Knowledge: 25.0% of total QA score

  EVALUATION LINE ITEMS TO RATE (Grouped by Category & Weight):
  - [Soft Skills (25.0%)] Branding and Survey: Adhered to greeting and closing scripts [Required Spiels: "Thank you for calling...", "Thank you for Choosing..."]
  - [Technical Knowledge (50.0%)] Verified customer: Validated all required fields.
  - [Process Knowledge (25.0%)] Case Tagging: Correct contact, location, and issue type tagging.
  ```

### 5. Dynamic Auto-Fail Zero-Tolerance Circuit Breakers
- **Algorithm**: Injects the company's exact auto-fail triggers directly into the prompt so the LLM and auditor have complete visibility over instant failure conditions:
  ```text
  COMPANY AUTO-FAIL ZERO-TOLERANCE CIRCUIT BREAKERS (Instant 0 Score):
  • Discourtesy: Profanity, bashing, impatience, sarcasm
  • Call/Ticket Avoidance: Rejecting or prematurely ending interaction without resolution
  • Escalation Refusal: Refusing supervisor request upon customer demand
  ```

### 6. Strict Auditor Persona & Guardrails
- **Role**: Instructs Gemma 3 4B to operate as a *Strict Quality Assurance Auditor* evaluating against the company's specific weights and SLAs.
- **Rating Scale**:
  - `PASS` (100 pts): Fully compliant with policies and scripts.
  - `PARTIAL` (50 pts): Minor omission or slight delay.
  - `FAIL` (0 pts): Policy breach or unhelpful/impolite conduct.
- **Output Guardrail**: Strict one-line-per-item format (`Line Item Name: PASS/PARTIAL/FAIL - Reason`).

### 7. User Inspection, Editing & Approval Loop
- **UI Integration**: In the **Live QA Test** page (`/test`), clicking **Preview Built Prompt** (👁️) generates the exact assembled prompt string.
- **Interactive Control**: Users can review, edit, or copy the prompt before clicking **Approve & Run Analysis** to trigger Gemma evaluation.

---

## 🔍 Full Example of a Built Dynamic Prompt

```text
You are a STRICT Call Quality Assurance Auditor evaluating a Call interaction.
Your task is to judge the AGENT against each specific evaluation line item according to company weights and policies.

COMPANY EVALUATION CATEGORIES & WEIGHTS:
• Soft Skills: 25.0% of total QA score
• Technical Knowledge: 50.0% of total QA score
• Process Knowledge: 25.0% of total QA score

COMPANY AUTO-FAIL ZERO-TOLERANCE CIRCUIT BREAKERS (Instant 0 Score):
• Discourtesy: Support displayed profanity, bashing, impatience, sarcasm
• Call/Ticket Avoidance: Support did not respond, rejected call, closed ticket without resolution
• Escalation Refusal: Support refuses to escalate to a Supervisor at customer request

RATING CRITERIA:
- PASS: Agent met all requirements, was polite, helpful, and followed required spiels/policies.
- PARTIAL: Agent was partially compliant, missed a spiel minorly, or showed minor delays.
- FAIL: Agent was rude, unhelpful, failed policy, or refused to help.

COMPANY POLICY CONTEXT (Retrieved from Knowledge Base):
• S-NET Communications - Hold & Silence Management SLA: S-NET Communications Policy: Hold times must NOT exceed 3 minutes. Dead air max 20 seconds.
• S-NET Communications - Customer Verification & Identification Standard: S-NET Communications Standard: All 4 details must be validated (Caller name, Company name, Email, Callback Phone).

EVALUATION LINE ITEMS TO RATE (Grouped by Category & Weight):
- [Soft Skills (25.0%)] Branding and Survey: The support adhered to the verbatim greeting spiel [Required Spiels: "Thank you for calling S-NET Communications. My name is _____ how can I help you today?", "Thank you for Choosing S-NET and have a great day."]
- [Soft Skills (25.0%)] Hold time and Dead Air: Support did not exceed 3-minute hold times. Dead air under 20s.
- [Technical Knowledge (50.0%)] Verified customer: All 4 required details validated.
- [Technical Knowledge (50.0%)] Provided appropriate solution: Performed logical troubleshooting steps.
- [Process Knowledge (25.0%)] Case Documentation: Complete and correct notes.
- [Process Knowledge (25.0%)] Case Tagging: Tagged Location, Account, Request Type, Self-QA checkboxes in Zoho.

FLAGGED TENSE MOMENTS:
- (none flagged)

HARSH/NEGATIVE AGENT LINES (Weigh heavily for tone):
- (none)

TRANSCRIPT:
[00:00] Agent: Thank you for calling S-NET Communications. My name is Alex how can I help you today?
[00:05] Client: Hi, I need to check my invoice.
[00:09] Agent: I can certainly help with that! May I confirm your full name, company name, and callback number?
[00:18] Client: Sure, John Doe from Acme Corp, 555-0199.
[00:25] Agent: Thank you John. Your current invoice balance is $150 and is due on the 30th.
[00:33] Client: Perfect, thanks Alex!
[00:36] Agent: You are very welcome! Thank you for Choosing S-NET and have a great day.

OUTPUT FORMAT INSTRUCTIONS:
Reply with ONE line per line item in this exact format:
Line Item Name: PASS/PARTIAL/FAIL - Short specific audit reason.
```

---

## 🧮 Mathematical Scoring Engine Formula

$$\text{Category Score} = \frac{\sum_{i=1}^{N} \text{Score}_i}{N}$$

$$\text{Final QA Score} = \sum_{c} \left( \text{Category Score}_c \times \frac{\text{Category Weight}_c}{\sum \text{Weights}} \right)$$

* If any **Auto-Fail Rule** is triggered \(\rightarrow\) Final QA Score = **0.0 / 100**.
