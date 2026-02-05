# Google Search Tool Reference

This reference contains the core API invocation patterns for using the Google Search grounding tool with Gemini models.

## Python Usage (Recommended for execution)
The Python client handles the orchestration of search queries, result processing, and citation metadata extraction.

```python
from google import genai
from google.genai import types

client = genai.Client() # Assumes GEMINI_API_KEY is set in environment
grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)
config = types.GenerateContentConfig(tools=[grounding_tool])

response = client.models.generate_content(
    model="gemini-2.5-flash-preview", # Or gemini-3-pro-preview
    contents="Who won the euro 2024?",
    config=config,
)

# The response.text will contain grounded output with citation links
print(response.text)
```

## Response Metadata Key Fields

When successful, the response contains `groundingMetadata`:
- `webSearchQueries`: The queries the model generated.
- `groundingChunks`: The raw web sources retrieved.
- `groundingSupports`: Data linking the response text segments to the sources.

## Pricing Note
When using Gemini 3.x models, you are billed per search query executed. This does not apply to Gemini 2.5 models.