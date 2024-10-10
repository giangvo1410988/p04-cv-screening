
- frontend: streamlit
- backend: fast api, postgres database
website objectives: upload list of cv, job desciption, screen cv 


enduser:

- login (return user_id)
- list all folders will be show in frontend (static/upload_cv/$user_id)
- click to $folder_name can see uploaded files inside (for created folder)
- create new folder (user_id): static/upload_cv/$user_id/$folder_name, at here can upload list files (limit: 200 files (word, pdf only) for each time of upload, max 1 folder is 100,000 files)
    + each downloaded file has the following atttributes: filename, uploaded_date, type (pdf/word), size (MB), words, number_page, language, status (parsed/unparsed) (can be sorted by column), text box to be selected to parsing 
    + having parsing button to parse 
    + having a button to import Job Description and text box to write (copy paste) jd text to here, when click AI search, backend will read inputed jd, or text from text box then search in database cv info, return cv list (matched, cv) 


auth.py file: 
+ crud enduser account
+ admin can delete, pending enduser
+ create account, validate by send otp to email then confirm
 (please return TD graph to show flow of auth also)

these is code for entire project, please fix and update all files if auth.py can sastify requirement
-------------------------------------------------------------------------------


- frontend: streamlit
- backend: fast api, postgres database
website objectives: upload list of cv, job desciption, screen cv 


enduser:

- login (return user_id)
- list all folders will be show in frontend (static/upload_cv/$user_id)
- click to $folder_name can see uploaded files inside (for created folder)
- create new folder (user_id): static/upload_cv/$user_id/$folder_name, at here can upload list files (limit: 200 files (word, pdf only) for each time of upload, max 1 folder is 100,000 files)
    + each downloaded file has the following atttributes: filename, uploaded_date, type (pdf/word), size (MB), words, number_page, language, status (parsed/unparsed) (can be sorted by column), text box to be selected to parsing 
    + having parsing button to parse 
    + having a button to import Job Description and text box to write (copy paste) jd text to here, when click AI search, backend will read inputed jd, or text from text box then search in database cv info, return cv list (matched, cv) 


folders.py file: contain all api related to folder in static/ folder
+ end user can crud folders in ./static/upload_cv/$user_id/$folder_name
+ end user can see number of files in this folder, folder size (MB/GB/KB)
 (please return TD graph to show flow )

these is code for entire project, please fix and update all files if folders.py can sastify requirement
-------------------------------------------------------------------------------

## show all code in repo
#!/bin/bash
cd /Users/giangvo/Desktop/01-projects/p04-cv-screening/
bash << 'EOF' > all_code.txt
# Function to display file content with a header
show_file() {
    if [ -f "$1" ]; then
        echo "========================================"
        echo "File: $1"
        echo "========================================"
        cat "$1"
        echo ""
        echo ""
    fi
}

# Navigate to the project root directory
cd project

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
EOF

echo "All code has been written to all_code.txt"

cd /Users/giangvo/Desktop/01-projects/p04-cv-screening
bash get_text.sh > all_code.txt