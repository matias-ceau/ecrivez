# Ecrivez Project Exploration & Direction Suggestions

## Executive Summary

Ecrivez is a terminal-based autonomous coding assistant that integrates LLMs with development workflows. The project is in early stages with ~1000 LOC and follows a modular architecture. This document explores the current state and proposes concrete implementation directions.

## Current State Analysis

### Architecture Overview

**Core Components:**
1. **CLI Interface** (`cli.py`) - Click-based command system with init, config, chat, and repl commands
2. **Chat/REPL System** (`chat.py`) - Interactive LLM conversation with provider abstraction
3. **Editor Integration** (`editor.py`, `nvim_api.py`) - Tmux-based split-pane setup with Neovim socket communication
4. **Project Management** (`project.py`) - Git-integrated project initialization and configuration
5. **Configuration System** (`config/`) - Pydantic-based config with XDG directory support
6. **UI Components** (`ui/`) - Qt-based browser + terminal interface (experimental)

**Technology Stack:**
- Python 3.13+ with modern syntax (`str | None` unions)
- Click for CLI, Pydantic for validation, PyYAML for config
- LLM Integration: OpenAI API with fallback Echo provider
- Editor: Neovim via pynvim socket communication
- Terminal: libtmux for session management
- UI: PyQt6 + WebEngine (experimental)
- Agent Framework: smolagents (imported but not yet integrated)

### Completed Features (Roadmap Analysis)

✅ **Milestone 1: Reliable OpenAI provider** - Provider selection logic with API key resolution
✅ **Milestone 3: Tool calls** - JSON-based tool invocation (`{"type":"tool","tool":"shell","cmd":"ls"}`)
✅ **Milestone 5: Config validation** - Pydantic schema validation with helpful errors

⚠️ **Partially Complete:**
- Milestone 2: Socket patching - `/apply` command exists but diff parsing is naive
- Milestone 4: Session persistence - `_save_history` implemented but incomplete (missing `_load_history`)

### Test Coverage

Good test coverage for core features:
- `test_chat_provider.py` - Provider selection logic
- `test_config_validation.py` - Pydantic config validation
- `test_json_tool_invocation.py` - Tool system
- `test_echo_provider.py`, `test_nvim_apply.py` - Basic functionality
- **Missing**: Integration tests, E2E workflows, Qt UI tests

### Key Strengths

1. **Clean Architecture** - Well-separated concerns with clear module boundaries
2. **Type Safety** - Modern Python typing with Pydantic validation
3. **Extensibility** - Provider abstraction allows multiple LLM backends
4. **XDG Compliance** - Follows Linux filesystem standards
5. **Test-First Approach** - Roadmap emphasizes tests before implementation

### Key Gaps & Technical Debt

1. **Incomplete History Persistence** - `_load_history` function is called but not implemented
2. **Naive Diff Application** - Simple line-based diff parsing (no real unified diff support)
3. **Unused Dependencies** - smolagents, gradio imported but not integrated
4. **UI Fragmentation** - Multiple UI approaches (tmux, Qt, gradio) without clear direction
5. **Configuration Complexity** - Large config spec in comments without implementation
6. **Session Management** - UUID-based sessions lack loading/resumption capability
7. **MCP Protocol** - Config references MCP but no implementation
8. **Tool System** - Only shell tool implemented; framework needs expansion

---

## Proposed Directions & Implementation Roadmap

### Direction 1: **Agentic Workflow Engine** 🤖

**Vision:** Transform Ecrivez into a sophisticated autonomous coding agent with multi-step reasoning, tool use, and task decomposition.

**Core Concept:** Leverage smolagents framework to create an agent that can plan, execute, and verify code changes through a structured workflow.

**Concrete Implementation:**

