from pathlib import Path

from elevenlabs_smart_tts import SmartTTS, SynthesisTask

tts = SmartTTS.from_env()
tts.sync_voices()

task = SynthesisTask(
    text="Добро пожаловать в наш сервис поддержки.",
    language="ru",
    style="professional",
    use_case="customer_support",
)

output_path = Path("output.mp3")
result = tts.synthesize_to_file(task, output_path)

print(f"Saved to {output_path.resolve()}")
print(f"Enhanced text: {result.enhanced_text}")
