# JELSTUDIO MCP AI Chatbot/Agent

An AI-powered chatbot interface equipped with **Model Context Protocol (MCP)** capabilities. This tool allows a local Large Language Model (via Ollama) to interact with, browse, and audit local files inside a sandboxed folder (It does NOT have internet-connection and it can NOT start/run programs or execute dangerous file-system commands)

The design-philosophy of this agent-harness is to keep things simple and as safe as possible and avoid use of engines such as node.js etc.

It's aimed at "beginners" who want to get a taste of what it is like to run an AI-agent but don't yet feel comfortable/ready to install and run the "big" systems, and for this reason this agent is very limited in what it can do. In some ways you can consider this a "trainer-agent" for those of us who are still "student-drivers" when it comes to AI-agentic use :)

The python-scripts are coded/checked/refined with the help of AI.

## Features

*   **GUI-based Chat Interface**: A clean Tkinter-based desktop application for seamless interaction with your AI.
*   **MCP Tool Integration**: The agent is not just a chatbot; it can use tools to:
    *   `list_files`: View all files in the sandbox.
    *   `get_project_structure`: Generate a visual tree of the repository.
    *   `search_in_files`: Perform keyword searches across multiple files.
    *   `read_file`: Read specific file contents (with size limits).
    *   `write_file`: Create or update files in the sandbox.
*   **Secure Sandboxing**: All file operations are restricted to a designated directory with strict extension filtering and size limits to prevent accidental system-wide damage.
*   **Real-time Thinking Logs**: Visualizes the model's reasoning process (for models that support `<thought>` or reasoning tags).

## Use Case example: Automated Security Audits

This agent can, among other things, perform **Security Audits** on code repositories. You can copy the files into the sandbox-folder, so you work on copies in case something goes wrong, and it can systematically scan for vulnerabilities, suspicious imports, or malicious obfuscation patterns.

### Recommended Security Audit Prompt
To get the best results when auditing a repository, use the following prompt in the chat interface:

> **You are a Senior Cyber Security Auditor. Your goal is to determine if the files in this sandbox are safe to execute.**
>
> **Follow this methodology:**
>
> 1. **Use `get_project_structure` to understand the layout.**
> 2. **Use `search_in_files` to look for high-risk patterns: `eval(`, `exec(`, `os.system(`, `subprocess.`, `base64.b64decode`, and suspicious import statements (like `socket` or `requests` being used in unexpected files).**
> 3. **If you find suspicious code, use `read_file` to examine the full context of that line.**
> 4. **Look for 'obfuscation' (long strings of random characters) which often hide malicious intent.**
> 5. **Provide a final report: [SAFE], [SUSPICIOUS], or [DANGEROUS], with a detailed explanation of your findings and save it to a text-file.**

You can also tell it to look at 2 files and combine the relevant info in a new file and save it. Or tell it to create a text-file with 10 poems or jokes or stories or whatever. Or have it edit an HTML file. Or spell-check a text in a file. Or summarize the content of a group of files. Use your imagination :)

---
## Changelog
Latest on top:

- **version 1.0.0**:
   - Initial version. This is a proto-type, or proof-of-concept if you will, and only tested on Windows11 and only with the included MCP-server. It MAY have bugs and should be considered beta-software for now! Updates to make this easier to config and use with other MCP-servers are planned.
---

## Installation & Setup

### Prerequisites

*   **Python 3.11** (It may work with other Python-versions, but only 3.11 is tested)
*   **Ollama** (Running locally with a model that supports tool calling, such as `gemma4` or other reasoning models).

### Step-by-Step Setup

1.  **Create and activate a Virtual Environment (Recommended):**
    ```bash
    # Windows
    py -3.11 -m venv venv311
    .\venv\Scripts\activate
    ```

2.  **Install Dependencies:**
	To install the core dependencies: pip install -r requirements.txt
    ```bash
    pip install -r requirements.txt
    ```
	To install the exact environment used for testing: pip install -r requirements-lock.txt
    ```bash
    pip install -r requirements-lock.txt
    ```

3.  **Configure the Model:**
    Open `chatbot_MCP2enabled_GUI.py` in a text-editor and ensure the `MODEL` constant matches a model you have pulled in Ollama (In a CMD window you can use "ollama list" to see your installed models and the full name you should use) :
    ```python
    MODEL = 'your-preferred-model-name'
    ```

4.  **Run the Application:**
    The system is designed so that the **MCP Server starts automatically** when you launch the GUI. You only need to run the following command:
    ```bash
    python chatbot_MCP2enabled_GUI.py
    ```

## Project Structure

*   `chatbot_MCP2enabled_GUI.py`: The main GUI application (starts the server automatically).
*   `mcp2_server.py`: The MCP server providing the file-system tools.
*   `requirements.txt`: List of required Python libraries.

## License
This project is licensed under the Apache License 2.0 (modified for jurisdiction) — see the LICENSE.txt file for details. A NOTICE file is included in this repo.