#### 1.1 Agent Architecture
```python
# src/ecrivez/agents/base.py
from smolagents import Agent, Tool
from typing import List, Dict, Any

class EcrivezAgent:
    """Autonomous coding agent with tool use and planning."""
    
    def __init__(self, config: ProjectConfig):
        self.tools = self._load_tools()
        self.agent = Agent(
            model=self._create_model(config),
            tools=self.tools,
            system_prompt=self._load_system_prompt()
        )
    
    def execute_task(self, task: str) -> TaskResult:
        """Execute a coding task with multi-step reasoning."""
        plan = self.agent.plan(task)
        results = []
        for step in plan.steps:
            result = self.agent.execute_step(step)
            results.append(result)
        return TaskResult(plan, results)
```

#### 1.2 Tool Ecosystem
```python
# src/ecrivez/tools/code_tools.py
from smolagents import Tool

class CodeAnalysisTool(Tool):
    name = "analyze_code"
    description = "Analyze code structure and dependencies"
    
    def forward(self, file_path: str) -> Dict[str, Any]:
        # Parse AST, extract functions, classes, imports
        return analysis_result

class TestGeneratorTool(Tool):
    name = "generate_tests"
    description = "Generate unit tests for given code"
    
    def forward(self, code: str, framework: str = "pytest") -> str:
        # Use LLM to generate tests
        return generated_tests

class RefactorTool(Tool):
    name = "refactor_code"
    description = "Suggest and apply refactorings"
    
    def forward(self, file_path: str, refactor_type: str) -> str:
        # Extract method, rename variable, etc.
        return refactored_code
```

#### 1.3 Workflow Definition
```yaml
# .ecrivez/workflows/feature_implementation.yaml
name: implement_feature
description: Implement a new feature from description

steps:
  - name: analyze_requirements
    tool: analyze_code
    inputs:
      context: ${project_files}
  
  - name: generate_implementation
    tool: code_generator
    inputs:
      spec: ${user_input}
      context: ${analyze_requirements.output}
  
  - name: generate_tests
    tool: generate_tests
    inputs:
      code: ${generate_implementation.output}
  
  - name: verify_implementation
    tool: run_tests
    inputs:
      test_files: ${generate_tests.output}
```

#### 1.4 Implementation Steps
1. **Week 1-2:** Integrate smolagents framework, create base Agent class
2. **Week 3-4:** Implement core tools (code analysis, test generation, refactoring)
3. **Week 5-6:** Build workflow engine with YAML definition parser
4. **Week 7-8:** Create agent memory system for context persistence
5. **Week 9-10:** Add multi-agent collaboration (specialist agents for different tasks)

**Benefits:**
- Autonomous task execution with minimal human intervention
- Structured approach to complex coding tasks
- Reusable tool ecosystem
- Clear audit trail of agent actions

---

### Direction 2: **RAG-Enhanced Codebase Assistant** 📚

**Vision:** Create an intelligent assistant that understands your entire codebase through vector embeddings and semantic search.

**Core Concept:** Index project code and docs into a vector database, enabling semantic search and context-aware code generation.

**Concrete Implementation:**

#### 2.1 Vector Database Setup
```python
# src/ecrivez/rag/indexer.py
from chromadb import Client
from sentence_transformers import SentenceTransformer

class CodebaseIndexer:
    """Index codebase for semantic search."""
    
    def __init__(self, project_root: Path):
        self.client = Client()
        self.collection = self.client.create_collection("codebase")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def index_project(self):
        """Index all Python files in project."""
        for py_file in self.project_root.rglob("*.py"):
            chunks = self._chunk_file(py_file)
            embeddings = self.model.encode(chunks)
            self.collection.add(
                documents=chunks,
                embeddings=embeddings,
                metadatas=[{"file": str(py_file), "type": "code"}]
            )
    
    def search(self, query: str, n_results: int = 5):
        """Semantic search over codebase."""
        query_embedding = self.model.encode([query])
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
        return results
```

