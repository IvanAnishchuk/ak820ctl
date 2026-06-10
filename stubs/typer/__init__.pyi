"""Minimal type stubs for the `typer` CLI framework.

Only the surface actually used by `ak820ctl.cli` is typed. The goal is
to remove framework-induced `Any` from mypy's reports — typer's real
runtime objects (`OptionInfo`, `ArgumentInfo`, `Typer`) are richer than
this, but for type-check purposes inside `Annotated[T, typer.Option(...)]`
all callers need to know is that the metadata expression has a concrete
type.

Lives under `stubs/` per the `mypy_path = "stubs"` setting in
pyproject.toml; pyright/basedpyright pick the same path up via
`pyrightconfig.json::extraPaths`.
"""

from collections.abc import Callable
from typing import Any, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])

class Exit(Exception):  # noqa: N818 — name mirrors the runtime typer API
    """Raised to exit the CLI with a specific exit code."""

    code: int
    def __init__(self, code: int = 0) -> None: ...

class OptionInfo:
    """Opaque sentinel returned by `Option(...)`."""

class ArgumentInfo:
    """Opaque sentinel returned by `Argument(...)`."""

def Option(  # noqa: N802 — matches the typer public API surface
    *param_decls: str,
    callback: Callable[..., Any] | None = ...,
    is_eager: bool = ...,
    help: str | None = ...,
) -> OptionInfo: ...
def Argument(  # noqa: N802
    *param_decls: str,
    help: str | None = ...,
) -> ArgumentInfo: ...

class Typer:
    def __init__(
        self,
        *,
        name: str | None = ...,
        help: str | None = ...,
        no_args_is_help: bool = ...,
        add_completion: bool = ...,
    ) -> None: ...
    def command(
        self,
        name: str | None = ...,
        *,
        help: str | None = ...,
    ) -> Callable[[_F], _F]: ...
    def callback(
        self,
        *,
        invoke_without_command: bool = ...,
    ) -> Callable[[_F], _F]: ...
    def __call__(self) -> None: ...
