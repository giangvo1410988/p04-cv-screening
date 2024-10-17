import typesense

def check_collections():
    client = typesense.Client({
        'nodes': [{
            'host': 'localhost',  # Update with your Typesense server details
            'port': '8108',
            'protocol': 'http',
        }],
        'api_key': 'typesensemulti',  # Use your Typesense API key
        'connection_timeout_seconds': 2
    })

    # List all collections
    return client

def list_documents_in_candidates_collection():
    client = check_collections()

    try:
        # Search for all documents (you can paginate if there are too many documents)
        search_parameters = {
            'q': '*',  # Wildcard to retrieve all documents
            'query_by': 'job_title',  # This can be any field that exists in your collection
            'per_page': 100  # Retrieve up to 100 documents per page
        }
        search_result = client.collections['candidates'].documents.search(search_parameters)

        print("Documents in 'candidates' collection:")
        for hit in search_result['hits']:
            document = hit['document']
            print(f"ID: {document['id']}, Job Title: {document['job_title']}, Industry: {document['industry']}, City: {document['city']}, Skills: {document['skills']}")

    except Exception as e:
        print(f"Error retrieving documents: {e}")

if __name__ == "__main__":
    list_documents_in_candidates_collection()
