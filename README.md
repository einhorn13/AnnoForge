# AnnoForge

**AnnoForge** is a desktop application for image annotation using the Florence-2 model. Designed for ML engineers and data scientists to quickly prepare high-quality datasets.

## Purpose

- Generate captions, tags, and prompts for images.
- Support for multiple output formats: captions, detailed descriptions, SD prompts, style tags.
- Batch processing with preview, editing, and export to CSV.
- Works locally — no data leaves your machine.

## Installation

1. Install Python 3.10+.
2. Install required packages:

    ```bash
    pip install torch torchvision "transformers==4.49.0" pillow tkinter
    ```

3. Download the Florence-2 model:

    ```bash
    git lfs install
    git clone https://huggingface.co/microsoft/Florence-2-base-ft ckpt/Florence-2-base-ft
    ```

4. Place your images in the `captions/` folder.
5. Launch the app:

    ```bash
    python AnnoForge.py
    ```

## Usage

- **Refresh** — reload image list.
- **Generate** — create annotations for selected images.
- **Edit** — double-click a file to edit its caption.
- **Change Prompt Type** — right-click multiple files to set annotation style.
- **Replace** — find and replace text across all caption files.
- **Export CSV** — save annotations for training pipelines.

The app remembers your last model and default prompt type in `config.json`.
