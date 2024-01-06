import os

telemetry_server = "https://khoj.beta.haletic.com/v1/telemetry"
KHOJ_WHATSAPP_PROD = "whatsapp:+18488004242"
KHOJ_WHATSAPP_DEBUG = "whatsapp:+14155238886"
KHOJ_INTRO_MESSAGE = f"""
Nice to meet you! I am Khoj, your dedicated personal AI 👋🏽. I can help you with:
- 📜 Free-form journaling and note-taking
- 🧠 Answering general knowledge questions
- 💡 Ideating over new ideas
- 🖊️ Being a scratchpad for your thoughts, links, concepts that you want to remember

You can also send me voice messages in your native language 🎙️.

I'm constantly learning and improving. I'm still in beta, so please report any bugs or issues to my creators on GitHub: https://github.com/khoj-ai/flint/issues
""".strip()

KHOJ_FAILED_AUDIO_TRANSCRIPTION_MESSAGE = f"""
Sorry, I wasn't able to understand your voice message this time. Could you please try typing out your message or send a shorter audio file? If you'd like to help me improve, email my creators at team@khoj.dev.
""".strip()

KHOJ_API_URL = os.getenv("KHOJ_API_URL", "https://khoj.dev")
KHOJ_API_CLIENT_ID = os.getenv("KHOJ_API_CLIENT_ID")
KHOJ_API_CLIENT_SECRET = os.getenv("KHOJ_API_CLIENT_SECRET")
