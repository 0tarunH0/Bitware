import sqlite3
import time
import jwt
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pwdlib import PasswordHash

# --- Configuration & Initialization ---
SECRET_KEY = "bitware-secure-secret-key"
ALGORITHM = "HS256"
app = FastAPI(title="Bitware Secure RAG Triage API", version="1.0")

# Enable CORS for frontend-backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()
password_hash = PasswordHash.recommended()

# Expanded Clinical Guidelines
CLINICAL_GUIDELINES = {
    "cardiac_arrest": "RED: chest pain, shortness of breath, radiating arm pain, diaphoresis.",
    "severe_trauma": "RED: severe blood loss, hemorrhage, fracture, amputation, unconscious.",
    "kidney_stone": "YELLOW: calculus, kidney, flank pain, hematuria, renal colic.",
    "infection_fever": "YELLOW: high temperature, chills, moderate distress, localized pain.",
    "laceration_minor": "GREEN: superficial cut, controlled bleeding, normal vitals."
}

# Expanded Treatment Protocols
TREATMENT_PROTOCOLS = {
    "cardiac_arrest": "IMMEDIATE TRAUMA ESCALATION - NO TRIAGE MEDICATION",
    "severe_trauma": "IMMEDIATE TRAUMA BAY - Tourniquet, IV fluids, prep for emergency surgery.",
    "kidney_stone": "IV fluids, pain management (Toradol), antiemetics, urology consult.",
    "infection_fever": "Dolo 650mg every 6 hours for fever, Oral Rehydration Salts, rest.",
    "laceration_minor": "Topical antibiotic ointment, sterile dressing, Tetanus booster if >10 years."
}

def init_db():
    conn = sqlite3.connect("hospital.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # Users Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
    
    # Triage Queue Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS queue 
                      (id INTEGER PRIMARY KEY, patient_name TEXT, report TEXT, 
                       category TEXT, arrival_time REAL, status TEXT, department TEXT, recommended_treatment TEXT)''')
    
    # Patient Records Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS patient_records 
                      (id INTEGER PRIMARY KEY, patient_name TEXT, history TEXT, allergies TEXT, vitals TEXT)''')
    
    # Seed Admin User
    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if not cursor.fetchone():
        hashed_pw = password_hash.hash("admin123")
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                       ("admin", hashed_pw, "ADMIN"))
                       
    # Seed Dummy Patient Record for Testing
    cursor.execute("SELECT * FROM patient_records WHERE id=1")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO patient_records (id, patient_name, history, allergies, vitals) VALUES (?, ?, ?, ?, ?)",
                       (1, "Patient A", "History of hypertension, Type 2 Diabetes. Previous CABG in 2021.", "Penicillin", "BP: 145/92, HR: 98, Temp: 99.1F"))
    conn.commit()
    return conn

db_conn = init_db()

# --- Pydantic Models ---
class LoginModel(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str

class PatientReport(BaseModel):
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    clinical_report: str
    vitals: str
    allergies: Optional[str] = None

class RoutingUpdate(BaseModel):
    patient_id: int
    department: str
    status: str

class DischargeUpdate(BaseModel):
    patient_id: int
    approved_treatment: str

# --- Security & RBAC ---
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=2)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(required_roles: List[str]):
    def role_checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in required_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker

# --- Lexical RAG & Triage Engine ---
def analyze_report(report: str) -> dict:
    report_tokens = set(report.lower().replace(',', '').replace('.', '').split())
    best_match_category = "GREEN" 
    best_match_condition = "laceration_minor"
    highest_overlap = 0
    
    for condition, guideline in CLINICAL_GUIDELINES.items():
        guideline_tokens = set(guideline.lower().replace(',', '').replace('.', '').split())
        overlap = len(report_tokens.intersection(guideline_tokens))
        
        if overlap > highest_overlap:
            highest_overlap = overlap
            best_match_category = guideline.split(":")[0] 
            best_match_condition = condition
            
    return {
        "category": best_match_category,
        "treatment": TREATMENT_PROTOCOLS.get(best_match_condition, "Consult Physician")
    }

def calculate_priority(category: str, arrival_time: float) -> float:
    wait_time = time.time() - arrival_time
    time_bonus = wait_time * 0.1 
    
    if category == "RED":
        return 1000 + time_bonus
    elif category == "YELLOW":
        return 100 + min(time_bonus, 200)
    elif category == "GREEN":
        return 10 + min(time_bonus, 150)
        
    return 0

# --- API Endpoints ---

