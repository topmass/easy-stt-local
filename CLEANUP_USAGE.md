# LLM Cleanup Feature

Remove filler words and clean up transcriptions using DeepSeek R1 Distill 1.5B.

## Quick Start

```bash
# 1. Install cleanup dependencies (one-time)
uv pip install mlx-lm

# 2. Run with cleanup enabled
uv run record_transcribe.py --cleanup
```

## What It Does

**Before cleanup:**
> "Um, okay, so like, you know, I think, uh, we should, like, finish this project by Friday, you know?"

**After cleanup:**
> "Okay, I think we should finish this project by Friday."

## How It Works

1. **Parakeet** transcribes your speech (~50ms)
2. **DeepSeek R1 Distill 1.5B** cleans it up (~150ms)
3. Result copied to clipboard (~200ms total)

Still feels instant!

## Customization

Edit `cleanup_prompt.txt` to change how cleanup works:

```
Remove filler words (um, uh, ah, like, you know, I mean, sort of, kind of) and clean up this transcription while keeping the exact meaning and tone.

Fix minor grammar issues but preserve the speaker's natural style.

Output only the cleaned transcription text, nothing else.
```

## Model Info

- **Model:** DeepSeek-R1-Distill-Qwen-1.5B
- **Release:** January 2025
- **Size:** ~1.5GB
- **Speed:** Very fast on M-series
- **Quality:** MATH-500: 94.3% (excellent for 1.5B!)
- **License:** Apache 2.0
- **Runs:** 100% locally on your Mac

## Why This Model?

✅ **Newest:** Released Jan 2025
✅ **Smartest:** Reasoning model, better at following instructions
✅ **Smallest:** Only 1.5B parameters
✅ **Fastest:** Optimized for Apple Silicon with MLX
✅ **Local:** No API calls, fully private

## Performance

| Mode | Transcription | Cleanup | Total | Feel |
|------|---------------|---------|-------|------|
| Default | 50ms | - | 50ms | ⚡ Instant |
| --cleanup | 50ms | 150ms | 200ms | ⚡ Still instant |

## Without Cleanup

Just run normally - cleanup is 100% optional:

```bash
uv run record_transcribe.py
```

No performance impact when not using `--cleanup` flag!
