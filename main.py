"""
SVG Editor API — FastAPI
========================
Provides REST endpoints to modify SVG files:
  - POST /svg/replace-text   : Replace text content + optional styling
  - POST /svg/replace-image  : Replace the first <image> element's href/src
  - POST /svg/set-alignment  : Set text-anchor on a specific element
  - POST /svg/transform      : Apply translate/scale/rotate transform to an element
"""

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, field_validator
from typing import Literal, Optional
import xml.etree.ElementTree as ET
import io

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SVG Editor API",
    description="A REST API for editing SVG files programmatically.",
    version="1.0.0",
)

# Register the SVG namespace so ET does not rewrite it as 'ns0'
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

# Common namespace map used in XPath-style searches
NS = {"svg": SVG_NS}

# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class ReplaceTextRequest(BaseModel):
    """Payload for the replace-text endpoint."""
    old_text: str
    new_text: str
    font_size: Optional[str] = None   # e.g. "18" or "18px"
    font_color: Optional[str] = None  # e.g. "#ff0000" or "red"


class SetAlignmentRequest(BaseModel):
    """Payload for the set-alignment endpoint."""
    element_id: str
    alignment: Literal["left", "center", "right"]

    # Map human-readable alignment to SVG text-anchor values
    @property
    def text_anchor(self) -> str:
        mapping = {"left": "start", "center": "middle", "right": "end"}
        return mapping[self.alignment]


class TransformRequest(BaseModel):
    """Payload for the transform endpoint."""
    element_id: str
    translate: Optional[str] = None  # e.g. "10,20"
    scale: Optional[str] = None      # e.g. "1.5" or "1.5,2"
    rotate: Optional[str] = None     # e.g. "45" or "45,100,100"

    @field_validator("translate", "scale", "rotate", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        """Remove accidental surrounding whitespace from transform values."""
        return v.strip() if isinstance(v, str) else v

    def build_transform_string(self) -> str:
        """Compose the SVG transform attribute value from the provided parts."""
        parts = []
        if self.translate:
            parts.append(f"translate({self.translate})")
        if self.scale:
            parts.append(f"scale({self.scale})")
        if self.rotate:
            parts.append(f"rotate({self.rotate})")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def parse_svg(content: bytes) -> ET.Element:
    """
    Parse raw SVG bytes into an ElementTree root.
    Raises HTTP 400 if the content is not valid XML/SVG.
    """
    try:
        return ET.fromstring(content)
    except ET.ParseError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid SVG file: {exc}",
        )


def svg_response(root: ET.Element) -> Response:
    """Serialise an ElementTree back to UTF-8 XML and return it as an SVG image."""
    buffer = io.BytesIO()
    ET.ElementTree(root).write(buffer, encoding="utf-8", xml_declaration=True)
    return Response(content=buffer.getvalue(), media_type="image/svg+xml")


def find_element_by_id(root: ET.Element, element_id: str) -> ET.Element:
    """
    Search the entire SVG tree for an element whose 'id' attribute matches.
    Raises HTTP 404 if not found.
    """
    for elem in root.iter():
        if elem.get("id") == element_id:
            return elem
    raise HTTPException(
        status_code=404,
        detail=f"Element with id='{element_id}' not found in SVG.",
    )


# ---------------------------------------------------------------------------
# Endpoint 1 — Replace text content (with optional font styling)
# ---------------------------------------------------------------------------

@app.post(
    "/svg/replace-text",
    summary="Replace text in SVG",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}}, 400: {"description": "Invalid SVG or input"}},
)
async def replace_svg_text(
    file: UploadFile = File(..., description="SVG file to edit"),
    payload: str = Form(..., description="JSON string matching ReplaceTextRequest schema"),
):
    """
    Find every text element whose content contains *old_text* and replace it
    with *new_text*. Optionally update font-size and fill (font color) attributes.

    The JSON payload must conform to ReplaceTextRequest:
        { "old_text": "...", "new_text": "...", "font_size": "18", "font_color": "#000" }
    """
    # Parse and validate the JSON payload via the Pydantic model
    try:
        req = ReplaceTextRequest.model_validate_json(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {exc}")

    content = await file.read()
    root = parse_svg(content)

    matched = False
    for elem in root.iter():
        # Check both .text (element body) and .tail (text after closing tag)
        if elem.text and req.old_text in elem.text:
            elem.text = elem.text.replace(req.old_text, req.new_text)
            matched = True

            # Apply optional font-size attribute
            if req.font_size is not None:
                elem.set("font-size", req.font_size)

            # Apply optional fill (font color) attribute
            if req.font_color is not None:
                elem.set("fill", req.font_color)

    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"Text '{req.old_text}' not found in any SVG text element.",
        )

    return svg_response(root)


