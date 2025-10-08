#!/usr/bin/env python3
"""
Email Test Script - Send Test Email
"""

import os
import sys
from pathlib import Path

# Add the scripts/python directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts', 'python'))

from env_config import load_environment
from email_automation import EmailSender, EmailConfig


def send_test_email():
    """Send a test email using configured settings"""
    print("📧 Testing Email Configuration")
    print("=" * 50)
    
    # Load environment configuration
    env_config = load_environment()
    email_config = env_config.get_email_config()
    
    # Check if email is configured
    if not email_config['enabled']:
        print("❌ Email not configured!")
        print("Missing: EMAIL_USERNAME and/or EMAIL_PASSWORD")
        return False
    
    print(f"📨 SMTP Server: {email_config['smtp_server']}:{email_config['smtp_port']}")
    print(f"👤 Username: {email_config['username']}")
    print(f"🔒 Password: {'*' * len(email_config['password']) if email_config['password'] else 'Not set'}")
    
    try:
        # Create email configuration
        email_cfg = EmailConfig(
            smtp_server=email_config['smtp_server'],
            smtp_port=email_config['smtp_port'],
            username=email_config['username'],
            password=email_config['password'],
            use_tls=True
        )
        
        # Create email sender
        sender = EmailSender(email_cfg)
        
        # Test email content
        test_subject = "🧪 Office Automation Test Email"
        test_body = """
        <html>
        <body>
            <h2>🎉 Office Automation Test Successful!</h2>
            <p>This is a test email from the Office Automation Framework.</p>
            
            <h3>📊 System Information:</h3>
            <ul>
                <li><strong>Sender:</strong> {username}</li>
                <li><strong>SMTP Server:</strong> {smtp_server}:{smtp_port}</li>
                <li><strong>Framework:</strong> Office Automation Framework v1.0</li>
                <li><strong>Test Date:</strong> {timestamp}</li>
            </ul>
            
            <h3>✅ What's Working:</h3>
            <ul>
                <li>✅ Environment configuration loaded</li>
                <li>✅ Email SMTP connection established</li>
                <li>✅ Email sending capability confirmed</li>
            </ul>
            
            <p>🚀 Your Office Automation Framework is ready to use!</p>
            
            <hr>
            <p><small>This email was generated automatically by the Office Automation Framework.</small></p>
        </body>
        </html>
        """.format(
            username=email_config['username'],
            smtp_server=email_config['smtp_server'],
            smtp_port=email_config['smtp_port'],
            timestamp=env_config.get('TEST_TIMESTAMP', 'Unknown')
        )
        
        # Send test email to yourself
        recipient = email_config['username']  # Send to yourself
        
        print(f"\n📤 Sending test email to: {recipient}")
        print("⏳ Please wait...")
        
        # Send the email
        success = sender.send_simple_email(
            to_email=recipient,
            subject=test_subject,
            body="Office Automation Test Email - Please check HTML version",
            html_body=test_body,
            from_name="Office Automation Framework"
        )
        
        if success:
            print("\n✅ TEST EMAIL SENT SUCCESSFULLY!")
            print(f"📧 Check your inbox: {recipient}")
            print("🎉 Email configuration is working correctly!")
            return True
        else:
            print("\n❌ Failed to send test email")
            print("🔍 Check your email configuration and try again")
            return False
            
    except Exception as e:
        print(f"\n❌ Error sending email: {e}")
        
        # Common error suggestions
        print("\n🔍 Troubleshooting:")
        if "authentication" in str(e).lower():
            print("• Check EMAIL_USERNAME and EMAIL_PASSWORD")
            print("• For Gmail: Use App Password, not regular password")
            print("• Enable 2-Factor Authentication first")
        elif "connection" in str(e).lower():
            print("• Check internet connection")
            print("• Verify SMTP server and port")
            print("• Check firewall/antivirus settings")
        else:
            print("• Verify all email settings in .env file")
            print("• Check Gmail security settings")
        
        return False


def show_email_setup_help():
    """Show help for setting up Gmail App Password"""
    print("\n📋 Gmail App Password Setup:")
    print("-" * 40)
    print("1. Go to your Google Account settings")
    print("2. Navigate to Security > 2-Step Verification")
    print("3. Enable 2-Step Verification if not already enabled")
    print("4. Go to Security > App passwords")
    print("5. Select app: 'Mail' and device: 'Other'")
    print("6. Copy the generated 16-character password")
    print("7. Use this password in EMAIL_PASSWORD (not your regular password)")
    print("\n🔗 Direct link: https://myaccount.google.com/apppasswords")


if __name__ == "__main__":
    print("🚀 Office Automation Email Test")
    print("=" * 60)
    
    # Load environment to check timestamp
    env_config = load_environment()
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Add timestamp to environment for the email
    os.environ['TEST_TIMESTAMP'] = timestamp
    
    # Send test email
    success = send_test_email()
    
    if not success:
        show_email_setup_help()
        
    print("\n" + "=" * 60)
    print("📝 Next Steps:")
    if success:
        print("✅ Email is working! You can now use email automation features")
        print("🔧 Try: python main.py pipeline --type simple --email")
    else:
        print("⚠️ Fix email configuration and try again")
        print("🔧 Edit .env file with correct EMAIL_USERNAME and EMAIL_PASSWORD")