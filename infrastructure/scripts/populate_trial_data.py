#!/usr/bin/env python3
"""Script to populate S3 with sample trial data for regulatory reports."""

import json
import os
import sys
from datetime import datetime, timedelta

import boto3

# Sample trial data
SAMPLE_TRIALS = {
    "TRIAL-001": {
        "trialId": "TRIAL-001",
        "trialName": "Phase II Oncology Study - Novel Immunotherapy",
        "phase": "Phase II",
        "indication": "Non-Small Cell Lung Cancer",
        "sponsor": "MedFlow Research Institute",
        "principalInvestigator": "Dr. Sarah Chen, MD, PhD",
        "startDate": "2024-06-01",
        "enrolledPatients": 45,
        "targetEnrollment": 60,
        "sites": [
            {"name": "Memorial Cancer Center", "location": "Boston, MA", "patients": 20},
            {"name": "Pacific Oncology Institute", "location": "San Francisco, CA", "patients": 15},
            {"name": "Midwest Cancer Research", "location": "Chicago, IL", "patients": 10},
        ],
        "adverseEvents": [
            {
                "eventId": "AE-001",
                "patientId": "PAT-012",
                "severity": "Grade 2",
                "description": "Fatigue",
                "onset": "2025-03-15",
                "resolved": True,
            },
            {
                "eventId": "AE-002",
                "patientId": "PAT-023",
                "severity": "Grade 1",
                "description": "Nausea",
                "onset": "2025-04-02",
                "resolved": True,
            },
            {
                "eventId": "AE-003",
                "patientId": "PAT-034",
                "severity": "Grade 3",
                "description": "Neutropenia",
                "onset": "2025-05-10",
                "resolved": False,
            },
        ],
        "efficacyData": {
            "objectiveResponseRate": 0.42,
            "diseaseControlRate": 0.78,
            "medianProgressionFreeSurvival": "8.3 months",
        },
        "drugInformation": {
            "name": "IMT-2024",
            "class": "PD-L1 Inhibitor",
            "dosage": "200mg IV every 3 weeks",
            "manufacturer": "BioPharma Solutions",
        },
    },
    "TRIAL-002": {
        "trialId": "TRIAL-002",
        "trialName": "Phase III Cardiovascular Outcomes Study",
        "phase": "Phase III",
        "indication": "Heart Failure with Reduced Ejection Fraction",
        "sponsor": "CardioHealth Research",
        "principalInvestigator": "Dr. Michael Rodriguez, MD",
        "startDate": "2023-09-01",
        "enrolledPatients": 320,
        "targetEnrollment": 400,
        "sites": [
            {"name": "Heart Institute of America", "location": "Cleveland, OH", "patients": 120},
            {"name": "Cardiovascular Research Center", "location": "Houston, TX", "patients": 100},
            {"name": "Advanced Cardiology Clinic", "location": "Atlanta, GA", "patients": 100},
        ],
        "adverseEvents": [
            {
                "eventId": "AE-101",
                "patientId": "PAT-145",
                "severity": "Grade 1",
                "description": "Dizziness",
                "onset": "2024-11-20",
                "resolved": True,
            },
            {
                "eventId": "AE-102",
                "patientId": "PAT-198",
                "severity": "Grade 2",
                "description": "Hypotension",
                "onset": "2025-01-15",
                "resolved": True,
            },
        ],
        "efficacyData": {
            "primaryEndpoint": "Cardiovascular death or HF hospitalization",
            "hazardRatio": 0.74,
            "pValue": 0.003,
            "nntBenefit": 18,
        },
        "drugInformation": {
            "name": "CVD-2023",
            "class": "SGLT2 Inhibitor",
            "dosage": "10mg PO daily",
            "manufacturer": "CardioPharm Inc",
        },
    },
    "TRIAL-003": {
        "trialId": "TRIAL-003",
        "trialName": "Phase I Safety and Tolerability Study",
        "phase": "Phase I",
        "indication": "Alzheimer's Disease",
        "sponsor": "NeuroScience Innovations",
        "principalInvestigator": "Dr. Emily Watson, PhD",
        "startDate": "2025-01-15",
        "enrolledPatients": 12,
        "targetEnrollment": 24,
        "sites": [
            {"name": "Brain Research Institute", "location": "New York, NY", "patients": 12},
        ],
        "adverseEvents": [
            {
                "eventId": "AE-201",
                "patientId": "PAT-301",
                "severity": "Grade 1",
                "description": "Headache",
                "onset": "2025-02-10",
                "resolved": True,
            },
        ],
        "efficacyData": {
            "primaryEndpoint": "Safety and tolerability",
            "doseEscalation": "Completed 3 dose levels",
            "maxToleratedDose": "Not yet determined",
        },
        "drugInformation": {
            "name": "NEURO-2025",
            "class": "Amyloid-beta Antibody",
            "dosage": "Variable (dose escalation)",
            "manufacturer": "NeuroTherapeutics Ltd",
        },
    },
}


def create_trial_data(bucket_name: str, region: str = "us-east-1"):
    """Upload sample trial data to S3."""
    s3_client = boto3.client("s3", region_name=region)

    # Check if bucket exists, create if not
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"✓ Bucket {bucket_name} exists")
    except:
        print(f"Creating bucket {bucket_name}...")
        try:
            if region == "us-east-1":
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": region},
                )
            print(f"✓ Created bucket {bucket_name}")
        except Exception as e:
            print(f"✗ Failed to create bucket: {e}")
            return False

    # Upload trial data
    for trial_id, trial_data in SAMPLE_TRIALS.items():
        key = f"trials/{trial_id}/data.json"
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=json.dumps(trial_data, indent=2),
                ContentType="application/json",
            )
            print(f"✓ Uploaded {key}")
        except Exception as e:
            print(f"✗ Failed to upload {key}: {e}")
            return False

    print(f"\n✓ Successfully populated {len(SAMPLE_TRIALS)} trials in S3")
    print(f"  Bucket: s3://{bucket_name}/")
    print(f"  Trials: {', '.join(SAMPLE_TRIALS.keys())}")
    return True


if __name__ == "__main__":
    bucket = os.environ.get("S3_TRIAL_DATA_BUCKET", "medflow-trial-data")
    region = os.environ.get("AWS_REGION", "us-east-1")

    print(f"Populating trial data in S3...")
    print(f"  Bucket: {bucket}")
    print(f"  Region: {region}\n")

    success = create_trial_data(bucket, region)
    sys.exit(0 if success else 1)
