import tiktoken
import subprocess
import json
import os
import re
from constants import DISCORD_EXPORT_DIR_PATH_RAW, CHANNEL_AND_THREAD_IDS 
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
load_dotenv()

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