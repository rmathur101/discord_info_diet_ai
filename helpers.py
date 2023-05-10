import tiktoken
import json

# constants
ENCODING = tiktoken.get_encoding("cl100k_base")

def get_token_count(text):
  return len(ENCODING.encode(text))

def format_messages(messages):
    formatted_messages = []
    
    for message in messages:
        # print(message)
        formatted_message = {
            "id": message["id"],
            "type": message["type"],
            "author_name": message["author"]["name"],
            "timestamp": message["timestamp"],
            "content": message["content"].replace("\n", "<br>"),
            "reactions": [{"emoji_name": reaction["emoji"]["code"], "count": reaction["count"]} for reaction in message["reactions"]],
            "mentions": [mention["name"] for mention in message["mentions"]],
            "reference_messageId": message.get("reference", {}).get("messageId", None)
        }
        formatted_messages.append(json.dumps(formatted_message))
    
    return formatted_messages
