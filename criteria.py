from typing import TypedDict


class Criterion(TypedDict):
    id: str
    title: str
    description: str
    weight: int | float


def default_criteria() -> list[Criterion]:
    return [
        {
            "id": "leadership",
            "title": "主体性",
            "description": "代表として自分から動き、周囲を前向きに巻き込めそうかを評価する。",
            "weight": 5,
        },
        {
            "id": "communication",
            "title": "コミュニケーション力",
            "description": "班員や研究室メンバーと丁寧に連携し、意思疎通を円滑に進められそうかを評価する。",
            "weight": 4,
        },
        {
            "id": "responsibility",
            "title": "責任感",
            "description": "役割を最後までやり切る姿勢が感じられるかを評価する。",
            "weight": 5,
        },
    ]
