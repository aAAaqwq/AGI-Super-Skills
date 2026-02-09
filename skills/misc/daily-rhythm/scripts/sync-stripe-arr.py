#!/usr/bin/env python3
"""
Stripe ARR Sync - Fetches active subscriptions and calculates ARR
"""
import os
import json
import warnings
from datetime import datetime

# Suppress urllib3 SSL warning on macOS (LibreSSL vs OpenSSL)
warnings.filterwarnings('ignore', category=UserWarning, module='urllib3')

import stripe

def load_config():
    """Load Stripe API key from env file."""
    env_paths = [
        '/Users/tom/.openclaw/workspace/.env.stripe',
        os.path.expanduser('~/.openclaw/workspace/.env.stripe'),
        '.env.stripe'
    ]
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
            break
    
    return os.environ.get('STRIPE_API_KEY')

def fetch_active_subscriptions():
    """Fetch all active subscriptions from Stripe."""
    api_key = load_config()
    if not api_key:
        print("❌ No Stripe API key found")
        return None
    
    stripe.api_key = api_key
    
    try:
        subscriptions = stripe.Subscription.list(
            status='active',
            limit=100,
            expand=['data.customer']
        )
        return subscriptions.data
    except Exception as e:
        print(f"❌ Stripe API error: {e}")
        return None

def calculate_arr(subscriptions):
    """Calculate ARR from active subscriptions."""
    if not subscriptions:
        return 0, 0, []
    
    customer_subscriptions = {}
    
    for sub in subscriptions:
        customer = sub.get('customer')
        if isinstance(customer, dict):
            customer_id = customer.get('id')
        else:
            customer_id = customer
        
        if not customer_id:
            continue
        
        # Calculate subscription amount
        amount_cents = 0
        for item in sub.get('items', {}).get('data', []):
            amount_cents += item.get('price', {}).get('unit_amount', 0) * item.get('quantity', 1)
        
        amount_gbp = amount_cents / 100
        interval = sub.get('items', {}).get('data', [{}])[0].get('price', {}).get('recurring', {}).get('interval', 'month')
        
        if interval == 'month':
            annual_amount = amount_gbp * 12
        elif interval == 'year':
            annual_amount = amount_gbp
        elif interval == 'week':
            annual_amount = amount_gbp * 52
        else:
            annual_amount = amount_gbp * 12
        
        if customer_id in customer_subscriptions:
            customer_subscriptions[customer_id] += annual_amount
        else:
            customer_subscriptions[customer_id] = annual_amount
    
    total_arr = round(sum(customer_subscriptions.values()))
    customer_count = len(customer_subscriptions)
    
    return total_arr, customer_count, list(customer_subscriptions.keys())

def sync_stripe():
    """Main sync function."""
    subscriptions = fetch_active_subscriptions()
    if subscriptions is None:
        return False
    
    arr, customer_count, customer_ids = calculate_arr(subscriptions)
    
    # Save detailed data
    output_dir = '/Users/tom/.openclaw/workspace/memory'
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'stripe-data.json')
    
    data = {
        'synced_at': datetime.now().isoformat(),
        'arr': arr,
        'customer_count': customer_count,
        'customer_ids': customer_ids,
        'subscription_count': len(subscriptions),
        'method': 'active_subscriptions_only'
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Update heartbeat state
    heartbeat_path = os.path.join(output_dir, 'heartbeat-state.json')
    if os.path.exists(heartbeat_path):
        with open(heartbeat_path, 'r') as f:
            hb_data = json.load(f)
    else:
        hb_data = {}
    
    hb_data['arrCurrent'] = arr
    hb_data['customerCount'] = customer_count
    hb_data['arrLastSynced'] = datetime.now().isoformat()
    
    with open(heartbeat_path, 'w') as f:
        json.dump(hb_data, f, indent=2)
    
    print(f"✅ Updated ARR: £{arr:,} ({customer_count} active customers)")
    return True

if __name__ == '__main__':
    sync_stripe()
