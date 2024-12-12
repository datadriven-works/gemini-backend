import json
import os
import hmac
from flask import Flask, request, Response
from flask_cors import CORS
import functions_framework
import vertexai
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig
import logging

logging.basicConfig(level=logging.INFO)


# Initialize the Vertex AI
project = os.environ.get("PROJECT")
location = os.environ.get("REGION")
vertex_cf_auth_token = os.environ.get("VERTEX_CF_AUTH_TOKEN")
model_name = os.environ.get("MODEL_NAME", "gemini-1.5-flash")

vertexai.init(project=project, location=location)


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

def gemini_generate(contents, parameters=None, model_name="gemini-1.5-flash", response_schema=None):
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
        model = GenerativeModel(model_name)

        # Make prediction to generate Looker Explore URL
        response = model.generate_content(
            contents=contents,
            generation_config=GenerationConfig(
                temperature=default_parameters["temperature"],
                top_p=default_parameters["top_p"],
                max_output_tokens=default_parameters["max_output_tokens"],
                candidate_count=1,
                response_schema=response_schema,
                response_mime_type=response_schema and "application/json" or 'text/plain'
            )
        )

        # Grab token character count metadata and log
        metadata = response.__dict__['_raw_response'].usage_metadata

        # Complete a structured log entry
        entry = dict(
            severity="INFO",
            message={"request": contents, "response": response.text,
                     "input_characters": metadata.prompt_token_count, "output_characters": metadata.candidates_token_count},
            component="explore-assistant-metadata",
        )
        logging.info(entry)
        return response.text
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
            model_name = incoming_request.get("model_name", "gemini-1.5-flash")
            response_schema = incoming_request.get("response_schema", None)

            if contents is None:
                return {"error": "Missing 'contents' parameter"}, 400

            if not has_valid_signature(request):
                return {"error": "Invalid signature"}, 403

            response_text = gemini_generate(contents, parameters, model_name, response_schema)
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

            if contents is None:
                return {"error": "Missing 'contents' parameter"}, 400

            if not has_valid_signature(request):
                return {"error": "Invalid signature"}, 403

            response_text = gemini_generate(contents, parameters, model_name, response_schema)
            return response_text, 200, get_response_headers(request)

        # Default response for unsupported paths
        return {"error": "Unsupported path"}, 404, get_response_headers(request)
    except Exception as e:
        logging.error(f"Error in cloud_function_entrypoint: {str(e)}", exc_info=True)
        return {"error": str(e)}, 500, get_response_headers(request)


# Function for Google Cloud Function
@functions_framework.http
def cloud_function_entrypoint(request):
    if request.method == "OPTIONS":
        return handle_options_request(request)

    # Handle the `/generate_content` path
    if request.path == "/generate_content":
        incoming_request = request.get_json()
        contents = incoming_request.get("contents")
        parameters = incoming_request.get("parameters")
        model_name = incoming_request.get("model_name", "gemini-1.5-flash")
        response_schema = incoming_request.get("response_schema", None)

        if contents is None:
            return "Missing 'contents' parameter", 400

        if not has_valid_signature(request):
            return "Invalid signature", 403

        response_text = gemini_generate(contents, parameters, model_name, response_schema)

        return response_text, 200, get_response_headers(request)

    # Default response for unsupported paths
    return "Unsupported path", 404, get_response_headers(request)

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
