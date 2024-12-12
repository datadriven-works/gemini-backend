import json
import os
import hmac
from flask import Flask, request, Response
from flask_cors import CORS
import functions_framework
from google import genai
from google.genai import types
import logging

logging.basicConfig(level=logging.INFO)


# Initialize the Vertex AI
project = os.environ.get("PROJECT")
location = os.environ.get("REGION", "us-central1")
vertex_cf_auth_token = os.environ.get("VERTEX_CF_AUTH_TOKEN")
model_name = os.environ.get("MODEL_NAME", "gemini-1.5-flash")


def is_invalid_history(history):
    """
    Validates that the history is a list of dictionaries with specific structure:
    - Each dictionary must contain "role" and "parts".
    - "role" must be either "user" or "model".
    - "parts" must be a non-empty string.
    """
    if not isinstance(history, list):
        return "History must be a list"

    for item in history:
        if not isinstance(item, dict):
            return "Each item in history must be a dictionary"
        if "role" not in item or "parts" not in item:
            return "Each item in history must contain 'role' and 'parts'"
        if item["role"] not in ["user", "model"]:
            return "Role must be 'user' or 'model'"
        if not isinstance(item["parts"], list) or not item["parts"]:
            return "Parts must be a non-empty list"

    return None


def get_response_headers(request):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Signature"
    }
    return headers


def has_valid_signature(request):
    signature = request.headers.get("X-Signature")
    if signature is None:
        return False

    # Validate the signature
    secret = vertex_cf_auth_token.encode("utf-8")
    request_data = request.get_data()
    hmac_obj = hmac.new(secret, request_data, "sha256")
    expected_signature = hmac_obj.hexdigest()

    return hmac.compare_digest(signature, expected_signature)


def gemini_generate(contents, parameters=None, model_name="gemini-2.0-flash-exp", response_schema=None, history=[]):
    try:
        # Define default parameters
        default_parameters = {
            "temperature": 1,
            "max_output_tokens": 8192,
            "top_p": 0.95,
        }

        # Override default parameters with any provided in the request
        if parameters:
            default_parameters.update(parameters)

        # Instantiate Gemini model for prediction
        client = genai.Client(vertexai=True, project=project, location=location)
        typed_history = []
        for x in history:
            role = x["role"]
            parts = []
            for part in x["parts"]:
                if isinstance(part, dict):  # Handle structured parts (function calls or function responses)
                    if "functionCall" in part:
                        parts.append(
                            types.Part(
                                function_call=types.FunctionCall(
                                    name=part["functionCall"]["name"],
                                    args=part["functionCall"]["args"]
                                )
                            )
                        )
                    elif "functionResponse" in part:
                        parts.append(
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=part["functionResponse"]["name"],
                                    response=part["functionResponse"]["response"]
                                )
                            )
                        )
                else:  # Handle plain text parts
                    parts.append(types.Part(text=part))
            typed_history.append(types.Content(parts=parts, role=role))

        chat = client.chats.create(model=model_name, history=typed_history, config={
            "temperature": default_parameters["temperature"],
            "top_p": default_parameters["top_p"],
            "max_output_tokens": default_parameters["max_output_tokens"],
            "candidate_count": 1,
            "response_schema": response_schema,
            "response_mime_type": response_schema and "application/json" or 'text/plain'
        })

        # add message to chat
        response = chat.send_message(contents)

        # return the function call or the text response
        condidate = response.candidates[0]
        response_parts = []
        for part in condidate.content.parts:
            if part.function_call:
                response_parts.append({"functionCall": part.function_call})
            elif response_schema:
                response_parts.append({"object": json.loads(part.text)})
            else:
                response_parts.append({"text": part.text})

        return response_parts
    except Exception as e:
        # Log the exception
        logging.error(f"Error in gemini_generate: {str(e)}", exc_info=True)
        raise RuntimeError(f"Gemini model error: {str(e)}") from e


# Flask app for running as a web server
def create_flask_app():
    app = Flask(__name__)
    CORS(app)

    @app.route("/generate_content", methods=["POST", "OPTIONS"])
    def generate_content():
        if request.method == "OPTIONS":
            return handle_options_request(request)

        try:
            incoming_request = request.get_json()
            contents = incoming_request.get("contents")
            parameters = incoming_request.get("parameters")
            model_name = incoming_request.get("model_name", "gemini-2.0-flash-exp")
            response_schema = incoming_request.get("response_schema", None)
            history = incoming_request.get("history", [])

            if is_invalid_history(history):
                return {"error": "Invalid history format"}, 400

            if contents is None:
                return {"error": "Missing 'contents' parameter"}, 400

            if not has_valid_signature(request):
                return {"error": "Invalid signature"}, 403

            response_text = gemini_generate(contents, parameters, model_name, response_schema, history)
            return response_text, 200, get_response_headers(request)
        except Exception as e:
            logging.error(f"Error in generate_content route: {str(e)}", exc_info=True)
            return {"error": str(e)}, 500, get_response_headers(request)

    return app


# Function for Google Cloud Function
@functions_framework.http
def cloud_function_entrypoint(request):
    if request.method == "OPTIONS":
        return handle_options_request(request)

    try:
        # Handle the `/generate_content` path
        if request.path == "/generate_content":
            incoming_request = request.get_json()
            contents = incoming_request.get("contents")
            parameters = incoming_request.get("parameters")
            model_name = incoming_request.get("model_name", "gemini-1.5-flash")
            response_schema = incoming_request.get("response_schema", None)
            history = incoming_request.get("history", [])

            if is_invalid_history(history):
                return {"error": "Invalid history format"}, 400

            if contents is None:
                return {"error": "Missing 'contents' parameter"}, 400

            if not has_valid_signature(request):
                return {"error": "Invalid signature"}, 403

            response_text = gemini_generate(contents, parameters, model_name, response_schema, history)
            return response_text, 200, get_response_headers(request)

        # Default response for unsupported paths
        return {"error": "Unsupported path"}, 404, get_response_headers(request)
    except Exception as e:
        logging.error(f"Error in cloud_function_entrypoint: {str(e)}", exc_info=True)
        return {"error": str(e)}, 500, get_response_headers(request)


def handle_options_request(request):
    return "", 204, get_response_headers(request)


# Determine the running environment and execute accordingly
if __name__ == "__main__":
    # Detect if running in a Google Cloud Function environment
    if os.environ.get("FUNCTIONS_FRAMEWORK"):
        # The Cloud Function entry point is defined by the decorator, so nothing is needed here
        pass
    else:
        app = create_flask_app()
        app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
