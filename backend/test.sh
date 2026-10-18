#!/bin/bash

BASE_URL="http://127.0.0.1:8000/api/v1"

echo "=========================================="
echo " Starting Bitware Triage API Tests"
echo "=========================================="
echo ""

# 1. Admin Login
echo "[1/8] Logging in as Admin..."
ADMIN_TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "admin123"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")
echo "Admin token acquired."
echo ""

# 2. Register Clinical Staff
echo "[2/8] Registering Doctor and Nurse..."
curl -s -X POST "$BASE_URL/users/register" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"username": "test_doctor", "password": "password123", "role": "DOCTOR"}' | grep -o '"message":[^}]*'
curl -s -X POST "$BASE_URL/users/register" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"username": "test_nurse", "password": "password123", "role": "NURSE"}' | grep -o '"message":[^}]*'
echo ""

# 3. Staff Logins
echo "[3/8] Authenticating Doctor and Nurse..."
DOC_TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" -d '{"username": "test_doctor", "password": "password123"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")
NURSE_TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" -d '{"username": "test_nurse", "password": "password123"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")
echo "Staff tokens acquired."
echo ""

# 4. Triage Analysis & Queuing (Using Nurse Token)
echo "[4/8] Submitting Patients to Triage Engine..."
echo "Submitting RED Patient..."
curl -s -X POST "$BASE_URL/triage/analyze" -H "Authorization: Bearer $NURSE_TOKEN" -H "Content-Type: application/json" -d '{"patient_name": "Patient Red", "clinical_report": "chest pain, shortness of breath, diaphoresis"}'
echo -e "\nSubmitting YELLOW Patient..."
curl -s -X POST "$BASE_URL/triage/analyze" -H "Authorization: Bearer $NURSE_TOKEN" -H "Content-Type: application/json" -d '{"patient_name": "Patient Yellow", "clinical_report": "high temperature, chills, moderate distress"}'
echo -e "\nSubmitting GREEN Patient..."
curl -s -X POST "$BASE_URL/triage/analyze" -H "Authorization: Bearer $NURSE_TOKEN" -H "Content-Type: application/json" -d '{"patient_name": "Patient Green", "clinical_report": "superficial cut, controlled bleeding"}'
echo -e "\n"

# 5. View Queue & Recommended Treatments
echo "[5/8] Fetching Priority Queue (Check for Recommended Treatments)..."
curl -s -X GET "$BASE_URL/triage/queue" -H "Authorization: Bearer $NURSE_TOKEN"
echo -e "\n\n"

# 6. Treat and Release (Discharge GREEN Patient)
# Patient Green will be ID 3 (since 1 is Red, 2 is Yellow based on this script's order)
echo "[6/8] Testing Treat and Release: Discharging Patient Green (ID 3)..."
curl -s -X PUT "$BASE_URL/triage/discharge" \
     -H "Authorization: Bearer $NURSE_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"patient_id": 3, "approved_treatment": "Topical antibiotic ointment, sterile dressing, Tetanus booster if >10 years."}'
echo -e "\n\n"

# 7. Update Routing for RED patient
echo "[7/8] Routing Patient Red (ID 1) to IN_TREATMENT..."
curl -s -X PUT "$BASE_URL/triage/route" \
     -H "Authorization: Bearer $NURSE_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"patient_id": 1, "department": "TRAUMA_BAY", "status": "IN_TREATMENT"}'
echo -e "\n\n"

# 8. Test Role-Based Data Masking
echo "[8/8] Testing Role-Based Patient Data Masking..."
echo "Nurse attempting to access FULL history (Should be denied):"
curl -s -X GET "$BASE_URL/patient/1/history" -H "Authorization: Bearer $NURSE_TOKEN"
echo -e "\nDoctor attempting to access FULL history (Should succeed):"
curl -s -X GET "$BASE_URL/patient/1/history" -H "Authorization: Bearer $DOC_TOKEN"
echo -e "\nNurse attempting to access TRIAGE SUMMARY (Should succeed):"
curl -s -X GET "$BASE_URL/patient/1/triage-summary" -H "Authorization: Bearer $NURSE_TOKEN"
echo -e "\n"

echo "=========================================="
echo " Tests Completed!"
echo "=========================================="