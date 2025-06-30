#!/usr/bin/env python3
"""
Check ngrok tunnel status
"""

from pyngrok import ngrok

def check_ngrok_status():
    """Check ngrok tunnel status"""
    try:
        tunnels = ngrok.get_ngrok_process().api_client.get_tunnels()
        
        if tunnels:
            print("✅ Active ngrok tunnels:")
            for tunnel in tunnels:
                print(f"  🌐 Public URL: {tunnel.public_url}")
                print(f"  🔗 Local: {tunnel.config['addr']}")
                print(f"  📡 Webhook URL: {tunnel.public_url}/webhook")
                print()
        else:
            print("❌ No active ngrok tunnels found")
            
    except Exception as e:
        print(f"❌ Error checking ngrok status: {e}")

if __name__ == "__main__":
    check_ngrok_status() 