#!/bin/bash

# Function to display file content with a header
show_file() {
    if [ -f "$1" ]; then
        # Convert filename to lowercase for comparison
        filename=$(echo "$1" | tr '[:upper:]' '[:lower:]')
        if [[ "$filename" != *.pdf ]] && [[ "$1" != *"/static/"* ]]; then
            echo "========================================"
            echo "File: $1"
            echo "========================================"
            cat "$1"
            echo ""
            echo ""
        fi
    fi
}

# Navigate to the project root directory
cd /Users/giangvo/Desktop/01-projects/p04-cv-screening/project

# Display backend files
show_file backend/main.py
show_file backend/database.py
show_file backend/models.py
show_file backend/schemas.py
show_file backend/routers/auth.py
show_file backend/routers/folders.py
show_file backend/routers/files.py

# Display frontend files
show_file frontend/app.py

# Display requirements.txt
show_file requirements.txt

echo "Script completed."