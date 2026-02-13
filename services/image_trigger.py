import re

IMAGE_TAG_PATTERN = re.compile(r"\[GENERATE_IMAGE:\s*(.+?)\]", re.DOTALL)


def check_response(response_text):
    """Return the image prompt if a [GENERATE_IMAGE:] tag is found, else None."""
    match = IMAGE_TAG_PATTERN.search(response_text)
    if match:
        return match.group(1).strip()
    return None


def clean_response(response_text):
    """Remove [GENERATE_IMAGE:] tags from text."""
    return IMAGE_TAG_PATTERN.sub("", response_text).strip()
