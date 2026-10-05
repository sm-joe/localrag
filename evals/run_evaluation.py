import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    ROOT_DIR
    / "evals"
    / "datasets"
    / "localrag_baseline.json"
)

RESULTS_DIR = (
    ROOT_DIR
    / "evals"
    / "results"
)

API_URL = "http://localhost:8000/chat"
TOP_K = 3


def load_dataset() -> dict[str, Any]:
    with DATASET_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def call_chat_api(
    question: str,
) -> dict[str, Any]:
    payload = json.dumps(
        {
            "question": question,
            "top_k": TOP_K,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=120,
        ) as response:
            response_body = response.read()

    except urllib.error.HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"Chat API returned HTTP {exc.code}: {body}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Unable to reach Chat API: {exc.reason}"
        ) from exc

    return json.loads(
        response_body.decode("utf-8")
    )


def normalize_text(text: str) -> str:
    normalized = text.lower()

    normalized = re.sub(
        r"[^a-z0-9\s]",
        " ",
        normalized,
    )

    return " ".join(
        normalized.split()
    )


def evaluate_concepts(
    answer: str,
    expected_concepts: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_answer = normalize_text(
        answer
    )

    matched: list[str] = []
    missing: list[str] = []

    details: list[dict[str, Any]] = []

    for concept in expected_concepts:
        name = str(
            concept["name"]
        )

        variants = [
            str(variant)
            for variant in concept.get(
                "variants",
                [],
            )
        ]

        matched_variant = None

        for variant in variants:
            normalized_variant = (
                normalize_text(variant)
            )

            if (
                normalized_variant
                and normalized_variant
                in normalized_answer
            ):
                matched_variant = variant
                break

        if matched_variant is not None:
            matched.append(name)

            details.append(
                {
                    "name": name,
                    "matched": True,
                    "matched_variant": (
                        matched_variant
                    ),
                }
            )
        else:
            missing.append(name)

            details.append(
                {
                    "name": name,
                    "matched": False,
                    "matched_variant": None,
                }
            )

    total = len(expected_concepts)

    score = (
        len(matched) / total
        if total
        else 1.0
    )

    return {
        "matched": matched,
        "missing": missing,
        "score": round(
            score,
            3,
        ),
        "passed": (
            len(missing) == 0
        ),
        "details": details,
    }


def extract_citations(
    answer: str,
) -> list[int]:
    matches = re.findall(
        r"\[(\d+)\]",
        answer,
    )

    citations = []

    for match in matches:
        citation = int(match)

        if citation not in citations:
            citations.append(citation)

    return citations


def evaluate_citations(
    answer: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    citations = extract_citations(
        answer
    )

    source_count = len(sources)

    valid_citations = [
        citation
        for citation in citations
        if 1 <= citation <= source_count
    ]

    invalid_citations = [
        citation
        for citation in citations
        if citation < 1
        or citation > source_count
    ]

    passed = bool(
        citations
        and not invalid_citations
    )

    return {
        "citations": citations,
        "valid_citations": valid_citations,
        "invalid_citations": invalid_citations,
        "source_count": source_count,
        "passed": passed,
    }


def evaluate_source(
    response: dict[str, Any],
    expected_filename: str,
) -> dict[str, Any]:
    sources = response.get(
        "sources",
        [],
    )

    matching_sources = [
        source
        for source in sources
        if source.get("filename")
        == expected_filename
    ]

    expected_source_ranks = []

    for index, source in enumerate(
        sources,
        start=1,
    ):
        if (
            source.get("filename")
            == expected_filename
        ):
            expected_source_ranks.append(
                index
            )

    passed = bool(
        matching_sources
    )

    return {
        "expected_filename": expected_filename,
        "matching_sources": len(
            matching_sources
        ),
        "expected_source_ranks": (
            expected_source_ranks
        ),
        "rank": (
            min(expected_source_ranks)
            if expected_source_ranks
            else None
        ),
        "passed": passed,
    }


def evaluate_retrieval(
    response: dict[str, Any],
    expected_filename: str,
) -> dict[str, Any]:
    retrieval = response.get(
        "retrieval",
        {},
    )

    sources = response.get(
        "sources",
        [],
    )

    source_evaluation = evaluate_source(
        response=response,
        expected_filename=expected_filename,
    )

    top_candidate_score = retrieval.get(
        "top_candidate_score"
    )

    top_score = retrieval.get(
        "top_score"
    )

    return {
        "expected_document_retrieved": (
            source_evaluation["passed"]
        ),
        "expected_document_rank": (
            source_evaluation["rank"]
        ),
        "candidate_count": retrieval.get(
            "candidate_count",
            0,
        ),
        "returned_count": retrieval.get(
            "returned_count",
            0,
        ),
        "filtered_count": retrieval.get(
            "filtered_count",
            0,
        ),
        "top_candidate_score": (
            top_candidate_score
        ),
        "top_returned_score": top_score,
        "has_context": retrieval.get(
            "has_context",
            False,
        ),
        "source_count": len(
            sources
        ),
    }


def evaluate_case(
    case: dict[str, Any],
) -> dict[str, Any]:
    question = case["question"]

    response = call_chat_api(
        question
    )

    answer = response.get(
        "answer",
        "",
    )

    sources = response.get(
        "sources",
        [],
    )

    expected_concepts = case.get(
        "expected_concepts",
        [],
    )

    concept_evaluation = evaluate_concepts(
        answer=answer,
        expected_concepts=(
            expected_concepts
        ),
    )

    citation_evaluation = (
        evaluate_citations(
            answer=answer,
            sources=sources,
        )
    )

    source_evaluation = evaluate_source(
        response=response,
        expected_filename=case[
            "expected_filename"
        ],
    )

    retrieval_evaluation = (
        evaluate_retrieval(
            response=response,
            expected_filename=case[
                "expected_filename"
            ],
        )
    )

    retrieval_passed = (
        retrieval_evaluation[
            "expected_document_retrieved"
        ]
        and retrieval_evaluation[
            "has_context"
        ]
    )

    grounding_passed = (
        retrieval_passed
        and citation_evaluation[
            "passed"
        ]
    )

    answer_passed = concept_evaluation[
        "passed"
    ]

    passed = (
        retrieval_passed
        and answer_passed
        and grounding_passed
    )

    return {
        "id": case["id"],
        "question": question,
        "expected_answer": case[
            "expected_answer"
        ],
        "actual_answer": answer,
        "retrieval": retrieval_evaluation,
        "source_evaluation": (
            source_evaluation
        ),
        "concept_evaluation": (
            concept_evaluation
        ),
        "citation_evaluation": (
            citation_evaluation
        ),
        "grounding_passed": (
            grounding_passed
        ),
        "answer_passed": answer_passed,
        "passed": passed,
        "performance": response.get(
            "performance",
            {},
        ),
    }


def calculate_summary(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(results)

    passed = sum(
        1
        for result in results
        if result.get(
            "passed",
            False,
        )
    )

    retrieval_passed = sum(
        1
        for result in results
        if result.get(
            "retrieval",
            {},
        ).get(
            "expected_document_retrieved",
            False,
        )
    )

    context_passed = sum(
        1
        for result in results
        if result.get(
            "retrieval",
            {},
        ).get(
            "has_context",
            False,
        )
    )

    concept_passed = sum(
        1
        for result in results
        if result.get(
            "answer_passed",
            False,
        )
    )

    grounding_passed = sum(
        1
        for result in results
        if result.get(
            "grounding_passed",
            False,
        )
    )

    citation_passed = sum(
        1
        for result in results
        if result.get(
            "citation_evaluation",
            {},
        ).get(
            "passed",
            False,
        )
    )

    concept_scores = [
        result[
            "concept_evaluation"
        ]["score"]
        for result in results
        if "concept_evaluation"
        in result
    ]

    return {
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": (
            total - passed
        ),
        "pass_rate": round(
            passed / total,
            3,
        )
        if total
        else 0.0,
        "expected_document_recall": round(
            retrieval_passed / total,
            3,
        )
        if total
        else 0.0,
        "context_retrieval_rate": round(
            context_passed / total,
            3,
        )
        if total
        else 0.0,
        "concept_answer_pass_rate": round(
            concept_passed / total,
            3,
        )
        if total
        else 0.0,
        "citation_coverage": round(
            citation_passed / total,
            3,
        )
        if total
        else 0.0,
        "grounded_answer_rate": round(
            grounding_passed / total,
            3,
        )
        if total
        else 0.0,
        "average_concept_score": round(
            sum(concept_scores)
            / len(concept_scores),
            3,
        )
        if concept_scores
        else 0.0,
    }


def print_case_result(
    result: dict[str, Any],
) -> None:
    retrieval = result[
        "retrieval"
    ]

    concepts = result[
        "concept_evaluation"
    ]

    citations = result[
        "citation_evaluation"
    ]

    print(
        f"  Retrieval: "
        f"{'PASS' if retrieval['expected_document_retrieved'] else 'FAIL'}"
    )

    print(
        f"  Concepts:  "
        f"{'PASS' if concepts['passed'] else 'FAIL'} "
        f"({concepts['score']:.0%})"
    )

    print(
        f"  Citation:  "
        f"{'PASS' if citations['passed'] else 'FAIL'}"
    )

    print(
        f"  Grounding: "
        f"{'PASS' if result['grounding_passed'] else 'FAIL'}"
    )

    print(
        f"  Overall:   "
        f"{'PASS' if result['passed'] else 'FAIL'}"
    )


def main() -> int:
    dataset = load_dataset()

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print(
        "========================================"
    )
    print("LocalRAG Evaluation")
    print(
        "========================================"
    )
    print(
        f"Dataset: {dataset['name']}"
    )
    print(
        f"Dataset version: "
        f"{dataset['version']}"
    )
    print(
        f"Cases: {len(dataset['cases'])}"
    )
    print()

    results = []

    for case in dataset["cases"]:
        print(
            f"Running {case['id']}: "
            f"{case['question']}"
        )

        try:
            result = evaluate_case(
                case
            )

            print_case_result(
                result
            )

        except Exception as exc:
            print(
                f"  ERROR: {exc}"
            )

            result = {
                "id": case["id"],
                "question": case[
                    "question"
                ],
                "passed": False,
                "error": str(exc),
            }

        results.append(result)

        print()

    summary = calculate_summary(
        results
    )

    output = {
        "dataset": dataset["name"],
        "dataset_version": dataset[
            "version"
        ],
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "summary": summary,
        "results": results,
    }

    output_path = (
        RESULTS_DIR
        / "localrag-baseline.json"
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
        )

    print(
        "========================================"
    )
    print("Evaluation Summary")
    print(
        "========================================"
    )
    print(
        f"Passed: "
        f"{summary['passed_cases']}/"
        f"{summary['total_cases']}"
    )
    print(
        f"Pass rate: "
        f"{summary['pass_rate']:.1%}"
    )
    print(
        f"Expected document recall: "
        f"{summary['expected_document_recall']:.1%}"
    )
    print(
        f"Context retrieval rate: "
        f"{summary['context_retrieval_rate']:.1%}"
    )
    print(
        f"Concept answer pass rate: "
        f"{summary['concept_answer_pass_rate']:.1%}"
    )
    print(
        f"Citation coverage: "
        f"{summary['citation_coverage']:.1%}"
    )
    print(
        f"Grounded answer rate: "
        f"{summary['grounded_answer_rate']:.1%}"
    )
    print(
        f"Average concept score: "
        f"{summary['average_concept_score']:.1%}"
    )
    print()
    print(
        f"Results written to: "
        f"{output_path}"
    )

    return (
        0
        if summary["failed_cases"] == 0
        else 1
    )


if __name__ == "__main__":
    sys.exit(
        main()
    )