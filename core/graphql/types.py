import strawberry


@strawberry.type
class MoneyType:
    amount: str = strawberry.field(description='Decimal amount as string to preserve precision')
    currency: str = strawberry.field(description='ISO 4217 currency code')


@strawberry.type
class ErrorType:
    code: str = strawberry.field(description='Machine-readable error code')
    message: str = strawberry.field(description='Human-readable error message')
    field: str | None = strawberry.field(
        description='The field that caused the error, if applicable', default=None
    )
