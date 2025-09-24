"""
T5-based text extraction for OCR System.

Uses a fine-tuned T5 model to extract structured information from OCR text.
This approach is much more accurate than regex for variable document structures.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

try:
    import tensorflow as tf
    from transformers import T5Tokenizer, T5ForConditionalGeneration
    T5_AVAILABLE = True
except ImportError:
    T5_AVAILABLE = False
    print("TensorFlow/Transformers not available. T5 extraction will be disabled.")


class T5Extractor:
    def __init__(self, model_path: str = "tf_model.h5"):
        """
        Initialize T5 extractor with the provided model.
        
        Args:
            model_path: Path to the T5 model file (.h5)
        """
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if T5_AVAILABLE and tf.config.list_physical_devices('GPU') else "cpu"
        
    def load_model(self) -> bool:
        """
        Load the T5 model and tokenizer.
        Returns True if successful, False otherwise.
        """
        if not T5_AVAILABLE:
            print("TensorFlow/Transformers not available. Cannot load T5 model.")
            return False
            
        try:
            # Load tokenizer (use a base T5 model for tokenizer)
            self.tokenizer = T5Tokenizer.from_pretrained("t5-small")
            
            # Load the fine-tuned model
            if os.path.exists(self.model_path):
                # For .h5 files, we need to load with TensorFlow/Keras
                self.model = tf.keras.models.load_model(self.model_path)
                print(f"Loaded T5 model from {self.model_path}")
                return True
            else:
                print(f"Model file not found: {self.model_path}")
                return False
                
        except Exception as e:
            print(f"Error loading T5 model: {e}")
            return False
    
    def extract_fields(self, text: str, field_types: List[str]) -> Dict[str, Optional[str]]:
        """
        Extract specified fields from OCR text using T5 model.
        
        Args:
            text: OCR text to extract from
            field_types: List of field types to extract (e.g., ["license_id", "date", "reference_id"])
            
        Returns:
            Dictionary with extracted field values
        """
        if not self.model or not self.tokenizer:
            if not self.load_model():
                return {field: None for field in field_types}
        
        results = {}
        
        for field_type in field_types:
            try:
                # Create input prompt for T5
                prompt = self._create_prompt(text, field_type)
                
                # Tokenize input
                inputs = self.tokenizer.encode(prompt, return_tensors="tf", max_length=512, truncation=True)
                
                # Generate output
                outputs = self.model.generate(
                    inputs,
                    max_length=50,
                    num_beams=4,
                    early_stopping=True,
                    temperature=0.1
                )
                
                # Decode output
                extracted_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                
                # Clean and validate extracted text
                cleaned_text = self._clean_extracted_text(extracted_text, field_type)
                results[field_type] = cleaned_text if cleaned_text else None
                
            except Exception as e:
                print(f"Error extracting {field_type}: {e}")
                results[field_type] = None
        
        return results
    
    def _create_prompt(self, text: str, field_type: str) -> str:
        """
        Create a prompt for T5 model to extract specific field.
        """
        field_descriptions = {
            "license_id": "license number or license ID",
            "date": "date or date of issue",
            "reference_id": "reference number or reference ID",
            "invoice_number": "invoice number",
            "amount": "amount or total amount",
            "customer_name": "customer name or client name"
        }
        
        field_desc = field_descriptions.get(field_type, field_type)
        
        # Truncate text if too long
        if len(text) > 1000:
            text = text[:1000] + "..."
        
        prompt = f"Extract the {field_desc} from this document text: {text}"
        return prompt
    
    def _clean_extracted_text(self, text: str, field_type: str) -> Optional[str]:
        """
        Clean and validate extracted text based on field type.
        """
        if not text or text.strip() == "":
            return None
        
        text = text.strip()
        
        # Field-specific validation
        if field_type == "date":
            # Validate date format
            if re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', text) or re.match(r'\d{4}[/-]\d{1,2}[/-]\d{1,2}', text):
                return text
            return None
            
        elif field_type == "license_id":
            # Validate license format (alphanumeric, reasonable length)
            if re.match(r'^[A-Z0-9]{3,20}$', text):
                return text
            return None
            
        elif field_type == "reference_id":
            # Validate reference format
            if re.match(r'^[A-Z0-9-]{3,20}$', text):
                return text
            return None
            
        elif field_type == "amount":
            # Validate amount format
            if re.match(r'^\d+[.,]?\d*$', text):
                return text
            return None
        
        # For other fields, return as-is if not empty
        return text if len(text) > 1 else None


def extract_with_context_t5(
    text: str,
    field_types: List[str],
    model_path: str = "tf_model.h5"
) -> Dict[str, Optional[str]]:
    """
    Convenience function to extract fields using T5 model.
    
    Args:
        text: OCR text to extract from
        field_types: List of field types to extract
        model_path: Path to T5 model file
        
    Returns:
        Dictionary with extracted field values
    """
    extractor = T5Extractor(model_path)
    return extractor.extract_fields(text, field_types)


# Example usage and testing
if __name__ == "__main__":
    # Test the extractor
    sample_text = """
    License Number: LIC123456
    Date of Issue: 12/25/2024
    Reference: REF-789012
    Customer: John Doe
    Amount: $1,250.00
    """
    
    extractor = T5Extractor()
    if extractor.load_model():
        results = extractor.extract_fields(sample_text, ["license_id", "date", "reference_id"])
        print("Extraction results:")
        for field, value in results.items():
            print(f"  {field}: {value}")
    else:
        print("Failed to load model")
