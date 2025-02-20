"""
Configuration for ecrivez. Structure of the toml file:
```toml
[[ecrivez]]
[user].authentication
    name = "gerard"
    email = "gerard@ecrivez.com"
    password = "password"
    api_key = "api_key"
    api_key_cmd = "api_key_strategy"
    'api_key_default_strategy' = ['$(sh pass api/all | grep name', python dotenv.load()']
    'include_cfg' = ['.config/ecrivez/extra.toml', '.config/ecrivez/guienv.local']

[aliases]
    'gerard' = 'ecrivez --agent <id2> --session <session_name> [ '' | chat | -- ] <message>'
    'grocerveau' = 'ecrivez --rag <id> --agent <id3> <message>'
    'remplicerveau' = 'ecrivez --rag <name> --model <embedding_model_name> --append <<< $cat <file> | rg -v head -n 1000 | tail -n 1000 | ecrivez --agent <id2> --session <session_name> --append <message>'
    'qtc' = 'ecrivez --tool <id2> --session <session_name> <message>'
    'tshell_master' = 'journalctl -b | ecrivez-cli --tool <id3> --session <session_name> <message>'
    'p2' = 'ecrivez --prompt <id2> --session <session_name> --file <file> --output_format <image_and_output_file> <message>'
    'p3' = 'ecrivez --prompt <id3> --no-stream --exec-wait <launch_ollama_server> --distill <distill_model_name> --output_format <image_and_output_file>  --nb_epochs <nb_epochs> --max_price <max_price> --max_output_tokens <max_output_tokens> --nb_samples <nb_samples> <message>'
    'obs' = 'ecrivez --from <obsidian_file_name> <message> --history <history_file_name> --stdout --no-stream | ecrivez convert --from <md> --to <json> --tee <output_file_name> | ecrivez speak -'
    'teamwork' = 'ecrivez --pipeline 'Q | ag_id ? tool1 | id_ag[>json] > { ag+id_mcp[id_prompt] }> >&>|  id_model | Q >@'
    'full_macro' = '\\<file>\\'

[defaults]
    model = "gpt-4o" # or command line argument
    editor = "nvim"
    agent = {'_': "agent<id1>.json",'cli': "agent<id2>.json"}
    tool_use = True
    autosave = True
    tool = {'_':"tool<id3>.json",'gui': "tool<id4>.json"}
    mcp = "mcp<id5>.json"
        prompt = "prompt<id6>.md"
[config]
    dir = "/home/user/.config/ecrivez"
    config_file = "/home/user/.config/ecrivez/config.toml"
    models = "/home/user/.config/ecrivez/models.toml"
    agents = {
            "dir": "agents",
            "file": "./{agent_id}.json",
            "agent_creator_file": "file:///home/user/.config/ecrivez/agent_creator.yaml"
        }
    tools = {"tools",
        },
    mcp = {
            "dir": "+= file:///alternative/mcp_folder",
        },
    prompts = {
            "dirs": ["/home/user/.config/ecrivez/prompts/**",   '<dir3>', fd -tf 'prompt__.*.md']
        }

[data]
    dir = "/home/user/.local/share/ecrivez"
    [user]
        rags = "rags"
        docs = "docs"
        graphrag = 'graphrag'
    [output]
        sessions = "session-<session_id>"
        image_dir = ["/home/user/.local/share/ecrivez/images", "<dir4>"]
        videos = "videos"
        audio = "audio"
        logs = "logs"
        stats = "stats"
    [cache]
        dir = "/home/user/.cache/ecrivez"
        prompt = ".temp-prompt<id6>.md"
        tmp = ".temp- <id7>.tmp"
    [runtime]
        dir = "/run/user/1000/ecrivez"
        socket = "<socket_name>.socket"
        pid = "<pid_name>.pid"
        lock = "<lock_name>.lock"
    [session]
```

config_defaults/templates/session-<session_id>.jsonld
```jsonld
{
    "@context": "https://schema.org/",
    "@type": "Session",
    "session": {
        "@type": "UUID",
        "uuid": "<session_id>"
    },
    "model": [{
        "@type": "Model",
        "name": "llama3.1",
        "fullName": "Ollama Llama 3.1 8B Instruct",
        "description": "The latest and most powerful model from Ollama",
        "provider": {
            "@type": "LocalInference",
            "name": "Ollama",
            "baseUrl": "http://localhost:11434"
        },
        "settings": {
            "temperature": 0.5,
            "top_p": 1,
            "max_tokens": 1000,
            "stop": ["\n\n"]
        },
        "message_ids": []
    },
    "messages": [
        {
            "@type": "Message",
            "role": "user",
            "content": "Hello, how are you?"
        }
    ]
}
```session-<session_id>/messages/<message_id>.{md,json,txt}

"""

from pydantic import BaseModel, Field

from .agents import DefaultAgents
from .general import GeneralConfig
from .mcp import DefaultMCP
from .paths import DefaultPaths
from .prompts import DefaultPrompts
from .session import DefaultSession
from .tools import DefaultTools


class Configuration(BaseModel, strict=True):
    general: GeneralConfig = Field(GeneralConfig, description="General config")
    paths: DefaultPaths = Field(DefaultPaths, description="Path config")
    tools: DefaultTools = Field(DefaultTools, description="Tool config")
    agents: DefaultAgents = Field(DefaultAgents, description="Agent config")
    mcp: DefaultMCP = Field(DefaultMCP, description="MCP config")
    prompts: DefaultPrompts = Field(DefaultPrompts, description="Prompts config")
    session: DefaultSession = Field(DefaultSession, description="Session config")

    def __init__(self):
        super().__init__()
        self.paths = _get_paths()
        self.general = _get_general_config()
        self.tools = DefaultTools()
        self.agents = DefaultAgents()
        self.mcp = DefaultMCP()
        self.prompts = DefaultPrompts()
        self.session = DefaultSession()
        self.session = DefaultSession()
