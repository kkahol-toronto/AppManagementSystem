import requests
import json

def test_chat_endpoint():
    # API endpoint
    url = "http://localhost:8000/chat"
    
    # Request payload
    payload = {
        "message": "Add diagram rendering functionality",
        "github_link": "https://github.com/your-repo/your-project.git",
        "username": "kkahol-toronto",
        "descriptive_name": "add-diagram-rendering"
    }
    
    # Make the request
    response = requests.post(url, json=payload)
    
    # Print response
    print("Status Code:", response.status_code)
    print("Response:", json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    test_chat_endpoint() 