import unittest
import hmac
import hashlib
import json
import requests
import os


class LiveBackendTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Backend URL
        cls.backend_url = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
        # Full path for the /generate_content endpoint
        cls.generate_content_url = f"{cls.backend_url}/generate_content"
        # Load the secret key from the file
        with open('../.vertex_cf_auth_token', 'r') as file:
            cls.secret_key = file.read().strip()  # Remove any potential newline characters

    def generate_hmac_signature(self, secret_key, data):
        """
        Generate HMAC-SHA256 signature for the given data using the secret key.
        """
        hmac_obj = hmac.new(secret_key.encode(), json.dumps(data).encode(), hashlib.sha256)
        return hmac_obj.hexdigest()

    def send_request(self, url, data, signature):
        """
        Send a POST request to the backend with the provided data and HMAC signature.
        """
        headers = {
            'Content-Type': 'application/json',
            'X-Signature': signature
        }
        response = requests.post(url, headers=headers, json=data)
        return response

    def test_generate_query_default_parameters(self):
        # Define payload with default parameters
        data = {
            "contents": "how are you doing?",
            "parameters": {"max_output_tokens": 1000}
        }
        # Generate HMAC signature
        signature = self.generate_hmac_signature(self.secret_key, data)

        # Send the request to the /generate_content endpoint
        response = self.send_request(self.generate_content_url, data, signature)

        # Assert response
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.text), 0)

    def test_generate_query_custom_parameters(self):
        # Define payload with custom parameters
        data = {
            "contents": "generate an example SQL query for some made up sales data. Use an invoice table. Return the full SQL statement",
            "parameters": {"max_output_tokens": 8192, "temperature": 1.2}
        }
        # Generate HMAC signature
        signature = self.generate_hmac_signature(self.secret_key, data)

        # Send the request to the /generate_content endpoint
        response = self.send_request(self.generate_content_url, data, signature)

        # Assert response
        self.assertEqual(response.status_code, 200)
        self.assertIn("select", response.text.lower())

    def test_generate_query_with_model_name(self):
        # Define payload with a model name
        data = {
            "contents": "write an exploratory query",
            "parameters": {"max_output_tokens": 200},
            "model_name": "gemini-2.0-flash-exp"
        }
        # Generate HMAC signature
        signature = self.generate_hmac_signature(self.secret_key, data)

        # Send the request to the /generate_content endpoint
        response = self.send_request(self.generate_content_url, data, signature)

        # Assert response
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.text), 0)

    def test_invalid_signature(self):
        # Define payload
        data = {
            "contents": "how are you doing?",
            "parameters": {"max_output_tokens": 1000}
        }
        # Use an invalid HMAC signature
        invalid_signature = "invalid_signature"

        # Send the request to the /generate_content endpoint
        response = self.send_request(self.generate_content_url, data, invalid_signature)

        # Assert response
        self.assertEqual(response.status_code, 403)
        self.assertIn("Invalid signature", response.text)

    def test_generate_query_with_response_schema(self):
        # Define payload with a response schema
        data = {
            "contents": "make me a list of recipes",
            "parameters": {"max_output_tokens": 500, "temperature": 0.3},
            "response_schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "recipe_name": {
                            "type": "string",
                            "description": "The name of the recipe."
                        },
                        "ingredients": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "A list of ingredients used in the recipe."
                        }
                    },
                    "required": ["recipe_name", "ingredients"]
                }
            }
        }
        
        # Generate HMAC signature
        signature = self.generate_hmac_signature(self.secret_key, data)

        # Send the request to the /generate_content endpoint
        response = self.send_request(self.generate_content_url, data, signature)

        # Assert response
        self.assertEqual(response.status_code, 200)

        # Validate response JSON
        response_json = response.json()
        self.assertIsInstance(response_json, list)  # Ensure the response is a list
        for recipe in response_json:
            self.assertIsInstance(recipe, dict)  # Each item should be a dictionary
            self.assertIn("recipe_name", recipe)
            self.assertIn("ingredients", recipe)
            self.assertIsInstance(recipe["recipe_name"], str)
            self.assertIsInstance(recipe["ingredients"], list)
            for ingredient in recipe["ingredients"]:
                self.assertIsInstance(ingredient, str)  # Each ingredient should be a string

    def test_exception_handling(self):
        # Define payload that will likely cause an error (e.g., invalid parameter type)
        data = {
            "contents": "this should trigger an exception",
            "parameters": {"max_output_tokens": "invalid_type"}  # Invalid type for max_output_tokens
        }
        # Generate HMAC signature
        signature = self.generate_hmac_signature(self.secret_key, data)

        # Send the request to the /generate_content endpoint
        response = self.send_request(self.generate_content_url, data, signature)

        # Assert response
        self.assertEqual(response.status_code, 500)  # Ensure it's an internal server error
        self.assertIn("error", response.json())  # Check that the response contains an "error" key
        self.assertIsInstance(response.json()["error"], str)  # Ensure the error message is a string
        self.assertIn("gemini model error", response.json()["error"].lower())  # Validate the content of the error message


    def test_generate_with_simple_history(self):
        # Define payload with simple conversation history
        data = {
            "contents": "What is the weather like today?",
            "history": [
                {"role": "user", "parts": ["How's the weather tomorrow?"]},
                {"role": "model", "parts": ["The weather tomorrow is sunny."]}
            ],
            "parameters": {"max_output_tokens": 500}
        }
        # Generate HMAC signature
        signature = self.generate_hmac_signature(self.secret_key, data)

        # Send the request to the /generate_content endpoint
        response = self.send_request(self.generate_content_url, data, signature)

        # Assert response
        self.assertEqual(response.status_code, 200)
        self.assertIn("weather", response.text.lower())

    def test_generate_with_detailed_history(self):
        # Define payload with more detailed conversation history
        data = {
            "contents": "Can you recommend a good recipe for dinner?",
            "history": [
                {"role": "user", "parts": ["What should I cook for lunch?"]},
                {"role": "model", "parts": ["How about a pasta dish?"]},
                {"role": "user", "parts": ["That's a good idea! What ingredients do I need?"]}
            ],
            "parameters": {"max_output_tokens": 500}
        }
        # Generate HMAC signature
        signature = self.generate_hmac_signature(self.secret_key, data)

        # Send the request to the /generate_content endpoint
        response = self.send_request(self.generate_content_url, data, signature)

        # Assert response
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.text), 0)

    def test_generate_with_large_history(self):
        # Define payload with extensive conversation history
        data = {
            "contents": "Summarize our conversation so far.",
            "history": [
                {"role": "user", "parts": ["Tell me a joke."]},
                {"role": "model", "parts": ["Why did the scarecrow win an award? Because he was outstanding in his field!"]},
                {"role": "user", "parts": ["Haha, that's great! Got another one?"]},
                {"role": "model", "parts": ["Why don’t skeletons fight each other? They don’t have the guts."]},
                {"role": "user", "parts": ["Thanks, that's enough for now."]}
            ],
            "parameters": {"max_output_tokens": 1000}
        }
        # Generate HMAC signature
        signature = self.generate_hmac_signature(self.secret_key, data)

        # Send the request to the /generate_content endpoint
        response = self.send_request(self.generate_content_url, data, signature)

        # Assert response
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.text), 0)

    def test_generate_with_empty_history(self):
        # Define payload with no conversation history
        data = {
            "contents": "Tell me a fun fact about mars.",
            "history": [],
            "parameters": {"max_output_tokens": 500}
        }
        # Generate HMAC signature
        signature = self.generate_hmac_signature(self.secret_key, data)

        # Send the request to the /generate_content endpoint
        response = self.send_request(self.generate_content_url, data, signature)

        # Assert response
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.text), 0)

    def test_generate_with_invalid_history_format(self):
        # Define payload with invalid conversation history format
        data = {
            "contents": "What should I do next?",
            "history": {"role": "user", "parts": ["Tell me what to do."]},  # Invalid format (should be a list)
            "parameters": {"max_output_tokens": 500}
        }
        # Generate HMAC signature
        signature = self.generate_hmac_signature(self.secret_key, data)

        # Send the request to the /generate_content endpoint
        response = self.send_request(self.generate_content_url, data, signature)

        # Assert response
        self.assertEqual(response.status_code, 400)  # Expecting a bad request due to invalid history format
        self.assertIn("invalid history format", response.text.lower())


if __name__ == "__main__":
    unittest.main()
