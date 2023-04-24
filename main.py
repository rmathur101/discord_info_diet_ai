import sys
from dotenv import load_dotenv
import openai
import json
import os
import tiktoken
from transformers import GPT2TokenizerFast
import datetime
load_dotenv()

# set my API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# path to discord json file
PATH_TO_JSON = '/Users/Shared/test_discord_export/The Network State - TNS - lectures [902967453183778836] (after 2023-03-01).json'

# openai constants
COMPLETIONS_MODEL = os.getenv("COMPLETIONS_MODEL")
COMPLETIONS_MODEL_MAX_TOKENS = int(os.getenv("COMPLETIONS_MODEL_MAX_TOKENS"))
COMPLETIONS_MODEL_TEMP = float(os.getenv("COMPLETIONS_MODEL_TEMP"))
ENCODING = tiktoken.get_encoding("cl100k_base")

# openai api params
COMPLETIONS_API_PARAMS = {
    "model": COMPLETIONS_MODEL,
    "temperature": COMPLETIONS_MODEL_TEMP, # We use temperature of 0.0 because it gives the most predictable, factual answer.
    # "top_p": 1
    # "max_tokens": COMPLETIONS_MODEL_MAX_TOKENS, # testing no max tokens limit, hoping that as long as i can be below the context length, the api can figure out num tokens to return
}

def get_token_count(text):
  return len(ENCODING.encode(text))

# read the json file
with open(PATH_TO_JSON) as f:
  data = json.load(f)
messages = data['messages']

def build_message(message):
  return "[" + str(message["message_id"]) + "] " + "[" + message["message_timestamp"] + "] " + "[AUTHOR: " + message["message_author"] + "] " + message["message_content"] + '\n\n'

# The idea is that we want to get messages over a given time period.
# The user will select using the following options:
# Last 24 hours
# Last 3 days 
# Last week
# Last month
# NOTE: you might also consider a custom time period
def get_messages(messages, time_period=None):
  if time_period == '24 hours':
    time_period_num = 1
  elif time_period == '3 days':
    time_period_num = 3
  elif time_period == 'week':
    time_period_num = 7
  elif time_period == 'month':
    time_period_num = 30
  elif (time_period == None):
    time_period_num = 1 
  else:
    time_period_num = 1 

  # current_date = datetime.datetime.now() # for testing purposes we use a fixed date afer the last message's timestamp TODO: this is hardcoded!!! if / when we have a real system we will want to go off of the current date
  current_date = datetime.datetime(2023, 4, 6)

  # substract time period num from current date to get the date of the lower bound of the time period
  time_period_date = current_date - datetime.timedelta(days=time_period_num)

  # TODO: i've removed the timezone stuff from the format str because it was causing issues (seemed complicated to extract timezone), will have to fix later or not
  def convert_message_timestamp_to_datetime(timestamp_str):
    if '.' in timestamp_str:
      format_str = '%Y-%m-%dT%H:%M:%S.%f'
    else:
      format_str = '%Y-%m-%dT%H:%M:%S'
    date_obj = datetime.datetime.strptime(timestamp_str[:-6], format_str)
    return date_obj

  # get messages from the last time period
  messages = [message for message in messages if convert_message_timestamp_to_datetime(message['timestamp']).timestamp() > time_period_date.timestamp()]

  messages_contents = []
  for index, message in enumerate(messages):
    if message['content']:
      messages_contents.append(
        {
          "message_content": message['content'].replace('\n', '<br>'),
          "message_token_count": len(ENCODING.encode(message['content'])),
          "message_author": message['author']['name'], 
          "message_timestamp": message['timestamp'], 
          "message_id": index,
          }) # TODO: can add author info here
  return messages_contents 

# options for time_period are: "24 hours", "3 days", "week", "month"
all_messages = get_messages(messages, '24 hours')

prompts = {
  16: "I have a series of messages formatted as follows:\n\n[message ID] [timestamp] [AUTHOR: username] Message content with line breaks represented by <br>.\n\nHere are the messages:\n\n<Insert Discord messages here>\n\nPlease carefully analyze the messages and generate a comprehensive list of topics discussed in these messages. Make sure to include as many relevant topics as possible, even if they are only mentioned briefly or in a single message. Your goal is to provide an exhaustive overview of the subjects discussed in the conversation."

}

