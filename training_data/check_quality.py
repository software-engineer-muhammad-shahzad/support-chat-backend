import json
from pathlib import Path


def check_dataset(dataset_path):
    print(f"\nChecking quality: {dataset_path}")

    total = 0
    issues = 0

    with dataset_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            total += 1

            try:
                example = json.loads(line)
            except json.JSONDecodeError:
                print(f"❌ Line {line_number}: Invalid JSON")
                issues += 1
                continue

            messages = example.get("messages", [])

            if len(messages) != 3:
                print(f"⚠️ Line {line_number}: Expected 3 messages")
                issues += 1
                continue

            system_message = messages[0].get("content", "")
            user_message = messages[1].get("content", "")
            assistant_message = messages[2].get("content", "")

            # Check system instruction
            if not system_message.strip():
                print(f"⚠️ Line {line_number}: Empty system message")
                issues += 1

            # Check user content
            if "Context:" not in user_message:
                print(f"⚠️ Line {line_number}: Missing 'Context:'")
                issues += 1

            if "Question:" not in user_message:
                print(f"⚠️ Line {line_number}: Missing 'Question:'")
                issues += 1

            # Check assistant answer
            if not assistant_message.strip():
                print(f"⚠️ Line {line_number}: Empty assistant answer")
                issues += 1

            print(f"✅ Line {line_number}: Basic quality checks passed")

    print("-----------------------------")
    print(f"Total examples : {total}")
    print(f"Issues found   : {issues}")
    print("-----------------------------")

    return issues == 0


BASE_DIR = Path(__file__).parent

training_file = BASE_DIR / "processed" / "training_data.jsonl"
validation_file = BASE_DIR / "validation" / "validation_data.jsonl"

training_ok = check_dataset(training_file)
validation_ok = check_dataset(validation_file)

print("\n=============================")
print("QUALITY CHECK RESULT")
print("=============================")

if training_ok and validation_ok:
    print("🎉 Basic quality checks passed!")
else:
    print("⚠️ Some quality issues were found.")