#!/usr/bin/env python3
"""
LLM Tool Executor
Enables LLM models (Ollama, NVIDIA, etc.) to use tools like file operations, web search, and bash commands.
"""

import json
import sys
import subprocess
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.parse


class OllamaToolExecutor:
    def __init__(self, model: str = "gemma4:e4b", base_url: str = "http://localhost:11434", api_key: str = "", api_url: str = None):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        # Use provided api_url or construct it from base_url
        self.api_url = api_url if api_url else f"{base_url}/v1/chat/completions"
        self.messages: List[Dict[str, Any]] = []
        self.max_turns = 10  # Prevent infinite loops
        self.is_claude = "anthropic.com" in self.api_url

    def get_tools(self) -> List[Dict[str, Any]]:
        """Define available tools for the model."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file. Returns the file content as string.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to the file to read"
                            }
                        },
                        "required": ["file_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file. Creates the file if it doesn't exist.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to the file to write"
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to write to the file"
                            }
                        },
                        "required": ["file_path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in a directory. Returns a list of filenames.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "description": "Directory path to list files from"
                            },
                            "pattern": {
                                "type": "string",
                                "description": "Optional glob pattern to filter files (e.g., '*.py')"
                            }
                        },
                        "required": ["directory"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web using DuckDuckGo. Returns search results.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "num_results": {
                                "type": "integer",
                                "description": "Number of results to return (default: 5)"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "bash_command",
                    "description": "Execute a bash command and return its output. Use with caution!",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The bash command to execute"
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "description": "Fetch content from a URL. Returns the response body as text.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The URL to fetch"
                            }
                        },
                        "required": ["url"]
                    }
                }
            }
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool and return the result."""
        try:
            if tool_name == "read_file":
                return self._read_file(arguments["file_path"])
            elif tool_name == "write_file":
                return self._write_file(arguments["file_path"], arguments["content"])
            elif tool_name == "list_files":
                return self._list_files(
                    arguments["directory"],
                    arguments.get("pattern")
                )
            elif tool_name == "web_search":
                return self._web_search(
                    arguments["query"],
                    arguments.get("num_results", 5)
                )
            elif tool_name == "bash_command":
                return self._bash_command(arguments["command"])
            elif tool_name == "fetch_url":
                return self._fetch_url(arguments["url"])
            else:
                return f"Error: Unknown tool '{tool_name}'"
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    def _read_file(self, file_path: str) -> str:
        """Read file contents."""
        path = Path(file_path).expanduser()
        if not path.exists():
            return f"Error: File not found: {file_path}"
        try:
            content = path.read_text()
            return f"File content of {file_path}:\n{content}"
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def _write_file(self, file_path: str, content: str) -> str:
        """Write content to file."""
        path = Path(file_path).expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return f"Successfully wrote {len(content)} characters to {file_path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    def _list_files(self, directory: str, pattern: Optional[str] = None) -> str:
        """List files in directory."""
        path = Path(directory).expanduser()
        if not path.exists():
            return f"Error: Directory not found: {directory}"
        if not path.is_dir():
            return f"Error: Not a directory: {directory}"

        try:
            if pattern:
                files = list(path.glob(pattern))
            else:
                files = list(path.iterdir())

            files_list = [str(f.relative_to(path)) for f in sorted(files)]
            return f"Files in {directory}:\n" + "\n".join(files_list)
        except Exception as e:
            return f"Error listing files: {str(e)}"

    def _web_search(self, query: str, num_results: int = 5) -> str:
        """Search the web using DuckDuckGo HTML."""
        try:
            # Simple DuckDuckGo HTML scraping
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0"}

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')

            # Basic parsing - extract result snippets
            results = []
            lines = html.split('\n')
            for i, line in enumerate(lines):
                if 'result__title' in line and len(results) < num_results:
                    # Extract title and URL (very basic parsing)
                    title_start = line.find('>') + 1
                    title_end = line.find('</a>')
                    if title_start > 0 and title_end > 0:
                        title = line[title_start:title_end].strip()
                        # Look for snippet in next lines
                        snippet = ""
                        for j in range(i+1, min(i+10, len(lines))):
                            if 'result__snippet' in lines[j]:
                                snippet_start = lines[j].find('>') + 1
                                snippet_end = lines[j].find('</a>')
                                if snippet_start > 0:
                                    snippet = lines[j][snippet_start:snippet_end].strip()
                                break

                        if title:
                            results.append(f"{len(results)+1}. {title}\n   {snippet}")

            if results:
                return f"Search results for '{query}':\n\n" + "\n\n".join(results)
            else:
                return f"No results found for '{query}'"

        except Exception as e:
            return f"Web search error: {str(e)}"

    def _bash_command(self, command: str) -> str:
        """Execute bash command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            return f"Command output:\n{output}"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out (30s limit)"
        except Exception as e:
            return f"Error executing command: {str(e)}"

    def _fetch_url(self, url: str) -> str:
        """Fetch content from URL."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8')
                # Limit content size
                if len(content) > 10000:
                    content = content[:10000] + "\n... (truncated)"
                return f"Content from {url}:\n{content}"
        except Exception as e:
            return f"Error fetching URL: {str(e)}"

    def call_ollama(self, messages: List[Dict], tools: List[Dict]) -> Dict:
        """Call LLM API (Ollama, NVIDIA, OpenAI, Claude)."""
        if self.is_claude:
            # Claude API format
            # Extract system message and clean messages for Claude
            system_msg = ""
            claude_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    # Clean message: only keep role and content (remove ts, etc.)
                    cleaned = {
                        "role": msg["role"],
                        "content": msg["content"]
                    }
                    claude_messages.append(cleaned)

            # Claude requires the last message to be from "user"
            if claude_messages and claude_messages[-1]["role"] != "user":
                # This shouldn't happen in normal flow, but log it for debugging
                print(f"WARNING: Last message is not 'user' (it's '{claude_messages[-1]['role']}')", file=sys.stderr)
                print(f"Messages: {[m['role'] for m in claude_messages]}", file=sys.stderr)

            # Convert tools to Claude format
            claude_tools = []
            for tool in tools:
                func = tool["function"]
                claude_tools.append({
                    "name": func["name"],
                    "description": func["description"],
                    "input_schema": func["parameters"]
                })

            data = {
                "model": self.model,
                "messages": claude_messages,
                "tools": claude_tools,
                "max_tokens": 4096
            }
            if system_msg:
                data["system"] = system_msg

            headers = {
                'Content-Type': 'application/json',
                'x-api-key': self.api_key,
                'anthropic-version': '2023-06-01'
            }
        else:
            # OpenAI-compatible format (Ollama, NVIDIA, OpenAI)
            data = {
                "model": self.model,
                "messages": messages,
                "tools": tools
            }

            headers = {'Content-Type': 'application/json'}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'

        # Debug: Log the request for OpenClaw
        if "openclaw" in self.api_url or "18789" in self.api_url:
            self.emit_progress({"type": "debug", "message": f"Sending request to {self.api_url}"})
            self.emit_progress({"type": "debug", "message": f"Request model: {data.get('model')}"})
            self.emit_progress({"type": "debug", "message": f"Tools in request: {len(data.get('tools', []))}"})
            self.emit_progress({"type": "debug", "message": f"Messages in request: {len(data.get('messages', []))}"})
            if len(data.get('tools', [])) > 0:
                tool_names = [t['function']['name'] for t in data.get('tools', [])]
                self.emit_progress({"type": "debug", "message": f"Tool names: {', '.join(tool_names)}"})
            self.emit_progress({"type": "debug", "message": f"Has Authorization: {'Authorization' in headers}"})

        req = urllib.request.Request(
            self.api_url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode('utf-8'))

                # Debug: Log OpenClaw response
                if "openclaw" in self.api_url or "18789" in self.api_url:
                    self.emit_progress({"type": "debug", "message": "Response received from OpenClaw"})
                    if "choices" in result and len(result["choices"]) > 0:
                        msg = result["choices"][0].get("message", {})
                        finish_reason = result['choices'][0].get('finish_reason')
                        self.emit_progress({"type": "debug", "message": f"finish_reason: {finish_reason}"})
                        self.emit_progress({"type": "debug", "message": f"Has tool_calls: {('tool_calls' in msg)}"})
                        if "tool_calls" in msg:
                            self.emit_progress({"type": "debug", "message": f"Tool calls: {len(msg['tool_calls'])}"})
                        else:
                            # No tool calls - show content preview
                            content = msg.get("content", "")[:100]
                            self.emit_progress({"type": "debug", "message": f"Content (no tools): {content}..."})

                # For Claude: return both original and converted
                if self.is_claude:
                    converted = self._convert_claude_to_openai(result)
                    # Add the original Claude content to the converted response
                    # so we can save it for the next request
                    converted["_claude_original_content"] = result.get("content", [])
                    return converted
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            # Try to pretty-print error if it's JSON
            try:
                error_json = json.loads(error_body)
                error_formatted = json.dumps(error_json, indent=2)
            except:
                error_formatted = error_body

            # Log the request for debugging
            print(f"DEBUG: Request to {self.api_url}", file=sys.stderr)
            print(f"DEBUG: Full request data:\n{json.dumps(data, indent=2)}", file=sys.stderr)
            print(f"DEBUG: Full error:\n{error_formatted}", file=sys.stderr)

            raise Exception(f"HTTP Error {e.code}: {e.reason}\n{error_formatted}")

    def _convert_claude_to_openai(self, claude_response: Dict) -> Dict:
        """Convert Claude API response to OpenAI format."""
        content = claude_response.get("content", [])

        # Build message content and tool calls
        text_content = ""
        tool_calls = []

        for block in content:
            if block.get("type") == "text":
                text_content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(block.get("input", {}))
                    }
                })

        # Determine finish reason
        stop_reason = claude_response.get("stop_reason")
        if stop_reason == "tool_use":
            finish_reason = "tool_calls"
        elif stop_reason == "end_turn":
            finish_reason = "stop"
        else:
            finish_reason = stop_reason or "stop"

        # Build OpenAI-compatible response
        message = {
            "role": "assistant",
            "content": text_content or None
        }
        if tool_calls:
            message["tool_calls"] = tool_calls

        return {
            "choices": [{
                "message": message,
                "finish_reason": finish_reason
            }]
        }

    def emit_progress(self, data: Dict[str, Any]):
        """Emit live progress update (streaming to QML)."""
        print(json.dumps(data, ensure_ascii=False), flush=True)
        sys.stdout.flush()

    def run(self, user_message: str = None, messages: List[Dict] = None, language: str = "de") -> Dict[str, Any]:
        """
        Run the tool executor with either a user message or a full message history.
        Returns a dict with the final response and metadata.

        Args:
            user_message: Single user message (for CLI usage)
            messages: Full message history from chat UI (for multi-turn context)
            language: UI language code (de/en)
        """
        # Debug: Log execution start (to stdout for immediate visibility)
        self.emit_progress({"type": "debug", "message": f"OllamaToolExecutor.run() started"})
        self.emit_progress({"type": "debug", "message": f"API URL: {self.api_url}"})
        self.emit_progress({"type": "debug", "message": f"Model: {self.model}"})
        self.emit_progress({"type": "debug", "message": f"Is Claude: {self.is_claude}"})

        # Direct system prompt: Be clear that tools MUST be used
        lang_instruction = "WICHTIG: Antworte IMMER auf Deutsch." if language == "de" else "IMPORTANT: Always respond in English."

        system_prompt = f"""You are an AI assistant with access to tools that execute on the user's HOST computer.

{lang_instruction}

TOOL USAGE GUIDELINES:
The tools provided (bash_command, read_file, write_file, list_files, web_search, fetch_url) execute on the USER'S HOST SYSTEM, not in your environment.

USE THESE HOST-SYSTEM TOOLS ONLY when the user asks about:
• Their computer state (open windows, running processes, system info)
• Files on THEIR filesystem (reading, writing, listing their actual files)
• System commands (windoesnot-hyprctl, systemctl, ps, etc. on THEIR machine)

EXAMPLE - User asks "What windows are open?":
→ Use bash_command("windoesnot-hyprctl clients") - this runs on THEIR computer
→ Analyze the output and answer

EXAMPLE - User asks "Explain how Python decorators work":
→ Just answer directly, no tools needed
→ Only use tools if they ask you to create/read actual files on their system

CRITICAL:
- bash_command, read_file, write_file, list_files → Execute on USER'S HOST computer
- Use these tools ONLY when necessary for accessing the user's actual system
- For general questions, explanations, or information not specific to their computer → answer directly
- NEVER say "I don't have access" for system queries - you DO have access via these tools

Be thoughtful: only use HOST tools when the task requires accessing the user's actual computer."""

        # Build initial messages
        if messages:
            # Use provided message history (from UI)
            self.messages = [{"role": "system", "content": system_prompt}] + messages
        elif user_message:
            # Single user message (CLI mode)
            self.messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        else:
            raise ValueError("Either user_message or messages must be provided")

        tools = self.get_tools()

        conversation_log = []
        turn = 0

        while turn < self.max_turns:
            turn += 1

            # Emit: Starting LLM call
            self.emit_progress({"type": "llm_start", "turn": turn})

            # Call Ollama
            response = self.call_ollama(self.messages, tools)
            choice = response['choices'][0]
            message = choice['message']
            finish_reason = choice['finish_reason']

            # Add assistant message to conversation
            # For Claude: use original content structure (with tool_use blocks)
            if self.is_claude and "_claude_original_content" in response:
                assistant_msg = {
                    "role": "assistant",
                    "content": response["_claude_original_content"]
                }
                self.messages.append(assistant_msg)
            else:
                self.messages.append(message)

            # Log this turn
            turn_log = {
                "turn": turn,
                "finish_reason": finish_reason,
                "message": message
            }

            # If model wants to use tools
            if finish_reason == "tool_calls" and "tool_calls" in message:
                tool_results = []

                for tool_call in message["tool_calls"]:
                    func = tool_call["function"]
                    tool_name = func["name"]
                    arguments = json.loads(func["arguments"])

                    # Emit: Tool started
                    self.emit_progress({
                        "type": "tool_start",
                        "tool": tool_name,
                        "arguments": arguments
                    })

                    # Execute tool
                    result = self.execute_tool(tool_name, arguments)

                    # Emit: Tool finished
                    self.emit_progress({
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": result[:500] if len(result) > 500 else result  # Truncate for display
                    })

                    tool_results.append({
                        "tool": tool_name,
                        "arguments": arguments,
                        "result": result
                    })

                    # Add tool result to messages (format depends on API)
                    if self.is_claude:
                        # Claude format: tool results go in a user message
                        self.messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": tool_call["id"],
                                "content": result
                            }]
                        })
                    else:
                        # OpenAI format: tool results are separate messages
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": result
                        })

                turn_log["tool_calls"] = tool_results
                conversation_log.append(turn_log)

                # Continue loop to get final answer
                continue

            # Model finished - no more tool calls
            conversation_log.append(turn_log)

            # Check if model gave a response
            final_response = message.get("content", "").strip()
            if not final_response and conversation_log:
                # Model used tools but gave no answer - provide fallback
                final_response = "[No response from model - tool results available above]"

            # Emit final response (truncate conversation_log to avoid JSON size issues)
            # Only send tool_calls summary, not full results (QML already has them from live updates)
            compact_log = []
            for log_entry in conversation_log:
                compact_entry = {
                    "turn": log_entry.get("turn"),
                    "finish_reason": log_entry.get("finish_reason")
                }
                if "tool_calls" in log_entry:
                    compact_entry["tool_calls"] = [
                        {
                            "tool": tc["tool"],
                            "arguments": tc["arguments"],
                            "result": tc["result"][:200] if tc.get("result") and len(tc.get("result", "")) > 200 else tc.get("result")  # Truncate large results
                        }
                        for tc in log_entry["tool_calls"]
                    ]
                compact_log.append(compact_entry)

            self.emit_progress({
                "type": "final",
                "response": final_response,
                "reasoning": message.get("reasoning", ""),
                "turns": turn,
                "conversation_log": compact_log
            })

            return {
                "success": True,
                "response": final_response,
                "reasoning": message.get("reasoning", ""),
                "turns": turn,
                "conversation_log": compact_log
            }

        # Max turns reached
        return {
            "success": False,
            "error": "Max turns reached",
            "turns": turn,
            "conversation_log": conversation_log
        }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "success": False,
            "error": "Usage: ollama_tool_executor.py <message> [model]"
        }))
        sys.exit(1)

    message = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "gemma4:e4b"

    executor = OllamaToolExecutor(model=model)

    try:
        result = executor.run(message)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e)
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