#### 2.2 Context-Aware Chat
```python
# src/ecrivez/rag/chat.py
class RAGChat:
    """Chat with RAG-enhanced context."""
    
    def __init__(self, indexer: CodebaseIndexer, provider: BaseProvider):
        self.indexer = indexer
        self.provider = provider
    
    def chat(self, user_query: str, history: List[Message]) -> str:
        # Retrieve relevant code context
        context = self.indexer.search(user_query, n_results=3)
        
        # Build augmented prompt
        augmented_prompt = f"""
        Relevant code context:
        {self._format_context(context)}
        
        User query: {user_query}
        """
        
        # Generate response with context
        history.append({"role": "user", "content": augmented_prompt})
        return self.provider.chat_completion(history)
```

#### 2.3 Incremental Indexing
```python
# src/ecrivez/rag/watcher.py
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CodeWatcher(FileSystemEventHandler):
    """Watch for file changes and re-index."""
    
    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            self.indexer.update_file(event.src_path)
```

#### 2.4 Implementation Steps
1. **Week 1-2:** Set up ChromaDB/Qdrant, implement basic indexer
2. **Week 3-4:** Add chunking strategies (function-level, class-level)
3. **Week 5-6:** Integrate with chat system, augmented prompts
4. **Week 7-8:** Implement incremental indexing with file watchers
5. **Week 9-10:** Add documentation indexing (README, docstrings, external docs)
6. **Week 11-12:** Build graph RAG for code relationships (imports, inheritance)

**Benefits:**
- Deep understanding of entire codebase
- Context-aware code suggestions
- Quick navigation and discovery
- Handles large projects efficiently

---

### Direction 3: **Multi-Modal Development Environment** 🖥️

**Vision:** Build a unified development environment that integrates code editing, terminal, browser, and LLM chat in a cohesive Qt interface.

**Core Concept:** Replace tmux/terminal-only approach with a rich GUI that provides better context switching and visual feedback.

**Concrete Implementation:**

#### 3.1 Enhanced Qt Interface
```python
# src/ecrivez/ui/main_window.py
from PyQt6.QtWidgets import QMainWindow, QSplitter, QTabWidget

class EcrivezMainWindow(QMainWindow):
    """Main development environment window."""
    
    def __init__(self):
        super().__init__()
        self.setup_layout()
        self.setup_keybindings()
        
    def setup_layout(self):
        # Main splitter: Editor | Assistant
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left: Code editor + terminal
        left_panel = QSplitter(Qt.Vertical)
        self.editor = CodeEditorWidget()  # Embedded Neovim or Qt text editor
        self.terminal = TerminalWidget()
        left_panel.addWidget(self.editor)
        left_panel.addWidget(self.terminal)
        
        # Right: Assistant panel with tabs
        right_panel = QTabWidget()
        self.chat_widget = ChatWidget()
        self.browser_widget = BrowserWidget()
        self.graph_widget = CodeGraphWidget()
        right_panel.addTab(self.chat_widget, "Assistant")
        right_panel.addTab(self.browser_widget, "Docs")
        right_panel.addTab(self.graph_widget, "Graph")
        
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        self.setCentralWidget(main_splitter)
```

#### 3.2 Integrated Chat Widget
```python
# src/ecrivez/ui/widgets/chat.py
class ChatWidget(QWidget):
    """LLM chat with code context awareness."""
    
    def __init__(self):
        self.layout = QVBoxLayout()
        self.messages = QListWidget()  # Chat history
        self.input = QTextEdit()  # User input
        self.send_button = QPushButton("Send")
        
        self.setup_ui()
        self.connect_signals()
    
    def send_message(self):
        # Get current editor selection as context
        selected_code = self.parent().editor.get_selection()
        
        # Build context-aware message
        message = {
            "text": self.input.toPlainText(),
            "context": {
                "code": selected_code,
                "file": self.parent().editor.current_file,
                "cursor_position": self.parent().editor.cursor_position
            }
        }
        
        # Send to LLM with context
        response = self.chat_handler.process(message)
        self.display_response(response)
```

