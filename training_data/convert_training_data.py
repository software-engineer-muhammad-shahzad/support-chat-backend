import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "processed" / "training_data.jsonl"
OUTPUT_FILE = BASE_DIR / "tuning" / "training_tuning.jsonl"


def convert_example(example):
    messages = example["messages"]

    system_message = next(
        message
        for message in messages
        if message["role"] == "system"
    )

    user_message = next(
        message
        for message in messages
        if message["role"] == "user"
    )

    assistant_message = next(
        message
        for message in messages
        if message["role"] == "assistant"
    )

    return {
        "systemInstruction": {
            "role": "system",
            "parts": [
                {
                    "text": system_message["content"]
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": user_message["content"]
                    }
                ]
            },
            {
                "role": "model",
                "parts": [
                    {
                        "text": assistant_message["content"]
                    }
                ]
            }
        ]
    }


def main():
    converted_examples = []

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):

            if not line.strip():
                continue

            try:
                example = json.loads(line)
                converted = convert_example(example)
                converted_examples.append(converted)

            except Exception as error:
                print(
                    f"Error on line {line_number}: {error}"
                )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        for example in converted_examples:
            file.write(
                json.dumps(
                    example,
                    ensure_ascii=False
                ) + "\n"
            )

    print("=" * 50)
    print("TRAINING DATA CONVERSION")
    print("=" * 50)

    print(f"Input examples : {len(converted_examples)}")
    print(f"Output file    : {OUTPUT_FILE}")

    print("=" * 50)
    print("Conversion completed successfully!")


if __name__ == "__main__":
    main()