#!/usr/bin/env python3
"""
Setup Google Earth Engine authentication.

Usage:
    python scripts/setup_gee.py

This script helps configure GEE authentication for the application.
You can use either:
1. Interactive authentication (for development)
2. Service account authentication (for production)
"""

import os
import sys


def setup_interactive():
    """Set up interactive GEE authentication."""
    try:
        import ee
        ee.Authenticate()
        ee.Initialize()
        print("Google Earth Engine authenticated successfully!")
        print("You can now use GEE in the application.")
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)


def setup_service_account(key_file: str):
    """Set up service account authentication."""
    try:
        import ee

        if not os.path.exists(key_file):
            print(f"Error: Key file not found: {key_file}")
            sys.exit(1)

        # Read the service account email from the key file
        import json
        with open(key_file) as f:
            key_data = json.load(f)
            service_account = key_data.get("client_email")

        if not service_account:
            print("Error: Could not find client_email in key file")
            sys.exit(1)

        credentials = ee.ServiceAccountCredentials(service_account, key_file)
        ee.Initialize(credentials)

        print(f"Authenticated with service account: {service_account}")
        print("GEE initialized successfully!")

    except Exception as e:
        print(f"Service account setup failed: {e}")
        sys.exit(1)


def test_connection():
    """Test the GEE connection."""
    try:
        import ee

        # Try a simple operation
        image = ee.Image("NASA/NASADEM_HGT/001")
        info = image.getInfo()
        print("Connection test successful!")
        print(f"  Test image bands: {list(info['bands'][0].keys())}")
        return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False


def main():
    print("Google Earth Engine Setup")
    print("=" * 40)
    print()
    print("Choose authentication method:")
    print("1. Interactive (for development)")
    print("2. Service account (for production)")
    print("3. Test existing connection")
    print()

    choice = input("Enter choice (1/2/3): ").strip()

    if choice == "1":
        setup_interactive()
        test_connection()
    elif choice == "2":
        key_file = input("Enter path to service account key file: ").strip()
        setup_service_account(key_file)
        test_connection()
    elif choice == "3":
        import ee
        try:
            ee.Initialize()
            test_connection()
        except Exception as e:
            print(f"No existing authentication found: {e}")
            print("Please run setup first.")
    else:
        print("Invalid choice")
        sys.exit(1)


if __name__ == "__main__":
    main()
