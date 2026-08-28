import os

file_path = r'd:\TiTech Prabha Solution\Rahul AI\Rahul AI\Rahul AI-AI---Lite-main\Rahul AI-AI---Lite-main\assets\web_background\index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

if 'accelerateReactor' not in text:
    js_code = """
        // Added for setup wizard boot sequence
        window.accelerateReactor = function() {
            // Speed up the rotation drastically for the boot sequence
            if (window.controls) {
                window.controls.autoRotateSpeed = 25.0;
            }
        };
    """
    text = text.replace('</script>', js_code + '\n</script>')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print('Added accelerateReactor to index.html')
else:
    print('accelerateReactor already exists')
