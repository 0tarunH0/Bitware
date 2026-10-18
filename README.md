# 🏥 Bitware Triage System
**Real-Time AI Clinical Routing & Secure Queue Management on IBM LinuxONE**

**IBM Z Datathon 2026 Submission**

## 👥 The Team (Bitware)
* **Tarun H** - Team Lead & AI Engine Architecture
* **Vikas S, Tushar GA, Vinod Karur** - Backend Systems & Database Management
* **Punith R, Vishwas** - Frontend Interface & UI/UX

## ⚠️ The Challenge
Overcrowded emergency rooms suffer from triage bottlenecks, where mis-prioritization of critical patients leads to severe medical consequences. Traditional triage relies on subjective human assessment and disconnected databases, leading to duplicated records, delayed care, and data silos.

## 💡 Our Solution
Bitware Triage is an enterprise-grade medical queuing system that removes human subjectivity and database duplication from the ER intake process. 

### 🔄 The Architectural Pivot (Vision vs. Execution)
* **Original Vision:** Build a generative RAG system using Meditron to actively prescribe medical treatments.
* **The Pivot:** To guarantee 100% medical safety and eliminate AI hallucinations, we pivoted to a **Lexical RAG framework** using `Llama-3.2-3B-Instruct-Q4_K_M.gguf`. 
* **The Result:** A Deterministic Protocol Engine that maps AI-identified symptoms strictly to approved, hard-coded hospital treatments, prioritizing patient safety above all.

## 🚀 IBM LinuxONE & s390x Platform Exploitation
A critical hospital triage system requires enterprise-grade security and scale. We achieved this by deeply exploiting the LinuxONE platform:
* **Enterprise Containerization:** Deployed securely via Docker on the LinuxONE Community Cloud (`jupyterlab-image-s390x`).
* **zDNN Hardware Acceleration:** Bound the open-source `llama_cpp_python` package directly to IBM Z Deep Neural Network shared libraries (`libggml-zdnn.so`) for native mainframe optimization.
* **Big-Endian Compatibility:** Validated our GGUF models for perfect execution on the mainframe's unique `s390x` architecture.

## ⚙️ Core Features
1. **Zero Hallucination AI:** Lexical AI strictly assigns RED, YELLOW, or GREEN triage priorities based on predefined clinical symptom protocols.
2. **Dynamic Identity Management:** Seamlessly recognizes returning patients and appends new clinical notes to their history without duplicating SQL records.
3. **Role-Based Access Control (RBAC):** Enterprise-grade data security that masks sensitive patient histories based on staff credentials (Admin vs. Doctor vs. Nurse).

## 🛠️ Tech Stack
* **AI Compute:** Llama-3.2-3B (GGUF), `llama_cpp_python`
* **Backend:** FastAPI, SQLite (Strict SQL constraints)
* **Infrastructure:** IBM LinuxONE (`s390x`), Docker, zDNN
* **Frontend:** HTML/CSS/JS
