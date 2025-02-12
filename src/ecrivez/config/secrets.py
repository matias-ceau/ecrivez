import os

correspondance = {
    "openai": ["OPENAI_API_KEY", "OPENAI_API", "ECRIVEZ_OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY", "ANTHROPIC_API", "ECRIVEZ_ANTHROPIC_API_KEY"],
    "mistral": ["MISTRAL_API_KEY", "MISTRAL_API", "ECRIVEZ_MISTRAL_API_KEY"],
    "xai": ["XAI_API_KEY", "XAI_API", "ECRIVEZ_XAI_API_KEY"],
    "groq": ["GROQ_API_KEY", "GROQ_API", "ECRIVEZ_GROQ_API_KEY"],
    "deepseek": ["DEEPSEEK_API_KEY", "DEEPSEEK_API", "ECRIVEZ_DEEPSEEK_API_KEY"],
    "voyageai": ["VOYAGEAI_API_KEY", "VOYAGEAI_API", "ECRIVEZ_VOYAGEAI_API_KEY"],
    "nomicai": ["NOMICAI_API_KEY", "NOMICAI_API", "ECRIVEZ_NOMICAI_API_KEY"],
    "perplexity": [
        "PERPLEXITY_API_KEY",
        "PERPLEXITY_API",
        "ECRIVEZ_PERPLEXITY_API_KEY",
    ],
    "tavily": ["TAVILY_API_KEY", "TAVILY_API", "ECRIVEZ_TAVILY_API_KEY"],
    "huggingface": [
        "HUGGINGFACE_API_KEY",
        "HUGGINGFACE_API",
        "ECRIVEZ_HUGGINGFACE_API_KEY",
    ],
    "gemini": ["GEMINI_API_KEY", "GEMINI_API", "ECRIVEZ_GEMINI_API_KEY"],
}

def get_api_for_provider(provider : str) ->  str:
    key = ''
    for i in correspondance[provider]:
        key = os.getenv(i,'')
    return key

def get_available_payed_apis() -> list:
    return [p for p in correspondance.keys() if get_api_for_provider(p) != ''])

