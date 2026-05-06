# -*- coding: utf-8 -*-
"""Checkpoints: salvar estado da planilha antes de cada alteração do agente; listar e restaurar."""
from .manager import CheckpointManager, CheckpointInfo

__all__ = ["CheckpointManager", "CheckpointInfo"]
