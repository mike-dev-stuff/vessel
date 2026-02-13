import json
import os
import time
import urllib.parse
import uuid

import requests
from config import Config


def load_workflow(workflow_path=None):
    """Load a ComfyUI workflow JSON file (API format)."""
    path = workflow_path or Config.WORKFLOW_PATH
    with open(path, "r") as f:
        return json.load(f)


def _apply_template(prompt_text, prefix="", suffix=""):
    """Wrap prompt with configured prefix/suffix."""
    parts = [s for s in (prefix, prompt_text, suffix) if s]
    return ", ".join(parts)


def inject_prompt(workflow, prompt_text, negative_prompt="", prefix="", suffix="",
                  node_id=None):
    """Inject positive and negative prompts into the workflow.

    Auto-detects CLIPTextEncode nodes by _meta.title:
    - 'positive' or 'prompt' → receives the templated prompt
    - 'negative'             → receives the negative prompt
    Falls back to first CLIPTextEncode for positive if no title match.
    """
    full_prompt = _apply_template(prompt_text, prefix, suffix)

    if node_id:
        workflow[node_id]["inputs"]["text"] = full_prompt
        return workflow

    positive_set = False
    negative_set = False
    fallback_nodes = []

    for nid, node in workflow.items():
        if node.get("class_type") != "CLIPTextEncode":
            continue
        title = node.get("_meta", {}).get("title", "").lower()

        if not positive_set and ("positive" in title or "prompt" in title):
            workflow[nid]["inputs"]["text"] = full_prompt
            positive_set = True
        elif not negative_set and "negative" in title:
            workflow[nid]["inputs"]["text"] = negative_prompt
            negative_set = True
        else:
            fallback_nodes.append(nid)

    # Fallback: use first unmatched CLIPTextEncode for positive
    if not positive_set and fallback_nodes:
        workflow[fallback_nodes[0]]["inputs"]["text"] = full_prompt

    return workflow


def queue_prompt(workflow):
    """Submit workflow to ComfyUI. Returns prompt_id."""
    client_id = str(uuid.uuid4())
    payload = {"prompt": workflow, "client_id": client_id}
    resp = requests.post(
        f"{Config.COMFYUI_BASE_URL}/prompt", json=payload, timeout=30
    )
    resp.raise_for_status()
    return resp.json()["prompt_id"]


def poll_history(prompt_id, timeout=120, interval=1.0):
    """Poll /history/{prompt_id} until the result appears."""
    url = f"{Config.COMFYUI_BASE_URL}/history/{prompt_id}"
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        history = resp.json()
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(interval)
    raise TimeoutError(
        f"ComfyUI did not complete prompt {prompt_id} within {timeout}s"
    )


def retrieve_image(filename, subfolder="", folder_type="output"):
    """Download image bytes from ComfyUI /view endpoint."""
    params = urllib.parse.urlencode(
        {"filename": filename, "subfolder": subfolder, "type": folder_type}
    )
    url = f"{Config.COMFYUI_BASE_URL}/view?{params}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def generate_image(prompt_text, workflow_path=None, negative_prompt="",
                    prompt_prefix="", prompt_suffix=""):
    """Full pipeline: load → inject → submit → poll → retrieve → save.

    Returns the URL path to the saved image (relative to static root).
    """
    workflow = load_workflow(workflow_path)
    workflow = inject_prompt(workflow, prompt_text, negative_prompt,
                             prompt_prefix, prompt_suffix)
    prompt_id = queue_prompt(workflow)
    history = poll_history(prompt_id)

    for node_output in history["outputs"].values():
        if "images" in node_output:
            for image_info in node_output["images"]:
                image_data = retrieve_image(
                    image_info["filename"],
                    image_info.get("subfolder", ""),
                    image_info.get("type", "output"),
                )
                local_filename = f"{prompt_id}_{image_info['filename']}"
                os.makedirs(Config.IMAGE_OUTPUT_DIR, exist_ok=True)
                local_path = os.path.join(Config.IMAGE_OUTPUT_DIR, local_filename)
                with open(local_path, "wb") as f:
                    f.write(image_data)
                return f"/static/images/{local_filename}"

    raise RuntimeError("No images found in ComfyUI output")
