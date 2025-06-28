#!/usr/bin/env python3
"""Example script showing how to use the JSON output from notion-dev CLI"""

import subprocess
import json

def get_current_task_info():
    """Get information about the current task being worked on"""
    result = subprocess.run(['notion-dev', 'info', '--json'], capture_output=True, text=True)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return data.get('current_task')
    return None

def get_all_tickets():
    """Get all assigned tickets"""
    result = subprocess.run(['notion-dev', 'tickets', '--json'], capture_output=True, text=True)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return data.get('tasks', [])
    return []

def main():
    """Example usage of JSON output"""
    
    # Get current task info
    print("Current Task Information:")
    current_task = get_current_task_info()
    if current_task:
        print(f"- ID: {current_task['id']}")
        print(f"- Name: {current_task['name']}")
        print(f"- Feature Code: {current_task['feature_code']}")
        print(f"- Status: {current_task['status']}")
        print(f"- Asana URL: {current_task['url']}")
        if current_task['notion_url']:
            print(f"- Notion URL: {current_task['notion_url']}")
    else:
        print("No task currently being worked on")
    
    print("\n" + "="*60 + "\n")
    
    # Get all tickets
    print("All Assigned Tickets:")
    tickets = get_all_tickets()
    
    # Group by status
    in_progress = [t for t in tickets if t['status'] == 'in_progress']
    completed = [t for t in tickets if t['status'] == 'completed']
    
    print(f"\nIn Progress ({len(in_progress)} tickets):")
    for ticket in in_progress[:5]:  # Show first 5
        print(f"- [{ticket['feature_code'] or '???'}] {ticket['name'][:50]}...")
    
    print(f"\nCompleted ({len(completed)} tickets):")
    for ticket in completed[:5]:  # Show first 5
        print(f"- [{ticket['feature_code'] or '???'}] {ticket['name'][:50]}...")
    
    # Example: Find tickets with due dates
    tickets_with_due_dates = [t for t in tickets if t.get('due_on')]
    if tickets_with_due_dates:
        print(f"\nTickets with due dates ({len(tickets_with_due_dates)}):")
        for ticket in tickets_with_due_dates[:5]:
            print(f"- {ticket['name'][:50]}... (Due: {ticket['due_on']})")

if __name__ == "__main__":
    main()