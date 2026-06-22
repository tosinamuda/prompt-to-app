"""A2A agent: an ADK LlmAgent wired to our MCP tools, served over the A2A protocol.

Same shape as mcp-apps-demo's service agent, but with in-memory stores (no Postgres).
The browser host talks to this agent with the official @a2a-js/sdk client; the agent
calls the `compile_prompt` MCP tool, whose result carries the generated-app UI resource.
"""

from __future__ import annotations

import os

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryPushNotificationConfigStore, InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.agents import LlmAgent
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import (
    InMemoryCredentialService,
)
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from starlette.applications import Starlette

from prompt2app.settings import Settings, get_settings

APP_NAME = "prompt2app_compiler"

AGENT_INSTRUCTION = """
You are Prompt2App, an assistant that turns natural-language prompts into reusable,
typed mini-applications.

When the user gives you a task, request, or prompt that they want to reuse or fill in
later (for example: "write a supplier email", "draft a GitHub issue", "create a
deployment request"), call the `compile_prompt` tool with their prompt. The tool
returns a generated app UI that the user can fill in and run.

After an app is compiled you may, when the user explicitly asks, call `get_app`,
`set_app_input`, `run_app`, or `optimize_inducer`. If the user just asks a question or
chats, answer briefly in plain language and do not call a tool. Keep replies concise.
""".strip()


def mcp_server_url(settings: Settings) -> str:
    if settings.mcp_server_url:
        return settings.mcp_server_url
    return f"{settings.app_base_url.rstrip('/')}/mcp/"


def build_agent(settings: Settings | None = None) -> LlmAgent:
    settings = settings or get_settings()
    if settings.openrouter_api_key:
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=mcp_server_url(settings),
            timeout=settings.a2a_timeout_seconds,
        )
    )
    return LlmAgent(
        name=APP_NAME,
        description="Compiles natural-language prompts into reusable, typed apps via MCP tools.",
        model=LiteLlm(
            settings.agent_model,
            timeout=settings.a2a_timeout_seconds,
            drop_params=True,
            api_key=settings.openrouter_api_key or None,
        ),
        instruction=AGENT_INSTRUCTION,
        tools=[toolset],
    )


def build_runner(agent: LlmAgent) -> Runner:
    return Runner(
        app_name=APP_NAME,
        agent=agent,
        artifact_service=InMemoryArtifactService(),
        session_service=InMemorySessionService(),
        memory_service=InMemoryMemoryService(),
        credential_service=InMemoryCredentialService(),
    )


def build_agent_card(settings: Settings) -> AgentCard:
    return AgentCard(
        name="Prompt2App Compiler",
        description=(
            "Turns natural-language prompts into reusable, typed apps and opens an "
            "interactive generated UI to fill in and run them."
        ),
        # Relative + trailing slash: the JSON-RPC endpoint is mounted at /a2a/ (the
        # sub-app's "/" route). Advertising "/a2a" would make clients POST to /a2a
        # and hit a 307 mount redirect; the trailing slash points straight at it.
        url="/a2a/",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=True, stateTransitionHistory=True),
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain", "application/json"],
        skills=[
            AgentSkill(
                id="prompt_to_app",
                name="Prompt to App",
                description=(
                    "Compile a prompt into a typed, reusable app with a generated UI; "
                    "then fill, run, and optimize it."
                ),
                tags=["prompt-compiler", "dspy", "mcp-apps", "generative-ui"],
                examples=[
                    "Write a polite supplier email asking for a revised quote",
                    "Draft a GitHub issue for a login bug, priority high",
                    "Create a Kubernetes deployment request for a Node.js service",
                ],
            )
        ],
    )


def build_a2a_app(settings: Settings | None = None) -> Starlette:
    settings = settings or get_settings()
    runner = build_runner(build_agent(settings))
    request_handler = DefaultRequestHandler(
        agent_executor=A2aAgentExecutor(runner=runner),
        task_store=InMemoryTaskStore(),
        push_config_store=InMemoryPushNotificationConfigStore(),
    )
    a2a_app = A2AStarletteApplication(
        agent_card=build_agent_card(settings),
        http_handler=request_handler,
    )
    starlette_app = Starlette()
    a2a_app.add_routes_to_app(starlette_app)
    return starlette_app