#### 3.3 Code Graph Visualization
```python
# src/ecrivez/ui/widgets/graph.py
import networkx as nx
from PyQt6.QtWidgets import QGraphicsView

class CodeGraphWidget(QGraphicsView):
    """Visualize code structure and dependencies."""
    
    def __init__(self):
        super().__init__()
        self.graph = nx.DiGraph()
        self.setup_graph()
    
    def build_graph_from_codebase(self, project_root: Path):
        """Build dependency graph from code analysis."""
        for py_file in project_root.rglob("*.py"):
            module = self._parse_module(py_file)
            self.graph.add_node(module.name, type="module")
            
            for import_stmt in module.imports:
                self.graph.add_edge(module.name, import_stmt.module)
        
        self.render_graph()
```

#### 3.4 Inline Code Suggestions
```python
# src/ecrivez/ui/widgets/editor.py
class CodeEditorWidget(QTextEdit):
    """Text editor with inline LLM suggestions."""
    
    def __init__(self):
        super().__init__()
        self.suggestion_overlay = SuggestionOverlay(self)
        self.setup_completion()
    
    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        
        # Trigger suggestions on specific keys
        if event.key() in [Qt.Key_Space, Qt.Key_Tab]:
            self.request_suggestions()
    
    def request_suggestions(self):
        """Request inline code completion from LLM."""
        context = self.get_context_around_cursor(lines=10)
        suggestions = self.llm_provider.get_completions(context)
        self.suggestion_overlay.show_suggestions(suggestions)
```

#### 3.5 Implementation Steps
1. **Week 1-2:** Refactor Qt interface with proper MVC architecture
2. **Week 3-4:** Integrate embedded editor (QScintilla or Neovim-Qt)
3. **Week 5-6:** Build context-aware chat widget with code selection
4. **Week 7-8:** Implement code graph visualization with NetworkX
5. **Week 9-10:** Add inline suggestions and completions
6. **Week 11-12:** Create themes, shortcuts, and customization system

**Benefits:**
- Better user experience than terminal-only
- Visual feedback and graph visualization
- Context-aware interactions
- Modern IDE-like features

---

### Direction 4: **Session & Workflow Persistence System** 💾

**Vision:** Create a comprehensive session management system that saves, resumes, and shares development sessions.

**Core Concept:** Treat each development session as a first-class object that can be persisted, analyzed, and replayed.

**Concrete Implementation:**

#### 4.1 Session Schema
```python
# src/ecrivez/session/schema.py
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class SessionMessage(BaseModel):
    id: str
    timestamp: datetime
    role: str  # user, assistant, system, tool
    content: str
    metadata: Dict[str, Any]

class CodeChange(BaseModel):
    id: str
    timestamp: datetime
    file_path: Path
    diff: str
    commit_hash: Optional[str]
    message: str

class ToolInvocation(BaseModel):
    id: str
    timestamp: datetime
    tool_name: str
    arguments: Dict[str, Any]
    result: str
    duration_ms: int

class Session(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    project_name: str
    model: str
    messages: List[SessionMessage]
    code_changes: List[CodeChange]
    tool_invocations: List[ToolInvocation]
    tags: List[str]
    
    class Config:
        json_schema_extra = {
            "@context": "https://schema.org/",
            "@type": "CreativeWork"
        }
```

