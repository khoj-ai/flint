telemetry_server = "https://khoj.beta.haletic.com/v1/telemetry"
KHOJ_WHATSAPP_PROD = "whatsapp:+18488004242"
KHOJ_WHATSAPP_DEBUG = "whatsapp:+14155238886"
KHOJ_INTRO_MESSAGE = f"""
By the way, I am Khoj, your dedicated personal AI 👋🏽. I can help you with:
- 📜 Free-form journaling and note-taking
- 🧠 Answering general knowledge questions
- 💡 Ideating over new ideas
- 🖊️ Being a scratchpad for your thoughts, links, concepts that you want to remember

You can also send me voice messages in your native language 🎙️.

I'm constantly learning and improving. I'm still in beta, so please report any bugs or issues to my creators on GitHub: https://github.com/khoj-ai/flint/issues
""".strip()
KHOJ_PROMPT_EXCEEDED_MESSAGE = f"""
I'm sorry, I can't read messages that are so long. Could you please shorten your message and try again? I'm constantly learning and improving, so I'll be able to read longer messages soon.
"""
MAX_TOKEN_LIMIT_PROMPT = 12000
KHOJ_FAILED_AUDIO_TRANSCRIPTION_MESSAGE = f"""
Sorry, I wasn't able to understand your voice message this time. Could you please try typing out your message? If you'd like to help me improve, please report this issue to my creators on GitHub: https://github.com/khoj-ai/flint/issues.
""".strip()
