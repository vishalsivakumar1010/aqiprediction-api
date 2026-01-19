#!/usr/bin/env python3
"""
Fix SSL Certificates for Python on macOS
This script installs SSL certificates so Python can verify HTTPS connections.
"""

import ssl
import certifi
import os
import shutil
import sys

def fix_ssl_certificates():
    """Install SSL certificates for Python."""
    
    print("=" * 60)
    print("Fixing SSL Certificates for Python")
    print("=" * 60)
    
    # Check certifi
    cert_path = certifi.where()
    print(f"\n1. Checking certifi...")
    print(f"   Certificate file: {cert_path}")
    
    if not os.path.exists(cert_path):
        print("   ✗ Certificate file not found!")
        print("   Installing certifi...")
        os.system(f"{sys.executable} -m pip install --upgrade certifi")
        cert_path = certifi.where()
        if not os.path.exists(cert_path):
            print("   ✗ Failed to install certificates")
            return False
    
    print(f"   ✓ Certificate file exists: {cert_path}")
    
    # Python's expected certificate location
    python_cert_dir = "/Library/Frameworks/Python.framework/Versions/3.13/etc/openssl"
    python_cert_file = f"{python_cert_dir}/cert.pem"
    
    print(f"\n2. Checking Python's certificate location...")
    print(f"   Expected location: {python_cert_file}")
    
    # Create directory if it doesn't exist (might need sudo)
    if not os.path.exists(python_cert_dir):
        print(f"   Creating directory: {python_cert_dir}")
        try:
            os.makedirs(python_cert_dir, exist_ok=True)
            print("   ✓ Directory created")
        except PermissionError:
            print("   ✗ Permission denied. This requires sudo.")
            print(f"\n   Please run manually with sudo:")
            print(f"   sudo mkdir -p {python_cert_dir}")
            print(f"   sudo cp {cert_path} {python_cert_file}")
            return False
    
    # Copy certificates (might need sudo)
    if not os.path.exists(python_cert_file) or os.path.getsize(python_cert_file) == 0:
        print(f"\n3. Copying certificates...")
        try:
            shutil.copy2(cert_path, python_cert_file)
            print(f"   ✓ Certificates copied to {python_cert_file}")
        except PermissionError:
            print("   ✗ Permission denied. This requires sudo.")
            print(f"\n   Please run manually with sudo:")
            print(f"   sudo cp {cert_path} {python_cert_file}")
            return False
    else:
        print(f"   ✓ Certificates already exist at {python_cert_file}")
    
    # Alternative: Set environment variable (no sudo needed)
    print(f"\n4. Setting up environment variable...")
    env_var_setup = f"""
# Add this to your ~/.zshrc or ~/.bash_profile:
export SSL_CERT_FILE={cert_path}
export REQUESTS_CA_BUNDLE={cert_path}

# Or run this in your current shell:
export SSL_CERT_FILE={cert_path}
export REQUESTS_CA_BUNDLE={cert_path}
"""
    print(env_var_setup)
    
    # Test SSL
    print("\n5. Testing SSL connection...")
    try:
        import urllib.request
        import urllib.error
        
        # Test with a simple HTTPS request
        ctx = ssl.create_default_context(cafile=cert_path)
        req = urllib.request.Request('https://www.python.org')
        response = urllib.request.urlopen(req, context=ctx, timeout=5)
        print(f"   ✓ SSL connection successful! (Status: {response.status})")
        return True
    except Exception as e:
        print(f"   ⚠ SSL test failed: {e}")
        print(f"\n   However, you can still use the environment variable method:")
        print(f"   export SSL_CERT_FILE={cert_path}")
        return False

if __name__ == "__main__":
    success = fix_ssl_certificates()
    if success:
        print("\n" + "=" * 60)
        print("✓ SSL Certificates are configured!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("⚠ Some steps require sudo. Please follow the manual instructions above.")
        print("=" * 60)
        print("\nOR use the environment variable method (no sudo needed):")
        cert_path = certifi.where()
        print(f"export SSL_CERT_FILE={cert_path}")
        print(f"export REQUESTS_CA_BUNDLE={cert_path}")