#### 4.2 Session Manager
```python
# src/ecrivez/session/manager.py
class SessionManager:
    """Manage session lifecycle: create, save, load, list."""
    
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.current_session: Optional[Session] = None
    
    def create_session(self, name: str, config: ProjectConfig) -> Session:
        """Create a new session."""
        session = Session(
            id=uuid4().hex,
            name=name,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            project_name=config.name,
            model=config.model,
            messages=[],
            code_changes=[],
            tool_invocations=[],
            tags=[]
        )
        self.current_session = session
        return session
    
    def save_session(self, session: Session):
        """Persist session to disk."""
        session_file = self.sessions_dir / f"{session.id}.json"
        session_file.write_text(session.model_dump_json(indent=2))
    
    def load_session(self, session_id: str) -> Session:
        """Load session from disk."""
        session_file = self.sessions_dir / f"{session_id}.json"
        return Session.model_validate_json(session_file.read_text())
    
    def list_sessions(self, project_name: Optional[str] = None) -> List[Session]:
        """List all sessions, optionally filtered by project."""
        sessions = []
        for session_file in self.sessions_dir.glob("*.json"):
            session = Session.model_validate_json(session_file.read_text())
            if project_name is None or session.project_name == project_name:
                sessions.append(session)
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)
```

#### 4.3 Session Replay
```python
# src/ecrivez/session/replay.py
class SessionReplay:
    """Replay a session to reproduce development history."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def replay(self, speed: float = 1.0):
        """Replay session at given speed multiplier."""
        for message in self.session.messages:
            self._display_message(message)
            time.sleep(message.delay / speed)
        
        for change in self.session.code_changes:
            self._apply_change(change)
            time.sleep(change.delay / speed)
    
    def export_to_markdown(self) -> str:
        """Export session as markdown document."""
        md = f"# Session: {self.session.name}\n\n"
        md += f"Date: {self.session.created_at}\n"
        md += f"Model: {self.session.model}\n\n"
        
        for msg in self.session.messages:
            md += f"## {msg.role.title()}\n\n{msg.content}\n\n"
        
        return md
```

#### 4.4 Session Analytics
```python
# src/ecrivez/session/analytics.py
class SessionAnalytics:
    """Analyze session metrics and patterns."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def compute_metrics(self) -> Dict[str, Any]:
        """Compute session statistics."""
        return {
            "duration_minutes": self._compute_duration(),
            "message_count": len(self.session.messages),
            "code_changes": len(self.session.code_changes),
            "tools_used": self._count_tools(),
            "files_modified": self._count_files(),
            "lines_added": self._count_lines_added(),
            "lines_removed": self._count_lines_removed(),
            "avg_response_time": self._avg_response_time(),
        }
    
    def generate_report(self) -> str:
        """Generate human-readable session report."""
        metrics = self.compute_metrics()
        return f"""
        Session Report: {self.session.name}
        ================================
        Duration: {metrics['duration_minutes']} minutes
        Messages: {metrics['message_count']}
        Files Modified: {metrics['files_modified']}
        Lines Changed: +{metrics['lines_added']} -{metrics['lines_removed']}
        Tools Used: {', '.join(metrics['tools_used'].keys())}
        """
```

#### 4.5 Implementation Steps
1. **Week 1-2:** Define session schema with Pydantic models
2. **Week 3-4:** Implement SessionManager with save/load/list
3. **Week 5-6:** Add session replay functionality
4. **Week 7-8:** Build session analytics and reporting
5. **Week 9-10:** Create CLI commands for session management
6. **Week 11-12:** Add session sharing and export (markdown, HTML)

**Benefits:**
- Resume work from any point
- Analyze development patterns
- Share sessions with team
- Audit trail for debugging
- Learning resource (replay sessions)

---

### Direction 5: **MCP (Model Context Protocol) Integration** 🔌

**Vision:** Implement MCP protocol to enable standardized tool integration and multi-provider support.

**Core Concept:** Adopt the Model Context Protocol for tool definitions, enabling interoperability with other MCP-compatible systems.

**Concrete Implementation:**

