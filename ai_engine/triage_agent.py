import json
import gc
from pydantic import BaseModel
from typing import List
from llama_cpp import Llama

# ==============================================================================
# 1. DEFINE THE OUTPUT SCHEMA
# ==============================================================================
class TriageAssessment(BaseModel):
    urgency_level: str
    primary_symptoms: List[str]
    recommended_action: str

# Define the exact JSON schema for GBNF Grammar enforcement.
# This mathematically forces the LLM to output this exact structure.
TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "urgency_level": {"type": "string", "enum": ["EMERGENCY", "URGENT", "ROUTINE"]},
        "primary_symptoms": {"type": "array", "items": {"type": "string"}},
        "recommended_action": {"type": "string"}
    },
    "required": ["urgency_level", "primary_symptoms", "recommended_action"]
}

# ==============================================================================
# 2. HARDWARE-OPTIMIZED SINGLETON FOR 3B MODEL (Under 2.5GB RAM footprint)
# ==============================================================================
class TriageModelManager:
    _instance = None

    @classmethod
    def get_model(cls):
        if cls._instance is None:
            print("Initializing Llama-3.2-3B for lightning-fast inference...")
            
            # NOTE: If your conversion script appended '-be' to the file, update this path to match!
            cls._instance = Llama(
                model_path="/home/ibm-user/shared/bitware/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
                n_ctx=512,       # Expanded context window since the 3B model uses less RAM
                n_threads=2,     # Strictly 2 vCPUs; leaves 1 free for FastAPI/OS
                n_batch=256,
                verbose=False
            )
        return cls._instance

# ==============================================================================
# 3. FAST GENERATION WITH JSON GRAMMAR ENFORCEMENT
# ==============================================================================
def analyze_patient_symptoms(patient_text: str) -> dict:
    llm = TriageModelManager.get_model()

    try:
        # Use Chat Completion API which supports strict JSON Schema enforcement natively
        response = llm.create_chat_completion(
            messages=[
                {
                    "role": "system", 
                    "content": "You are a medical triage AI. Extract symptoms and determine urgency. The urgency level must be exactly EMERGENCY, URGENT, or ROUTINE."
                },
                {
                    "role": "user", 
                    "content": f"Patient Report: {patient_text}"
                }
            ],
            response_format={
                "type": "json_object",
                "schema": TRIAGE_SCHEMA
            },
            temperature=0.0,
            max_tokens=150
        )
        
        raw_text = response['choices'][0]['message']['content']
        
        # Parse strictly into Pydantic model
        assessment = TriageAssessment.parse_raw(raw_text)
        return assessment.dict()
        
    except Exception as e:
        print(f"Generation failed: {e}")
        return {
            "urgency_level": "URGENT",
            "primary_symptoms": ["Parsing Error - Model Generation Failed"],
            "recommended_action": "Refer to human triage staff immediately for manual review."
        }