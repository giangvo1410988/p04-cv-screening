import typesense

client = typesense.Client({
    'nodes': [{
        'host': 'localhost',
        'port': '8108',
        'protocol': 'http'
    }],
    'api_key': 'typesensemulti',
    'connection_timeout_seconds': 2
})

try:
    current_page = 1
    all_documents = []

    while True:
        # Search using a dummy field for `query_by`, such as 'name'
        results = client.collections['candidates'].documents.search({
            'q': '*',               # Wildcard '*' matches all documents
            'query_by': 'name',     # Use any field; replace with a known field if necessary
            'per_page': 100,        # Retrieve 100 documents per page
            'page': current_page    # Track the current page
        })

        # Add the documents from the current page to the list
        all_documents.extend([hit['document'] for hit in results['hits']])

        # Stop if there are no more documents to retrieve
        if len(results['hits']) < 100:
            break

        # Move to the next page
        current_page += 1

    # Print all documents
    for document in all_documents:
        print(document)

except Exception as e:
    print(f"An error occurred: {str(e)}")
