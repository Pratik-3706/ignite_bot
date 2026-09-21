import json
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable
from openai import AsyncOpenAI
from src.config import AICREDITS_API_KEY, AICREDITS_BASE_URL, AI_MODEL
from src.utils.tools.web_search import search_web
from src.utils.tools.pdf_maker import create_pdf_document
from src.utils.memory.memory import memory_manager

logger = logging.getLogger("ignite_bot.ai")

_async_client: Optional[AsyncOpenAI] = None

def get_ai_client() -> Optional[AsyncOpenAI]:
    global _async_client
    if _async_client is None and AICREDITS_API_KEY:
        _async_client = AsyncOpenAI(
            base_url=AICREDITS_BASE_URL,
            api_key=AICREDITS_API_KEY
        )
    return _async_client

AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the live web using Tavily for current news, facts, technical guides, or real-time info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_pdf",
            "description": "Generate a PDF document from text content and save it to media for sending.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The title of the document."},
                    "body_text": {"type": "string", "description": "Detailed text content for the PDF."}
                },
                "required": ["title", "body_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_user_fact",
            "description": "Remember a specific detail or preference about a user by their user ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Discord user ID number."},
                    "key": {"type": "string", "description": "Fact label (e.g. project, skills, timezone)."},
                    "value": {"type": "string", "description": "Fact content to remember."}
                },
                "required": ["user_id", "key", "value"]
            }
        }
    }
]

def build_system_prompt(club_memories: Dict[str, str], user_facts: Dict[str, str]) -> str:
    prompt_lines = [
        "You are Ignite Bot, the AI assistant for the Ignite Club.",
        "Tone: Friendly, concise, helpful, and technically capable.",
        "",
        "CRITICAL INSTRUCTIONS FOR MULTI-USER CONVERSATIONS:",
        "1. Every user message is labeled with canonical metadata: [User ID: <id> | Name: <display_name> (@<username>)].",
        "2. Always track who is speaking using their User ID. Never confuse statements made by one member with another.",
        "3. You may converse with multiple people concurrently in the same channel or thread without confusing their roles or contexts.",
        "4. Address users by their display name naturally."
    ]

    if club_memories:
        prompt_lines.append("\nIGNITE CLUB KNOWLEDGE BASE:")
        for k, v in club_memories.items():
            prompt_lines.append(f"- {k}: {v}")

    if user_facts:
        prompt_lines.append("\nKNOWN FACTS ABOUT THE CURRENT USER:")
        for k, v in user_facts.items():
            prompt_lines.append(f"- {k}: {v}")

    return "\n".join(prompt_lines)

async def ask_ai(
    channel_id: int | str,
    guild_id: Optional[int | str],
    user_id: int | str,
    user_name: str,
    prompt: str,
    image_url_or_data: Optional[str] = None,
    status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    allow_tools: bool = True
) -> Dict[str, Any]:
    client = get_ai_client()
    if not client:
        return {
            "text": "AICREDITS_API_KEY is not configured in `.env`. Please add your API key to enable AI features.",
            "pdf_path": None
        }

    # Fetch rolling channel history
    history = await memory_manager.get_channel_history(channel_id, limit=12)
    user_facts = await memory_manager.get_user_facts(user_id)
    club_memories = await memory_manager.get_club_memories(guild_id) if guild_id else {}

    system_prompt = build_system_prompt(club_memories, user_facts)
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)

    # Format current user message
    formatted_author = f"[User ID: {user_id} | Name: {user_name}]"
    if image_url_or_data:
        current_msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": f"{formatted_author}: {prompt}"},
                {"type": "image_url", "image_url": {"url": image_url_or_data}}
            ]
        }
    else:
        current_msg = {
            "role": "user",
            "content": f"{formatted_author}: {prompt}"
        }
    messages.append(current_msg)

    generated_pdf_path = None
    tools_param = AVAILABLE_TOOLS if allow_tools else None

    try:
        # First turn to check for tool calls or direct answer
        response = await client.chat.completions.create(
            model=AI_MODEL,
            messages=messages,
            tools=tools_param,
            tool_choice="auto" if tools_param else None
        )

        response_message = response.choices[0].message
        tool_calls = getattr(response_message, "tool_calls", None)

        if tool_calls:
            # Add assistant's tool call message to history
            messages.append(response_message.model_dump())

            for tc in tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)

                if status_callback:
                    await status_callback(f"⚙️ Running {fn_name}...")

                tool_result_content = ""
                if fn_name == "search_web":
                    query = fn_args.get("query", "")
                    tool_result_content = await search_web(query)
                elif fn_name == "create_pdf":
                    title = fn_args.get("title", "Document")
                    body = fn_args.get("body_text", "")
                    pdf_file = await create_pdf_document(title, body)
                    generated_pdf_path = pdf_file
                    tool_result_content = f"PDF created successfully at {pdf_file.name}."
                elif fn_name == "save_user_fact":
                    uid = fn_args.get("user_id", str(user_id))
                    f_key = fn_args.get("key", "")
                    f_val = fn_args.get("value", "")
                    await memory_manager.set_user_fact(uid, f_key, f_val)
                    tool_result_content = f"Saved fact '{f_key}: {f_val}' for user {uid}."

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result_content
                })

            # Get final answer after tool executions
            final_resp = await client.chat.completions.create(
                model=AI_MODEL,
                messages=messages
            )
            final_text = final_resp.choices[0].message.content or ""
        else:
            final_text = response_message.content or ""

        # Store in channel memory
        await memory_manager.add_message(channel_id, guild_id, user_id, user_name, "user", prompt)
        await memory_manager.add_message(channel_id, guild_id, "ignite_bot", "Ignite Bot", "assistant", final_text)

        return {
            "text": final_text,
            "pdf_path": generated_pdf_path
        }

    except Exception as e:
        logger.exception("Error during AI execution")
        return {
            "text": f"Error contacting AI service: {str(e)}",
            "pdf_path": None
        }
