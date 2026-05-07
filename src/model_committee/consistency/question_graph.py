from collections import defaultdict

from model_committee.markdown.questions_parser import Question


def dependency_edges(questions: list[Question]) -> list[tuple[str, str]]:
    return [
        (question.question_id, dependency)
        for question in questions
        for dependency in question.metadata.depends_on
    ]


def find_dependency_cycles(questions: list[Question]) -> list[list[str]]:
    graph = defaultdict(list)
    for question in questions:
        graph[question.question_id].extend(question.metadata.depends_on)

    cycles: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, stack: list[str]) -> None:
        if node in visiting:
            cycles.append(stack[stack.index(node) :] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        for nxt in graph[node]:
            visit(nxt, stack + [nxt])
        visiting.remove(node)
        visited.add(node)

    for question in questions:
        visit(question.question_id, [question.question_id])
    return cycles
