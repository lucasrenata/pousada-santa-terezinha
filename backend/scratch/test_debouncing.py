import requests
import time
import threading

BASE_URL = "http://localhost:8003" 
SESSION_ID = "test_debounce_" + str(int(time.time()))
TENANT_ID = 1

def send_msg(msg):
    url = f"{BASE_URL}/chat/customer"
    payload = {
        "message": msg,
        "session_id": SESSION_ID,
        "tenant_id": TENANT_ID
    }
    try:
        resp = requests.post(url, json=payload)
        data = resp.json()
        print(f"Sent: '{msg}' | Status: {resp.status_code} | Job Status: {data.get('status')}")
        return data
    except Exception as e:
        print(f"Error sending '{msg}': {e}")
        return {}

def test_debouncing():
    print(f"--- Starting Debouncing Test (Session: {SESSION_ID}) ---")
    
    t1 = threading.Thread(target=send_msg, args=("Ola,",))
    t2 = threading.Thread(target=send_msg, args=("queria saber",))
    t3 = threading.Thread(target=send_msg, args=("sobre os quartos.",))
    
    t1.start()
    time.sleep(0.3)
    t2.start()
    time.sleep(0.3)
    t3.start()
    
    t1.join()
    t2.join()
    t3.join()
    
    print("\nWaiting for processing (delay + AI)...")
    time.sleep(10) 
    
    hist_url = f"{BASE_URL}/chat/history/{SESSION_ID}?tenant_id={TENANT_ID}"
    resp = requests.get(hist_url)
    history = resp.json()
    
    print("\nFINAL HISTORY:")
    for m in history:
        # Avoid emojis in print
        content = m['content'].encode('ascii', 'ignore').decode('ascii')
        print(f"[{m['role'].upper()}]: {content}")

if __name__ == "__main__":
    test_debouncing()