#### 5.1 MCP Server
```python
# src/ecrivez/mcp/server.py
from mcp import MCPServer, Tool, Resource

class EcrivezMCPServer(MCPServer):
    """MCP server exposing Ecrivez tools."""
    
    def __init__(self, project_root: Path):
        super().__init__(name="ecrivez", version="0.1.0")
        self.project_root = project_root
        self.register_tools()
        self.register_resources()
    
    def register_tools(self):
        """Register available tools."""
        self.add_tool(Tool(
            name="read_file",
            description="Read contents of a file",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            },
            handler=self.read_file
        ))
        
        self.add_tool(Tool(
            name="write_file",
            description="Write contents to a file",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            },
            handler=self.write_file
        ))
    
    def register_resources(self):
        """Register accessible resources."""
        # Expose project structure
        self.add_resource(Resource(
            uri=f"file://{self.project_root}",
            name="Project Root",
            description="Project source code",
            mime_type="application/x-directory"
        ))
```

#### 5.2 MCP Client
```python
# src/ecrivez/mcp/client.py
from mcp import MCPClient

class EcrivezMCPClient:
    """Client for connecting to MCP servers."""
    
    def __init__(self):
        self.servers = {}
    
    def connect_to_server(self, server_url: str, name: str):
        """Connect to an MCP server."""
        client = MCPClient(server_url)
        tools = client.list_tools()
        resources = client.list_resources()
        
        self.servers[name] = {
            "client": client,
            "tools": tools,
            "resources": resources
        }
    
    def call_tool(self, server_name: str, tool_name: str, **kwargs):
        """Call a tool on a connected server."""
        server = self.servers[server_name]
        result = server["client"].call_tool(tool_name, kwargs)
        return result
```

#### 5.3 MCP Configuration
```yaml
# .ecrivez/mcp.yaml
servers:
  - name: filesystem
    url: http://localhost:8080/mcp
    tools:
      - read_file
      - write_file
      - list_directory
  
  - name: github
    url: http://localhost:8081/mcp
    tools:
      - create_issue
      - create_pr
      - list_repos
  
  - name: browser
    url: http://localhost:8082/mcp
    tools:
      - navigate
      - click
      - screenshot
```

#### 5.4 LLM Integration
```python
# src/ecrivez/mcp/llm_integration.py
class MCPEnabledChat:
    """Chat with MCP tool calling support."""
    
    def __init__(self, provider: BaseProvider, mcp_client: EcrivezMCPClient):
        self.provider = provider
        self.mcp = mcp_client
    
    def chat(self, message: str, history: List[Message]) -> str:
        # Get available tools from all connected servers
        available_tools = self._get_all_tools()
        
        # Include tools in system prompt
        system_prompt = self._build_system_prompt(available_tools)
        history.insert(0, {"role": "system", "content": system_prompt})
        
        # Get LLM response with tool calls
        response = self.provider.chat_completion(history)
        
        # Check if response contains tool calls
        tool_calls = self._extract_tool_calls(response)
        
        # Execute tool calls via MCP
        for tool_call in tool_calls:
            result = self.mcp.call_tool(
                server_name=tool_call.server,
                tool_name=tool_call.name,
                **tool_call.arguments
            )
            # Append result to history and continue conversation
            history.append({"role": "tool", "content": result})
        
        return response
```

#### 5.5 Implementation Steps
1. **Week 1-2:** Study MCP protocol specification
2. **Week 3-4:** Implement basic MCP server with file tools
3. **Week 5-6:** Build MCP client and connection manager
4. **Week 7-8:** Integrate MCP tools with LLM chat system
5. **Week 9-10:** Create MCP tool adapters for existing tools
6. **Week 11-12:** Add support for custom MCP servers (plugins)

**Benefits:**
- Standardized tool integration
- Interoperability with other MCP systems
- Easy plugin development
- Multi-provider support

---

## Recommended Prioritization

### Phase 1: Foundation (Months 1-3)
**Priority: Complete existing roadmap milestones**

1. ✅ Fix session persistence (`_load_history` implementation)
2. ✅ Improve diff application (proper unified diff parsing)
3. ✅ Complete remaining roadmap milestones
4. Create comprehensive test suite
5. Set up CI/CD pipeline

**Rationale:** Stabilize core functionality before adding new features.

### Phase 2: Enhanced Capabilities (Months 4-6)
**Priority: Direction 1 (Agentic Workflow) + Direction 4 (Session Management)**

