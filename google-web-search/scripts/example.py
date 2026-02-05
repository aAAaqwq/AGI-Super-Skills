#!/usr/bin/env python3
"""
Core script for google-web-search skill.
This script handles the actual execution of the Google Search grounding tool.
NOTE: API Key should be retrieved from environment variables (e.g., GEMINI_API_KEY) or Skill Config.
"""
import os
import json
from google import genai
from google.genai import types
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Configuration Management ---
class GoogleSearchSettings(BaseSettings):
    """Configuration for the Google Search Tool."""
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )
    # Keys are loaded from environment variables or .env file
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"  # Default model

SETTINGS = GoogleSearchSettings()
# -----------------------------------------------------------------------------

def get_grounded_response(prompt: str, model: str = None) -> str:
    """
    Executes the Google Search tool to provide a grounded response.
    
    Args:
        prompt: The user's query string.
        model: Optional model name to use (defaults to GEMINI_MODEL env var or gemini-2.5-flash-lite)
        
    Returns:
        str: The model's grounded response text, including citations metadata.
    """
    # Get API key from environment
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "ERROR: GEMINI_API_KEY environment variable not set. Cannot ground search."
    
    # Get model from parameter, env var, or default
    if model is None:
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

    try:
        client = genai.Client(api_key=api_key)
        
        # Define the tool configuration
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        config = types.GenerateContentConfig(
            tools=[grounding_tool]
        )
        
        # Call the API
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        
        # Return the response text which contains grounded information and metadata
        return response.text

    except Exception as e:
        return f"ERROR during API call or grounding: {e}"

if __name__ == "__main__":
    # Direct test execution for demonstration.
    test_prompt = "What is the current status of the OpenClaw Gateway?"
    
    print(f"--- Running Direct Test with prompt: {test_prompt} ---")
    result = get_grounded_response(test_prompt)
    print(result)
    print("--- Test Complete ---")