---
name: vision-analyze
description: Image analysis using multimodal vision models. Use when user needs to: (1) Describe what's in an image, (2) Extract text from images (OCR), (3) Analyze visual content, (4) Compare images, (5) Answer questions about images. Supports JPG, PNG, GIF, WebP formats.
metadata:
  {
    "openclaw":
      {
        "emoji": "👁️",
        "requires": {},
      },
  }
---

# Vision Analyze

Analyze images using the built-in vision capabilities of multimodal AI models.

## Quick Start

### Analyze an Image

Describe what's in an image:

```python
# The agent will automatically use vision when you provide an image path
image("/path/to/image.jpg", prompt="Describe what's in this image")
```

### Extract Text (OCR)

Extract text from images:

```python
image("/path/to/document.png", prompt="Extract all text from this image")
```

### Analyze Multiple Images

Compare or analyze multiple images:

```python
images(["/path/to/image1.jpg", "/path/to/image2.jpg"], 
       prompt="Compare these two images and describe the differences")
```

## Usage Patterns

### Visual Q&A

Ask specific questions about image content:

```python
image("menu.jpg", prompt="What are the prices of the main courses?")
image("chart.png", prompt="What trend does this graph show?")
image("screenshot.png", prompt="What error message is displayed?")
```

### Content Moderation

Check image content:

```python
image("upload.jpg", prompt="Is this image appropriate for a professional setting?")
```

### Data Extraction

Extract structured data from visual content:

```python
image("receipt.jpg", prompt="Extract the date, total amount, and items purchased")
image("business_card.png", prompt="Extract name, phone, email, and company")
image("form.jpg", prompt="Extract all filled fields as key-value pairs")
```

### Visual Comparison

Compare images:

```python
images(["before.jpg", "after.jpg"], 
       prompt="What changes were made between these two images?")
```

## Tips

- **Be specific**: The more specific your prompt, the better the results
- **Multiple images**: You can analyze up to 20 images at once
- **Supported formats**: JPG, PNG, GIF, WebP
- **Size limits**: Large images are automatically resized

## When to Use

- Reading text from screenshots, documents, or photos
- Describing visual content for accessibility
- Analyzing charts, graphs, or diagrams
- Comparing visual changes
- Extracting data from forms or receipts
- Understanding UI elements or error messages
