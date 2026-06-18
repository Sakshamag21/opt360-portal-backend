(# Operator360 API)

Operator360 API is a FastAPI-based service for managing signals and features used by the Operator360 system. It exposes REST endpoints for creating and retrieving features and signals, backed by utility helpers in `src/utils`.

**Contents**
- `src/main.py` - application entrypoint and FastAPI app configuration
- `src/routes.py` - router registration and API routes
- `src/feature/` - feature-related handlers (`create_feature.py`, `get_feature.py`)
- `src/signals/` - signal-related handlers (`create.py`, `info.py`, `info_id.py`)
- `src/utils/` - helper modules for DB and responses
- `resources/config.yaml` - runtime configuration
- `requirements.txt` - Python dependencies

## Requirements

- Python 3.10+
- Install dependencies from `requirements.txt`.

## Installation

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # on Windows use: .venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the app

Run the application using the included entrypoint. By default it starts on port 8000:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

You can set the `PORT` environment variable to override the port used by the app.

## API

All routes are mounted under the `/api` prefix. The app exposes endpoints for creating and fetching features and signals. Start the server and visit the interactive docs at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Configuration

Application configuration is read from `resources/config.yaml` and environment variables where applicable. Review `src/config/config.py` for details on how configuration values are loaded.

## Development

- Run with `--reload` for local development.
- Add tests and run them before committing changes.

## Project Structure

```
Dockerfile
README.md
requirements.txt
resources/
	config.yaml
src/
	main.py
	routes.py
	feature/
		create_feature.py
		get_feature.py
	opt_details/
		info.py
	signals/
		create.py
		info.py
		info_id.py
	utils/
		database.py
		response.py
```

## Notes & Next Steps

- This README provides quick start instructions; extend it with endpoint examples, authentication details, and deployment notes as the project evolves.
- I can add example `curl` commands, a `docker-compose.yml`, or a `CONTRIBUTING.md` if you want—tell me which.

