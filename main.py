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

# read the json file
with open(PATH_TO_JSON) as f:
  data = json.load(f)
messages = data['messages']

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
  for message in messages:
    if message['content']:
      messages_contents.append({"message_content": message['content'], "message_token_count": len(ENCODING.encode(message['content']))}) # TODO: can add author info here
  return messages_contents 

# options for time_period are: "24 hours", "3 days", "week", "month"
all_messages = get_messages(messages, 'week')

prompts = {
  0: "The following are messages from a Discord chat. Please summarize the following messages by categorizing the messages into high level topic. Then output those topics as a list of bullet points. Each bullet points should have the name of the topic, a short 1-sentence description, and the number of messages related to that topic in parentheses. For bullets that have 3 or more related messages, please give a more detailed summary in the bullet.\n\n",
  1: "The following messages are from a Discord chat. Please summarize the following messages in a short paragraph that gives a high level overview of the topics discussed.\n\n",
  2: "The following messages are from a Discord chat. Please give me a detailed summary of everything that was discussed. In a separate paragraph, please list all the links that were shared along with a summary of what the links contain if possible.\n\n",
  3: "The following messages are from a Discord chat. Please summarize the following messages in a detailed paragraph.\n\n",
  4: "The following messages are from a Discord chat. Please summarize the following messages in an essay that details the topics covered.\n\n"
}

token_count = 0
prompt_messages = ''
message_summaries = []
# TODO: probably need to customize this to appropriate number of tokens, 2500 is the max amount we target for the prompt (this doesn't include the "role", "content" and other stuff openai adds to the prompt); the thought is this is good enough for the prompt, want to leave ~ 1500 tokens for the actual summary
MAX_TOKEN_COUNT = 2500

def handle_prompt_and_response(prompt_messages):
    prompt = prompts[4] + prompt_messages 
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

# create prompts and send to openai
for index, message in enumerate(all_messages):
  prompt_messages += message["message_content"] + '\n'
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

# TODO / NOTE: i'm not accounting for possibility of all the message summaries being too large to fit in one prompt, should probs throw an error if that happens
if (len(message_summaries) > 1):
  # concatenate all the summaries
  all_summaries = ''
  for summary in message_summaries:
    all_summaries += summary["choices"][0]["message"]["content"] + '\n\n'

  # prompt = "What follows is a list of summaries of messages from a Discord chat. Please summarize the following summaries in a paragraph that gives a high level overview of the topics discussed.\n\n" + all_summaries
  # prompt = "What follows is a list of summaries of messages from The Network State Dicord chat over the course of the last week. Please synthesize the following summaries into a single essay describing each of the summaries in turn. Please err on the side of being too long instead of losing detail.\n\n" + all_summaries
  prompt = "What follows is a list of summaries of messages from The Network State Dicord chat. Please synthesize the following summaries into a single essay summary covering everything. This essay summary is meant to be an update that members can read instead of checking the Discord chat on a daily basis. It should read like an update or briefing.\n\n" + all_summaries

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





