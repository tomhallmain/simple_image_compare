from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class ImageClassifierModelConfig:
    model_name: str
    model_location: str
    model_categories: list[str]
    use_hub_keras_layers: bool = False
    backend: str = "auto"
    model_kwargs: dict[str, Any] = field(default_factory=dict)
    hf_repo_id: Optional[str] = None
    hf_selected_filename: Optional[str] = None

    REQUIRED_KEYS = {"model_name", "model_location", "model_categories"}
    WRAPPER_ALLOWED_KEYS = {
        "model_name",
        "model_categories",
        "model_location",
        "use_hub_keras_layers",
        "backend",
        "model_kwargs",
    }
    AUXILIARY_KEYS = {"hf_repo_id", "hf_selected_filename"}
    KNOWN_KEYS = WRAPPER_ALLOWED_KEYS.union(AUXILIARY_KEYS)

    @classmethod
    def from_dict(cls, data: dict[str, Any], logger=None, warn_unknown_keys: bool = True) -> "ImageClassifierModelConfig":
        if not isinstance(data, dict):
            raise ValueError(f"Expected model config dict, got {type(data)}")

        missing_required = [key for key in cls.REQUIRED_KEYS if key not in data]
        if missing_required:
            raise ValueError(f"Missing required model config keys: {missing_required}")

        unknown_keys = [k for k in data.keys() if k not in cls.KNOWN_KEYS]
        if unknown_keys and logger is not None and warn_unknown_keys:
            suggestions = []
            for unknown in unknown_keys:
                close = difflib.get_close_matches(unknown, list(cls.KNOWN_KEYS), n=1)
                if close:
                    suggestions.append(f"{unknown}->{close[0]}")
            suggestion_text = f" (did you mean: {', '.join(suggestions)})" if suggestions else ""
            logger.warning(f"Unsupported image model config keys ignored: {unknown_keys}{suggestion_text}")

        model_name = str(data.get("model_name", "") or "").strip()
        model_location = str(data.get("model_location", "") or "").strip()
        if not model_name:
            raise ValueError("model_name must be a non-empty string")
        if not model_location:
            raise ValueError("model_location must be a non-empty string")

        categories = data.get("model_categories")
        if not isinstance(categories, list) or len(categories) == 0:
            raise ValueError("model_categories must be a non-empty list")
        model_categories = [str(c).strip() for c in categories if str(c).strip()]
        if len(model_categories) == 0:
            raise ValueError("model_categories must contain at least one non-empty category")

        use_hub_keras_layers = bool(data.get("use_hub_keras_layers", False))
        backend = str(data.get("backend", "auto") or "auto").strip().lower()
        if backend == "":
            backend = "auto"

        model_kwargs = data.get("model_kwargs", {})
        if model_kwargs is None:
            model_kwargs = {}
        if not isinstance(model_kwargs, dict):
            raise ValueError("model_kwargs must be a dict when provided")

        hf_repo_id_raw = str(data.get("hf_repo_id", "") or "").strip()
        hf_selected_filename_raw = str(data.get("hf_selected_filename", "") or "").strip()

        return cls(
            model_name=model_name,
            model_location=model_location,
            model_categories=model_categories,
            use_hub_keras_layers=use_hub_keras_layers,
            backend=backend,
            model_kwargs=dict(model_kwargs),
            hf_repo_id=hf_repo_id_raw if hf_repo_id_raw else None,
            hf_selected_filename=hf_selected_filename_raw if hf_selected_filename_raw else None,
        )

    def to_dict(self) -> dict[str, Any]:
        out = {
            "model_name": self.model_name,
            "model_location": self.model_location,
            "model_categories": list(self.model_categories),
            "use_hub_keras_layers": bool(self.use_hub_keras_layers),
            "backend": self.backend,
        }
        if self.model_kwargs:
            out["model_kwargs"] = dict(self.model_kwargs)
        if self.hf_repo_id:
            out["hf_repo_id"] = self.hf_repo_id
        if self.hf_selected_filename:
            out["hf_selected_filename"] = self.hf_selected_filename
        return out

    def to_wrapper_kwargs(self) -> dict[str, Any]:
        kwargs = {
            "model_name": self.model_name,
            "model_location": self.model_location,
            "model_categories": list(self.model_categories),
            "use_hub_keras_layers": bool(self.use_hub_keras_layers),
            "backend": self.backend,
        }
        if self.model_kwargs:
            kwargs["model_kwargs"] = dict(self.model_kwargs)
        return kwargs
