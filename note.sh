project/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── routers/
│       ├── auth.py
│       ├── folders.py
│       └── files.py
├── frontend/
│   └── app.py
├── static/
│   └── upload_cv/
└── requirements.txt


#!/bin/bash

# Create the main project directory
mkdir -p project

# Create the backend structure
mkdir -p project/backend/routers
touch project/backend/main.py
touch project/backend/database.py
touch project/backend/models.py
touch project/backend/schemas.py
touch project/backend/routers/auth.py
touch project/backend/routers/folders.py
touch project/backend/routers/files.py

# Create the frontend structure
mkdir -p project/frontend
touch project/frontend/app.py

# Create the static structure
mkdir -p project/static/upload_cv

# Create requirements.txt
touch project/requirements.txt

echo "Project structure created successfully!"