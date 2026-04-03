# AgentMesh Built-in Tools

AgentMesh provides a comprehensive set of built-in tools for file operations, command execution, and more.

## File Operation Tools

### read
Read file contents. Supports text files and images (jpg, png, gif, webp).

**Parameters:**
- `path` (required): Path to the file to read
- `offset` (optional): Line number to start reading from (1-indexed)
- `limit` (optional): Maximum number of lines to read

**Features:**
- Automatic truncation to 2000 lines or 50KB
- Support for partial file reading with offset/limit
- Image support with base64 encoding

### write
Write content to a file. Creates the file if it doesn't exist, overwrites if it does.

**Parameters:**
- `path` (required): Path to the file to write
- `content` (required): Content to write to the file

**Features:**
- Automatically creates parent directories
- UTF-8 encoding support

### edit
Edit a file by replacing exact text. The oldText must match exactly (including whitespace).

**Parameters:**
- `path` (required): Path to the file to edit
- `oldText` (required): Exact text to find and replace
- `newText` (required): New text to replace the old text with

**Features:**
- Fuzzy matching fallback if exact match fails
- Validates uniqueness (rejects if multiple matches found)
- Generates unified diff of changes
- Handles BOM and line ending normalization

## Command Execution Tools

### bash
Execute bash commands in the current working directory.

**Parameters:**
- `command` (required): Bash command to execute
- `timeout` (optional): Timeout in seconds (default: 30)

**Features:**
- Security checks for dangerous commands
- Output truncation to last 2000 lines or 50KB
- Saves full output to temp file when truncated
- Combines stdout and stderr

**Security:**
- Blocks dangerous commands (rm -rf, sudo, shutdown, etc.)

## Search Tools

### grep
Search file contents for a pattern using ripgrep.

**Parameters:**
- `pattern` (required): Search pattern (regex or literal string)
- `path` (optional): Directory or file to search (default: current directory)
- `glob` (optional): Filter files by glob pattern (e.g., '*.ts')
- `ignoreCase` (optional): Case-insensitive search (default: false)
- `literal` (optional): Treat pattern as literal string (default: false)
- `context` (optional): Number of context lines (default: 0)
- `limit` (optional): Maximum number of matches (default: 100)

**Features:**
- Fast searching with ripgrep
- Respects .gitignore files
- Context lines around matches
- Long lines truncated to 500 characters

**Requirements:**
- Requires ripgrep (rg) to be installed

### find
Search for files by glob pattern.

**Parameters:**
- `pattern` (required): Glob pattern (e.g., '*.ts', '**/*.json')
- `path` (optional): Directory to search in (default: current directory)
- `limit` (optional): Maximum number of results (default: 1000)

**Features:**
- Respects .gitignore files
- Recursive search support
- Directory indicators with trailing '/'

### ls
List directory contents.

**Parameters:**
- `path` (optional): Directory to list (default: current directory)
- `limit` (optional): Maximum number of entries (default: 500)

**Features:**
- Alphabetically sorted (case-insensitive)
- Directory indicators with trailing '/'
- Includes dotfiles
- Output truncation to 500 entries or 50KB

## Other Tools

### time
Returns current date and time.

**Parameters:**
- `format` (optional): "iso", "unix", or "human" (default: "human")
- `timezone` (optional): "UTC" or "local" (default: "local")

### calculator
Evaluates mathematical expressions.

**Parameters:**
- `expression` (required): Python expression (e.g., "2 + 2", "sqrt(16)")

### google_search
Performs Google searches using the Serper API.

**Parameters:**
- `query` (required): The search query

**Configuration:**
- Requires `api_key` in config.yaml (get from https://serper.dev/)

### browser
Browser automation for web navigation and interaction.

**Requirements:**
- Requires `browser-use>=0.1.40` package

## Tool Configuration

Tools can be configured in `config.yaml`:

```yaml
tools:
  google_search:
    api_key: "YOUR_SERPER_API_KEY"
```

## Usage in Teams

Add tools to agents in your team configuration:

```yaml
teams:
  my_team:
    agents:
      - name: "My Agent"
        tools:
          - read
          - write
          - edit
          - bash
          - grep
          - find
          - ls
```

## Migration Guide

### From terminal to bash
The `terminal` tool has been replaced by `bash`:
- Same functionality with improved output handling
- Better truncation and temp file support
- Update your config to use `bash` instead of `terminal`

### From file_save to write
The `file_save` tool has been replaced by `write`:
- Simpler interface focused on file writing
- No automatic content extraction
- Direct path and content parameters
- Update your config to use `write` instead of `file_save`

## Truncation Behavior

Most tools implement intelligent truncation to prevent overwhelming output:

- **Line limit**: 2000 lines (default)
- **Byte limit**: 50KB (default)
- **Grep line limit**: 500 characters per line

When truncation occurs, tools provide continuation hints (e.g., "Use offset=X to continue").