token_count = 0
prompt_messages = ''
message_summaries = []
# TODO: probably need to customize this to appropriate number of tokens, 2500 is the max amount we target for the prompt (this doesn't include the "role", "content" and other stuff openai adds to the prompt); the thought is this is good enough for the prompt, want to leave ~ 1500 tokens for the actual summary
MAX_TOKEN_COUNT = 2500
# MAX_TOKEN_COUNT = 1000

def handle_prompt_and_response(prompt_messages):
  # prompt = prompts[13] + prompt_messages 
  prompt = prompts[16].replace("<Insert Discord messages here>", prompt_messages)
  print("*" * 100)
  print("PROMPT")
  print(prompt)
  print("Prompt Num Tokens: " + str(len(ENCODING.encode(prompt))))
  print("*" * 100)
  print('\n')

  response = openai.ChatCompletion.create(
    messages=[{"role": "user", "content": prompt}], 
    **COMPLETIONS_API_PARAMS)

  message_summaries.append(response)
  return None

def get_model_response(prompt):
  print("*" * 100)
  print("PROMPT")
  print(prompt)
  print("Prompt Num Tokens: " + str(len(ENCODING.encode(prompt))))
  print("*" * 100)
  print('\n')

  response = openai.ChatCompletion.create(
    messages=[{"role": "user", "content": prompt}], 
    **COMPLETIONS_API_PARAMS)

  return response 

# create prompts and send to openai
for index, message in enumerate(all_messages):
  # prompt_messages += message["message_timestamp"] + ": " +  message["message_content"] + ' ' + 'AUTHOR: ' + message["message_author"] + '\n\n'
  prompt_messages += build_message(message) 
  #TODO: shouldn't i just compute the message token count here?
  token_count += message["message_token_count"]

  if (index == len(all_messages) - 1):
    handle_prompt_and_response(prompt_messages)

  elif ((token_count + all_messages[index + 1]["message_token_count"]) > MAX_TOKEN_COUNT):
    handle_prompt_and_response(prompt_messages)

    # reset token count and prompt messages
    token_count = 0
    prompt_messages = ''
  else:
    continue

print("MESSAGE SUMMARIES")
print(message_summaries)

# the purpose of this section is to have the model assign a topic (from the list of topics already generated) to each message 
SHOULD_RUN_TOPIC_CAT = True

