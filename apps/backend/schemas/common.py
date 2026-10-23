from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Деньги считаются в Decimal, а в JSON отдаются числом (как в примерах ТЗ: "price": 1800)
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
