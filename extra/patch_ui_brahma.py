import sys
from pathlib import Path

path = Path("ui.py")
content = path.read_text(encoding="utf-8")

# Replace standard literal strings
replacements = {
    '"Try asking Rahul AI"': 'f"Try asking {identity.get_assistant_name()}"',
    '"Rahul AI Home"': 'f"{identity.get_application_name()} Home"',
    '"Rahul AI is listening..."': 'f"{identity.get_assistant_name()} is listening..."',
    '"Restart Rahul AI"': 'f"Restart {identity.get_application_name()}"',
    '"Quit Rahul AI"': 'f"Quit {identity.get_application_name()}"',
    '"Hide Rahul AI icon?"': 'f"Hide {identity.get_application_name()} icon?"',
    '"Launch Rahul AI →"': 'f"Launch {identity.get_application_name()} →"',
    '"Tell Rahul AI what to do..."': 'f"Tell {identity.get_assistant_name()} what to do..."',
    '"Ask Rahul AI anything..."': 'f"Ask {identity.get_assistant_name()} anything..."',
    '"Open Rahul AI Home"': 'f"Open {identity.get_application_name()} Home"',
    'self.setWindowTitle("Rahul AI")': 'self.setWindowTitle(identity.get_application_name())',
    'self._app.setApplicationDisplayName("Rahul AI")': 'self._app.setApplicationDisplayName(identity.get_application_name())',
    'self._tray.setToolTip("Rahul AI")': 'self._tray.setToolTip(identity.get_application_name())',
    'self._task_card.set_task("Working on it...", "Rahul AI is processing your request.", 72)': 'self._task_card.set_task("Working on it...", f"{identity.get_assistant_name()} is processing your request.", 72)',
    'self._task_card.set_task("Responding...", "Rahul AI is speaking now.", 100)': 'self._task_card.set_task("Responding...", f"{identity.get_assistant_name()} is speaking now.", 100)',
    'self._task_card.set_task("Ready", "Rahul AI is idle and ready.", 0)': 'self._task_card.set_task("Ready", f"{identity.get_assistant_name()} is idle and ready.", 0)',
}

for k, v in replacements.items():
    content = content.replace(k, v)

# For "Rahul AI: " string slicing
content = content.replace('raw[len("Rahul AI:"):].strip()', 'raw[len(f"{identity.get_assistant_name()}:"):].strip()')

path.write_text(content, encoding="utf-8")
print("ui.py patched for hardcoded strings")
