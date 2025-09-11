from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
import shutil
import os
import subprocess
import traceback

app = FastAPI()

# Temporary folder for uploaded images
TMP_DIR = "/tmp/ollama_images"
os.makedirs(TMP_DIR, exist_ok=True)

# Ollama model name
MODEL_NAME = "llama3.2-vision"

@app.post("/process")
async def process_image(prompt: str = Form(...), file: UploadFile = File(...)):
    try:
        # Save uploaded image
        image_path = os.path.join(TMP_DIR, file.filename)
        with open(image_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Run Ollama CLI to handle the image
        result = subprocess.run(
            [
                "ollama",
                "run",
                MODEL_NAME,
                "--prompt", prompt,
                "--image", image_path
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return JSONResponse(
                content={"error": f"Ollama CLI error: {result.stderr}"},
                status_code=500
            )

        answer_text = result.stdout.strip()

        return JSONResponse(content={"prompt": prompt, "answer": answer_text})

    except Exception as e:
        print(traceback.format_exc())
        return JSONResponse(content={"error": str(e)}, status_code=500)