# ---------------------------------------------------------------------------
# Endpoint 2 — Replace the first <image> element's href / src
# ---------------------------------------------------------------------------

@app.post(
    "/svg/replace-image",
    summary="Replace image URL in SVG",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}}, 400: {"description": "Invalid SVG or input"}},)
async def replace_svg_image(
    file: UploadFile = File(..., description="SVG file to edit"),
    new_image_url: str = Form(..., description="New image URL to use as href/src"),
):
    """
    Locate the **first** ``<image>`` element in the SVG and replace its
    ``href``, ``xlink:href``, and/or ``src`` attributes with *new_image_url*.
    """
    if not new_image_url.strip():
        raise HTTPException(status_code=422, detail="new_image_url must not be empty.")

    content = await file.read()
    root = parse_svg(content)

    # SVG images may use 'href' (SVG 2) or the older 'xlink:href'
    XLINK_NS = "http://www.w3.org/1999/xlink"
    image_tag_variants = (
        "image",
        f"{{{SVG_NS}}}image",
    )

    image_elem = None
    for elem in root.iter():
        if elem.tag in image_tag_variants:
            image_elem = elem
            break

    if image_elem is None:
        raise HTTPException(status_code=404, detail="No <image> element found in SVG.")

    # Update whichever href attributes are present; set 'href' as default
    replaced = False
    if image_elem.get("href") is not None:
        image_elem.set("href", new_image_url)
        replaced = True
    if image_elem.get(f"{{{XLINK_NS}}}href") is not None:
        image_elem.set(f"{{{XLINK_NS}}}href", new_image_url)
        replaced = True
    if image_elem.get("src") is not None:
        image_elem.set("src", new_image_url)
        replaced = True

    # If none of the above existed, add a plain 'href'
    if not replaced:
        image_elem.set("href", new_image_url)

    return svg_response(root)


# ---------------------------------------------------------------------------
# Endpoint 3 — Set text alignment via text-anchor
# ---------------------------------------------------------------------------

@app.post(
    "/svg/set-alignment",
    summary="Set text alignment on an SVG element",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}}, 400: {"description": "Invalid SVG"}, 404: {"description": "Element not found"}},
)
async def set_svg_alignment(
    file: UploadFile = File(..., description="SVG file to edit"),
    payload: str = Form(..., description="JSON string matching SetAlignmentRequest schema"),
):
    """
    Update the ``text-anchor`` attribute of the element identified by
    *element_id*. Accepted alignment values: ``left`` | ``center`` | ``right``.

    Mapping:
        left   → text-anchor="start"
        center → text-anchor="middle"
        right  → text-anchor="end"
    """
    try:
        req = SetAlignmentRequest.model_validate_json(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {exc}")

    content = await file.read()
    root = parse_svg(content)

    elem = find_element_by_id(root, req.element_id)
    elem.set("text-anchor", req.text_anchor)

    return svg_response(root)


# ---------------------------------------------------------------------------
# Endpoint 4 — Apply a geometric transform to an element
# ---------------------------------------------------------------------------

@app.post(
    "/svg/transform",
    summary="Apply a transform to an SVG element",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}}, 400: {"description": "Invalid SVG"}, 404: {"description": "Element not found"}, 422: {"description": "No transform specified"}},
)
async def transform_svg_element(
    file: UploadFile = File(..., description="SVG file to edit"),
    payload: str = Form(..., description="JSON string matching TransformRequest schema"),
):
    """
    Build and apply an SVG ``transform`` attribute on the element identified
    by *element_id*. At least one of *translate*, *scale*, or *rotate* must
    be provided.

    Example payload:
        { "element_id": "myRect", "translate": "50,100", "rotate": "45" }

    Produces:  transform="translate(50,100) rotate(45)"
    """
    try:
        req = TransformRequest.model_validate_json(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {exc}")

    transform_str = req.build_transform_string()
    if not transform_str:
        raise HTTPException(
            status_code=422,
            detail="At least one of 'translate', 'scale', or 'rotate' must be provided.",
        )

    content = await file.read()
    root = parse_svg(content)

    elem = find_element_by_id(root, req.element_id)
    elem.set("transform", transform_str)

    return svg_response(root)