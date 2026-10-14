# --- CONFIGURATION ---
MODEL = 'gemma4:26b-a4b-it-qat'
SERVER_SCRIPT = "mcp2_server.py"

# No user-configs below this line
SCRIPT_VERSION = "1.0.0"
APP_NAME = "JELSTUDIO MCP AI Chatbot"
APP_TITLE = f"{APP_NAME} v{SCRIPT_VERSION} – {MODEL}"

import tkinter as tk
from tkinter import scrolledtext
import asyncio
import threading
import ollama
import sys
import os
import traceback
import re
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Thinking-tag patterns (start → end pairs)
THINK_START_PATTERNS = [r"<thought>", r"\[thought\]", r"<reasoning>", r"\[reasoning\]", r"Reasoning:"]
THINK_END_PATTERNS   = [r"</thought>", r"\[/thought\]", r"</reasoning>", r"\[/reasoning\]"]

# Buffer tail we hold back so a tag split across chunks is still caught
_HOLD_BACK = 12  # longest tag is 11 chars: "[/reasoning]"


class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("800x950")
        self.root.minsize(800, 950)

        # ── Window 1: System / Thinking log ──────────────────────────
        tk.Label(root, text="System / Thinking", font=('Arial', 8, 'bold')).pack(anchor="w", padx=5)
        self.system_log = scrolledtext.ScrolledText(
            root, height=16, state='disabled', bg="#f5f5f5", font=('Consolas', 9))
        self.system_log.pack(fill="x", padx=5, pady=2)

        # ── Window 2: Conversation ───────────────────────────────────
        tk.Label(root, text="Conversation", font=('Arial', 10, 'bold')).pack(anchor="w", padx=5)
        self.chat_display = scrolledtext.ScrolledText(
            root, state='disabled', font=('Arial', 11), wrap="word")
        self.chat_display.pack(fill="both", expand=True, padx=5, pady=2)

        # ── Metrics bar ──────────────────────────────────────────────
        self.metrics_var = tk.StringVar(value="Context: 0 tokens  |  Speed: 0.00 t/s")
        self.metrics_label = tk.Label(root, textvariable=self.metrics_var,
                                      font=('Arial', 9, 'italic'), fg="#4444aa")
        self.metrics_label.pack(pady=2)

        # ── Input area ───────────────────────────────────────────────
        self.input_frame = tk.Frame(root)
        self.input_frame.pack(fill="x", padx=5, pady=10)
        self.user_input = tk.Entry(self.input_frame, font=('Arial', 12))
        self.user_input.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.user_input.bind("<Return>", lambda e: self.on_send_click())
        self.send_btn = tk.Button(self.input_frame, text="Send", command=self.on_send_click, width=10)
        self.send_btn.pack(side="right")

        # ── State ────────────────────────────────────────────────────
        self.messages = []
        self.ollama_tools = []
        self.mcp_session = None
        self.async_queue = None
        self.loop = asyncio.new_event_loop()

        threading.Thread(target=self._start_async_loop, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────
    #  ASYNC RUNNER  (unchanged)
    # ─────────────────────────────────────────────────────────────────
    def _start_async_loop(self):
        try:
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.main_async_logic())
        except Exception:
            traceback.print_exc()

    async def main_async_logic(self):
        self.async_queue = asyncio.Queue()
        server_params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT])
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.mcp_session = session
                    await session.initialize()

                    tools_resp = await session.list_tools()
                    for tool in tools_resp.tools:
                        self.ollama_tools.append({
                            'type': 'function',
                            'function': {
                                'name': tool.name,
                                'description': tool.description,
                                'parameters': tool.input_schema,
                            }
                        })
                    self._log_sys(f"MCP Connected – tools: {', '.join(t.name for t in tools_resp.tools)}")

                    while True:
                        query = await self.async_queue.get()
                        if query is None:
                            break
                        await self.process_query_logic(query)
                        self.async_queue.task_done()
        except Exception as e:
            self._log_sys(f"CONNECTION ERROR: {e}")

    # ─────────────────────────────────────────────────────────────────
    #  UI HELPERS  (rewritten for clean visual output)
    # ─────────────────────────────────────────────────────────────────
    def _ui(self, fn, *args):
        """Thread-safe widget update."""
        self.root.after(0, fn, *args)

    def _log_sys(self, text):
        """One-line system / tool event."""
        self._ui(self._insert, self.system_log, f"  {text}\n", "#333333")

    def _log_think_header(self):
        self._ui(self._insert, self.system_log,
                  "\n" + "━" * 52 + "\n"
                  "  🧠  MODEL THINKING\n"
                  + "━" * 52 + "\n", "#2255aa")

    def _log_think_footer(self):
        self._ui(self._insert, self.system_log,
                  "\n" + "━" * 52 + "\n"
                          "  ✅  Thinking complete\n"
                          + "━" * 52 + "\n\n", "#2255aa")

    def _log_think_text(self, text):
        """Stream a piece of thinking text (no prefix, preserves newlines)."""
        if not text:
            return
        self._ui(self._insert, self.system_log, text, "#1a5fb4")
        # Ensure we scroll to the bottom so the user sees the current thought
        self.system_log.see("end")

    def _chat_user(self, text):
        # Added extra newline and Blue color (#0055aa)
        self._ui(self._insert, self.chat_display, f"\n\nYOU: {text}\n", "#0055aa")

    def _chat_bot_header(self):
        # Added extra newline to separate from user
        self._ui(self._insert, self.chat_display, "\nBot: ", "#333333")

    def _chat_text(self, text):
        # Darker text for bot response
        self._ui(self._insert, self.chat_display, text, "#222222")

    def _insert(self, widget, text, color):
        widget.configure(state='normal')
        tag = f"c_{color.replace('#','')}" # Clean tag naming
        widget.tag_configure(tag, foreground=color)
        widget.insert("end", text, tag)
        widget.see("end")
        widget.configure(state='disabled')

    def _update_metrics_ui(self, response_dict):
        try:
            p = response_dict.get('prompt_eval_count', 0)
            g = response_dict.get('eval_count', 0)
            dur = response_dict.get('eval_duration', 1) / 1e9
            speed = g / dur if dur > 0 else 0
            self._ui(lambda: self.metrics_var.set(f"Context: {p+g} tokens  |  Speed: {speed:.2f} t/s"))
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────
    #  SEND  (unchanged logic)
    # ─────────────────────────────────────────────────────────────────
    def on_send_click(self):
        query = self.user_input.get().strip()
        if not query:
            return
        self.user_input.delete(0, tk.END)
        self._chat_user(query)
        if self.async_queue:
            self.loop.call_soon_threadsafe(self.async_queue.put_nowait, query)

    # ─────────────────────────────────────────────────────────────────
    #  QUERY PROCESSING (The Manager Loop)
    # ─────────────────────────────────────────────────────────────────
    async def process_query_logic(self, query):
        self.messages.append({'role': 'user', 'content': query})
        
        # SAFETY VALVE: prevents infinite tool-call loops from freezing your app
        max_iterations = 100 
        iterations = 0
        
        try:
            while iterations < max_iterations:
                iterations += 1
                
                # Get a single response turn from the model
                result_type, result_val = await self._get_model_response()

                if result_type == "DONE":
                    # AI has finished and given a final answer. Exit loop.
                    break

                elif result_type == "ERROR":
                    self._log_sys(f"Stream error: {result_val}")
                    self._chat_bot_header()
                    self._chat_text(f"[Error] {result_val}\n")
                    break

                elif result_type == "TOOL_CALL":
                    # Process the tool calls and add them to the message history
                    tool_msg = result_val['message']
                    self.messages.append(tool_msg)
                    
                    for tc in tool_msg.get('tool_calls', []):
                        name = tc['function']['name']
                        args = tc['function']['arguments']
                        self._log_sys(f"⚙  Tool call → {name}({args})")
                        
                        try:
                            result = await self.mcp_session.call_tool(name, arguments=args)
                            tool_text = "".join(c.text for c in result.content if hasattr(c, 'text'))
                            self._log_sys(f"   ↳ returned {len(tool_text)} chars")
                            self.messages.append({'role': 'tool', 'content': tool_text})
                        except Exception as tool_e:
                            self._log_sys(f"   ❌ Tool Error: {tool_e}")
                            self.messages.append({'role': 'tool', 'content': f"Error executing tool: {str(tool_e)}"})
                    
                    # The 'while' loop will now repeat, sending the tool results 
                    # back to the model for the next turn.
            
            if iterations >= max_iterations:
                self._log_sys("⚠️  Max tool-call limit reached. Stopping to prevent infinite loop.")

        except Exception as e:
            self._log_sys(f"Logic Error: {e}")
            self._chat_bot_header()
            self._chat_text(f"[Error] {e}\n")

    # ─────────────────────────────────────────────────────────────────
    #  SINGLE RESPONSE CYCLE (The Worker)
    # ─────────────────────────────────────────────────────────────────
    async def _get_model_response(self):
        full_content = ""
        last_chunk = None

        # local state flags
        response_started = False
        think_open = False

        def open_think():
            nonlocal think_open
            if not think_open:
                _think_header()
                think_open = True

        def close_think():
            nonlocal think_open
            if think_open:
                _think_footer()
                think_open = False

        def stream_iterator():
            nonlocal full_content, last_chunk, response_started, think_open
            buf = ""
            state = 0  # 0: NORMAL, 1: THINKING (tag‑based fallback)

            try:
                for chunk in ollama.chat(model=MODEL, messages=self.messages,
                                         tools=self.ollama_tools, stream=True):
                    last_chunk = chunk
                    msg = chunk.get('message', {})

                    # ---- tool call ------------------------------------------------
                    if msg.get('tool_calls'):
                        if buf:
                            if state == 1:
                                _emit_think(buf); close_think()
                            else:
                                if not response_started: _bot_header()
                                _resp_text(buf); response_started = True
                            buf = ""
                        return ("TOOL_CALL", chunk)

                    # ---- 1) DEDICATED THINKING FIELD (Ollama thinking models) ----
                    thinking = msg.get('thinking')
                    if thinking:
                        open_think()
                        _emit_think(thinking)          # streamed live into the log
                        continue

                    # ---- 2) NORMAL CONTENT (with tag fallback) -------------------
                    content = msg.get('content', '')
                    if not content:
                        continue
                    full_content += content
                    buf += content

                    while True:
                        if state == 0:  # NORMAL
                            m = _find_first(buf, THINK_START_PATTERNS)
                            if m:
                                before, after = buf[:m.start()], buf[m.end():]
                                if before.strip():
                                    if not response_started: _bot_header()
                                    _resp_text(before); response_started = True
                                buf = after
                                state = 1
                                open_think()
                                continue
                            else:
                                safe = len(buf) - _HOLD_BACK
                                if safe > 0:
                                    if not response_started: _bot_header()
                                    _resp_text(buf[:safe]); response_started = True
                                    buf = buf[safe:]
                                break
                        else:          # THINKING (tag‑based)
                            m = _find_first(buf, THINK_END_PATTERNS)
                            if m:
                                before, after = buf[:m.start()], buf[m.end():]
                                if before.strip(): _emit_think(before)
                                buf = after
                                state = 0
                                close_think()
                                continue
                            else:
                                safe = len(buf) - _HOLD_BACK
                                if safe > 0:
                                    _emit_think(buf[:safe]); buf = buf[safe:]
                                break

                # ---- flush leftovers ---------------------------------------------
                if buf:
                    if state == 1:
                        _emit_think(buf); close_think()
                    else:
                        if not response_started: _bot_header()
                        _resp_text(buf); response_started = True
                close_think()
                return ("DONE", full_content)

            except Exception as e:
                close_think()
                return ("ERROR", str(e))

        def _bot_header(): self._chat_bot_header()
        def _resp_text(t): self._chat_text(t)
        def _think_header(): self._log_think_header()
        def _think_footer(): self._log_think_footer()
        def _emit_think(t): self._log_think_text(t)

        result_type, result_val = await asyncio.to_thread(stream_iterator)

        if result_type == "DONE":
            self.messages.append({'role': 'assistant', 'content': result_val})
            if last_chunk:
                self._update_metrics_ui(last_chunk)

        return result_type, result_val

    # ─────────────────────────────────────────────────────────────────
    #  TAG SEARCH HELPER
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _noop():
        pass


def _find_first(text, patterns):
    """Return the earliest match among *patterns* in *text*, or None."""
    best = None
    for pat in patterns:
        m = re.search(pat, text)
        if m and (best is None or m.start() < best.start()):
            best = m
    return best


if __name__ == "__main__":
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()
