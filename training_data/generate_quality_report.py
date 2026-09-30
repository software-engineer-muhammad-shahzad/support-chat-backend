import json
from pathlib import Path


# =========================================================
# Configuration
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "evaluation_results.jsonl"
REPORT_FILE = BASE_DIR / "quality_report.json"


# =========================================================
# Load evaluation results
# =========================================================

def load_results():

    results = []

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        for line in file:

            if not line.strip():
                continue

            results.append(json.loads(line))

    return results


# =========================================================
# Generate report
# =========================================================

def generate_report(results):

    evaluations = [
        result["evaluation"]
        for result in results
        if "evaluation" in result
    ]

    total = len(evaluations)

    if total == 0:
        raise ValueError("No successful evaluations found.")

    # -----------------------------------------------------
    # Calculate average score
    # -----------------------------------------------------

    average_score = sum(
        evaluation["score"]
        for evaluation in evaluations
    ) / total

    # -----------------------------------------------------
    # Count each metric
    # -----------------------------------------------------

    grounded_count = sum(
        evaluation["grounded"]
        for evaluation in evaluations
    )

    relevant_count = sum(
        evaluation["relevant"]
        for evaluation in evaluations
    )

    correct_count = sum(
        evaluation["correct"]
        for evaluation in evaluations
    )

    concise_count = sum(
        evaluation["concise"]
        for evaluation in evaluations
    )

    professional_count = sum(
        evaluation["professional"]
        for evaluation in evaluations
    )

    hallucination_count = sum(
        evaluation["hallucination"]
        for evaluation in evaluations
    )

    # -----------------------------------------------------
    # Calculate percentages
    # -----------------------------------------------------

    grounded_percentage = (
        grounded_count / total
    ) * 100

    relevant_percentage = (
        relevant_count / total
    ) * 100

    correct_percentage = (
        correct_count / total
    ) * 100

    concise_percentage = (
        concise_count / total
    ) * 100

    professional_percentage = (
        professional_count / total
    ) * 100

    hallucination_percentage = (
        hallucination_count / total
    ) * 100

    # -----------------------------------------------------
    # Determine overall status
    # -----------------------------------------------------

    if (
        average_score >= 0.80
        and hallucination_count == 0
    ):
        status = "PASS"
    else:
        status = "REVIEW"

    # -----------------------------------------------------
    # Create report
    # -----------------------------------------------------

    report = {

        "total_examples": total,

        "average_score": round(
            average_score,
            2
        ),

        "metrics": {

            "grounded": {
                "passed": grounded_count,
                "total": total,
                "percentage": round(
                    grounded_percentage,
                    2
                )
            },

            "relevant": {
                "passed": relevant_count,
                "total": total,
                "percentage": round(
                    relevant_percentage,
                    2
                )
            },

            "correct": {
                "passed": correct_count,
                "total": total,
                "percentage": round(
                    correct_percentage,
                    2
                )
            },

            "concise": {
                "passed": concise_count,
                "total": total,
                "percentage": round(
                    concise_percentage,
                    2
                )
            },

            "professional": {
                "passed": professional_count,
                "total": total,
                "percentage": round(
                    professional_percentage,
                    2
                )
            },

            "hallucination": {
                "detected": hallucination_count,
                "total": total,
                "percentage": round(
                    hallucination_percentage,
                    2
                )
            }
        },

        "status": status
    }

    return report


# =========================================================
# Print report
# =========================================================

def print_report(report):

    print()
    print("=" * 45)
    print("DATASET QUALITY REPORT")
    print("=" * 45)

    print()

    print(
        f"Total examples:      "
        f"{report['total_examples']}"
    )

    print(
        f"Average score:       "
        f"{report['average_score']:.2f}"
    )

    print()

    print("Metrics:")
    print("-" * 45)

    metrics = report["metrics"]

    print(
        f"Grounded:            "
        f"{metrics['grounded']['passed']}/"
        f"{metrics['grounded']['total']} "
        f"({metrics['grounded']['percentage']}%)"
    )

    print(
        f"Relevant:            "
        f"{metrics['relevant']['passed']}/"
        f"{metrics['relevant']['total']} "
        f"({metrics['relevant']['percentage']}%)"
    )

    print(
        f"Correct:             "
        f"{metrics['correct']['passed']}/"
        f"{metrics['correct']['total']} "
        f"({metrics['correct']['percentage']}%)"
    )

    print(
        f"Concise:             "
        f"{metrics['concise']['passed']}/"
        f"{metrics['concise']['total']} "
        f"({metrics['concise']['percentage']}%)"
    )

    print(
        f"Professional:        "
        f"{metrics['professional']['passed']}/"
        f"{metrics['professional']['total']} "
        f"({metrics['professional']['percentage']}%)"
    )

    print(
        f"Hallucinations:      "
        f"{metrics['hallucination']['detected']}/"
        f"{metrics['hallucination']['total']} "
        f"({metrics['hallucination']['percentage']}%)"
    )

    print()

    print(
        f"Overall status:      "
        f"{report['status']}"
    )

    print("=" * 45)
    print()


# =========================================================
# Main
# =========================================================

def main():

    print("Loading evaluation results...")

    results = load_results()

    print(
        f"Loaded {len(results)} evaluation results."
    )

    report = generate_report(results)

    print_report(report)

    # Save JSON report

    with open(
        REPORT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=2
        )

    print(
        f"Report saved to:"
    )

    print(
        REPORT_FILE
    )


# =========================================================
# Entry point
# =========================================================

if __name__ == "__main__":
    main()