import sys
from dotenv import load_dotenv
import openai
import json
import os
import tiktoken
from transformers import GPT2TokenizerFast
from datetime import datetime, date, timedelta
import subprocess
from pathlib import Path
import re
from helpers import get_token_count, transform_message_data, build_message_str
load_dotenv()

# constants 
DISCORD_EXPORT_DIR_PATH = os.getenv('DISCORD_EXPORT_DIR_PATH') 
DISCORD_EXPORT_DIR_PATH_RAW = os.getenv('DISCORD_EXPORT_DIR_PATH_RAW') 
DISCORD_TOKEN_ID = os.getenv('DISCORD_TOKEN_ID')
CHANNEL_AND_THREAD_IDS = {
    'lectures': {
        'id': '902967453183778836',
    },
    'staying_ahead_ai_accel': {
        'id': '1088550425524961360'
    },
    'proof_of_building': {
        'id': '1086919421790015629'
    },
    'proof_of_workout': {
        'id': '915652523677868042'
    },
    'educational_contents_for_builders': {
        'id': '1043848628097261658'
    },
    'proof_of_learning': {
        'id': '919209947072434176'
    },
    'building_wealth_and_sharing_alpha': {
        'id': '950184868837490748'
    },
    'tns_nostr': {
        'id': '1073100882700406824'
    }
}

# set my API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# openai constants
COMPLETIONS_MODEL = os.getenv("COMPLETIONS_MODEL")
ENCODING = tiktoken.get_encoding("cl100k_base")

def prompt_get_topics_from_msgs(discord_msgs_str):
    prompt = "I have a series of messages formatted as follows:\n\n[message ID] [timestamp] [AUTHOR: username] Message content with line breaks represented by <br>.\n\nHere are the messages:\n\n<Insert Discord messages here>\n\nPlease carefully analyze the messages and generate a comprehensive list of topics discussed in these messages. Make sure to include as many relevant topics as possible, even if they are only mentioned briefly or in a single message. Your goal is to provide an exhaustive overview of the subjects discussed in the conversation."
    # replace <Insert Discord messages here> with actual messages
    prompt = prompt.replace("<Insert Discord messages here>", discord_msgs_str)
    return prompt

PROMPTS = {
    "get_topics_from_msgs": prompt_get_topics_from_msgs
}

# get date a week ago from today
def get_one_week_before_ref_date(reference_date=None):
    # if custom date str get timedelta from that
    if reference_date:
        custom_date = datetime.strptime(reference_date, '%Y-%m-%d')
    else:
        custom_date = date.today()

    last_week = custom_date - timedelta(days=7)
    last_week_str = last_week.strftime('%Y-%m-%d')
    return last_week_str

# get today's date as string
def get_today_str():
    return date.today().strftime('%Y-%m-%d')

def check_file_exists(file_path):
    return os.path.isfile(file_path)

# if file matches the following we don't want to recreate it, note that it's ok if the files were created on different dates (i.e. created_on doesn't have to match)
def check_matching_file_exists_ignore_creation_date(dir, file_name):
    # check if file exists with same created_on date first
    if check_file_exists(dir + '/' + file_name):
        return True, file_name

    pattern = r"_created_on_\d{4}-\d{2}-\d{2}"
    file_name_adjusted = re.sub(pattern, "", file_name)

    for check_file in os.listdir(dir):
        check_file_adjusted = re.sub(pattern, "", check_file)
        if check_file_adjusted == file_name_adjusted:
            return True, check_file

    return False, None

def gen_and_get_discord_export(export_path, discord_token, channel_key, output_type, after, before, force_file_regen=False):
    # print arguments
    print(f"\nGEN_AND_GET_DISCORD_EXPORT:\nexport_path: {export_path}\nchannel_key: {channel_key}\noutput_type: {output_type}\nafter: {after}\nbefore: {before}\nforce_file_regen: {force_file_regen}\n")

    # get channel id
    channel_id = CHANNEL_AND_THREAD_IDS[channel_key]['id']

    # get output_ext 
    output_ext = 'html' if output_type == 'htmldark' else 'json'

    # build output file
    output_file = f"export_{channel_key}_after_{after}_before_{before}_created_on_{get_today_str()}.{output_ext}"

    # if file exists and not force_file_regen, return
    file_path = DISCORD_EXPORT_DIR_PATH_RAW + '/' + output_file 
    is_match, matching_output_file = check_matching_file_exists_ignore_creation_date(DISCORD_EXPORT_DIR_PATH_RAW, output_file)
    if (is_match and not force_file_regen):
        print(f"\nFILE EXISTS: {DISCORD_EXPORT_DIR_PATH_RAW}/{matching_output_file}\n")
        return matching_output_file, output_type

    # generate discord export
    docker_command = f"docker run --rm -v {export_path}:/out tyrrrz/discordchatexporter:stable export -t {discord_token} -c {channel_id} -f {output_type} -o {output_file} --after {after} --before {before}"
    print(f"\nCREATING NEW FILE! FORCED: {force_file_regen}. DOCKER COMMAND:\n{docker_command}\n")
    subprocess.run(docker_command, shell=True)

    return output_file, output_type

