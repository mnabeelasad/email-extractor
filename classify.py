"""
classify.py
-----------
Step 1 - the cheap gate. BEFORE the expensive extraction, we ask the model a
one-word question: does this email actually contain medical-device data?

  NO  -> skip the email (don't waste an extraction call)
  YES -> go ahead and extract

If the model is unsure, it answers YES on purpose. A wrong YES only wastes one
call (the result will be empty and we won't save it). A wrong NO would silently
lose real client data - the worst outcome. So we always lean towards YES.
"""

from llm import generate

MODEL = "qwen2.5:32b"


def build_classifier_prompt(email_text: str) -> str:
    return f"""You are a filter for a medical-device regulatory consultancy.

Decide whether the email below contains any technical or regulatory data about
a medical device - for example: product name, manufacturer, article number,
intended purpose, indications, classification, identifiers (SRN/UDI/codes),
variants, or a description of the device or how it is used.

General correspondence - greetings, scheduling, invoices, status updates,
questions with no device data - does NOT count.

If you are unsure, answer YES.
Answer with exactly one word: YES or NO.

EMAIL:
\"\"\"
{email_text}
\"\"\"
"""


def call_gemini_raw(prompt: str) -> str:
    # only need one word back, so a tiny output limit is enough
    return generate(model=MODEL, prompt=prompt, max_output_tokens=5)


def is_device_data_email(email_text: str) -> bool:
    answer = call_gemini_raw(build_classifier_prompt(email_text)).strip().upper()
    # Lean towards YES: only a clean "NO" counts as NO.
    return not answer.startswith("NO")