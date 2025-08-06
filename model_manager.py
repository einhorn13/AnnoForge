# model_manager.py
import torch
import os
from transformers import AutoProcessor, AutoModelForCausalLM

processor = None
model = None
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if device == "cuda" else torch.float32


def load_model(model_path):
    """Load Florence-2 model from path"""
    global processor, model
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=dtype,
            trust_remote_code=True,
            attn_implementation="eager"
        ).to(device)
        processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
        return True, f"✅ Loaded: {os.path.basename(model_path)}"
    except Exception as e:
        return False, f"❌ Load failed: {str(e)[:100]}"


def generate_caption(image_path, prompt_type, prompt_map):
    """Generate caption for image using selected prompt"""
    from PIL import Image as PILImage
    global processor, model
    if model is None:
        return False, "Model not loaded"
    try:
        image = PILImage.open(image_path).convert("RGB")
        prompt = prompt_map[prompt_type]
        inputs = processor(images=image, text=prompt, return_tensors="pt").to(device, dtype)
        generated_ids = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=1024,
            num_beams=3,
            do_sample=False
        )
        caption = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        if "Tags" in prompt_type:
            parts = [p.strip() for p in caption.split(",")]
            caption = ", ".join(parts[:30])
        return True, caption
    except Exception as e:
        return False, f"Error: {str(e)}"