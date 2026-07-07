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

In this service we list several apis, which have the following request response contracts
```bash
-- /api/opt_details/info/{operator_id}
-- reponse data:{
	"status": "OK",
	"message": "Operator retrieved successfully",
	"data": {
		"operator": [
		{
			"optId": "OPT12345",
			"name": "John Doe",
			"email": "johndoe@example.com",
			"reg": "RegName",
			"regCode": "RC001",
			"ea": "EAName",
			"eaCode": "EA002",
			"pincode": "560001",
			"district": "Bengaluru",
			"state": "Karnataka",
			"ro": "RO_South",
			"machineCode": "MCH-9981",
			"riskScore": 14.5
		}
		]
	}
}
```

```bash
-- /api/opt_details/sid/{sid}
-- reponse data:{
		'success': True, 
		'message': 'Operator details retrieved successfully', 
		'data': {'operator': 
			{
				'operator': [
				{
					'optId': 'WCDKOJ_NS776624', 
					'name': 'Sahanaj Parvina Mondal', 
					'email': '', 
					'reg': 'WCD Assam', 
					'regCode': '991.0', 
					'ea': 'WCD Assam', 
					'eaCode': '991', 
					'pincode': '783337.0', 
					'district': 'Kokrajhar', 
					'state': 'Assam', 
					'ro': 'Guwahati', 
					'machineCode':'LENOVOB053F1E5-F10A-21BD-6B6F-F2D672CCA9A',
                    'riskScore': 0.04
				}
			],
			'pktType': 'U', 
			'id': 'S132222983161020260418055209'
            'idType':'sid'
			}
		}
	}
```



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

## Current Deployed IP:-
10.10.118.48:8000

