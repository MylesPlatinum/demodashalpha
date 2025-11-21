"""
Google Drive Watcher - Monitors drive folder and syncs Excel files
"""

import os
import time
import json
from pathlib import Path
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io


class GDriveWatcher:
    """Watches Google Drive folder and syncs Excel files"""
    
    def __init__(self, credentials_path='gdrive_credentials.json', config_path='config.yaml'):
        """
        Initialize watcher
        
        Args:
            credentials_path: Path to service account JSON
            config_path: Path to config.yaml
        """
        self.credentials_path = credentials_path
        self.local_data_dir = Path('data')
        self.local_data_dir.mkdir(exist_ok=True)
        
        # Load config for folder ID
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.folder_id = config.get('gdrive', {}).get('folder_id')
        if not self.folder_id:
            raise ValueError("No 'gdrive.folder_id' found in config.yaml")
        
        # Track downloaded files
        self.sync_log = self.local_data_dir / '.gdrive_sync.json'
        self.synced_files = self._load_sync_log()
        
        # Initialize Google Drive API
        self.service = self._init_drive_service()
        
        print(f"✅ GDrive Watcher initialized")
        print(f"   Monitoring folder: {self.folder_id}")
        print(f"   Local directory: {self.local_data_dir}")
    
    def _init_drive_service(self):
        """Initialize Google Drive API service"""
        if not Path(self.credentials_path).exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self.credentials_path}\n"
                "Follow setup instructions to create service account"
            )
        
        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path, scopes=SCOPES
        )
        
        service = build('drive', 'v3', credentials=credentials)
        return service
    
    def _load_sync_log(self):
        """Load record of synced files"""
        if self.sync_log.exists():
            with open(self.sync_log, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_sync_log(self):
        """Save record of synced files"""
        with open(self.sync_log, 'w') as f:
            json.dump(self.synced_files, f, indent=2)
    
    def list_drive_files(self):
        """List Excel files in watched folder"""
        query = f"'{self.folder_id}' in parents and (mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or mimeType='application/vnd.ms-excel') and trashed=false"
        
        results = self.service.files().list(
            q=query,
            fields="files(id, name, modifiedTime, size)",
            orderBy="modifiedTime desc"
        ).execute()
        
        return results.get('files', [])
    
    def download_file(self, file_id, file_name):
        """Download file from Drive to local data folder"""
        request = self.service.files().get_media(fileId=file_id)
        
        local_path = self.local_data_dir / file_name
        
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"   Download {int(status.progress() * 100)}%")
        
        # Write to file
        with open(local_path, 'wb') as f:
            f.write(fh.getvalue())
        
        print(f"✅ Downloaded: {file_name}")
        return local_path
    
    def sync_once(self):
        """
        Check for new/updated files and download them
        Returns: List of newly downloaded files
        """
        print(f"\n🔍 Checking Google Drive at {datetime.now():%H:%M:%S}")
        
        drive_files = self.list_drive_files()
        new_downloads = []
        
        for file in drive_files:
            file_id = file['id']
            file_name = file['name']
            modified_time = file['modifiedTime']
            
            # Check if file is new or updated
            if file_id not in self.synced_files or self.synced_files[file_id]['modified'] != modified_time:
                print(f"📥 Syncing: {file_name}")
                
                try:
                    local_path = self.download_file(file_id, file_name)
                    
                    # Update sync log
                    self.synced_files[file_id] = {
                        'name': file_name,
                        'modified': modified_time,
                        'local_path': str(local_path),
                        'synced_at': datetime.now().isoformat()
                    }
                    
                    new_downloads.append(file_name)
                    
                except Exception as e:
                    print(f"❌ Error downloading {file_name}: {e}")
            else:
                print(f"✓ Up to date: {file_name}")
        
        if new_downloads:
            self._save_sync_log()
            print(f"\n✅ Synced {len(new_downloads)} file(s)")
        else:
            print("✓ All files up to date")
        
        return new_downloads
    
    def watch(self, interval_seconds=60):
        """
        Continuously watch folder and sync files
        
        Args:
            interval_seconds: How often to check (default: 60)
        """
        print(f"👁️  Watching Google Drive (checking every {interval_seconds}s)")
        print("   Press Ctrl+C to stop")
        
        try:
            while True:
                self.sync_once()
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n⏹️  Watcher stopped")


# ============================================================================
# STREAMLIT INTEGRATION FUNCTION
# ============================================================================

def check_and_sync_drive(config):
    """
    Check Drive for updates and sync files
    Called by dashboard on startup/refresh
    
    Returns: True if new files downloaded
    """
    try:
        # Check if GDrive integration is enabled
        if not config.get('gdrive', {}).get('enabled', False):
            return False
        
        watcher = GDriveWatcher(config_path='config.yaml')
        new_files = watcher.sync_once()
        
        return len(new_files) > 0
        
    except Exception as e:
        print(f"⚠️ GDrive sync failed: {e}")
        return False


# ============================================================================
# STANDALONE RUNNER
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Google Drive Watcher')
    parser.add_argument('--once', action='store_true', help='Sync once and exit')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
    
    args = parser.parse_args()
    
    watcher = GDriveWatcher()
    
    if args.once:
        watcher.sync_once()
    else:
        watcher.watch(interval_seconds=args.interval)
