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
    "> /dev/sda", "chmod -R 777 /",
}

# Only allow these command prefixes by default
ALLOWED_PREFIXES = {
    "ls", "cat", "head", "tail", "find", "grep", "wc",
    "pwd", "echo", "tree", "du", "df",
    "git", "npm", "yarn", "pip", "poetry",
    "python", "node",
    "mkdir", "touch", "cp",
    "docker", "docker-compose",
}


@dataclass
class CommandResult:
    command: str
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.return_code == 0

    @property
    def output(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"STDERR: {self.stderr}")
        if self.timed_out:
            parts.append("(command timed out)")
        return "\n".join(parts) if parts else "(no output)"


def is_safe_command(command: str) -> tuple[bool, str]:
    cmd_lower = command.strip().lower()

    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return False, f"Blocked command detected: {blocked}"

    # Check if the command starts with an allowed prefix
    first_word = cmd_lower.split()[0] if cmd_lower.split() else ""
    # Strip path prefix (e.g., /usr/bin/ls -> ls)
    first_word = first_word.rsplit("/", 1)[-1]

    if first_word not in ALLOWED_PREFIXES:
        return False, (f"Command '{first_word}' not in allowed list. "
                       f"Allowed: {', '.join(sorted(ALLOWED_PREFIXES))}")

    return True, ""


def execute_command(command: str, cwd: str | None = None,
                    timeout: int = 30, force: bool = False) -> CommandResult:
    if not force:
        safe, reason = is_safe_command(command)
        if not safe:
            return CommandResult(
                command=command,
                stdout="",
                stderr=f"Command blocked: {reason}",
                return_code=-1,
            )

    logger.info(f"Executing: {command}")

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
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
    except Exception as e:
        return CommandResult(
            command=command,
            stdout="",
            stderr=str(e),
            return_code=-1,
        )


def create_execution_plan(commands: list[str]) -> list[dict]:
    plan = []
    for cmd in commands:
        safe, reason = is_safe_command(cmd)
        plan.append({
            "command": cmd,
            "safe": safe,
            "reason": reason if not safe else "OK",
        })
    return plan