@app.post("/api/v1/auth/login")
def login(credentials: LoginModel):
    cursor = db_conn.cursor()
    cursor.execute("SELECT password, role FROM users WHERE username=?", (credentials.username,))
    user = cursor.fetchone()
    
    if not user or not password_hash.verify(credentials.password, user[0]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    token = create_access_token({"sub": credentials.username, "role": user[1]})
    return {"access_token": token, "token_type": "bearer", "role": user[1]}

@app.post("/api/v1/users/register", dependencies=[Depends(require_role(["ADMIN"]))])
def register_user(new_user: UserCreate):
    cursor = db_conn.cursor()
    try:
        hashed_pw = password_hash.hash(new_user.password)
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                       (new_user.username, hashed_pw, new_user.role.upper()))
        db_conn.commit()
        return {"message": f"User '{new_user.username}' successfully registered as {new_user.role.upper()}"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists")

@app.get("/api/v1/triage/next-id", dependencies=[Depends(require_role(["ADMIN", "NURSE"]))])
def get_next_id():
    cursor = db_conn.cursor()
    cursor.execute("SELECT MAX(id) FROM patient_records")
    max_id = cursor.fetchone()[0]
    next_id = (max_id or 0) + 1
    return {"next_id": next_id}

@app.post("/api/v1/triage/analyze", dependencies=[Depends(require_role(["ADMIN", "NURSE"]))])
def analyze_and_queue(report: PatientReport):
    analysis = analyze_report(report.clinical_report)
    category = analysis["category"]
    recommended_treatment = analysis["treatment"]
    arrival_time = time.time()
    
    assigned_department = "TRAUMA_BAY" if category == "RED" else "FAST_TRACK"
    
    cursor = db_conn.cursor()
    
    if report.patient_id:
        # Existing Patient Flow
        cursor.execute("SELECT patient_name, history FROM patient_records WHERE id=?", (report.patient_id,))
        record = cursor.fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="Patient ID not found in database")
            
        pat_name = record[0]
        updated_history = record[1] + f" | New Visit: {report.clinical_report}"
        
        cursor.execute(
            "UPDATE patient_records SET history=?, vitals=? WHERE id=?",
            (updated_history, report.vitals, report.patient_id)
        )
        final_patient_id = report.patient_id
    else:
        # New Patient Flow
        pat_name = report.patient_name
        cursor.execute(
            "INSERT INTO patient_records (patient_name, history, allergies, vitals) VALUES (?, ?, ?, ?)",
            (pat_name, f"Admitting Notes: {report.clinical_report}", report.allergies, report.vitals)
        )
        final_patient_id = cursor.lastrowid
    
    # Add to live queue
    # FIX: Delete the old queue record first so we don't get a Primary Key crash when an existing patient returns!
    cursor.execute("DELETE FROM queue WHERE id=?", (final_patient_id,))
    
    cursor.execute(
        "INSERT INTO queue (id, patient_name, report, category, arrival_time, status, department, recommended_treatment) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (final_patient_id, pat_name, report.clinical_report, category, arrival_time, "WAITING", assigned_department, recommended_treatment)
    )
    db_conn.commit()
    
    return {
        "patient_id": final_patient_id, 
        "assigned_category": category, 
        "assigned_department": assigned_department,
        "recommended_treatment": recommended_treatment,
        "status": "Queued successfully"
    }

@app.get("/api/v1/triage/queue", dependencies=[Depends(require_role(["ADMIN", "NURSE", "DOCTOR"]))])
def get_queue():
    cursor = db_conn.cursor()
    cursor.execute("SELECT id, patient_name, category, arrival_time, status, department, recommended_treatment FROM queue WHERE status='WAITING'")
    rows = cursor.fetchall()
    
    queue = []
    for row in rows:
        priority_score = calculate_priority(row[2], row[3])
        queue.append({
            "id": row[0],
            "patient_name": row[1],
            "category": row[2],
            "priority_score": priority_score,
            "status": row[4],
            "department": row[5],
            "recommended_treatment": row[6]
        })
    queue.sort(key=lambda x: x["priority_score"], reverse=True)
    return {"queue": queue}

@app.put("/api/v1/triage/route", dependencies=[Depends(require_role(["ADMIN", "NURSE"]))])
def update_routing(update: RoutingUpdate):
    cursor = db_conn.cursor()
    cursor.execute(
        "UPDATE queue SET department=?, status=? WHERE id=?",
        (update.department, update.status, update.patient_id)
    )
    db_conn.commit()
    return {"message": "Patient routing updated successfully"}

@app.put("/api/v1/triage/discharge", dependencies=[Depends(require_role(["ADMIN", "NURSE", "DOCTOR"]))])
def treat_and_release(update: DischargeUpdate):
    cursor = db_conn.cursor()
    cursor.execute("SELECT category FROM queue WHERE id=?", (update.patient_id,))
    patient = cursor.fetchone()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found in queue")
    if patient[0] == "RED":
        raise HTTPException(status_code=403, detail="Cannot treat-and-release RED trauma patients")
        
    cursor.execute(
        "UPDATE queue SET status=?, department=?, recommended_treatment=? WHERE id=?",
        ("DISCHARGED", "RELEASED", update.approved_treatment, update.patient_id)
    )
    db_conn.commit()
    return {"message": "Patient successfully treated and discharged", "final_treatment": update.approved_treatment}

@app.get("/api/v1/patient/{patient_id}/history", dependencies=[Depends(require_role(["ADMIN", "DOCTOR"]))])
def get_patient_history(patient_id: int):
    cursor = db_conn.cursor()
    cursor.execute("SELECT patient_name, history FROM patient_records WHERE id=?", (patient_id,))
    record = cursor.fetchone()
    if not record:
        raise HTTPException(status_code=404, detail="Patient record not found")
    
    return {
        "patient_id": patient_id, 
        "patient_name": record[0], 
        "full_history": record[1]
    }

@app.get("/api/v1/patient/{patient_id}/triage-summary", dependencies=[Depends(require_role(["ADMIN", "DOCTOR", "NURSE"]))])
def get_triage_summary(patient_id: int):
    cursor = db_conn.cursor()
    cursor.execute("SELECT patient_name, allergies, vitals FROM patient_records WHERE id=?", (patient_id,))
    record = cursor.fetchone()
    if not record:
        raise HTTPException(status_code=404, detail="Patient record not found")
    
    return {
        "patient_id": patient_id, 
        "patient_name": record[0], 
        "allergies": record[1], 
        "vitals": record[2]
    }