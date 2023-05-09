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
from helpers import get_token_count, transform_message_data, build_message_str, format_messages
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

def prompt_summarize_discord_msgs(discord_msgs_str):
    # ID:20 
    prompt = 'I have a series of messages formatted in JSON as follows:\n\n{\n "id": "message ID",\n "type": "message type",\n "author_name": "username",\n "timestamp": "timestamp",\n "content": "Message content with line breaks represented by <br>.",\n "reactions": [{"emoji_name": "emoji name", "count": "number of reactions"}],\n "mentions": ["mentioned user names"],\n "reference_messageId": "referenced message ID"\n}\n\nHere are the messages:\n\n<Insert Discord messages here>\n\nPlease generate a comprehensive list of bullet points summarizing the messages. Each bullet point should start with a brief statement of the topic followed by a colon. Then, summarize the messages germane to that topic and make sure to cite the authors in the summaries in parentheses. You can cite the authors using the author_name field in the provided discord messages. There is no need to add any other metadata like message ID as part of the summaries.\n\nExample output format:\n- Title of Topic 1: Summary of relevant messages (Author1), additional information (Author2).\n- Title of Topic 2: Summary of the conversation (Author3), supporting points (Author4), opposing views (Author5).' 

    # replace <Insert Discord messages here> with actual messages
    prompt = prompt.replace("<Insert Discord messages here>", discord_msgs_str)
    return prompt

def prompt_remove_no_context_summaries(concat_summaries_str):
    prompt = "Please refine the following list of bullet points by removing any items that are too vague or lacking sufficient context. Maintain the original formatting and order for the remaining bullet points.\n\n<Insert Summaries here>\n\nExample of bullet points to be removed:\n- Twitter posts: Links to various Twitter posts are shared (jakejinglez, icreatelife, bengillin).\n- YouTube video links: Users share links to various YouTube videos (jakejinglez, kevinadidas).\n- Twitter links: Users share links to various tweets (jakejinglez, DataChaz).\n"

    prompt = prompt.replace("<Insert Summaries here>", concat_summaries_str)
    return prompt

def prompt_consolidate_summaries_where_appropriate(concat_summaries_str):
    prompt = "I have a list of bullet points, each summarizing a topic of discussion. Every bullet point starts with a topic name, followed by a brief summary of the topic, and the author(s) of the discussion enclosed in parentheses. Here is the list of bullet points:\n\n<Insert Summaries here>\n\nYour task is to analyze these bullet points, identify overlapping topics, and consolidate the bullet points with overlapping topics into a single bullet point. For each consolidated bullet point, create a new topic name and summary, and include all relevant authors. If a bullet point does not overlap with others, leave it as is.\n\nPlease ensure that the consolidated bullet points adhere to the original format, i.e., they start with the topic name, followed by the summary, and the author(s) in parentheses. All bullet points, whether consolidated or unaltered, should be included in a single list.\n\nThe final output should be a bulleted list consisting of both consolidated and unaltered bullet points. Here is an example of the format of the output:\n\n- Consolidated Topic: Combined Summary (Author 1, Author 2).\n- Unaltered Topic: Summary of Unaltered Topic (Author 3).\n...\n\nIn your analysis and consolidation, please strive to maintain the accuracy and clarity of the original information."

    prompt = prompt.replace("<Insert Summaries here>", concat_summaries_str)
    return prompt

PROMPTS = {
    "summarize_discord_msgs": prompt_summarize_discord_msgs,
    "remove_no_context_summaries": prompt_remove_no_context_summaries,
    "consolidate_summaries_where_appropriate": prompt_consolidate_summaries_where_appropriate
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
    # reference_date = '2023-04-27'
    reference_date = '2023-05-08'

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
    # "top_p": 1,
    "max_tokens": 1200 
}
summarize_discord_msgs_responses = {}
# iterate through channel key to message data
for channel_key in channel_key_to_message_data:
    summarize_discord_msgs_responses[channel_key] = [] 

    # get message data
    message_data = channel_key_to_message_data[channel_key]
    # messages_structured = transform_message_data(message_data['messages'])
    messages_structured = format_messages(message_data['messages'])


    # this is what we will insert into the prompt    
    insert_discord_msgs_str = ""
    insert_discord_msgs_str_token_count = 0
    # iterate through messages_structured
    for message_structured in messages_structured:
        # message_str, tokens_count = build_message_str(message_structured)
        message_str = message_structured + "\n"
        tokens_count = get_token_count(message_str)

        # if we are over the token limit, we don't want to include the current message, but we want to take the insert_discord_msgs_str and insert it into the prompt and then call the api; then we want to reset the insert str and token count and add the current message to it and continue iterating
        if insert_discord_msgs_str_token_count + tokens_count > MAX_PROMPT_TOKENS:
            prompt = PROMPTS['summarize_discord_msgs'](insert_discord_msgs_str)
            print(f"\nCHANNEL KEY: {channel_key}\nPROMPT:\n{prompt}\n")

            # call api
            response = openai.ChatCompletion.create(messages=[{"role": "user", "content": prompt}], **COMPLETIONS_API_PARAMS)

            summarize_discord_msgs_responses[channel_key].append(response)

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
                prompt = PROMPTS['summarize_discord_msgs'](insert_discord_msgs_str)
                print(f"\nCHANNEL KEY: {channel_key}\nPROMPT:\n{prompt}\n")

                # call api
                response = openai.ChatCompletion.create(messages=[{"role": "user", "content": prompt}], **COMPLETIONS_API_PARAMS)
                summarize_discord_msgs_responses[channel_key].append(response)

                # reset insert_discord_msgs_str and insert_discord_msgs_str_token_count
                insert_discord_msgs_str = ""
                insert_discord_msgs_str_token_count = 0

print(f"\nSUMMARIZE DISCORD MSGS RESPONSES:\n{summarize_discord_msgs_responses}\n")

# summarize summaries in summarize_discord_msgs_responses
for channel_key in summarize_discord_msgs_responses:

   # get responses for channel
    responses = summarize_discord_msgs_responses[channel_key]

    # get summaries from responses and create insert_summaries_str
    concat_summaries_str = ""
    for response in responses:
        summary_str = response.choices[0].message.content
        concat_summaries_str += summary_str + "\n"

    # remove summaries that don't have context
    prompt = PROMPTS['remove_no_context_summaries'](concat_summaries_str)
    print(f"\nCHANNEL KEY: {channel_key}\nPROMPT: remove_no_context_summaries\n{prompt}\n")
    response = openai.ChatCompletion.create(messages=[{"role": "user", "content": prompt}], **COMPLETIONS_API_PARAMS)
    print(f"\nRESPONSE: remove_no_context_summaries\n{response.choices[0].message.content}\n")

    no_context_summaries_str = response.choices[0].message.content

    # consolidate summaries where appropriate
    prompt = PROMPTS['consolidate_summaries_where_appropriate'](no_context_summaries_str)
    print(f"\nCHANNEL KEY: {channel_key}\nPROMPT: consolidate_summaries_where_appropriate\n{prompt}\n")
    response = openai.ChatCompletion.create(messages=[{"role": "user", "content": prompt}], **COMPLETIONS_API_PARAMS)
    print(f"\nRESPONSE: consolidate_summaries_where_appropriate\n{response.choices[0].message.content}\n")


