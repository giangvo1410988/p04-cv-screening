from openai import OpenAI


def prompt_general_info(cv_text):
    return  f"""Please extract the above [Resume] exactly according to the corresponding keys and values as the following headers in JSON minified format. 
    (Inside each header below are smaller headers, you must follow strictly that format and do not omit any that small headers even if you cannot find any information about it.)
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
        "linkedln": "string"
    }},
    "skills": ["string"],
    "education": [{{
        "degree": "string",
        "institution_name": "string",
        "major": "string",
        "gpa": "string",
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
    }}]
    }}

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

api_key = "sk-YqojbIFRP8lpP7opSdJ0MpxDuObbyu2cRE8WzT5czyT3BlbkFJ9ulezjJyKYdbKn0nqZ0Z8izB_g0V1EStEvSYYWlSwA"

