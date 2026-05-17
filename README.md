# 🎨 SVG Editor API

A modern, high-performance REST API built with **FastAPI** to dynamically modify, style, and transform SVG (Scalable Vector Graphics) files on the fly. 

This API parses standard SVG files, processes XML modifications safely using Pydantic models for request validation, and returns the modified SVG directly as a response.

---

## 🚀 Quick Start

### 1. Setup Virtual Environment
If you haven't already, create and activate a Python virtual environment:
```bash
# Create venv
python3 -m venv venv

# Activate venv (macOS / Linux)
source venv/bin/activate

# Activate venv (Windows)
venv\Scripts\activate
```

### 2. Install Dependencies
Install all required dependencies using the generated `requirements.txt` file:
```bash
pip install -r requirements.txt
```

### 3. Run the Development Server
Launch the FastAPI development server with Uvicorn:
```bash
uvicorn main:app --reload
```
Once running, the application will be live at **`http://127.0.0.1:8000`**.

---

## 📖 Interactive Documentation

FastAPI automatically generates interactive, self-documenting API explorers:

* **Swagger UI (Interactive Playground):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
  * *Use this to upload a file directly in the browser and test requests immediately.*
* **ReDoc (Detailed Specifications):** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🛠️ API Reference & Usage

All endpoints accept a file upload under the form parameter `file` and return the newly modified SVG file directly with an `application/xml` content-type.

### 1. Replace Text
Finds all text elements containing `old_text` and replaces the text with `new_text`. It can optionally set a custom font size and font color.

* **Endpoint:** `POST /svg/replace-text`
* **Content-Type:** `multipart/form-data`
* **Form Parameters:**
  * `file`: (Binary SVG File)
  * `payload`: (JSON String matching the schema below)

#### Payload Schema (`ReplaceTextRequest`)
```json
{
  "old_text": "Text to search for (required)",
  "new_text": "Text to replace it with (required)",
  "font_size": "Optional font size (e.g. '24px' or '16')",
  "font_color": "Optional hex or color name (e.g. '#FF5733' or 'red')"
}
```

#### Example `curl` Command:
```bash
curl -X POST "http://127.0.0.1:8000/svg/replace-text" \
  -F "file=@sample.svg" \
  -F 'payload={"old_text": "Welcome", "new_text": "Hello World", "font_size": "24px", "font_color": "#ff0000"}' \
  --output modified_sample.svg
```

---

### 2. Replace Image URL
Locates the **first** `<image>` element in the SVG structure and replaces its `href` or `xlink:href` (or `src`) attributes with a new URL.

* **Endpoint:** `POST /svg/replace-image`
* **Content-Type:** `multipart/form-data`
* **Form Parameters:**
  * `file`: (Binary SVG File)
  * `new_image_url`: (Plain string of the new image URL, e.g. `https://example.com/new-image.jpg`)

#### Example `curl` Command:
```bash
curl -X POST "http://127.0.0.1:8000/svg/replace-image" \
  -F "file=@sample.svg" \
  -F "new_image_url=https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5" \
  --output modified_sample.svg
```

---

### 3. Set Text Alignment
Aligns a specific text element (using its unique SVG `id` attribute) by updating its `text-anchor` property.

* **Endpoint:** `POST /svg/set-alignment`
* **Content-Type:** `multipart/form-data`
* **Form Parameters:**
  * `file`: (Binary SVG File)
  * `payload`: (JSON String matching the schema below)

#### Payload Schema (`SetAlignmentRequest`)
```json
{
  "element_id": "unique-svg-element-id (required)",
  "alignment": "left | center | right (required)"
}
```
* **Alignment Mapping:**
  * `left` → `text-anchor="start"`
  * `center` → `text-anchor="middle"`
  * `right` → `text-anchor="end"`

#### Example `curl` Command:
```bash
curl -X POST "http://127.0.0.1:8000/svg/set-alignment" \
  -F "file=@sample.svg" \
  -F 'payload={"element_id": "title-text", "alignment": "center"}' \
  --output modified_sample.svg
```

---

### 4. Apply Geometric Transformation
Applies geometric transformations (`translate`, `scale`, `rotate`) to any specific SVG element using its unique `id` attribute.

* **Endpoint:** `POST /svg/transform`
* **Content-Type:** `multipart/form-data`
* **Form Parameters:**
  * `file`: (Binary SVG File)
  * `payload`: (JSON String matching the schema below)

#### Payload Schema (`TransformRequest`)
```json
{
  "element_id": "unique-svg-element-id (required)",
  "translate": "Optional 'x,y' offsets (e.g. '50,100')",
  "scale": "Optional scale factor (e.g. '1.5' or '1.5,2')",
  "rotate": "Optional rotation angle in degrees (e.g. '45' or '45,100,100')"
}
```

#### Example `curl` Command:
```bash
curl -X POST "http://127.0.0.1:8000/svg/transform" \
  -F "file=@sample.svg" \
  -F 'payload={"element_id": "brand-logo", "translate": "20,40", "scale": "1.2", "rotate": "15"}' \
  --output modified_sample.svg
```

---

## 📂 Project Structure

```
├── main.py              # FastAPI endpoints, request models, and SVG processing logic
├── sample.svg           # A sample SVG file used for development/testing
├── requirements.txt     # Locked production dependencies
├── .gitignore           # Git ignore profiles for Python and OS-specific clutter
└── README.md            # Project and API Documentation
```

## 🛠️ Tech Stack & Features
* **FastAPI:** High-performance web framework.
* **Pydantic v2:** Fast, robust, and automated payload data validation.
* **XML ElementTree (Python Standard Library):** Safe, high-speed, native parsing of XML and SVG namespaces.
* **Uvicorn:** Extremely fast ASGI server for ASGI production deployments.