Combine these for maximum impact:
- Implement agent framework with smolagents
- Build robust session persistence system
- Create basic tool ecosystem
- Add workflow definitions

**Rationale:** These provide the most value with existing codebase. Sessions enable learning from history, agents enable autonomy.

### Phase 3: Intelligence Layer (Months 7-9)
**Priority: Direction 2 (RAG Enhancement)**

- Implement vector database indexing
- Add semantic code search
- Create context-aware chat
- Build incremental indexing system

**Rationale:** RAG enhances agent capabilities and scales to large codebases.

### Phase 4: Integration & UX (Months 10-12)
**Priority: Direction 3 (Multi-Modal UI) or Direction 5 (MCP)**

Choose based on target audience:
- **Direction 3** if targeting developers who want IDE-like experience
- **Direction 5** if targeting integration with existing tooling ecosystem

**Rationale:** These are polish and ecosystem plays, best done after core capabilities are solid.

---

## Technical Recommendations

### Immediate Actions (Next 2 Weeks)

1. **Fix Critical Bugs:**
   ```python
   # src/ecrivez/chat.py - Add missing function
   def _load_history(session_id: str) -> List[Message]:
       """Load conversation history from disk."""
       sessions_dir = Path(".ecrivez") / "sessions"
       session_file = sessions_dir / f"{session_id}.jsonl"
       
       if not session_file.exists():
           return []
       
       history = []
       with session_file.open() as fh:
           for line in fh:
               history.append(json.loads(line))
       return history
   
   # Fix _save_history signature
   def _save_history(history: List[Message], session_id: str) -> None:
       sessions_dir = Path(".ecrivez") / "sessions"
       sessions_dir.mkdir(exist_ok=True)
       out_file = sessions_dir / f"{session_id}.jsonl"
       
       with out_file.open("w") as fh:
           for item in history:
               json.dump(item, fh, ensure_ascii=False)
               fh.write("\n")
   ```

2. **Improve Diff Application:**
   ```python
   # Replace naive diff parsing with unidiff library
   from unidiff import PatchSet
   
   def apply_diff(nvim, diff: str) -> None:
       """Apply a proper unified diff to the current buffer."""
       patch = PatchSet(diff)
       
       for patched_file in patch:
           if patched_file.is_modified_file:
               buf = list(nvim.current.buffer)
               
               for hunk in patched_file:
                   buf = self._apply_hunk(buf, hunk)
               
               nvim.current.buffer[:] = buf
               nvim.command("write")
   ```

3. **Add Integration Tests:**
   ```python
   # tests/test_integration.py
   def test_full_workflow(tmp_path):
       """Test complete init -> chat -> save workflow."""
       # Init project
       os.chdir(tmp_path)
       init_project(model="gpt-4o", name="test_project")
       
       # Start REPL
       # ... test complete user flow
   ```

### Code Quality Improvements

1. **Add Type Stubs for Third-Party Libraries:**
   ```toml
   [dependency-groups]
   dev = [
       "types-PyYAML",
       "types-click",
       # ...
   ]
   ```

2. **Enable Strict Type Checking:**
   ```toml
   [tool.mypy]
   strict = true
   warn_return_any = true
   warn_unused_configs = true
   ```

3. **Add Pre-commit Hooks:**
   ```yaml
   # .pre-commit-config.yaml
   repos:
     - repo: https://github.com/astral-sh/ruff-pre-commit
       rev: v0.4.0
       hooks:
         - id: ruff
         - id: ruff-format
     - repo: https://github.com/pre-commit/mirrors-mypy
       rev: v1.10.0
       hooks:
         - id: mypy
   ```

### Architecture Decisions

1. **Plugin System:** Use entry points for tool plugins
   ```python
   # pyproject.toml
   [project.entry-points."ecrivez.tools"]
   shell = "ecrivez.tools:run_shell"
   ```

