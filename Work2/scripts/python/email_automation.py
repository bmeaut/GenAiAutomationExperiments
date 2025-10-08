#!/usr/bin/env python3
"""
Email Automation Module
Advanced email handling with attachments, templates, and bulk operations
"""

import os
import smtplib
import imaplib
import email
import mimetypes
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from datetime import datetime, timedelta
import json
import time
import re

logger = logging.getLogger(__name__)


class EmailConfig:
    """Email configuration container"""
    
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str,
                 imap_server: str = None, imap_port: int = 993, use_tls: bool = True):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.imap_server = imap_server or smtp_server.replace('smtp', 'imap')
        self.imap_port = imap_port
        self.use_tls = use_tls
    
    @classmethod
    def gmail(cls, username: str, password: str):
        """Create Gmail configuration"""
        return cls(
            smtp_server='smtp.gmail.com',
            smtp_port=587,
            username=username,
            password=password,
            imap_server='imap.gmail.com',
            imap_port=993
        )
    
    @classmethod
    def outlook(cls, username: str, password: str):
        """Create Outlook configuration"""
        return cls(
            smtp_server='smtp-mail.outlook.com',
            smtp_port=587,
            username=username,
            password=password,
            imap_server='outlook.office365.com',
            imap_port=993
        )


class EmailSender:
    """Email sending functionality"""
    
    def __init__(self, config: EmailConfig):
        self.config = config
        self.smtp_connection = None
    
    def connect(self) -> bool:
        """Establish SMTP connection"""
        try:
            self.smtp_connection = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
            
            if self.config.use_tls:
                self.smtp_connection.starttls()
            
            self.smtp_connection.login(self.config.username, self.config.password)
            
            logger.info("✅ SMTP connection established")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error connecting to SMTP server: {e}")
            return False
    
    def disconnect(self):
        """Close SMTP connection"""
        try:
            if self.smtp_connection:
                self.smtp_connection.quit()
                self.smtp_connection = None
                logger.info("✅ SMTP connection closed")
        except Exception as e:
            logger.error(f"❌ Error disconnecting from SMTP: {e}")
    
    def send_simple_email(self, to_email: str, subject: str, body: str,
                         from_name: str = None, html_body: str = None) -> bool:
        """Send a simple email"""
        try:
            if not self.smtp_connection:
                if not self.connect():
                    return False
            
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{from_name} <{self.config.username}>" if from_name else self.config.username
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add text version
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Add HTML version if provided
            if html_body:
                html_part = MIMEText(html_body, 'html', 'utf-8')
                msg.attach(html_part)
            
            self.smtp_connection.send_message(msg)
            
            logger.info(f"✅ Email sent to: {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending email to {to_email}: {e}")
            return False
    
    def send_email_with_attachments(self, to_email: str, subject: str, body: str,
                                   attachments: List[str], from_name: str = None,
                                   html_body: str = None, cc: List[str] = None,
                                   bcc: List[str] = None) -> bool:
        """Send email with attachments"""
        try:
            if not self.smtp_connection:
                if not self.connect():
                    return False
            
            msg = MIMEMultipart()
            msg['From'] = f"{from_name} <{self.config.username}>" if from_name else self.config.username
            msg['To'] = to_email
            msg['Subject'] = subject
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            # Add body
            if html_body:
                msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Add attachments
            for attachment_path in attachments:
                if not os.path.exists(attachment_path):
                    logger.warning(f"⚠️ Attachment not found: {attachment_path}")
                    continue
                
                ctype, encoding = mimetypes.guess_type(attachment_path)
                
                if ctype is None or encoding is not None:
                    ctype = 'application/octet-stream'
                
                maintype, subtype = ctype.split('/', 1)
                
                with open(attachment_path, 'rb') as fp:
                    if maintype == 'text':
                        attachment = MIMEText(fp.read().decode(), _subtype=subtype)
                    elif maintype == 'image':
                        attachment = MIMEImage(fp.read(), _subtype=subtype)
                    else:
                        attachment = MIMEBase(maintype, subtype)
                        attachment.set_payload(fp.read())
                        encoders.encode_base64(attachment)
                
                filename = os.path.basename(attachment_path)
                attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                msg.attach(attachment)
            
            # Build recipient list
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            self.smtp_connection.send_message(msg, to_addrs=recipients)
            
            logger.info(f"✅ Email with {len(attachments)} attachments sent to: {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending email with attachments: {e}")
            return False
    
    def send_bulk_emails(self, email_list: List[Dict[str, Any]], 
                        template_path: str = None, delay: float = 1.0) -> Dict[str, int]:
        """Send bulk emails with personalization"""
        results = {'sent': 0, 'failed': 0}
        
        try:
            if not self.smtp_connection:
                if not self.connect():
                    return results
            
            # Load template if provided
            template_content = None
            if template_path and os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    template_content = f.read()
            
            for email_data in email_list:
                try:
                    to_email = email_data['email']
                    subject = email_data.get('subject', 'No Subject')
                    body = email_data.get('body', '')
                    
                    # Apply template if available
                    if template_content:
                        personalized_body = template_content
                        for key, value in email_data.items():
                            placeholder = f"{{{{{key}}}}}"
                            personalized_body = personalized_body.replace(placeholder, str(value))
                        body = personalized_body
                    
                    success = self.send_simple_email(
                        to_email=to_email,
                        subject=subject,
                        body=body,
                        html_body=email_data.get('html_body')
                    )
                    
                    if success:
                        results['sent'] += 1
                    else:
                        results['failed'] += 1
                    
                    # Add delay to avoid overwhelming the server
                    if delay > 0:
                        time.sleep(delay)
                        
                except Exception as e:
                    logger.error(f"❌ Error sending bulk email to {email_data.get('email', 'unknown')}: {e}")
                    results['failed'] += 1
            
            logger.info(f"✅ Bulk email completed: {results['sent']} sent, {results['failed']} failed")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in bulk email operation: {e}")
            return results
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class EmailReceiver:
    """Email receiving functionality"""
    
    def __init__(self, config: EmailConfig):
        self.config = config
        self.imap_connection = None
    
    def connect(self) -> bool:
        """Establish IMAP connection"""
        try:
            self.imap_connection = imaplib.IMAP4_SSL(self.config.imap_server, self.config.imap_port)
            self.imap_connection.login(self.config.username, self.config.password)
            
            logger.info("✅ IMAP connection established")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error connecting to IMAP server: {e}")
            return False
    
    def disconnect(self):
        """Close IMAP connection"""
        try:
            if self.imap_connection:
                self.imap_connection.close()
                self.imap_connection.logout()
                self.imap_connection = None
                logger.info("✅ IMAP connection closed")
        except Exception as e:
            logger.error(f"❌ Error disconnecting from IMAP: {e}")
    
    def list_folders(self) -> List[str]:
        """List all email folders"""
        try:
            if not self.imap_connection:
                if not self.connect():
                    return []
            
            _, folders = self.imap_connection.list()
            folder_names = []
            
            for folder in folders:
                folder_info = folder.decode().split(' "/" ')
                if len(folder_info) >= 2:
                    folder_name = folder_info[-1].strip('"')
                    folder_names.append(folder_name)
            
            logger.info(f"✅ Found {len(folder_names)} folders")
            return folder_names
            
        except Exception as e:
            logger.error(f"❌ Error listing folders: {e}")
            return []
    
    def get_emails(self, folder: str = 'INBOX', search_criteria: str = 'ALL',
                   max_emails: int = 50) -> List[Dict[str, Any]]:
        """Get emails from specified folder"""
        emails = []
        
        try:
            if not self.imap_connection:
                if not self.connect():
                    return emails
            
            self.imap_connection.select(folder)
            
            # Search for emails
            _, message_ids = self.imap_connection.search(None, search_criteria)
            email_ids = message_ids[0].split()
            
            # Limit the number of emails
            email_ids = email_ids[-max_emails:] if len(email_ids) > max_emails else email_ids
            
            for email_id in email_ids:
                try:
                    _, msg_data = self.imap_connection.fetch(email_id, '(RFC822)')
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # Extract email information
                    email_info = {
                        'id': email_id.decode(),
                        'subject': email_message['Subject'] or 'No Subject',
                        'from': email_message['From'] or 'Unknown Sender',
                        'to': email_message['To'] or 'Unknown Recipient',
                        'date': email_message['Date'] or 'Unknown Date',
                        'body': self._extract_body(email_message),
                        'attachments': self._extract_attachments(email_message)
                    }
                    
                    emails.append(email_info)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing email {email_id}: {e}")
                    continue
            
            logger.info(f"✅ Retrieved {len(emails)} emails from {folder}")
            return emails
            
        except Exception as e:
            logger.error(f"❌ Error getting emails: {e}")
            return emails
    
    def _extract_body(self, email_message) -> str:
        """Extract body text from email message"""
        body = ""
        
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition'))
                    
                    if content_type == 'text/plain' and 'attachment' not in content_disposition:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    elif content_type == 'text/html' and not body and 'attachment' not in content_disposition:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                
        except Exception as e:
            logger.error(f"❌ Error extracting email body: {e}")
            body = "Error extracting body"
        
        return body
    
    def _extract_attachments(self, email_message) -> List[Dict[str, str]]:
        """Extract attachment information from email message"""
        attachments = []
        
        try:
            for part in email_message.walk():
                content_disposition = str(part.get('Content-Disposition'))
                
                if 'attachment' in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        attachment_info = {
                            'filename': filename,
                            'content_type': part.get_content_type(),
                            'size': len(part.get_payload(decode=True)) if part.get_payload(decode=True) else 0
                        }
                        attachments.append(attachment_info)
                        
        except Exception as e:
            logger.error(f"❌ Error extracting attachments: {e}")
        
        return attachments
    
    def download_attachments(self, email_id: str, download_dir: str, folder: str = 'INBOX') -> List[str]:
        """Download attachments from a specific email"""
        downloaded_files = []
        
        try:
            if not self.imap_connection:
                if not self.connect():
                    return downloaded_files
            
            self.imap_connection.select(folder)
            _, msg_data = self.imap_connection.fetch(email_id, '(RFC822)')
            email_body = msg_data[0][1]
            email_message = email.message_from_bytes(email_body)
            
            os.makedirs(download_dir, exist_ok=True)
            
            for part in email_message.walk():
                content_disposition = str(part.get('Content-Disposition'))
                
                if 'attachment' in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        file_path = os.path.join(download_dir, filename)
                        
                        with open(file_path, 'wb') as f:
                            f.write(part.get_payload(decode=True))
                        
                        downloaded_files.append(file_path)
                        logger.info(f"✅ Downloaded attachment: {filename}")
            
            return downloaded_files
            
        except Exception as e:
            logger.error(f"❌ Error downloading attachments: {e}")
            return downloaded_files
    
    def search_emails(self, query: str, folder: str = 'INBOX') -> List[Dict[str, Any]]:
        """Search emails by subject or content"""
        try:
            # Build search criteria
            search_criteria = f'(OR (SUBJECT "{query}") (BODY "{query}"))'
            return self.get_emails(folder=folder, search_criteria=search_criteria)
            
        except Exception as e:
            logger.error(f"❌ Error searching emails: {e}")
            return []
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class EmailTemplateManager:
    """Email template management"""
    
    def __init__(self, templates_dir: str):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(exist_ok=True)
    
    def create_template(self, name: str, subject: str, body: str, html_body: str = None) -> bool:
        """Create a new email template"""
        try:
            template_data = {
                'name': name,
                'subject': subject,
                'body': body,
                'html_body': html_body,
                'created_at': datetime.now().isoformat()
            }
            
            template_path = self.templates_dir / f"{name}.json"
            
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Created email template: {name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating template: {e}")
            return False
    
    def load_template(self, name: str) -> Dict[str, str]:
        """Load an email template"""
        try:
            template_path = self.templates_dir / f"{name}.json"
            
            if not template_path.exists():
                logger.error(f"❌ Template not found: {name}")
                return {}
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            logger.info(f"✅ Loaded email template: {name}")
            return template_data
            
        except Exception as e:
            logger.error(f"❌ Error loading template: {e}")
            return {}
    
    def list_templates(self) -> List[str]:
        """List all available templates"""
        try:
            templates = []
            for template_file in self.templates_dir.glob("*.json"):
                templates.append(template_file.stem)
            
            logger.info(f"✅ Found {len(templates)} email templates")
            return templates
            
        except Exception as e:
            logger.error(f"❌ Error listing templates: {e}")
            return []
    
    def apply_template(self, template_name: str, variables: Dict[str, str]) -> Dict[str, str]:
        """Apply variables to template"""
        try:
            template = self.load_template(template_name)
            
            if not template:
                return {}
            
            # Replace variables in subject and body
            subject = template.get('subject', '')
            body = template.get('body', '')
            html_body = template.get('html_body', '')
            
            for variable, value in variables.items():
                placeholder = f"{{{{{variable}}}}}"
                subject = subject.replace(placeholder, str(value))
                body = body.replace(placeholder, str(value))
                if html_body:
                    html_body = html_body.replace(placeholder, str(value))
            
            return {
                'subject': subject,
                'body': body,
                'html_body': html_body
            }
            
        except Exception as e:
            logger.error(f"❌ Error applying template: {e}")
            return {}


def test_email_automation():
    """Test function for email automation"""
    print("🧪 Testing Email Automation...")
    
    # This is a test function - would need real credentials to work
    print("⚠️ Email automation requires real SMTP/IMAP credentials")
    print("📧 Configure email settings in settings.yaml for testing")
    
    # Test template manager
    try:
        template_manager = EmailTemplateManager("test_templates")
        
        # Create test template
        template_manager.create_template(
            name="welcome",
            subject="Welcome {{name}}!",
            body="Hello {{name}},\n\nWelcome to our service!\n\nBest regards,\nThe Team"
        )
        
        # Apply template
        applied = template_manager.apply_template("welcome", {"name": "John Doe"})
        print(f"✅ Template test: {applied.get('subject', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Template test failed: {e}")
    
    print("🏁 Email automation tests completed")


if __name__ == "__main__":
    test_email_automation()