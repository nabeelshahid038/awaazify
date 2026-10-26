"""Optional Modal deployment adapter. Requires `pip install -e '.[modal]'` and Modal credentials.
Run: modal serve modal_app.py (from backend directory).
"""
import modal

image = modal.Image.debian_slim(python_version="3.11").pip_install("fastapi>=0.115,<1", "uvicorn>=0.30,<1", "pydantic-settings>=2.5,<3", "httpx>=0.27,<1").add_local_python_source("app")
app = modal.App("awaazify-api")
api_secret = modal.Secret.from_name("awaazify-api-production")

@app.function(image=image, secrets=[api_secret], timeout=300, scaledown_window=120)
@modal.asgi_app()
def web():
    from app.main import app
    return app
