#!/usr/bin/env python3
"""Validation script for MedFlow AgentCore Gateway and Identity configurations."""

import sys
import yaml
from pathlib import Path


def load_yaml(file_path):
    """Load YAML file and return parsed content."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f), None
    except yaml.YAMLError as e:
        return None, f"YAML syntax error: {e}"
    except FileNotFoundError:
        return None, f"File not found: {file_path}"


def validate_gateway(config):
    """Validate Gateway configuration."""
    errors = []
    warnings = []
    
    if 'name' not in config:
        errors.append("Gateway: Missing 'name' field")
    
    if 'transformations' not in config:
        errors.append("Gateway: Missing 'transformations' field")
        return errors, warnings
    
    transformations = config['transformations']
    print(f"✓ Gateway has {len(transformations)} API transformation(s)")
    
    for idx, transform in enumerate(transformations):
        source_api = transform.get('source_api', {})
        api_name = source_api.get('name', f'transformation-{idx}')
        
        for field in ['name', 'base_url', 'auth_type']:
            if field not in source_api:
                errors.append(f"{api_name}: Missing '{field}'")
        
        if 'mcp_tools' in transform:
            print(f"  ✓ {api_name}: {len(transform['mcp_tools'])} tool(s)")
    
    return errors, warnings


def validate_identity(config):
    """Validate Identity configuration."""
    errors = []
    warnings = []
    
    if 'name' not in config:
        errors.append("Identity: Missing 'name' field")
    
    if 'oauth_providers' in config:
        providers = config['oauth_providers']
        print(f"✓ Identity has {len(providers)} OAuth provider(s)")
        
        for provider in providers:
            provider_id = provider.get('provider_id', 'unnamed')
            if 'scopes' in provider:
                print(f"  ✓ {provider_id}: {len(provider['scopes'])} scope(s)")
    
    return errors, warnings


def main():
    """Main validation function."""
    print("=" * 70)
    print("MedFlow AgentCore Configuration Validator")
    print("=" * 70)
    
    script_dir = Path(__file__).parent
    gateway_path = script_dir / "services" / "agentcore-gateway.yaml"
    identity_path = script_dir / "services" / "agentcore-identity.yaml"
    
    print(f"\n📂 Loading configurations...")
    
    gateway_config, gateway_error = load_yaml(gateway_path)
    if gateway_error:
        print(f"\n❌ {gateway_error}")
        return 1
    
    identity_config, identity_error = load_yaml(identity_path)
    if identity_error:
        print(f"\n❌ {identity_error}")
        return 1
    
    print("✅ YAML syntax valid\n")
    
    print("🔍 Validating Gateway...")
    gateway_errors, _ = validate_gateway(gateway_config)
    
    print("\n🔍 Validating Identity...")
    identity_errors, _ = validate_identity(identity_config)
    
    all_errors = gateway_errors + identity_errors
    
    print("\n" + "=" * 70)
    if all_errors:
        print(f"❌ {len(all_errors)} ERROR(S):")
        for error in all_errors:
            print(f"  - {error}")
        return 1
    else:
        print("✅ Validation PASSED!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
