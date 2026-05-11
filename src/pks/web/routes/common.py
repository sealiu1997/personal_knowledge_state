from __future__ import annotations

from fastapi import Request
from fastapi.templating import Jinja2Templates

from pks.kernel import Kernel


def kernel_from(request: Request) -> Kernel:
    return request.app.state.kernel


def templates_from(request: Request) -> Jinja2Templates:
    return request.app.state.templates


def dump_model(model) -> dict:
    return model.model_dump(mode="json")
