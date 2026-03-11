"""Patient data models for EHR API responses."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class Demographics(BaseModel):
    """Patient demographic information."""
    age: int
    gender: str = Field(..., pattern="^(M|F|Other)$")
    ethnicity: Optional[str] = None


class Diagnosis(BaseModel):
    """Patient diagnosis record."""
    icd10_code: str = Field(..., alias="icd10Code")
    description: str
    diagnosis_date: str = Field(..., alias="diagnosisDate")


class MedicalHistory(BaseModel):
    """Patient medical history."""
    diagnoses: List[Diagnosis]
    allergies: List[str]
    comorbidities: List[str]


class Medication(BaseModel):
    """Current medication record."""
    drug_name: str = Field(..., alias="drugName")
    dosage: str
    frequency: str
    start_date: str = Field(..., alias="startDate")


class VitalSigns(BaseModel):
    """Patient vital signs."""
    blood_pressure: Optional[str] = Field(None, alias="bloodPressure")
    heart_rate: Optional[int] = Field(None, alias="heartRate")
    temperature: Optional[float] = None
    last_updated: str = Field(..., alias="lastUpdated")


class LabResult(BaseModel):
    """Laboratory test result."""
    test_name: str = Field(..., alias="testName")
    value: float
    unit: str
    reference_range: str = Field(..., alias="referenceRange")
    test_date: str = Field(..., alias="testDate")


class PatientRecord(BaseModel):
    """Complete patient medical record from EHR system."""
    patient_id: str = Field(..., alias="patientId")
    demographics: Demographics
    medical_history: MedicalHistory = Field(..., alias="medicalHistory")
    current_medications: List[Medication] = Field(..., alias="currentMedications")
    vital_signs: VitalSigns = Field(..., alias="vitalSigns")
    lab_results: List[LabResult] = Field(..., alias="labResults")

    model_config = ConfigDict(populate_by_name=True)
