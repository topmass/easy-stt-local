"""Local cleanup providers (MLX-based Qwen, PyTorch-based for Linux)."""
import re
from .base import CleanupProvider


class QwenMLXCleanupProvider(CleanupProvider):
    """macOS Apple Silicon cleanup using Qwen2.5 via MLX.

    Features:
    - MLX-optimized for Apple Silicon
    - 4-bit quantization for speed
    - PARA framework for structured output
    - ~150ms latency on M1+
    """

    def __init__(self, prompt_file: str = "cleanup_prompt.txt"):
        """Initialize Qwen2.5 cleanup model.

        Args:
            prompt_file: Path to cleanup prompt file
        """
        from mlx_lm import load
        print("Loading Qwen2.5-1.5B-Instruct for cleanup...")
        self.model, self.tokenizer = load("mlx-community/Qwen2.5-1.5B-Instruct-4bit")
        print("Cleanup model loaded!")

        # Load prompt
        try:
            with open(prompt_file, 'r') as f:
                self.base_prompt = f.read().strip()
        except FileNotFoundError:
            self.base_prompt = "Remove filler words (um, uh, ah, like, you know) and clean up this transcription while keeping the exact meaning. Output only the cleaned text."

    def cleanup(self, text: str) -> str:
        """Clean up transcription using Qwen2.5.

        Args:
            text: Raw transcription text

        Returns:
            str: Cleaned transcription text
        """
        from mlx_lm import generate

        # Format with Qwen's chat template
        messages = [
            {"role": "system", "content": self.base_prompt},
            {"role": "user", "content": f"Transcription to clean:\n{text}"}
        ]

        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        # Generate the response (high max_tokens for long transcriptions)
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=2048,  # Support up to ~10 minutes of speech
            verbose=False
        )

        # Extract content between <output> tags if present
        output_match = re.search(r'<output>\s*(.*?)\s*</output>', response, re.DOTALL)

        if output_match:
            cleaned_text = output_match.group(1).strip()
        else:
            # Qwen doesn't use thinking tags, so just use the response
            cleaned_text = response.strip()
            # Remove any XML-like tags that might have leaked through
            cleaned_text = re.sub(r'<output>|</output>', '', cleaned_text)
            cleaned_text = cleaned_text.strip()

        return cleaned_text

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "Qwen2.5-1.5B (MLX)"


class QwenPyTorchCleanupProvider(CleanupProvider):
    """Linux CUDA cleanup using Qwen2.5 via PyTorch + transformers.

    Features:
    - CUDA-accelerated on NVIDIA GPUs
    - 4-bit quantization via bitsandbytes
    - Same model as macOS MLX version
    - ~100-200ms latency on modern GPUs
    """

    def __init__(self, prompt_file: str = "cleanup_prompt.txt"):
        """Initialize Qwen2.5 cleanup model with PyTorch.

        Args:
            prompt_file: Path to cleanup prompt file
        """
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

        print("Loading Qwen2.5-1.5B-Instruct for cleanup (PyTorch)...")

        # 4-bit quantization config
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4"
        )

        model_name = "Qwen/Qwen2.5-1.5B-Instruct"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=quantization_config,
            device_map="auto",
            torch_dtype=torch.float16
        )
        self.model.eval()
        print("Cleanup model loaded!")

        # Load prompt
        try:
            with open(prompt_file, 'r') as f:
                self.base_prompt = f.read().strip()
        except FileNotFoundError:
            self.base_prompt = "Remove filler words (um, uh, ah, like, you know) and clean up this transcription while keeping the exact meaning. Output only the cleaned text."

    def cleanup(self, text: str) -> str:
        """Clean up transcription using Qwen2.5 with PyTorch.

        Args:
            text: Raw transcription text

        Returns:
            str: Cleaned transcription text
        """
        import torch

        # Format with Qwen's chat template
        messages = [
            {"role": "system", "content": self.base_prompt},
            {"role": "user", "content": f"Transcription to clean:\n{text}"}
        ]

        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        # Generate
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=2048,
                do_sample=False,
                temperature=None,
                top_p=None
            )

        response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)

        # Extract content between <output> tags if present
        output_match = re.search(r'<output>\s*(.*?)\s*</output>', response, re.DOTALL)

        if output_match:
            cleaned_text = output_match.group(1).strip()
        else:
            cleaned_text = response.strip()
            cleaned_text = re.sub(r'<output>|</output>', '', cleaned_text)
            cleaned_text = cleaned_text.strip()

        return cleaned_text

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "Qwen2.5-1.5B (PyTorch/CUDA)"


class NoCleanupProvider(CleanupProvider):
    """Pass-through provider that returns text unchanged."""

    def cleanup(self, text: str) -> str:
        """Return text unchanged.

        Args:
            text: Input text

        Returns:
            str: Same text unchanged
        """
        return text

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "None (No cleanup)"
