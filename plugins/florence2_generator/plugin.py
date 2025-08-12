# plugins/florence2_generator/plugin.py
import os
import torch
from transformers import AutoProcessor, AutoModelForCausalLM
from PIL import Image as PILImage
from plugins.api import ModelAssistantPlugin

# REFACTORED: Use a constant for the models directory
MODELS_DIR = "ckpt"

class Florence2GeneratorPlugin(ModelAssistantPlugin):
    def __init__(self):
        super().__init__()
        self.processor = None
        self.model = None
        self.loaded_model_path = None # Keep track of the loaded model path
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.prompt_map = {
            "Caption": "<CAPTION>",
            "Detailed Caption": "<DETAILED_CAPTION>",
            "More Detailed": "<MORE_DETAILED_CAPTION>",
            "Tags (General)": "<GENERATE_TAGS>",
            "Tags (Objects)": "<GENERATE_TAGS_OBJECT>",
            "Tags (Style)": "<GENERATE_TAGS_STYLE>",
            "Tags (Composition)": "<GENERATE_TAGS_COMPOSITION>",
            "Prompt (SD)": "<GENERATE_PROMPT>",
            "Prompt (V2)": "<GENERATE_PROMPT_V2>",
        }

    @property
    def name(self) -> str:
        return "florence2_generator"
    
    @property
    def display_name(self) -> str:
        return "Florence-2"
        
    def is_model_loaded(self, model_path: str) -> bool:
        """Checks if the model at the given path is the currently active one."""
        return self.model is not None and self.loaded_model_path == os.path.abspath(model_path)

    def get_model_paths(self) -> list[str]:
        """Scan for valid Florence-2 models."""
        if not os.path.exists(MODELS_DIR):
            return []
        models = []
        for d in os.listdir(MODELS_DIR):
            path = os.path.join(MODELS_DIR, d)
            if os.path.isdir(path) and os.path.exists(os.path.join(path, "config.json")):
                models.append(path)
        return models

    def load_model(self, model_path: str) -> (bool, str):
        # REFACTORED: Add a check to avoid reloading the same model.
        if self.is_model_loaded(model_path):
            return True, f"✅ Already loaded: {os.path.basename(model_path)}"

        try:
            # REFACTORED: Use SDPA for better performance on compatible hardware (PyTorch 2.0+),
            # with a fallback to the original 'eager' implementation.
            attn_implementation = "sdpa" if hasattr(torch.nn.functional, 'scaled_dot_product_attention') else "eager"
            
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=self.dtype,
                trust_remote_code=True,
                attn_implementation=attn_implementation
            ).to(self.device)
            self.processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
            self.loaded_model_path = os.path.abspath(model_path) # Store the absolute path
            return True, f"✅ Loaded: {os.path.basename(model_path)}"
        except Exception as e:
            self.model = None
            self.processor = None
            self.loaded_model_path = None
            return False, f"❌ Load failed: {str(e)[:100]}"

    def run_inference(self, image_path: str, prompt_type: str) -> (bool, str):
        if self.model is None or self.processor is None:
            return False, "Model not loaded"
        try:
            image = PILImage.open(image_path).convert("RGB")
            prompt = self.prompt_map.get(prompt_type, "<CAPTION>")
            inputs = self.processor(images=image, text=prompt, return_tensors="pt").to(self.device, self.dtype)
            
            generated_ids = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                num_beams=3,
                do_sample=False
            )
            
            generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            # Post-process caption to remove the task prompt part that sometimes leaks
            # Find the final prompt marker and take the text after it.
            # E.g., for "<MORE_DETAILED_CAPTION>", it will split by ">" and take the last part.
            prompt_parts = generated_text.split('>')
            caption = prompt_parts[-1].strip()

            if "Tags" in prompt_type:
                parts = [p.strip() for p in caption.split(",")]
                caption = ", ".join(parts[:30])
                
            return True, caption
        except Exception as e:
            return False, f"Error: {str(e)}"

    def get_supported_prompts(self) -> dict:
        return self.prompt_map

def register():
    return Florence2GeneratorPlugin()