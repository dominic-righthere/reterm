"""YAML script parser for .reterm files."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from reterm.output.models import (
    ExpectClause,
    Script,
    ScriptConfig,
    ScriptMeta,
    ScriptOutput,
    Step,
)


class ScriptError(Exception):
    """Error parsing or validating a script."""

    def __init__(self, message: str, line: int | None = None) -> None:
        self.line = line
        super().__init__(f"{message}" + (f" (line {line})" if line else ""))


def parse_script(path: Path) -> Script:
    """Parse a .reterm script file.

    Args:
        path: Path to the .reterm file

    Returns:
        Parsed Script object

    Raises:
        ScriptError: If the file cannot be parsed or validated
    """
    if not path.exists():
        raise ScriptError(f"Script file not found: {path}")

    try:
        content = path.read_text()
    except Exception as e:
        raise ScriptError(f"Cannot read script file: {e}")

    return parse_script_string(content)


def parse_script_string(content: str) -> Script:
    """Parse a .reterm script from a string.

    Args:
        content: YAML content

    Returns:
        Parsed Script object

    Raises:
        ScriptError: If the content cannot be parsed or validated
    """
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ScriptError(f"Invalid YAML: {e}")

    if not isinstance(data, dict):
        raise ScriptError("Script must be a YAML mapping")

    return _parse_script_dict(data)


def _parse_script_dict(data: dict[str, Any]) -> Script:
    """Parse a script from a dictionary."""
    try:
        # Parse meta section
        meta = ScriptMeta()
        if "meta" in data:
            meta_data = data["meta"]
            if isinstance(meta_data, dict):
                meta = ScriptMeta(**meta_data)

        # Parse config section
        config = ScriptConfig()
        if "config" in data:
            config_data = data["config"]
            if isinstance(config_data, dict):
                # Handle size as tuple
                if "size" in config_data:
                    size = config_data["size"]
                    if isinstance(size, list) and len(size) == 2:
                        config_data["size"] = tuple(size)
                config = ScriptConfig(**config_data)

        # Parse output section
        output = ScriptOutput()
        if "output" in data:
            output_data = data["output"]
            if isinstance(output_data, dict):
                output = ScriptOutput(**output_data)

        # Parse env section
        env: dict[str, str] = {}
        if "env" in data:
            env_data = data["env"]
            if isinstance(env_data, dict):
                env = {str(k): str(v) for k, v in env_data.items()}

        # Parse steps
        steps: list[Step] = []
        if "steps" in data:
            steps_data = data["steps"]
            if isinstance(steps_data, list):
                for i, step_data in enumerate(steps_data):
                    try:
                        step = _parse_step(step_data)
                        steps.append(step)
                    except Exception as e:
                        raise ScriptError(f"Invalid step {i + 1}: {e}")

        return Script(
            meta=meta,
            config=config,
            output=output,
            env=env,
            steps=steps,
        )

    except ValidationError as e:
        raise ScriptError(f"Validation error: {e}")


def _parse_step(step_data: Any) -> Step:
    """Parse a single step."""
    if isinstance(step_data, str):
        # Simple string step: treat as run command
        return Step(run=step_data)

    if not isinstance(step_data, dict):
        raise ScriptError(f"Step must be a string or mapping, got {type(step_data)}")

    # Handle expect clause
    if "expect" in step_data:
        expect_data = step_data["expect"]
        if isinstance(expect_data, dict):
            step_data["expect"] = ExpectClause(**expect_data)

    return Step(**step_data)


def validate_script(path: Path) -> list[str]:
    """Validate a script and return any warnings.

    Args:
        path: Path to the .reterm file

    Returns:
        List of warning messages (empty if no warnings)

    Raises:
        ScriptError: If the script is invalid
    """
    script = parse_script(path)
    warnings: list[str] = []

    # Check for empty steps
    if not script.steps:
        warnings.append("Script has no steps")

    # Check for missing output
    if not script.output.gif and not script.output.log:
        warnings.append("No output specified (gif or log)")

    # Check for unknown step types
    for i, step in enumerate(script.steps):
        step_type = step.get_step_type()
        if step_type == "unknown":
            warnings.append(f"Step {i + 1} has no recognized action")

    return warnings
