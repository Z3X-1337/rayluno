from __future__ import annotations

from pathlib import Path

path = Path("src/future_assistant/runtime.py")
text = path.read_text(encoding="utf-8")
old_setup = """    config = config or AssistantConfig.from_env()\n    actions = ActionFactory(config)\n    deterministic = RouterPlanner(DeterministicRouter(actions))\n"""
new_setup = """    config = config or AssistantConfig.from_env()\n    resolved_effects = effects or SystemEffects()\n    actions = ActionFactory(config)\n    deterministic = RouterPlanner(\n        DeterministicRouter(actions, clock=resolved_effects.current_time)\n    )\n"""
old_effects = """        effects or SystemEffects(),\n"""
new_effects = """        resolved_effects,\n"""
if text.count(old_setup) != 1:
    raise SystemExit("Expected build_runtime setup block exactly once.")
if text.count(old_effects) != 1:
    raise SystemExit("Expected AssistantRuntime effects argument exactly once.")
text = text.replace(old_setup, new_setup).replace(old_effects, new_effects)
path.write_text(text, encoding="utf-8")
