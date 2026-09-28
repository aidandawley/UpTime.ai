import sys
from pathlib import Path

from pydantic import BaseModel
import uagents


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The execution image contains a placeholder uagents 0.1.0 package. Production
# installs the project requirements; this narrow shim lets service tests exercise
# the typed payloads without starting any agents.
if not hasattr(uagents, "Model"):
    uagents.Model = BaseModel
