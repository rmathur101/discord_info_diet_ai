import tiktoken

# constants
ENCODING = tiktoken.get_encoding("cl100k_base")

def get_token_count(text):
  return len(ENCODING.encode(text))

def transform_message_data(messages):
  transformed_messages = []
  for index, message in enumerate(messages):
    if message['content']:
      messages_contents.append(
        {
          "message_content": message['content'].replace('\n', '<br>'),
          "message_author": message['author']['name'], 
          "message_timestamp": message['timestamp'], 
          "message_id": index,
          }) 
  return transformed_messages 

def build_message_str(message_structured):
  message_str = "[{0}] [{1}] [AUTHOR: {2}] {3}\n\n".format(
    message['message_id'],
    message['message_timestamp'],
    message['message_author'],
    message['message_content']
  )

  token_count = get_token_count(message_str)
  return message_str, num_tokens