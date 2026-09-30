import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "training_tuning.jsonl"


def validate_example(example, line_number):
    # 1. systemInstruction
    if "systemInstruction" not in example:
        raise ValueError(f"Line {line_number}: missing systemInstruction")

    system = example["systemInstruction"]

    if system.get("role") != "system":
        raise ValueError(
            f"Line {line_number}: systemInstruction role must be 'system'"
        )

    if not isinstance(system.get("parts"), list) or not system["parts"]:
        raise ValueError(
            f"Line {line_number}: systemInstruction.parts must be a non-empty list"
        )

    for part in system["parts"]:
        if not part.get("text", "").strip():
            raise ValueError(
                f"Line {line_number}: systemInstruction contains empty text"
            )

    # 2. contents
    if "contents" not in example:
        raise ValueError(f"Line {line_number}: missing contents")

    contents = example["contents"]

    if not isinstance(contents, list) or not contents:
        raise ValueError(
            f"Line {line_number}: contents must be a non-empty list"
        )

    # Our current dataset is single-turn:
    # user -> model
    if len(contents) != 2:
        raise ValueError(
            f"Line {line_number}: expected 2 contents messages, got {len(contents)}"
        )

    expected_roles = ["user", "model"]

    for index, (message, expected_role) in enumerate(
        zip(contents, expected_roles),
        start=1,
    ):
        if message.get("role") != expected_role:
            raise ValueError(
                f"Line {line_number}: message {index} "
                f"must have role '{expected_role}'"
            )

        if not isinstance(message.get("parts"), list) or not message["parts"]:
            raise ValueError(
                f"Line {line_number}: message {index}.parts must be non-empty"
            )

        for part in message["parts"]:
            if not part.get("text", "").strip():
                raise ValueError(
                    f"Line {line_number}: message {index} contains empty text"
                )


def main():
    print("=" * 60)
    print("GEMINI TUNING DATASET VALIDATION")
    print("=" * 60)

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        lines = [line.strip() for line in file if line.strip()]

    print(f"File     : {INPUT_FILE}")
    print(f"Examples : {len(lines)}")
    print()

    for line_number, line in enumerate(lines, start=1):
        try:
            example = json.loads(line)
            validate_example(example, line_number)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Line {line_number}: invalid JSON: {error}"
            ) from error

    print("✓ JSON syntax is valid")
    print("✓ systemInstruction is valid")
    print("✓ contents structure is valid")
    print("✓ user/model roles are valid")
    print("✓ All text fields are non-empty")
    print()
    print("Gemini tuning dataset validation PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()