"""
schema.py
---------
The "empty form" for one medical device: every field from the Word template
(Device_description_01.docx). Every AI model we test fills in THIS same form,
so we can compare them fairly.

Rule: every field is Optional. A client email rarely has everything, and the
model must be allowed to leave a field empty (None) instead of inventing data.
We NEVER want a model to make up an SRN, UDI or code that wasn't in the email.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class Variant(BaseModel):
    """One row of the 'Variants' table: an article number + product name."""
    art_no: Optional[str] = None
    product_name: Optional[str] = None


class DeviceInfo(BaseModel):
    # --- General information ---
    manufacturer: Optional[str] = None
    srn: Optional[str] = None                      # regulatory ID - never invent
    product_name: Optional[str] = None
    article_number_ref: Optional[str] = None
    basic_udi_di: Optional[str] = None             # regulatory ID - never invent
    device_description: Optional[str] = None
    intended_purpose: Optional[str] = None
    indications: Optional[str] = None
    contraindications: Optional[str] = None
    warnings: Optional[str] = None

    # --- Classification ---
    classification: Optional[str] = None
    rule: Optional[str] = None

    # --- Codes (regulatory IDs - never invent) ---
    code_emdn: Optional[str] = None
    code_gmdn: Optional[str] = None
    code_mdr: Optional[str] = None

    # --- Variants (a list, there can be several) ---
    variants: List[Variant] = Field(default_factory=list)

    # --- Device characteristics ---
    previous_generations: Optional[str] = None
    innovative_properties: Optional[str] = None
    accessories: Optional[str] = None
    products_for_combined_use: Optional[str] = None

    # --- Application specifications ---
    patient_population: Optional[str] = None
    intended_users: Optional[str] = None
    description_of_use: Optional[str] = None

    # --- Labeling ---
    special_labeling: Optional[str] = None


if __name__ == "__main__":
    print(DeviceInfo().model_dump_json(indent=2))