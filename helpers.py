import tiktoken
import json

# constants
ENCODING = tiktoken.get_encoding("cl100k_base")

def get_token_count(text):
  return len(ENCODING.encode(text))

# DEPRECATED? (see format_messages instead, we use to use this one when we were not inserting json into the prompt)
def transform_message_data(messages):
  transformed_messages = []
  for index, message in enumerate(messages):
    if message['content']:
      transformed_messages.append(
        {
          "message_content": message['content'].replace('\n', '<br>'),
          "message_author": message['author']['name'], 
          "message_timestamp": message['timestamp'], 
          "message_id": index,
          }) 
  return transformed_messages 

# DEPRECATED? we used this when we were not inserting json into the prompt
def build_message_str(message_structured):
  message_str = "[{0}] [{1}] [AUTHOR: {2}] {3}\n\n".format(
    message_structured['message_id'],
    message_structured['message_timestamp'],
    message_structured['message_author'],
    message_structured['message_content']
  )

  token_count = get_token_count(message_str)
  return message_str, token_count 

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