# dict of channel key to message data
channel_key_to_message_data = {}

# gen and load discord exports for all channels
for channel_key in CHANNEL_AND_THREAD_IDS:
    #TODO this should be today's date when you want to generate a weekly summary; in fact you may need to do today's date + 1 - need to check this 
    reference_date = '2023-04-27'

    # create discord export (NOTE: json or htmldark for type)
    file_name, file_type = gen_and_get_discord_export(
        DISCORD_EXPORT_DIR_PATH, 
        DISCORD_TOKEN_ID, 
        channel_key, 
        'json',
        get_one_week_before_ref_date(reference_date=reference_date), 
        reference_date, 
        False
    )

    # read file as json if json
    if file_type == 'json':
        with open(DISCORD_EXPORT_DIR_PATH_RAW + '/' + file_name)  as f:
            data = json.load(f)
            channel_key_to_message_data[channel_key] = data
            # print(f"\nCHANNEL KEY: {channel_key}\nDATA:\n{data}\n")
    
    # TODO: calling break will do it for one channel for testing
    break

# exit program
# exit()

MAX_PROMPT_TOKENS = 2500
COMPLETIONS_API_PARAMS = {
    "model": COMPLETIONS_MODEL,
    "temperature": 0, # We use temperature of 0.0 because it gives the most predictable, factual answer.
    # "top_p": 1
}
get_topics_responses = {}
# iterate through channel key to message data
for channel_key in channel_key_to_message_data:
    get_topics_responses[channel_key] = [] 

    # get message data
    message_data = channel_key_to_message_data[channel_key]
    messages_structured = transform_message_data(message_data['messages'])


    # this is what we will insert into the prompt    
    insert_discord_msgs_str = ""
    insert_discord_msgs_str_token_count = 0
    # iterate through messages_structured
    for message_structured in messages_structured:
        message_str, tokens_count = build_message_str(message_structured)

        # if we are over the token limit, we don't want to include the current message, but we want to take the insert_discord_msgs_str and insert it into the prompt and then call the api; then we want to reset the insert str and token count and add the current message to it and continue iterating
        if insert_discord_msgs_str_token_count + tokens_count > MAX_PROMPT_TOKENS:
            prompt = PROMPTS['get_topics_from_msgs'](insert_discord_msgs_str)
            print(f"\nINSERT DISCORD MSGS STR:\n{insert_discord_msgs_str}\n")

            # call api
            response = openai.ChatCompletion.create(messages=[{"role": "user", "content": prompt}], **COMPLETIONS_API_PARAMS)

            get_topics_responses[channel_key].append(response)

            # reset insert_discord_msgs_str and insert_discord_msgs_str_token_count
            insert_discord_msgs_str = ""
            insert_discord_msgs_str_token_count = 0

            # add current message to insert_discord_msgs_str
            insert_discord_msgs_str += message_str
            insert_discord_msgs_str_token_count += tokens_count
        else:
            insert_discord_msgs_str += message_str
            insert_discord_msgs_str_token_count += tokens_count

            # if we are at the end of the messages_structured, we want to call the api
            if message_structured == messages_structured[-1]:
                prompt = PROMPTS['get_topics_from_msgs'](insert_discord_msgs_str)
                print(f"\nINSERT DISCORD MSGS STR:\n{insert_discord_msgs_str}\n")

                # call api
                response = openai.ChatCompletion.create(messages=[{"role": "user", "content": prompt}], **COMPLETIONS_API_PARAMS)
                get_topics_responses[channel_key].append(response)

                # reset insert_discord_msgs_str and insert_discord_msgs_str_token_count
                insert_discord_msgs_str = ""
                insert_discord_msgs_str_token_count = 0

print(f"\nGET TOPICS RESPONSES:\n{get_topics_responses}\n")



