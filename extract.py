"""
extract.py
----------
Takes one email, sends it to the local model (Qwen via Ollama), and returns
the filled-in device form as a validated DeviceInfo object.

Rule: extract ONLY what is explicitly written in the email. Never invent
values, especially regulatory IDs (SRN, UDI, codes) - those stay null.
"""

import json

from llm import generate
from schema import DeviceInfo


# ----------------------------------------------------------------------
# 1) Build the instruction (prompt) we send to the model
# ----------------------------------------------------------------------
def build_prompt(email_text: str) -> str:
    json_template = """{
  "manufacturer": null,
  "srn": null,
  "product_name": null,
  "article_number_ref": null,
  "basic_udi_di": null,
  "device_description": null,
  "intended_purpose": null,
  "indications": null,
  "contraindications": null,
  "warnings": null,
  "classification": null,
  "rule": null,
  "code_emdn": null,
  "code_gmdn": null,
  "code_mdr": null,
  "variants": [{"art_no": null, "product_name": null}],
  "previous_generations": null,
  "innovative_properties": null,
  "accessories": null,
  "products_for_combined_use": null,
  "patient_population": null,
  "intended_users": null,
  "description_of_use": null,
  "special_labeling": null
}"""

    return f"""You extract medical-device information from a client email for a
regulatory consultancy.

Fill in the JSON template below using ONLY information that is explicitly stated
in the email. Follow these rules strictly:
- If a value is not clearly in the email, leave it as null.
- NEVER guess or invent values. This is especially important for regulatory
  identifiers (srn, basic_udi_di, code_emdn, code_gmdn, code_mdr) - if they are
  not written in the email, they MUST stay null.
- For "variants", return one object per variant. If there are no variants,
  return an empty list [].
- The email may contain noise: email signatures, legal disclaimers,
  "Sent from my iPhone", and quoted earlier emails (replies/forwards). Ignore
  this noise and extract only the actual device information.
- Return ONLY the JSON object. No explanation, no markdown, no code fences.

JSON template (use exactly these keys):
{json_template}

EMAIL:
\"\"\"
{email_text}
\"\"\"
"""


# ----------------------------------------------------------------------
# 2) Send the prompt to the model and get the raw text back
# ----------------------------------------------------------------------
def call_model(prompt: str) -> str:
    return generate(prompt, max_output_tokens=8192)


# ----------------------------------------------------------------------
# 3) Turn the model's text into a validated DeviceInfo form
# ----------------------------------------------------------------------
def parse_model_output(raw: str) -> DeviceInfo:
    cleaned = raw.strip()

    # Some models wrap JSON in ```json ... ``` fences. Strip them.
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.lstrip().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
        cleaned = cleaned.strip().rstrip("`").strip()

    # Some models add text around the JSON; keep only the {...} block.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start:end + 1]

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print("\n--- Could not parse the model's answer as JSON ---")
        print(f"Error: {e}")
        print("Raw answer from the model was:\n")
        print(raw)
        print("\n--------------------------------------------------")
        raise
    return DeviceInfo(**data)