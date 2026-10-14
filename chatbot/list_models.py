"""
list_models.py
--------------
Lists the Gemini models this API key can use, with the actions each one supports
(generateContent for chat, embedContent for embeddings).

    python -m chatbot.list_models
"""

from chatbot import llm


def main() -> None:
    models = sorted(llm._client().models.list(), key=lambda model: model.name)
    print(f"{'Model ID':45s} {'Display name':40s} Supported actions")
    for model in models:
        model_id = model.name.removeprefix("models/")
        print(f"{model_id:45s} {model.display_name or '':40s} {', '.join(model.supported_actions or [])}")
    print(f"\n{len(models)} models. Current defaults: chat {', '.join(llm.chat_models())}; embeddings {llm.embed_model()}")


if __name__ == "__main__":
    main()
