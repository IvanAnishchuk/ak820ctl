"""Type stubs for `typer.testing` — only the surface tests use.

`CliRunner.invoke(app, args)` returns a `Result` with `exit_code` and
`output` attributes; that's all the tests touch.
"""

from typer import Typer

class Result:
    exit_code: int
    output: str

class CliRunner:
    def __init__(self) -> None: ...
    def invoke(
        self,
        app: Typer,
        args: list[str] | None = ...,
        *,
        input: str | bytes | None = ...,
        env: dict[str, str] | None = ...,
        catch_exceptions: bool = ...,
        color: bool = ...,
    ) -> Result: ...
