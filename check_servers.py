import requests
import sys
import time

def check_backend():
    try:
        # Check backend health
        response = requests.get("http://localhost:8000/health")
        if response.status_code == 200:
            print("✅ Backend is running and healthy")
            print("Environment status:")
            env = response.json().get("environment", {})
            for key, value in env.items():
                print(f"  - {key}: {'✅' if value else '❌'}")
        else:
            print("❌ Backend is running but unhealthy")
            print(response.json())
    except requests.exceptions.ConnectionError:
        print("❌ Backend is not running")
        return False
    return True

def check_frontend():
    try:
        # Check frontend
        response = requests.get("http://localhost:3000")
        if response.status_code == 200:
            print("✅ Frontend is running")
        else:
            print("❌ Frontend is running but returned status code:", response.status_code)
    except requests.exceptions.ConnectionError:
        print("❌ Frontend is not running")
        return False
    return True

def main():
    print("Checking servers...")
    
    # Check backend
    backend_ok = check_backend()
    if not backend_ok:
        print("\nTo start the backend server:")
        print("cd backend")
        print("uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    
    # Check frontend
    frontend_ok = check_frontend()
    if not frontend_ok:
        print("\nTo start the frontend server:")
        print("cd frontend")
        print("npm start")
    
    if not (backend_ok and frontend_ok):
        sys.exit(1)

if __name__ == "__main__":
    main() 