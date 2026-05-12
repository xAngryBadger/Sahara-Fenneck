"""Checkpoints: salvar estado da planilha antes de cada alteração do agente; listar e restaurar."""
from .manager import CheckpointInfo, CheckpointManager

__all__ = ["CheckpointManager", "CheckpointInfo"]
