"""
extract.py
----------
Step 2 test: take ONE email, send it to Gemini, get back the filled-in
device form, and save it as a JSON "source of truth" file.

For now the email is HARDCODED below (the TEST_EMAIL variable). Once this
works, we replace that variable with a real email read from the mailbox.

HOW TO RUN (on your no-GPU machine):
    pip install -r requirements.txt
    export GEMINI_API_KEY="your-key-here"      # Windows: set GEMINI_API_KEY=...
    python extract.py
"""

import os
import json
from pathlib import Path

from llm import generate

from schema import DeviceInfo


# Local Qwen model running on Ollama (RTX machine).
MODEL = "qwen2.5:32b"

# Where the source-of-truth file for client KWP is written.
OUTPUT_PATH = Path("data/KWP/device_info.json")


# ----------------------------------------------------------------------
# THE TEST EMAIL  (later: replaced by a real email from the mailbox)
# ----------------------------------------------------------------------
TEST_EMAIL = """\
Subject: Device information for technical documentation - AeroFlow X200

Dear Mr. Schmidt,

As discussed, here are the initial device details for our nebulizer so you
can begin the technical documentation. A few items (the regulatory IDs and
the full code list) are still being finalised internally - we will send those
in a follow-up email next week.

Manufacturer: KWP Medizintechnik GmbH, Industriestrasse 14, 33602 Bielefeld, Germany

Product: AeroFlow X200 portable mesh nebulizer
Article number: REF 88421

Description: The AeroFlow X200 is a portable, battery-powered mesh nebulizer
that turns liquid medication into a fine aerosol for inhalation. It is intended
for both home and clinical use.

Intended purpose: To deliver prescribed inhalation medication to patients who
require aerosol therapy for respiratory conditions.

Indications: Treatment of asthma, COPD and other respiratory conditions that
require aerosolised medication, as prescribed by a physician.

Contraindications: Must not be used with medications that are not approved for
nebulisation.

We classify the device as Class IIa under Rule 11.

There are two variants:
- AeroFlow X200 (REF 88421) - standard version
- AeroFlow X200P (REF 88422) - paediatric version with a smaller mask

Intended users: patients (including at home) and healthcare professionals. The
paediatric variant is for use on children under adult supervision.

Please note: the SRN, the Basic UDI-DI and the EMDN/GMDN codes are not yet
assigned on our side. We will provide these in the next email.

Best regards,
Maria Hoffmann
Regulatory Affairs, KWP Medizintechnik GmbH
"""


# ----------------------------------------------------------------------
# 1) Build the instruction (prompt) we send to the model
# ----------------------------------------------------------------------
def build_prompt(email_text: str) -> str:
    # We show the model the exact JSON shape we want back (an inline template),
    # and we are very strict about NOT inventing anything.
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
# 2) Send the prompt to Gemini and get the raw text back (with auto-retry)
# ----------------------------------------------------------------------
def call_gemini(prompt: str) -> str:
    return generate(model=MODEL, prompt=prompt, max_output_tokens=8192)


# ----------------------------------------------------------------------
# 3) Turn the model's text into a validated DeviceInfo form
# ----------------------------------------------------------------------
def parse_model_output(raw: str) -> DeviceInfo:
    # Models sometimes wrap JSON in ```json ... ``` fences. Strip them.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]          # take the fenced part
        if cleaned.lstrip().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
        cleaned = cleaned.strip().rstrip("`").strip()

    try:
        data = json.loads(cleaned)      # text -> Python dict
    except json.JSONDecodeError as e:
        # Show what the model actually returned, so the problem is easy to see
        # (most common cause: the answer was cut off = raise max_output_tokens).
        print("\n--- Could not parse the model's answer as JSON ---")
        print(f"Error: {e}")
        print("Raw answer from the model was:\n")
        print(raw)
        print("\n--------------------------------------------------")
        raise
    return DeviceInfo(**data)           # dict -> validated form (Pydantic checks it)


# ----------------------------------------------------------------------
# 4) Save the form as the JSON source of truth
# ----------------------------------------------------------------------
def save_source_of_truth(device: DeviceInfo, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(device.model_dump_json(indent=2), encoding="utf-8")


def main():
    print(f"Model: {MODEL}")
    prompt = build_prompt(TEST_EMAIL)

    print("Sending the email to Gemini...")
    raw = call_gemini(prompt)

    print("Parsing and validating the answer...")
    device = parse_model_output(raw)

    save_source_of_truth(device, OUTPUT_PATH)
    print(f"\nDone. Source of truth saved to: {OUTPUT_PATH}\n")
    print(device.model_dump_json(indent=2))


if __name__ == "__main__":
    main()