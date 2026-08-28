import sys
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

# Replace "Rahul AI" with {identity.get_application_name()} in logs and strings where applicable
content = content.replace('output="Rahul AI is inspecting the screen for what you asked about."', 'output=f"{identity.get_application_name()} is inspecting the screen for what you asked about."')
content = content.replace('f"Rahul AI: {detail}"', 'f"{identity.get_assistant_name()}: {detail}"')
content = content.replace('f"Rahul AI: {answer}"', 'f"{identity.get_assistant_name()}: {answer}"')
content = content.replace('f"Rahul AI: {preview}"', 'f"{identity.get_assistant_name()}: {preview}"')
content = content.replace('output="Rahul AI is drafting a direct reply."', 'output=f"{identity.get_application_name()} is drafting a direct reply."')
content = content.replace('f"Rahul AI: {reply}"', 'f"{identity.get_assistant_name()}: {reply}"')
content = content.replace('f"Rahul AI: {tool_voice}"', 'f"{identity.get_assistant_name()}: {tool_voice}"')
content = content.replace('f"Rahul AI: {full_out}"', 'f"{identity.get_assistant_name()}: {full_out}"')
content = content.replace('"SYS: Rahul AI online."', 'f"SYS: {identity.get_application_name()} online."')
content = content.replace('"SYS: Mobile Connect is already running in another Rahul AI instance."', 'f"SYS: Mobile Connect is already running in another {identity.get_application_name()} instance."')
content = content.replace('"You are Rahul AI, a concise, helpful desktop assistant. "', 'f"You are {identity.get_application_name()}, a concise, helpful desktop assistant. "')
content = content.replace("close the assistant, say goodbye, or stop Rahul AI.", "{identity.get_application_name()}")
content = content.replace("Rahul AI automatically infers", "{identity.get_application_name()} automatically infers")
content = content.replace("If omitted, Rahul AI infers", "If omitted, {identity.get_application_name()} infers")
content = content.replace("'Rahul AI', 'hey', 'hi', and 'hello'.", "f\"'{identity.get_application_name()}', 'hey', 'hi', and 'hello'.\"")

path.write_text(content, encoding="utf-8")
print("main.py patched for hardcoded strings")
