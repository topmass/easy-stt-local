"""LLM cleanup for transcription text."""
import sys
import re


def load_cleanup_model():
    """Load Qwen2.5 for text cleanup (macOS MLX only for now).

    Returns:
        tuple: (model, tokenizer)
    """
    try:
        from mlx_lm import load
        print("Loading Qwen2.5-1.5B-Instruct for cleanup...")
        model, tokenizer = load("mlx-community/Qwen2.5-1.5B-Instruct-4bit")
        print("Cleanup model loaded!")
        return model, tokenizer
    except ImportError:
        print("mlx-lm not installed. Install with: uv pip install mlx-lm")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to load cleanup model: {e}")
        sys.exit(1)


def load_cleanup_prompt(prompt_file="cleanup_prompt.txt"):
    """Load the cleanup prompt from file.

    Args:
        prompt_file: Path to prompt file

    Returns:
        str: Cleanup prompt text
    """
    try:
        with open(prompt_file, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        # Fallback default prompt
        return "Remove filler words (um, uh, ah, like, you know) and clean up this transcription while keeping the exact meaning. Output only the cleaned text."


def cleanup_transcription(text, model, tokenizer, base_prompt):
    """Clean up transcription using Qwen2.5.

    Args:
        text: Raw transcription text
        model: MLX-LM model instance
        tokenizer: MLX-LM tokenizer instance
        base_prompt: System prompt for cleanup

    Returns:
        str: Cleaned transcription text
    """
    from mlx_lm import generate

    # Format with Qwen's chat template
    messages = [
        {"role": "system", "content": base_prompt},
        {"role": "user", "content": f"Transcription to clean:\n{text}"}
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    print("\nCleaned transcription:")
    print("-" * 50)

    # Generate the response (high max_tokens for long transcriptions)
    response = generate(
        model,
        tokenizer,
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

    print(cleaned_text)
    print("-" * 50)

    return cleaned_text