2. **Event System:** Implement pub/sub for loose coupling
   ```python
   from typing import Callable, Dict, List
   
   class EventBus:
       def __init__(self):
           self.listeners: Dict[str, List[Callable]] = {}
       
       def emit(self, event: str, data: Any):
           for listener in self.listeners.get(event, []):
               listener(data)
   ```

3. **Configuration Layers:** Support multiple config sources
   ```python
   class ConfigLoader:
       def load(self) -> Configuration:
           # 1. Load defaults
           # 2. Load user config (~/.config/ecrivez/config.toml)
           # 3. Load project config (.ecrivez/config.yaml)
           # 4. Load environment variables
           # 5. Merge with precedence
   ```

---

## Competitive Analysis

### Comparison with Similar Tools

| Feature | Ecrivez | Cursor | Aider | Continue.dev |
|---------|---------|--------|-------|--------------|
| Terminal-based | ✅ | ❌ | ✅ | ❌ |
| Agent framework | 🚧 | ✅ | ✅ | ❌ |
| Editor integration | Neovim | VSCode | Any | VSCode |
| RAG support | 🚧 | ✅ | ❌ | ✅ |
| Open source | ✅ | ❌ | ✅ | ✅ |
| Workflow automation | 🚧 | ✅ | ❌ | ❌ |

**Differentiation Opportunities:**
1. **Terminal-first with advanced workflows** (vs Cursor's GUI-only)
2. **Transparent agent reasoning** (vs Aider's simpler tool use)
3. **Extensible plugin system** (vs Continue's VSCode lock-in)
4. **Session replay and learning** (unique feature)

---

## Risk Assessment

### Technical Risks

1. **Dependency on External LLM APIs**
   - *Mitigation:* Support multiple providers (OpenAI, Anthropic, local models)
   - *Fallback:* Ollama integration for local inference

2. **Complexity Creep**
   - *Mitigation:* Keep core small, use plugins for extensions
   - *Monitoring:* Track LOC, maintain <5000 for core

3. **Neovim Socket Reliability**
   - *Mitigation:* Add retry logic, better error messages
   - *Alternative:* Support other editors via LSP

### Product Risks

1. **User Adoption in Crowded Space**
   - *Mitigation:* Focus on unique value props (terminal, agents, sessions)
   - *Strategy:* Target Neovim/terminal power users initially

2. **Maintaining Feature Parity**
   - *Mitigation:* Don't compete on features, compete on philosophy
   - *Focus:* Transparency, control, extensibility

---

## Success Metrics

### Technical Metrics
- Test coverage > 80%
- Type checking coverage 100%
- CI build time < 5 minutes
- Response time < 2 seconds for chat

### Product Metrics
- Active users per month
- Session completion rate
- Average session duration
- Tool usage distribution
- Code changes per session

### Community Metrics
- GitHub stars
- Contributors
- Plugin ecosystem size
- Documentation completeness

---

## Conclusion

Ecrivez has a solid foundation with clean architecture and modern Python practices. The project should:

1. **Short term (0-3 months):** Complete roadmap milestones, fix bugs, stabilize core
2. **Medium term (3-9 months):** Implement agentic workflows + session management + RAG
3. **Long term (9-12 months):** Polish UX (Qt or terminal TUI) and ecosystem (MCP)

The recommended path prioritizes **Direction 1 (Agents)** and **Direction 4 (Sessions)** because they:
- Leverage existing code (smolagents dependency, session stubs)
- Provide unique value in crowded market
- Enable other directions (agents benefit from RAG, sessions enable learning)
- Align with project vision of autonomous coding assistant

**Next Steps:**
1. Review and approve this exploration document
2. Create detailed implementation spec for chosen direction
3. Break down into 2-week sprints
4. Start with bug fixes and roadmap completion
5. Iterate based on user feedback

---

*Document created: 2025-10-23*
*Author: Copilot (GitHub AI Assistant)*
*Status: Draft for Review*
