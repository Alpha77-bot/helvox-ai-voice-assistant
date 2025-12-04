#!/usr/bin/env python3
"""
Weaviate Backup and Restore Utility

This script provides backup and restore functionality for Weaviate databases using filesystem backend.
Supports cross-system backup/restore by transferring the backup directory between systems.

Usage:
    python weaviate_backup.py backup --id my-backup
    python weaviate_backup.py restore --id my-backup
    python weaviate_backup.py status --id my-backup --operation backup
    python weaviate_backup.py list-collections

Cross-System Migration:
    1. On System A: python weaviate_backup.py backup --id migration-backup
    2. Copy ./backups/migration-backup directory to System B
    3. On System B: python weaviate_backup.py restore --id migration-backup
"""

import argparse
import json
import os
import sys
import time
from typing import List, Optional
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

load_dotenv()


class WeaviateBackupClient:
    """Client for Weaviate backup and restore operations"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8081,
        scheme: str = "http",
        timeout: int = 300
    ):
        self.base_url = f"{scheme}://{host}:{port}"
        self.timeout = timeout
        self.session = requests.Session()
    
    def create_backup(
        self,
        backup_id: str,
        include_collections: Optional[List[str]] = None,
        exclude_collections: Optional[List[str]] = None,
        wait_for_completion: bool = True,
        wait_timeout: int = 300
    ) -> dict:
        """
        Create a backup of Weaviate data to filesystem
        
        Args:
            backup_id: Unique identifier for the backup
            include_collections: List of collections to include (None = all)
            exclude_collections: List of collections to exclude
            wait_for_completion: Wait for backup to complete before returning
            wait_timeout: Maximum time to wait for completion (seconds)
            
        Returns:
            Response dictionary with backup status
        """
        url = urljoin(self.base_url, "/v1/backups/filesystem")
        
        payload = {"id": backup_id}
        
        if include_collections:
            payload["include"] = include_collections
        if exclude_collections:
            payload["exclude"] = exclude_collections
        
        print(f"Starting backup '{backup_id}'...")
        
        try:
            response = self.session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            
            print("Backup initiated successfully")
            print(f"Status: {result.get('status', 'UNKNOWN')}")
            
            if wait_for_completion:
                result = self._wait_for_backup_completion(backup_id, wait_timeout)
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Backup failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"Error details: {json.dumps(error_detail, indent=2)}")
                except:
                    print(f"Response: {e.response.text}")
            raise
    
    def _wait_for_backup_completion(self, backup_id: str, timeout: int) -> dict:
        """Wait for backup operation to complete"""
        start_time = time.time()
        
        print("Waiting for backup to complete...")
        
        while time.time() - start_time < timeout:
            status = self.get_backup_status(backup_id, verbose=False)
            
            current_status = status.get('status', 'UNKNOWN')
            
            if current_status == "SUCCESS":
                elapsed = time.time() - start_time
                print(f"Backup completed successfully in {elapsed:.1f}s")
                return status
            elif current_status == "FAILED":
                print("Backup failed")
                if 'error' in status:
                    print(f"Error: {status['error']}")
                return status
            elif current_status in ["STARTED", "TRANSFERRING"]:
                print(f"Status: {current_status}...", end='\r')
                time.sleep(2)
            else:
                time.sleep(2)
        
        print(f"Backup timeout reached after {timeout}s")
        return self.get_backup_status(backup_id, verbose=False)
    
    def get_backup_status(self, backup_id: str, verbose: bool = True) -> dict:
        """
        Get the status of a backup operation
        
        Args:
            backup_id: Backup identifier
            verbose: Print status information
            
        Returns:
            Response dictionary with backup status
        """
        url = urljoin(self.base_url, f"/v1/backups/filesystem/{backup_id}")
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            
            if verbose:
                print(f"Backup Status for '{backup_id}':")
                print(json.dumps(result, indent=2))
            
            return result
            
        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"Failed to get backup status: {e}")
            raise
    
    def restore_backup(
        self,
        backup_id: str,
        include_collections: Optional[List[str]] = None,
        exclude_collections: Optional[List[str]] = None,
        wait_for_completion: bool = True,
        wait_timeout: int = 300
    ) -> dict:
        """
        Restore data from a backup
        
        Args:
            backup_id: Backup identifier to restore
            include_collections: List of collections to restore (None = all)
            exclude_collections: List of collections to exclude from restore
            wait_for_completion: Wait for restore to complete before returning
            wait_timeout: Maximum time to wait for completion (seconds)
            
        Returns:
            Response dictionary with restore status
        """
        url = urljoin(self.base_url, f"/v1/backups/filesystem/{backup_id}/restore")
        
        payload = {"id": backup_id}
        
        if include_collections:
            payload["include"] = include_collections
        if exclude_collections:
            payload["exclude"] = exclude_collections
        
        print(f"Starting restore from backup '{backup_id}'...")
        
        try:
            response = self.session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            
            print("Restore initiated successfully")
            print(f"Status: {result.get('status', 'UNKNOWN')}")
            
            if wait_for_completion:
                result = self._wait_for_restore_completion(backup_id, wait_timeout)
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Restore failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"Error details: {json.dumps(error_detail, indent=2)}")
                except:
                    print(f"Response: {e.response.text}")
            raise
    
    def _wait_for_restore_completion(self, backup_id: str, timeout: int) -> dict:
        """Wait for restore operation to complete"""
        start_time = time.time()
        
        print("Waiting for restore to complete...")
        
        while time.time() - start_time < timeout:
            status = self.get_restore_status(backup_id, verbose=False)
            
            current_status = status.get('status', 'UNKNOWN')
            
            if current_status == "SUCCESS":
                elapsed = time.time() - start_time
                print(f"Restore completed successfully in {elapsed:.1f}s")
                return status
            elif current_status == "FAILED":
                print("Restore failed")
                if 'error' in status:
                    print(f"Error: {status['error']}")
                return status
            elif current_status in ["STARTED", "TRANSFERRING"]:
                print(f"Status: {current_status}...", end='\r')
                time.sleep(2)
            else:
                time.sleep(2)
        
        print(f"Restore timeout reached after {timeout}s")
        return self.get_restore_status(backup_id, verbose=False)
    
    def get_restore_status(self, backup_id: str, verbose: bool = True) -> dict:
        """
        Get the status of a restore operation
        
        Args:
            backup_id: Backup identifier
            verbose: Print status information
            
        Returns:
            Response dictionary with restore status
        """
        url = urljoin(self.base_url, f"/v1/backups/filesystem/{backup_id}/restore")
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            
            if verbose:
                print(f"Restore Status for '{backup_id}':")
                print(json.dumps(result, indent=2))
            
            return result
            
        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"Failed to get restore status: {e}")
            raise
    
    def list_collections(self) -> List[str]:
        """
        List all collections in the Weaviate instance
        
        Returns:
            List of collection names
        """
        url = urljoin(self.base_url, "/v1/schema")
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            schema = response.json()
            
            collections = [cls['class'] for cls in schema.get('classes', [])]
            
            return collections
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to list collections: {e}")
            raise


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Weaviate Backup and Restore Utility (Filesystem Backend)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a backup
  python weaviate_backup.py backup --id my-backup-20250123
  
  # Create a backup with specific collections
  python weaviate_backup.py backup --id my-backup --include Collection1 Collection2
  
  # Restore a backup
  python weaviate_backup.py restore --id my-backup-20250123
  
  # Restore specific collections from a backup
  python weaviate_backup.py restore --id my-backup --include Collection1
  
  # Check backup status
  python weaviate_backup.py status --id my-backup-20250123 --operation backup
  
  # Check restore status
  python weaviate_backup.py status --id my-backup-20250123 --operation restore
  
  # List available collections
  python weaviate_backup.py list-collections

Cross-System Backup/Restore:
  1. On System A: python weaviate_backup.py backup --id migration-backup
  2. Copy ./backups/migration-backup directory to System B
  3. On System B: python weaviate_backup.py restore --id migration-backup
        """
    )
    
    # Connection parameters
    parser.add_argument(
        "--host",
        default=os.getenv("WEAVIATE_HOST", "localhost"),
        help="Weaviate host (default: localhost or WEAVIATE_HOST env var)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("WEAVIATE_PORT", "8081")),
        help="Weaviate port (default: 8081 or WEAVIATE_PORT env var)"
    )
    parser.add_argument(
        "--scheme",
        choices=["http", "https"],
        default="http",
        help="Connection scheme (default: http)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Request timeout in seconds (default: 300)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Create a backup")
    backup_parser.add_argument(
        "--id",
        required=True,
        help="Unique backup identifier"
    )
    backup_parser.add_argument(
        "--include",
        nargs="+",
        help="Collections to include in backup (default: all)"
    )
    backup_parser.add_argument(
        "--exclude",
        nargs="+",
        help="Collections to exclude from backup"
    )
    backup_parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for backup to complete"
    )
    backup_parser.add_argument(
        "--wait-timeout",
        type=int,
        default=300,
        help="Maximum time to wait for completion in seconds (default: 300)"
    )
    
    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore from a backup")
    restore_parser.add_argument(
        "--id",
        required=True,
        help="Backup identifier to restore"
    )
    restore_parser.add_argument(
        "--include",
        nargs="+",
        help="Collections to restore (default: all from backup)"
    )
    restore_parser.add_argument(
        "--exclude",
        nargs="+",
        help="Collections to exclude from restore"
    )
    restore_parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for restore to complete"
    )
    restore_parser.add_argument(
        "--wait-timeout",
        type=int,
        default=300,
        help="Maximum time to wait for completion in seconds (default: 300)"
    )
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check backup or restore status")
    status_parser.add_argument(
        "--id",
        required=True,
        help="Backup identifier"
    )
    status_parser.add_argument(
        "--operation",
        choices=["backup", "restore"],
        required=True,
        help="Operation type to check status for"
    )
    
    # List collections command
    list_parser = subparsers.add_parser(
        "list-collections",
        help="List all collections in Weaviate instance"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Create client
    client = WeaviateBackupClient(
        host=args.host,
        port=args.port,
        scheme=args.scheme,
        timeout=args.timeout
    )
    
    try:
        if args.command == "backup":
            result = client.create_backup(
                backup_id=args.id,
                include_collections=args.include,
                exclude_collections=args.exclude,
                wait_for_completion=not args.no_wait,
                wait_timeout=args.wait_timeout
            )
            
            print("\nBackup Details:")
            print(json.dumps(result, indent=2))
            
            if result.get('status') == 'SUCCESS':
                print(f"\nBackup '{args.id}' created successfully!")
                print(f"Backup location: ./backups/{args.id}/")
            else:
                print(f"\nBackup status: {result.get('status')}")
                sys.exit(1)
        
        elif args.command == "restore":
            result = client.restore_backup(
                backup_id=args.id,
                include_collections=args.include,
                exclude_collections=args.exclude,
                wait_for_completion=not args.no_wait,
                wait_timeout=args.wait_timeout
            )
            
            print("\nRestore Details:")
            print(json.dumps(result, indent=2))
            
            if result.get('status') == 'SUCCESS':
                print(f"\nData restored successfully from backup '{args.id}'!")
            else:
                print(f"\nRestore status: {result.get('status')}")
                sys.exit(1)
        
        elif args.command == "status":
            if args.operation == "backup":
                result = client.get_backup_status(args.id)
            else:
                result = client.get_restore_status(args.id)
        
        elif args.command == "list-collections":
            collections = client.list_collections()
            
            print("Collections in Weaviate:")
            if collections:
                for i, collection in enumerate(collections, 1):
                    print(f"  {i}. {collection}")
                print(f"\nTotal: {len(collections)} collection(s)")
            else:
                print("No collections found")
    
    except Exception as e:
        print(f"\nOperation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
