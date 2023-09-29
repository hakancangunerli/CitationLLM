import streamlit as st
import openai
import os, requests,json
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
load_dotenv()
st.title(os.getenv("APP_NAME"))
# App title
# Create a sidebar with navigation links
page = st.sidebar.selectbox("Navigation", ["Home", "Citations"])

# Initialize citations in session state
if "citations" not in st.session_state:
    st.session_state["citations"] = {}

# Initialize conversation history
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": os.getenv("WELCOME_MESSAGE")}]

# Function to extract citations
def extract_citations(json_data):
    citations = []
    
    # Traverse the JSON structure to find citations
    if "choices" in json_data and len(json_data["choices"]) > 0:
        for choice in json_data["choices"]:
            if "message" in choice and "context" in choice["message"]:
                messages = choice["message"]["context"]["messages"]
                for message in messages:
                    if "content" in message:
                        content = message["content"]
                        # Extract citations from the "content" field
                        # Assuming citations are enclosed in square brackets
                        citation_start = content.find("[")
                        citation_end = content.find("]")
                        if citation_start != -1 and citation_end != -1:
                            citations.append(content[citation_start + 1:citation_end])
    
    return citations


def generate_response(messages):
   

    openai.api_type = os.getenv("OPENAI_API_TYPE")

    # Azure OpenAI on your own data is only supported by the 2023-08-01-preview API version
    openai.api_version = os.getenv("OPENAI_API_VERSION")

    # Azure OpenAI setup
    openai.api_base = os.getenv("OPENAI_API_BASE")
    openai.api_key = os.getenv("OPENAI_KEY")
    deployment_id = os.getenv("DEPLOYMENT_ID") # Add your deployment ID here
    # Azure Cognitive Search setup
    search_endpoint = os.getenv("SEARCH_ENDPOINT") # Add your Azure Cognitive Search endpoint here
    search_key = os.getenv("SEARCH_KEY")
    search_index_name = os.getenv("AZURE_SEARCH_INDEX_NAME") # Add your Azure Cognitive Search index name here
    def setup_byod(deployment_id: str) -> None:
        class BringYourOwnDataAdapter(requests.adapters.HTTPAdapter):

            def send(self, request, **kwargs):
                request.url = f"{openai.api_base}/openai/deployments/{deployment_id}/extensions/chat/completions?api-version={openai.api_version}"
                return super().send(request, **kwargs)

        session = requests.Session()

        # Mount a custom adapter which will use the extensions endpoint for any call using the given `deployment_id`
        session.mount(
            prefix=f"{openai.api_base}/openai/deployments/{deployment_id}",
            adapter=BringYourOwnDataAdapter()
        )

        openai.requestssession = session
    setup_byod(deployment_id)
    conversation = [
        {"role": "system", "content": os.getenv("FIRST_PROMPT")},
    ]
    conversation.extend(messages)
    
    completion = openai.ChatCompletion.create(
        messages=conversation,
        deployment_id=deployment_id,
        dataSources=[  # camelCase is intentional, as this is the format the API expects
            {
                "type": "AzureCognitiveSearch",
                "parameters": {
                    "endpoint": search_endpoint,
                    "key": search_key,
                    "indexName": search_index_name,
                }
            }
        ]
    )
    answer = completion['choices'][0]['message']['content']
    extract_citations(completion)   
    citations = completion["choices"][0]["message"]["context"]["messages"][0]["content"]
    
    # export this citations into a json file 
    # Remove backslashes and newline characters
    cleaned_string = citations.replace("\\", "").replace("\n", "")

    # Remove the first and last double quotes
    if cleaned_string.startswith("\""):
        cleaned_string = cleaned_string[1:]
    if cleaned_string.endswith("\""):
        cleaned_string = cleaned_string[:-1]

    citations_as_json = json.loads(cleaned_string)
    
    # Extract the "citations" list from the data
    citations = citations_as_json.get("citations", [])

    cite_list = {}
    # Loop through the citations and print them with numbers
    for i, citation in enumerate(citations, start=1):
        content = citation.get("content", "")
        cite_list[i]= content
        # the x has the citation
    import re
    # replace [doc1] and [doc2] with 1,2
    answer = re.sub(r'\[doc(\d+)\]', r'(See Document \1)', answer)
    
    answer = answer.replace("{endOfTokens}", "")
    
    return f"{answer}", cite_list






if page == "Home":
    # Display chat messages
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # User-provided input
    if (prompt := st.chat_input()):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

    # Generate a new response if the last message is not from the assistant
    if st.session_state["messages"][-1]["role"] != "assistant":
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response,citations = generate_response(st.session_state["messages"]) 
                st.write(response)
        st.session_state["messages"].append({"role": "assistant", "content": response})
        # Add citations to the session state
        st.session_state["citations"] = citations


def extract_citations(json_data):
    citations = []
    
    # Traverse the JSON structure to find citations
    if "choices" in json_data and len(json_data["choices"]) > 0:
        for choice in json_data["choices"]:
            if "message" in choice and "context" in choice["message"]:
                messages = choice["message"]["context"]["messages"]
                for message in messages:
                    if "content" in message:
                        content = message["content"]
                        # Extract citations from the "content" field
                        # Assuming citations are enclosed in square brackets
                        citation_start = content.find("[")
                        citation_end = content.find("]")
                        if citation_start != -1 and citation_end != -1:
                            citations.append(content[citation_start + 1:citation_end])
    
    return citations        
        
# Citations page content
if page == "Citations":
    # Access citations from session state
    citations = st.session_state.get("citations", {})
    
    st.title("Citations")
    if not citations:
        st.warning("No citations available.")
    else:
        # Display citations
        for key, citation_text in citations.items():
            with st.expander(f"Document {key}"):
                st.text(citation_text)
