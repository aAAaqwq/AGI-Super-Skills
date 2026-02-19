#!/usr/bin/env python3
"""
Google Tasks Sync - Fetches tasks from Google Tasks API
"""
import os
import json
import sys

# Add path for google auth
sys.path.insert(0, '/Users/tom/Library/Python/3.9/lib/python/site-packages')

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime

SCOPES = ['https://www.googleapis.com/auth/tasks.readonly']

def get_credentials():
    """Get or refresh Google credentials."""
    creds_dir = os.path.expanduser('~/.openclaw/google-tasks')
    token_path = os.path.join(creds_dir, 'token.json')
    creds_path = os.path.join(creds_dir, 'credentials.json')
    
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                print(f"❌ Credentials not found at {creds_path}")
                print("Please set up Google Tasks API first")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    
    return creds

def sync_tasks():
    """Sync Google Tasks to local JSON file."""
    creds = get_credentials()
    if not creds:
        return False
    
    try:
        service = build('tasks', 'v1', credentials=creds, cache_discovery=False)
        
        # Get all task lists
        tasklists = service.tasklists().list().execute()
        
        all_data = {
            'synced_at': datetime.now().isoformat(),
            'tasklists': []
        }
        
        for tasklist in tasklists.get('items', []):
            list_id = tasklist['id']
            list_title = tasklist['title']
            
            # Get tasks for this list
            tasks_result = service.tasks().list(tasklist=list_id, showCompleted=False).execute()
            tasks = tasks_result.get('items', [])
            
            tasklist_data = {
                'id': list_id,
                'title': list_title,
                'updated': tasklist.get('updated'),
                'task_count': len(tasks),
                'tasks': []
            }
            
            for task in tasks:
                task_data = {
                    'id': task['id'],
                    'title': task['title'],
                    'notes': task.get('notes', ''),
                    'due': task.get('due'),
                    'updated': task.get('updated'),
                    'position': task.get('position'),
                    'parent': task.get('parent'),
                    'links': task.get('links', [])
                }
                tasklist_data['tasks'].append(task_data)
            
            all_data['tasklists'].append(tasklist_data)
        
        # Save to memory file
        output_dir = '/Users/tom/.openclaw/workspace/memory'
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'google-tasks.json')
        
        with open(output_path, 'w') as f:
            json.dump(all_data, f, indent=2)
        
        total_tasks = sum(tl['task_count'] for tl in all_data['tasklists'])
        print(f"✅ Synced {total_tasks} tasks to {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error syncing tasks: {e}")
        return False

if __name__ == '__main__':
    sync_tasks()
