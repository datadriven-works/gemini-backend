import hmac
import hashlib
import requests
import json
import argparse  # Import the argparse module

def generate_hmac_signature(secret_key, data):
    """
    Generate HMAC-SHA256 signature for the given data using the secret key.
    """
    hmac_obj = hmac.new(secret_key.encode(), json.dumps(data).encode(), hashlib.sha256)
    return hmac_obj.hexdigest()

def send_request(url, data, signature):
    """
    Send a POST request to the given URL with the provided data and HMAC signature.
    """
    headers = {
        'Content-Type': 'application/json',
        'X-Signature': signature
    }
    response = requests.post(url, headers=headers, json=data)
    return response.text

def main(url):
    # Request payload
    data = {"contents": "how are you doing?", "parameters": {"max_output_tokens": 1000}}

    # Read the secret key from a file
    with open('../.vertex_cf_auth_token', 'r') as file:
        secret_key = file.read().strip()  # Remove any potential newline characters

    # Generate HMAC signature
    signature = generate_hmac_signature(secret_key, data)

    # Send the request
    response = send_request(url, data, signature)
    print("Response from server:", response)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a secured request to a server.")
    parser.add_argument('--backend-url', type=str, default='http://127.0.0.1:8000',
                        help='URL to send the request to (default: http://127.0.0.1:8000)')
    args = parser.parse_args()
    main(args.backend_url)
