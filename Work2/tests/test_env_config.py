#!/usr/bin/env python3
"""
Test Environment Configuration Setup
"""

import os
import sys
from pathlib import Path

# Add the scripts/python directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts', 'python'))

from env_config import load_environment


def main():
    """Test the environment configuration system"""
    print("🧪 Testing Environment Configuration System")
    print("=" * 60)
    
    # Load environment
    env_config = load_environment()
    
    print("\n📋 Configuration Status:")
    env_config.print_configuration_status()
    
    print("\n🔧 Detailed Configuration:")
    print("-" * 40)
    
    # Google configuration
    google_config = env_config.get_google_config()
    print(f"Google API Key set: {bool(google_config['api_key']) and google_config['api_key'] != 'your_google_api_key_here'}")
    print(f"Google enabled: {google_config['enabled']}")
    
    # Email configuration  
    email_config = env_config.get_email_config()
    print(f"Email username set: {bool(email_config['username']) and email_config['username'] != 'your_email@gmail.com'}")
    print(f"Email enabled: {email_config['enabled']}")
    
    # Paths configuration
    paths_config = env_config.get_paths_config()
    print(f"Input directory: {paths_config['input_dir']}")
    print(f"Output directory: {paths_config['output_dir']}")
    print(f"Templates directory: {paths_config['templates_dir']}")
    
    # Automation settings
    automation_config = env_config.get_automation_config()
    print(f"Auto convert to PDF: {automation_config['auto_convert_to_pdf']}")
    print(f"Auto send email: {automation_config['auto_send_email']}")
    print(f"Max records per batch: {automation_config['max_records_per_batch']}")
    
    print("\n📝 Next Steps:")
    print("-" * 40)
    if not os.path.exists('.env'):
        print("1. Copy .env.example to .env:")
        print("   cp .env.example .env")
        print("2. Edit .env file with your actual values")
        print("3. Set GOOGLE_API_KEY with your Google API key")
        print("4. Set EMAIL_USERNAME and EMAIL_PASSWORD for email automation")
    else:
        print("✅ .env file exists")
        
        # Check if it's still using example values
        if not google_config['enabled']:
            print("⚠️ Update GOOGLE_API_KEY in .env file")
        if not email_config['enabled']:
            print("⚠️ Update EMAIL_USERNAME and EMAIL_PASSWORD in .env file")
        
        if google_config['enabled'] and email_config['enabled']:
            print("🎉 All major components are configured!")
    
    print("\n💡 To get your Google API key:")
    print("   1. Go to https://console.cloud.google.com/")
    print("   2. Create or select a project")
    print("   3. Enable Google Sheets API and Google Docs API")
    print("   4. Create credentials (API key)")
    print("   5. Copy the API key to your .env file")


if __name__ == "__main__":
    main()