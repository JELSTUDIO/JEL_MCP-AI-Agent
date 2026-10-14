import os
import sys
import logging
from datetime import datetime
from mcp.server.mcpserver import MCPServer

# --- CONFIGURATION ---
BASE_DIR = os.path.abspath(r"F:\AI_RunOnX4\JEL_AIchatbot\my_ai_sandbox")

ALLOWED_EXTENSIONS = {
    ".txt", ".py", ".json", ".md", ".yaml", ".yml", ".ini", ".toml",
    ".html", ".htm", ".css", ".js"
}

MAX_FILE_COUNT  = 50
MAX_READ_BYTES  = 512 * 1024  # 512 KB read cap
MAX_WRITE_BYTES = 512 * 1024  # 512 KB write cap

# Audit log lives next to this script, *outside* the sandbox
_AUDIT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_audit.log")

if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

# ── Lightweight audit logger ──────────────────────────────────────────
_audit_logger = logging.getLogger("mcp_audit")
_audit_logger.setLevel(logging.INFO)
_file_handler = logging.FileHandler(_AUDIT_LOG, encoding="utf-8")
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
_audit_logger.addHandler(_file_handler)


def _audit(op: str, filename: str, detail: str = ""):
    _audit_logger.info(f"{op}  {filename}  {detail}".rstrip())


# ── Safety gate ───────────────────────────────────────────────────────
def is_safe_path(filename: str) -> bool:
    """Path must resolve inside the sandbox AND carry an allowed extension."""
    target_path = os.path.realpath(os.path.join(BASE_DIR, filename))  # (2) realpath
    if not target_path.startswith(BASE_DIR + os.sep):                 # (3) trailing sep
        return False
    _, ext = os.path.splitext(target_path)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return False
    return True


# ── MCP server ────────────────────────────────────────────────────────
mcp = MCPServer("FileSandboxServer")


@mcp.tool()
def list_files() -> list:
    """Lists all files currently in the sandbox folder."""
    try:
        return os.listdir(BASE_DIR)
    except Exception as e:
        return [f"Error: {str(e)}"]


@mcp.tool()
def get_project_structure() -> str:
    """Returns a visual tree structure of the sandbox directory. Useful for understanding project layout."""
    tree = []
    for root, dirs, files in os.walk(BASE_DIR):
        level = root.replace(BASE_DIR, '').count(os.sep)
        indent = ' ' * 4 * level
        tree.append(f"{indent}{os.path.basename(root)}/")
        sub_indent = ' ' * 4 * (level + 1)
        for f in files:
            if any(f.endswith(ext) for ext in ALLOWED_EXTENSIONS):
                tree.append(f"{sub_indent}{f}")
    return "\n".join(tree)


@mcp.tool()
def search_in_files(query: str) -> str:
    """
    Searches for a specific string/keyword across all allowed files in the sandbox.
    Returns: 'filename:line_number: content'
    Use this to look for suspicious patterns like 'eval(', 'os.system', or 'requests.post'.
    """
    results = []
    try:
        for root, dirs, files in os.walk(BASE_DIR):
            for file in files:
                if any(file.endswith(ext) for ext in ALLOWED_EXTENSIONS):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for i, line in enumerate(f, 1):
                                if query.lower() in line.lower():
                                    rel_path = os.path.relpath(file_path, BASE_DIR)
                                    results.append(f"{rel_path}:{i}: {line.strip()}")
                    except Exception:
                        continue
        if not results:
            return f"No matches found for '{query}'."
        return "\n".join(results[:50])
    except Exception as e:
        return f"Error during search: {str(e)}"


@mcp.tool()
def read_file(filename: str) -> str:
    """Reads the content of a specific file in the sandbox (max 512 KB)."""
    if not is_safe_path(filename):
        _audit("READ (denied)", filename, "path/extension check failed")
        return "Error: Access Denied or invalid extension."
    target_path = os.path.realpath(os.path.join(BASE_DIR, filename))
    try:
        if os.path.getsize(target_path) > MAX_READ_BYTES:            # (1) size cap
            size_kb = os.path.getsize(target_path) // 1024
            return f"Error: File is {size_kb} KB, exceeds {MAX_READ_BYTES // 1024} KB read limit."
        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()
        _audit("READ", filename, f"{len(content)} chars")
        return content
    except Exception as e:
        _audit("READ (error)", filename, str(e))
        return f"Error: {str(e)}"


@mcp.tool()
def write_file(filename: str, content: str) -> str:
    """Writes a file to the sandbox (max 512 KB, max 50 files total)."""
    if not is_safe_path(filename):
        _audit("WRITE (denied)", filename, "path/extension check failed")
        return "Error: Access Denied or invalid extension."
    if len(content.encode('utf-8')) > MAX_WRITE_BYTES:               # (1) size cap
        size_kb = len(content.encode('utf-8')) // 1024
        return f"Error: Content is {size_kb} KB, exceeds {MAX_WRITE_BYTES // 1024} KB write limit."
    target_path = os.path.realpath(os.path.join(BASE_DIR, filename))
    current_files = os.listdir(BASE_DIR)
    if filename not in current_files and len(current_files) >= MAX_FILE_COUNT:
        _audit("WRITE (denied)", filename, f"file count limit ({MAX_FILE_COUNT}) reached")
        return f"Error: Max file limit ({MAX_FILE_COUNT}) reached."
    try:
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)
        _audit("WRITE", filename, f"{len(content)} chars")
        return f"Success: {filename} written."
    except Exception as e:
        _audit("WRITE (error)", filename, str(e))
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run()
