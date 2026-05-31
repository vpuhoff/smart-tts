import asyncio
from pathlib import Path

from elevenlabs_smart_tts import AsyncSmartTTS, SynthesisTask


async def main() -> None:
    async with AsyncSmartTTS.from_env() as tts:
        await tts.sync_voices()

        task = SynthesisTask(
            text="Добро пожаловать в наш сервис поддержки.",
            language="ru",
            style="professional",
            emotion="warm",
            use_case="conversational",
            voice_description="warm conversational professional",
        )

        output_path = Path("output.mp3")
        result = await tts.synthesize_to_file(task, output_path)

        print(f"Saved to {output_path.resolve()}")
        print(f"Enhanced text: {result.enhanced_text}")


if __name__ == "__main__":
    asyncio.run(main())
