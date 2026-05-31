NORMALIZATION_INSTRUCTIONS = """
When normalizing text for TTS:
- Expand numbers, dates, times, currency, phone numbers, and URLs into spoken form.
- Preserve the original words and meaning.
- Do not add audio tags unless instructed by the model-specific prompt.
- For non-English text, apply language-appropriate spoken forms in the LLM step.
""".strip()
