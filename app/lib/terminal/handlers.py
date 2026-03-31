"""Safe terminal command execution with allowlist-based security."""

import logging
import shlex
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Commands that are never allowed
BLOCKED_COMMANDS = {
    "rm", "rmdir", "mkfs", "dd", "format",
    "shutdown", "reboot", "halt", "poweroff",
    "kill", "killall", "pkill",
}

# Only allow these command prefixes by default — read-only/safe commands
ALLOWED_PREFIXES = {
    "ls", "cat", "head", "tail", "find", "grep", "wc",
    "pwd", "echo", "tree", "du", "df",
}

# Commands allowed only with safe subcommands
_SUBCOMMAND_ALLOWLIST: dict[str, frozenset[str]] = {
    "git": frozenset({"status", "log", "diff", "show", "branch", "tag", "ls-files", "remote"}),
    "npm": frozenset({"list", "ls", "outdated", "audit", "info", "view"}),
    "yarn": frozenset({"list", "info", "why", "audit"}),
    "pip": frozenset({"list", "show", "freeze", "check"}),
    "poetry": frozenset({"show", "check", "env"}),
    "docker": frozenset({"ps", "images", "logs", "inspect", "stats", "version", "info"}),
    "docker-compose": frozenset({"ps", "logs", "config", "version"}),
}

# Shell metacharacters that indicate injection attempts
_SHELL_METACHARACTERS = set("|;&$`(){}!><\n")


@dataclass
class CommandResult:
    """Result of a terminal command execution."""

    command: str
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool = False

    @property
    def success(self) -> bool:
        """Return True if the command exited with code 0."""
        return self.return_code == 0

    @property
    def output(self) -> str:
        """Format the command output for display."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"STDERR: {self.stderr}")
        if self.timed_out:
            parts.append("(command timed out)")
        return "\n".join(parts) if parts else "(no output)"


def is_safe_command(command: str) -> tuple[bool, str]:
    """Check whether a command is safe to execute against the allowlist."""
    cmd_stripped = command.strip()

    # Reject commands containing shell metacharacters
    for char in _SHELL_METACHARACTERS:
        if char in cmd_stripped:
            return False, f"Shell metacharacter '{char}' not allowed"

    try:
        parts = shlex.split(cmd_stripped)
    except ValueError as e:
        return False, f"Invalid command syntax: {e}"

    if not parts:
        return False, "Empty command"

    # Extract the base command name (strip path prefix)
    first_word = parts[0].rsplit("/", 1)[-1].lower()

    if first_word in BLOCKED_COMMANDS:
        return False, f"Blocked command: {first_word}"

    # Unconditionally safe commands
    if first_word in ALLOWED_PREFIXES:
        return True, ""

    # Commands with subcommand restrictions
    if first_word in _SUBCOMMAND_ALLOWLIST:
        allowed_subs = _SUBCOMMAND_ALLOWLIST[first_word]
        if len(parts) < 2:
            return False, f"'{first_word}' requires a subcommand: {', '.join(sorted(allowed_subs))}"
        sub = parts[1].lower().lstrip("-")
        if sub not in allowed_subs:
            return False, (f"'{first_word} {parts[1]}' not allowed. "
                           f"Allowed subcommands: {', '.join(sorted(allowed_subs))}")
        return True, ""

    all_allowed = sorted(ALLOWED_PREFIXES | set(_SUBCOMMAND_ALLOWLIST))
    return False, (f"Command '{first_word}' not in allowed list. "
                   f"Allowed: {', '.join(all_allowed)}")


def execute_command(command: str, cwd: str | None = None,
                    timeout: int = 30) -> CommandResult:
    """Execute a terminal command with safety checks and timeout."""
    safe, reason = is_safe_command(command)
    if not safe:
        return CommandResult(
            command=command,
            stdout="",
            stderr=f"Command blocked: {reason}",
            return_code=-1,
        )

    logger.info("Executing: %s", command)

    try:
        args = shlex.split(command)
        result = subprocess.run(
            args,
            shell=False,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            command=command,
            stdout=result.stdout[:10000],  # Limit output size
            stderr=result.stderr[:5000],
            return_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            command=command,
            stdout="",
            stderr=f"Command timed out after {timeout}s",
            return_code=-1,
            timed_out=True,
        )
    except OSError as e:
        return CommandResult(
            command=command,
            stdout="",
            stderr=str(e),
            return_code=-1,
        )


def create_execution_plan(commands: list[str]) -> list[dict]:
    """Create a safety-checked execution plan for a list of commands."""
    plan = []
    for cmd in commands:
        safe, reason = is_safe_command(cmd)
        plan.append({
            "command": cmd,
            "safe": safe,
            "reason": reason if not safe else "OK",
        })
    return plan
