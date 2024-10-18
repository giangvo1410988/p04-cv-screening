from openai import OpenAI
import openai

def prompt_general_info(cv_text):
    return  f"""Please extract the above [Resume] exactly according to the corresponding keys and values as the following headers in JSON minified format. 
    (Inside each header below are smaller headers, you must follow strictly that format and do not omit any that small headers even if you cannot find any information about it.)
    If "years of experience" is not specified in the resume, calculate it based on the provided work experience. To calculate the total years of experience, follow these rules:
    - Use the difference between the "start_time" and "end_time" of each experience to calculate the duration for that job.
    - If "end_time" is not provided or set as "Present", assume the job is ongoing and calculate the years of experience up to the current date.
    - Add up the durations of all jobs to calculate the total years of experience.
    - If the "start_time" or "end_time" is missing, do not include that job in the calculation.
    - If no valid dates are provided, do not calculate the "years of experience".

    {{
    "personal_information": {{
        "full_name": "string",
        "industry": "string",
        "job_title": "string",
        "level": "string",
        "phone": "string",
        "address": "string",
        "city/province": "string",
        "country": "string",
        "date_of_birth": "string",
        "gender": "string",
        "linkedln": "string",
        "yoe": "number (calculated from the experience section if not directly provided, otherwise, use the provided value)"
    }},
    "skills": ["string"],
    "education": [{{
        "degree": "string",
        "institution_name": "string",
        "major": "string",
        "gpa": "string (if GPA is on a 4-point scale, convert it to a 10-point scale using the formula: (gpa/4)*10)",
        "start_time": "string",
        "end_time": "string"
    }}],
    "certificates": {{ 
        "language_certificates": [{{
        "language": "string",
        "certificate_name": "string", 
        "certificate_point_level": "string",
        "start_time": "string",
        "end_time": "string"
        }}],
        "other_certificates": [{{
        "certificate_name": "string",
        "certificate_point": "string",
        "start_time": "string",
        "end_time": "string"
        }}]
    }},
    "projects": [{{
        "project_name": "string",
        "start_time": "string",
        "end_time": "string",
        "detailed_descriptions": ["string"]
    }}],
    "objectives": "string",
    "awards": [{{
        "award_name": "string",
        "time": "string",
        "description": "string"
    }}],
    "work_experience": [{{
        "company_name": "string",
        "job_title": "string",
        "start_time": "string",  // date format: YYYY-MM-DD
        "end_time": "string",  // date format: YYYY-MM-DD or "NOW" if current job
        "job_descriptions": ["string"],  // List of job responsibilities and achievements
        "industry": "string",  // Industry of the company
        "achievements": "String",
        "level": "Strig" // Jr, Senior,...
    }}]
    }}

    Include all available work experiences, listing them in reverse chronological order (most recent first). If any information is not available, use an empty string or empty list as appropriate. Ensure all dates are in YYYY-MM-DD format.

    CV Text:
    {cv_text}
    """


def prompt_experience(cv_text):
    return f"""Please extract the work experience information from the following CV text. Return the result in JSON minified format, following this structure:

    {{
        "work_experience": [
            {{
                "company_name": "string",
                "job_title": "string",
                "start_time": "string", // date format: YYYY-MM-DD
                "end_time": "string", // date format: YYYY-MM-DD or "NOW" if current job
                "job_descriptions": ["string"], // List of job responsibilities and achievements
                "industry": "string", // Industry of the company
                "company_location": {{
                    "city": "string",
                    "country": "string"
                }}
            }}
        ]
    }}

    Include all available work experiences, listing them in reverse chronological order (most recent first). If any information is not available, use an empty string or empty list as appropriate. Ensure all dates are in YYYY-MM-DD format.

    CV Text:
    {cv_text}
    """

def prompt_job_description(job_description_text):
    return f"""Extract key details from the Job Description below. Represent them in JSON format, focusing on keywords for optimized search. Avoid special characters like quotation marks, slashes, and parentheses.

{{
    job_title: string,
    industry: string,
    company_name: string,
    location: {{
        city: string,
        country: string
    }},
    employment_type: string,
    level: string,
    age_range: {{
        min_age: integer,
        max_age: integer
    }},
    job_requirements: {{
        skills: [string],
        languages: [string],
        experience: {{
            years_of_experience: integer,
            specific_experience: [string]
        }},
        education: {{
            degree: string,
            major: string
        }},
        points: {{
            min_points: integer,
            max_points: integer
        }}
    }},
    salary: string,
    start_time: string
}}

Job Description Text:
{job_description_text}
"""


def call_openAI(text="", api_key=""):
    client = OpenAI(api_key = api_key)
    model="gpt-4o-mini-2024-07-18"
    print("==> text: ", text)
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": text,
            }
        ],
        model=model,
        temperature=0,
    )

    response_openai=chat_completion.choices[0].message.content
    token_out=chat_completion.usage.completion_tokens
    token_in=chat_completion.usage.prompt_tokens
    return response_openai, token_in, token_out

def generate_embedding(text: str, model="text-embedding-ada-002", api_key=""):
    # Initialize the OpenAI client with your API key
    client = OpenAI(api_key=api_key)
    
    # Replace newlines in the input text
    text = text.replace("\n", " ")
    
    # Use the client to create embeddings
    response = client.embeddings.create(
        input=[text],
        model=model
    )
    
    # Extract the embedding from the response
    embedding = response.data[0].embedding
    return embedding


api_key = "sk-G38Ai7gpt2YT0MfKy2o1-q5KMmCqt4d3x0fdxb03UKT3BlbkFJPMZpKII6a4EhJYz-81n25Z_Sp8yYmdWQ1uUZojZ-gA"