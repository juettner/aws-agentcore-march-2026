#!/usr/bin/env python3
"""Script to set up Amazon Verified Permissions policy store for insurance authorization."""

import json
import os
import sys

import boto3

# Cedar schema for MedFlow authorization
CEDAR_SCHEMA = {
    "MedFlow": {
        "entityTypes": {
            "Provider": {
                "shape": {
                    "type": "Record",
                    "attributes": {
                        "providerId": {"type": "String"},
                        "inNetwork": {"type": "Boolean"},
                    },
                }
            },
            "Procedure": {
                "shape": {
                    "type": "Record",
                    "attributes": {
                        "procedureCode": {"type": "String"},
                        "covered": {"type": "Boolean"},
                    },
                }
            },
        },
        "actions": {
            "AuthorizeProcedure": {
                "appliesTo": {
                    "principalTypes": ["Provider"],
                    "resourceTypes": ["Procedure"],
                    "context": {
                        "type": "Record",
                        "attributes": {
                            "estimatedCost": {"type": "Long"},
                            "patientId": {"type": "String"},
                            "procedureDescription": {"type": "String"},
                        },
                    },
                }
            }
        },
    }
}

# Cedar policies
CEDAR_POLICIES = [
    {
        "policyId": "coverage-policy",
        "description": "Allow authorization if procedure is covered",
        "statement": """
permit(
    principal,
    action == MedFlow::Action::"AuthorizeProcedure",
    resource
)
when {
    resource.covered == true
};
""",
    },
    {
        "policyId": "network-policy",
        "description": "Allow authorization if provider is in network",
        "statement": """
permit(
    principal,
    action == MedFlow::Action::"AuthorizeProcedure",
    resource
)
when {
    principal.inNetwork == true
};
""",
    },
    {
        "policyId": "cost-threshold-policy",
        "description": "Require additional approval for high-cost procedures",
        "statement": """
forbid(
    principal,
    action == MedFlow::Action::"AuthorizeProcedure",
    resource
)
when {
    context.estimatedCost > 5000
}
unless {
    principal has supervisorApproval
};
""",
    },
]


def setup_verified_permissions(region: str = "us-east-1"):
    """Create Verified Permissions policy store and policies."""
    client = boto3.client("verifiedpermissions", region_name=region)

    print("Setting up Amazon Verified Permissions for MedFlow...")

    # Create policy store
    try:
        print("\n1. Creating policy store...")
        response = client.create_policy_store(
            validationSettings={"mode": "STRICT"},
            description="MedFlow Insurance Authorization Policies",
        )
        policy_store_id = response["policyStoreId"]
        print(f"✓ Created policy store: {policy_store_id}")
    except client.exceptions.ServiceQuotaExceededException:
        print("✗ Policy store quota exceeded. Listing existing stores...")
        stores = client.list_policy_stores()
        if stores["policyStores"]:
            policy_store_id = stores["policyStores"][0]["policyStoreId"]
            print(f"✓ Using existing policy store: {policy_store_id}")
        else:
            print("✗ No existing policy stores found")
            return None
    except Exception as e:
        print(f"✗ Failed to create policy store: {e}")
        return None

    # Put schema
    try:
        print("\n2. Uploading Cedar schema...")
        client.put_schema(
            policyStoreId=policy_store_id,
            definition={"cedarJson": json.dumps(CEDAR_SCHEMA)},
        )
        print("✓ Schema uploaded")
    except Exception as e:
        print(f"✗ Failed to upload schema: {e}")
        return None

    # Create policies
    print("\n3. Creating Cedar policies...")
    created_policies = []
    for policy in CEDAR_POLICIES:
        try:
            response = client.create_policy(
                policyStoreId=policy_store_id,
                definition={
                    "static": {
                        "description": policy["description"],
                        "statement": policy["statement"],
                    }
                },
            )
            created_policies.append(response["policyId"])
            print(f"✓ Created policy: {policy['policyId']}")
        except Exception as e:
            print(f"✗ Failed to create policy {policy['policyId']}: {e}")

    print(f"\n✓ Setup complete!")
    print(f"  Policy Store ID: {policy_store_id}")
    print(f"  Policies Created: {len(created_policies)}")
    print(f"\nAdd this to your .env file:")
    print(f"VERIFIED_PERMISSIONS_POLICY_STORE_ID={policy_store_id}")

    return policy_store_id


def create_sample_entities(policy_store_id: str, region: str = "us-east-1"):
    """Create sample provider and procedure entities."""
    client = boto3.client("verifiedpermissions", region_name=region)

    print("\n4. Creating sample entities...")

    entities = [
        {
            "identifier": {"entityType": "MedFlow::Provider", "entityId": "PROV-001"},
            "attributes": {
                "providerId": {"string": "PROV-001"},
                "inNetwork": {"boolean": True},
            },
        },
        {
            "identifier": {"entityType": "MedFlow::Procedure", "entityId": "PROC-001"},
            "attributes": {
                "procedureCode": {"string": "PROC-001"},
                "covered": {"boolean": True},
            },
        },
        {
            "identifier": {"entityType": "MedFlow::Procedure", "entityId": "PROC-002"},
            "attributes": {
                "procedureCode": {"string": "PROC-002"},
                "covered": {"boolean": True},
            },
        },
    ]

    for entity in entities:
        try:
            # Note: Verified Permissions doesn't have a direct "create entity" API
            # Entities are typically managed in your application's data store
            # and referenced in authorization requests
            print(f"✓ Entity defined: {entity['identifier']['entityId']}")
        except Exception as e:
            print(f"✗ Failed to define entity: {e}")


if __name__ == "__main__":
    region = os.environ.get("AWS_REGION", "us-east-1")

    print(f"Region: {region}\n")

    policy_store_id = setup_verified_permissions(region)

    if policy_store_id:
        create_sample_entities(policy_store_id, region)
        sys.exit(0)
    else:
        sys.exit(1)
