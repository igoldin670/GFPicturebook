"""Safe processing reasons: no decoder exception text or private paths in responses."""
MESSAGES = {
    "unsupported_format": "This file type is not supported. Use JPEG, PNG, WebP, or HEIC.",
    "animated_image": "This file contains multiple frames. Animated images are not supported.",
    "image_too_large": "This image exceeds the 50-megapixel processing limit.",
    "invalid_image": "This image is damaged or could not be decoded.",
    "invalid_or_unsupported_image": "This image is damaged or uses an unsupported format.",
    "missing_original": "The original file is missing from storage. Check the server’s photo storage.",
    "storage_unavailable": "Photo storage could not be read or written. Check disk space and permissions.",
    "processing_failed": "Processing failed. Check the worker log and photo storage before retrying.",
    "decoder_interrupted": "The decoder stopped or exceeded its processing limits. Check the worker log.",
}


def safe_code(code):
    return code if code in MESSAGES else "processing_failed"


def failure_message(code):
    normalized = safe_code(code)
    if normalized == "missing_original":
        return MESSAGES[normalized]
    return MESSAGES[normalized] + " Your uploaded original has been retained."
