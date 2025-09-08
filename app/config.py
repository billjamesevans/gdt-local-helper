import os

class Settings:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-not-for-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///gdt_helper.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH_MB', '25')) * 1024 * 1024  # bytes

    WTF_CSRF_ENABLED = os.getenv('WTF_CSRF_ENABLED', 'true').lower() not in ('0','false','no')

    # PDF.js CDN (adjust if you need to pin a different version)
    PDFJS_JS = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.3.136/pdf.min.js'
    PDFJS_WORKER = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.3.136/pdf.worker.min.js'

    # Feature flags / UI
    HIGH_CONTRAST_DEFAULT = False
