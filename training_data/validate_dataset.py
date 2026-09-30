import json
from pathlib import Path


def validate_dataset(dataset_path):
    print(f"\nChecking: {dataset_path}")

    valid_count = 0
    error_count = 0

    with dataset_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                example = json.loads(line)
            except json.JSONDecodeError as error:
                print(f"❌ Line {line_number}: Invalid JSON")
                print(f"   {error}")
                error_count += 1
                continue

            if "messages" not in example:
                print(f"❌ Line {line_number}: Missing 'messages'")
                error_count += 1
                continue

            messages = example["messages"]

            if not isinstance(messages, list):
                print(f"❌ Line {line_number}: 'messages' must be a list")
                error_count += 1
                continue

            expected_roles = ["system", "user", "assistant"]
            roles = [message.get("role") for message in messages]

            if roles != expected_roles:
                print(
                    f"❌ Line {line_number}: " f"Expected {expected_roles}, got {roles}"
                )
                error_count += 1
                continue

            content_valid = True

            for message in messages:
                content = message.get("content")

                if not isinstance(content, str) or not content.strip():
                    content_valid = False
                    break

            if not content_valid:
                print(f"❌ Line {line_number}: " "Message content is missing or empty")
                error_count += 1
                continue

            print(f"✅ Line {line_number}: Valid")
            valid_count += 1

    print("-----------------------------")
    print(f"Valid examples  : {valid_count}")
    print(f"Invalid examples: {error_count}")
    print("-----------------------------")

    return error_count == 0


BASE_DIR = Path(__file__).parent

training_file = BASE_DIR / "processed" / "training_data.jsonl"
validation_file = BASE_DIR / "validation" / "validation_data.jsonl"

training_valid = validate_dataset(training_file)
validation_valid = validate_dataset(validation_file)

print("\n=============================")
print("FINAL RESULT")
print("=============================")

if training_valid and validation_valid:
    print("🎉 Both datasets are valid!")
else:
    print("⚠️ One or both datasets contain errors.")