if(SHOULD_RUN_TOPIC_CAT):

  # we choose 2000 because we assume the completion tokens will be about the same as the prompt tokens assuming that the output contains each message and associated category; therefore we allot 2000 for the prompt tokens and leave 2000 for completion tokens which comes out to 4000 which is just under the limit for the model
  MAX_PROMPT_TOKEN_COUNT_FOR_TOPIC_CAT = 3000

  BASE_PROMPT="I have a series of messages formatted as follows:\n\n[message ID] [timestamp] [AUTHOR: username] Message content with line breaks represented by <br>\n\nHere are the messages:\n\n<Insert Discord messages here>\n\nPlease categorize each message by the following topics:\n\n<Insert topics here>\n\nIt is crucial to categorize every single message without exception. If a message doesn't seem to apply to any of the topics or is difficult to categorize, you must place it under \"Miscellaneous\". A message can be assigned to multiple topics if applicable.\n\nFormat the message categorization output as follows: \n- Do not use numbering for the topics.\n- Write the topic name followed by a colon.\n- After the colon, write ' Message IDs' followed by the list of message IDs separated by commas.\n- Start a new line for each topic.\n\nExample Output:\nBitcoin and cryptocurrency: Message IDs 1, 4, 7\nLiving in the USA: Message IDs 2, 6\nMiscellaneous: Message IDs 3, 5, 8"


  TOPICS = message_summaries[0]["choices"][0]["message"]["content"]

  BASE_AND_TOPICS_PROMPT = BASE_PROMPT.replace("<Insert topics here>", TOPICS)

  BASE_AND_TOPICS_PROMPT_TOKEN_COUNT = get_token_count(text=BASE_AND_TOPICS_PROMPT)

  # if this token count is greater than the max of the model throw an error
  if (BASE_AND_TOPICS_PROMPT_TOKEN_COUNT > COMPLETIONS_MODEL_MAX_TOKENS):
    raise ValueError("BASE_AND_TOPICS_PROMPT_TOKEN_COUNT > COMPLETIONS_MODEL_MAX_TOKENS. This is even before we add the discord messages! Obviously this shouldn't happen. Investigate!")

  discord_messages_for_prompt = ''
  for index, message in enumerate(all_messages):
    single_message = build_message(message)
    discord_messages_for_prompt += single_message 

    # this condition means that we have reached the end of the messages and we need to handle the last prompt
    if (index == len(all_messages) - 1):
      final_prompt = BASE_AND_TOPICS_PROMPT.replace("<Insert Discord messages here>", discord_messages_for_prompt)
      resp = get_model_response(prompt=final_prompt)
      print("RESPONSE")
      print(resp)
      continue

    next_single_message = build_message(all_messages[index + 1])
    check_max_discord_messages_for_prompt = discord_messages_for_prompt + next_single_message
    check_max_discord_messages_for_prompt_token_count = get_token_count(text=check_max_discord_messages_for_prompt)

    if (BASE_AND_TOPICS_PROMPT_TOKEN_COUNT + check_max_discord_messages_for_prompt_token_count > MAX_PROMPT_TOKEN_COUNT_FOR_TOPIC_CAT):
      final_prompt = BASE_AND_TOPICS_PROMPT.replace("<Insert Discord messages here>", discord_messages_for_prompt)
      discord_messages_for_prompt = ''
      resp = get_model_response(prompt=final_prompt)
      print("RESPONSE")
      print(resp)
      continue

exit()

# TODO / NOTE: i'm not accounting for possibility of all the message summaries being too large to fit in one prompt, should probs throw an error if that happens
if (len(message_summaries) > 1):
  # concatenate all the summaries
  all_summaries = ''
  for summary in message_summaries:
    all_summaries += summary["choices"][0]["message"]["content"] + '\n\n'

  # prompt = "What follows is a list of summaries of messages from a Discord chat. Please summarize the following summaries in a paragraph that gives a high level overview of the topics discussed.\n\n" + all_summaries
  # prompt = "What follows is a list of summaries of messages from The Network State Dicord chat over the course of the last week. Please synthesize the following summaries into a single essay describing each of the summaries in turn. Please err on the side of being too long instead of losing detail.\n\n" + all_summaries
  # prompt = "What follows is a list of summaries of messages from The Network State Dicord chat. Please synthesize the following summaries into a single essay summary covering everything. This essay summary is meant to be an update that members can read instead of checking the Discord chat on a daily basis. It should read like an update or briefing.\n\n" + all_summaries # this is an essay summary, but want to try the bullet version
  # prompt = "What follows is a series of bulleted lists which contain topics discussed in The Network State Dicord chat. A list of authors who participated in the discussion of the topic are listed in parentheses next to each topic. Please synthesize the the bulleted lists into a single list.\n\n" + all_summaries # this doesn't seem to compress the list at all, it just smooshes it all together
  prompt = "What follows is a series of bulleted lists which contain topics discussed in The Network State Dicord chat. A list of authors who participated in the discussion of the topic are listed in parentheses next to each topic. Please synthesize/compress the bulleted lists into a single list. If there are related topics, please summarize them as a single topic. Please put the list of authors who participated in the discussion of the topic in parentheses next to each topic in the final list.\n\n" + all_summaries # this doesn't seem to compress the list at all, it just smooshes it all together

  response = openai.ChatCompletion.create(
    messages=[{"role": "user", "content": prompt}], 
    **COMPLETIONS_API_PARAMS)

  print('\n')
  print("*" * 100)
  print(prompt)
  print("Prompt Num Tokens: " + str(len(ENCODING.encode(prompt))))
  print("*" * 100)
  print('\n')
  print("FINAL SUMMARY")
  print(response)
  None
  # TODO: this is where i create prompt to summarize the summaries
else:
  print('\n')
  print("FINAL SUMMARY")
  print(message_summaries[0])





