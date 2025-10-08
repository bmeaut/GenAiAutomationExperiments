#!/usr/bin/env python3
"""
Main Entry Point for Office Automation Pipeline
Simplified launcher for the office automation tools
"""

import os
import sys
import argparse
from pathlib import Path

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts', 'python'))

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Office Automation Pipeline')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Pipeline commands
    pipeline_parser = subparsers.add_parser('pipeline', help='Run automation pipeline')
    pipeline_parser.add_argument('--type', choices=['google-sheets', 'excel-word', 'simple'], 
                                default='simple', help='Pipeline type to run')
    pipeline_parser.add_argument('--config', default='config/settings.yaml', 
                                help='Configuration file path')
    
    # Test commands
    test_parser = subparsers.add_parser('test', help='Run tests')
    test_parser.add_argument('--module', choices=['all', 'google', 'office', 'pdf', 'email', 'env'], 
                            default='all', help='Test module to run')
    
    # Setup commands
    setup_parser = subparsers.add_parser('setup', help='Setup and configuration')
    setup_parser.add_argument('--action', choices=['check', 'env', 'google'], 
                             default='check', help='Setup action')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'pipeline':
            run_pipeline(args)
        elif args.command == 'test':
            run_tests(args)
        elif args.command == 'setup':
            run_setup(args)
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all required packages are installed:")
        print("pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Error: {e}")

def run_pipeline(args):
    """Run automation pipeline"""
    print(f"🚀 Running {args.type} pipeline...")
    
    if args.type == 'simple':
        from main_pipeline_simple import SimpleAutomationPipeline
        pipeline = SimpleAutomationPipeline(args.config)
        
        # Run a basic pipeline demonstration
        print("📋 Running sample pipeline...")
        
        # Check if we have Google API configured
        google_config = pipeline.env_config.get_google_config()
        if google_config['enabled']:
            # Try Google Sheets to PDF pipeline
            sample_id = google_config.get('example_spreadsheet_id')
            if sample_id:
                pipeline.run_google_sheets_to_pdf_pipeline(sample_id)
            else:
                print("⚠️ No example spreadsheet ID configured")
        else:
            print("⚠️ Google API not configured - running local demo")
            # Generate a sample PDF report instead
            from pdf_generator import generate_sample_report
            report_path = generate_sample_report("Sample Automation Report")
            if report_path and report_path.exists():
                print(f"✅ Generated sample report: {report_path}")
    
    elif args.type == 'google-sheets':
        from main_pipeline_simple import SimpleAutomationPipeline
        pipeline = SimpleAutomationPipeline(args.config)
        
        google_config = pipeline.env_config.get_google_config()
        if not google_config['enabled']:
            print("❌ Google API not configured. Run: python main.py setup --action google")
            return
        
        sample_id = google_config.get('example_spreadsheet_id')
        if sample_id:
            pipeline.run_google_sheets_to_pdf_pipeline(sample_id)
        else:
            print("❌ No example spreadsheet ID configured in environment")
    
    elif args.type == 'excel-word':
        print("📊 Excel-Word pipeline coming soon...")

def run_tests(args):
    """Run tests"""
    print(f"🧪 Running {args.module} tests...")
    
    if args.module == 'all' or args.module == 'env':
        from env_config import load_environment
        env_config = load_environment()
        env_config.print_configuration_status()
    
    if args.module == 'all' or args.module == 'google':
        try:
            from google_integration_simple import SimpleGoogleIntegration
            print("✅ Google integration module available")
        except ImportError:
            print("❌ Google integration module not available")
    
    if args.module == 'all' or args.module == 'office':
        try:
            from office_integration import ExcelIntegration, WordIntegration
            print("✅ Office integration modules available")
        except ImportError:
            print("❌ Office integration modules not available")
    
    if args.module == 'all' or args.module == 'pdf':
        try:
            from pdf_generator import PDFGenerator, generate_sample_report
            # Test PDF generation
            report_path = generate_sample_report("Test Report")
            if report_path and report_path.exists():
                print(f"✅ PDF generation test passed: {report_path}")
            else:
                print("❌ PDF generation test failed")
        except ImportError:
            print("❌ PDF generation module not available")
    
    if args.module == 'all' or args.module == 'email':
        try:
            from email_automation import EmailSender, EmailConfig
            print("✅ Email automation modules available")
        except ImportError:
            print("❌ Email automation modules not available")

def run_setup(args):
    """Run setup and configuration"""
    if args.action == 'check':
        print("🔧 Checking system configuration...")
        from env_config import load_environment
        env_config = load_environment()
        env_config.print_configuration_status()
        
        # Check if .env file exists
        if not os.path.exists('.env'):
            print("\n💡 To get started:")
            print("1. Copy config/.env.example to .env")
            print("2. Edit .env with your configuration values")
            print("3. Run: python main.py setup --action google")
    
    elif args.action == 'env':
        print("📝 Environment setup...")
        config_dir = Path('config')
        env_example = config_dir / '.env.example'
        env_file = Path('.env')
        
        if env_example.exists() and not env_file.exists():
            # Copy .env.example to .env
            import shutil
            shutil.copy(env_example, env_file)
            print(f"✅ Created .env file from {env_example}")
            print("📝 Please edit .env file with your configuration values")
        elif env_file.exists():
            print("✅ .env file already exists")
        else:
            print("❌ .env.example not found in config directory")
    
    elif args.action == 'google':
        print("🔑 Google API setup...")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create or select a project")
        print("3. Enable Google Sheets API and Google Docs API")
        print("4. Create credentials (API key)")
        print("5. Add the API key to your .env file as GOOGLE_API_KEY")
        print("6. Test with: python main.py test --module google")

if __name__ == "__main__":
    main()