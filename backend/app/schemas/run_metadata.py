"""Schemas for run configuration metadata."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import BackendTarget, EasyGoal, RunAlgorithm


class ConfigChoiceMetadata(BaseModel):
    """Metadata for a selectable run-configuration registry item."""

    id: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    supported_algorithms: list[RunAlgorithm] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EasyGoalPresetMetadata(BaseModel):
    """Target value advertised for an easy-mode goal tier."""

    goal: EasyGoal
    label: str
    chemical_accuracy_target_ha: float = Field(gt=0)


class RunConfigMetadataResponse(BaseModel):
    """Registry-backed metadata needed to build algorithm configuration controls."""

    catalog_version: str
    algorithms: list[RunAlgorithm]
    backend_targets: list[BackendTarget]
    easy_goals: list[EasyGoal]
    easy_goal_presets: list[EasyGoalPresetMetadata]
    ansatzes: list[ConfigChoiceMetadata]
    optimizers: list[ConfigChoiceMetadata]
    limits: dict[str, dict[str, int | float]] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, dict[str, bool]] = Field(default_factory=dict)
    recommendations: dict[str, dict[str, dict[str, Any]]] = Field(default_factory=dict)
