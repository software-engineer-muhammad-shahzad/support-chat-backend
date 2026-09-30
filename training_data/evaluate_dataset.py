import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

# =========================================================
# 1. PATHS AND CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "processed" / "training_data.jsonl"
OUTPUT_FILE = BASE_DIR / "evaluation_results.jsonl"

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing from your .env file")


# Create Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)

# Gemini model used for evaluation
MODEL = "gemini-3.1-flash-lite"


# =========================================================
# 2. EVALUATION RESPONSE SCHEMA
# =========================================================


class EvaluationResult(BaseModel):

    grounded: bool = Field(
        description="Whether the answer is supported by the provided context."
    )

    relevant: bool = Field(
        description="Whether the answer directly addresses the question."
    )

    correct: bool = Field(
        description="Whether the answer is factually correct according to the context."
    )

    concise: bool = Field(
        description="Whether the answer is concise and avoids unnecessary information."
    )

    professional: bool = Field(
        description="Whether the answer is professional and clearly written."
    )

    hallucination: bool = Field(
        description="Whether the answer contains unsupported information."
    )

    score: float = Field(description="Overall quality score from 0.0 to 1.0.")

    reason: str = Field(description="Short explanation of the evaluation.")


# =========================================================
# 3. GEMINI EVALUATOR INSTRUCTIONS
# =========================================================

SYSTEM_INSTRUCTIONS = """
You are an expert AI dataset quality evaluator.

Your job is to evaluate an AI assistant's answer using ONLY
the provided context, question, and expected answer.

Evaluate the candidate answer according to these criteria:

1. GROUNDED
Is the answer supported by the provided context?

2. RELEVANT
Does the answer directly answer the question?

3. CORRECT
Is the answer factually correct according to the context
and expected answer?

4. CONCISE
Is the answer reasonably short and free from unnecessary information?

5. PROFESSIONAL
Is the answer clear, professional, and appropriate for an AI assistant?

6. HALLUCINATION
Does the answer contain information that is not supported
by the provided context?

SCORING:

1.0 = excellent
0.8 = good with a minor issue
0.6 = partially correct
0.4 = significant problem
0.2 = mostly incorrect
0.0 = completely incorrect or unsupported

IMPORTANT:

- Do not judge based on exact wording.
- Semantically equivalent answers should be considered correct.
- Different wording is acceptable if the meaning is the same.
- Be strict about unsupported facts.
- If the context does not contain information and the answer
  invents information, mark hallucination=true.
"""


# =========================================================
# 4. EVALUATE ONE EXAMPLE
# =========================================================


def evaluate_example(example):

    messages = example["messages"]

    # -----------------------------------------------------
    # Extract user message
    # -----------------------------------------------------

    user_message = messages[1]["content"]

    # -----------------------------------------------------
    # Extract expected answer
    # -----------------------------------------------------

    expected_answer = messages[2]["content"]

    # -----------------------------------------------------
    # Validate expected format
    # -----------------------------------------------------

    if "Context:" not in user_message:
        raise ValueError("Context section is missing.")

    if "Question:" not in user_message:
        raise ValueError("Question section is missing.")

    # -----------------------------------------------------
    # Extract context
    # -----------------------------------------------------

    context_part, question_part = user_message.split("Question:", 1)

    context = context_part.replace("Context:", "", 1).strip()

    question = question_part.strip()

    # -----------------------------------------------------
    # For the current dataset:
    #
    # assistant answer = candidate answer
    # -----------------------------------------------------

    candidate_answer = expected_answer

    # -----------------------------------------------------
    # Build evaluator prompt
    # -----------------------------------------------------

    prompt = f"""
{SYSTEM_INSTRUCTIONS}

--------------------------------
CONTEXT
--------------------------------

{context}

--------------------------------
QUESTION
--------------------------------

{question}

--------------------------------
EXPECTED ANSWER
--------------------------------

{expected_answer}

--------------------------------
CANDIDATE ANSWER
--------------------------------

{candidate_answer}

--------------------------------

Evaluate the candidate answer.
Return the evaluation using the required JSON schema.
"""

    # -----------------------------------------------------
    # Call Gemini
    # -----------------------------------------------------

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": EvaluationResult,
            "temperature": 0,
        },
    )

    # -----------------------------------------------------
    # Validate Gemini response with Pydantic
    # -----------------------------------------------------

    evaluation = EvaluationResult.model_validate_json(response.text)

    return evaluation


# =========================================================
# 5. MAIN DATASET EVALUATION
# =========================================================


def main():

    print("========================================")
    print("Gemini Dataset Evaluator")
    print("========================================")
    print()

    print(f"Input file : {INPUT_FILE}")
    print(f"Output file: {OUTPUT_FILE}")
    print()

    results = []

    # -----------------------------------------------------
    # Read JSONL dataset
    # -----------------------------------------------------

    with open(INPUT_FILE, "r", encoding="utf-8") as file:

        for index, line in enumerate(file, start=1):

            # Skip empty lines
            if not line.strip():
                continue

            print(f"Evaluating example {index}...")

            try:

                # Parse JSON
                example = json.loads(line)

                # Evaluate example
                evaluation = evaluate_example(example)

                # Store result
                result = {"example_id": index, "evaluation": evaluation.model_dump()}

                results.append(result)

                # Display result
                print(f"  Score          : {evaluation.score:.2f}")

                print(f"  Grounded       : {evaluation.grounded}")

                print(f"  Relevant       : {evaluation.relevant}")

                print(f"  Correct        : {evaluation.correct}")

                print(f"  Concise        : {evaluation.concise}")

                print(f"  Professional   : {evaluation.professional}")

                print(f"  Hallucination  : {evaluation.hallucination}")

                print(f"  Reason         : {evaluation.reason}")

                print()

            except Exception as error:

                print(f"  ERROR: {error}")

                results.append({"example_id": index, "error": str(error)})

                print()

    # =====================================================
    # SAVE RESULTS
    # =====================================================

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:

        for result in results:

            file.write(json.dumps(result, ensure_ascii=False) + "\n")

    # =====================================================
    # SUMMARY
    # =====================================================

    successful = [result for result in results if "evaluation" in result]

    failed = [result for result in results if "error" in result]

    print("========================================")
    print("Evaluation Completed")
    print("========================================")

    print(f"Total examples : {len(results)}")

    print(f"Successful     : {len(successful)}")

    print(f"Failed         : {len(failed)}")

    print()

    print(f"Results saved to:")

    print(OUTPUT_FILE)


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()
