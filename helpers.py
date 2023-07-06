import tiktoken
from collections import defaultdict
import subprocess
import json
import os
import re
from constants import DISCORD_EXPORT_DIR_PATH_RAW, CHANNEL_AND_THREAD_IDS 
from datetime import datetime, date, timedelta
from dateutil import parser
from dotenv import load_dotenv
load_dotenv()

# constantsprompt_summarize_conversation_threao
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
            "reactions": [{"emoji_name": reaction["emoji"]["code"], "count": reaction["count"], "image_url": reaction["emoji"]["imageUrl"]} for reaction in message["reactions"]],
            "mentions": [mention["name"] for mention in message["mentions"]],
            "reference_messageId": message.get("reference", {}).get("messageId", None)
        }
        formatted_messages.append(json.dumps(formatted_message))
    
    return formatted_messages

def format_single_message(message):
    formatted_message = {
        "id": message["id"],
        "type": message["type"],
        "author_name": message["author"]["name"],
        "timestamp": message["timestamp"],
        "content": message["content"].replace("\n", "<br>"),
        "reactions": [{"emoji_name": reaction["emoji"]["code"], "count": reaction["count"], "image_url": reaction["emoji"]["imageUrl"]} for reaction in message["reactions"]],
        "mentions": [mention["name"] for mention in message["mentions"]],
        "reference_messageId": message.get("reference", {}).get("messageId", None),
        "embeds": message.get("embeds", [])
    }
    return formatted_message

def prompt_get_consolidate_mappings(bullet_summaries_str):
    prompt = "Given a series of bullet summaries of conversation threads, each summary is structured as follows:\n\n1. An identification number (ID)\n2. Reactions (Data of reactions include the type of reaction, count, and image URL)\n3. Conversation participants\n4. Topic of the conversation\n5. A brief summary of the discussion\n\nFormat: \"ID: [ID number]\\n\\[Reactions data]\\n\\\"[Conversation participants] talk about [Topic]: [Summary].\\\"\n\nFor instance,\n\n\"ID: 0\\nReactions: {\\n\\\"fire\\\": {\\n\\\"count\\\": 9,\\n\\\"image_url\\\": \\\"https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f525.svg\\\"\\n},\\n\\\"thumbsup_tone4\\\": {\\n\\\"count\\\": 1,\\n\\\"image_url\\\": \\\"https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f44d-1f3fe.svg\\\"\\n}\\n}\\n\\\"John and Jane talk about AI: John shares an article about the advancement of AI, and Jane provides her insights on the potential of AI in the future.\\\"\"\n\nHere are the summaries:\n\n<Insert bullet summaries here>\n\nYour tasks are:\n\n1. Analyze each summary. \n2. Identify which summaries highly overlap in topic content that they should be consolidated. Summaries that should be consolidated should be very similar or related in topic or content.\n3. Generate a JSON string to represent the consolidation results. Each consolidation group should have its own unique key, starting with 0 and incrementing by 1 for each group. The value for each key should be an object with two keys:\n   - \"consolidate_ids\": an array of the IDs to be consolidated\n   - \"reasoning\": a string providing an explanation for the consolidation\n\nThe output JSON string should follow this format:\n\n{\n   \"0\": {\"consolidate_ids\": [2, 4, 6], \"reasoning\": \"All discuss AI development\"},\n   \"1\": {\"consolidated_id\": [3, 5, 7], \"reasoning\": \"All explore the implications of climate change\"},\n   ...\n}\n\nThe aim is to identify which IDs need to be consolidated to create a more streamlined and concise set of summaries by reducing redundancy and grouping similar topics together. You only need to return the JSON string representing the consolidation groups."

    prompt = prompt.replace("<Insert bullet summaries here>", bullet_summaries_str)

    return prompt

def prompt_consolidate_bullet_summaries(bullet_summaries_str):
    # prompt = 'Given a series of bullet summaries of conversation threads, each summary is structured as follows:\n\n1. An identification number (ID)\n2. Reactions (Data of reactions include the type of reaction, count, and image URL)\n3. Conversation participants\n4. Topic of the conversation\n5. A brief summary of the discussion\n\nFormat: "ID: [ID number]\n[Reactions data]\n"[Conversation participants] talk about [Topic]: [Summary]."\n\nFor instance,\n\n"ID: 0\nReactions: {\n"fire": {\n"count": 9,\n"image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f525.svg\"\\n},\\n\"thumbsup_tone4\": {\n"count": 1,\n"image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f44d-1f3fe.svg\"\\n}\\n}\\n\"John and Jane talk about AI: John shares an article about the advancement of AI, and Jane provides her insights on the potential of AI in the future.""\n\nHere are the summaries:\n\n<Insert bullet summaries here>\n\nYour task is:\n\nTake the bullet summaries and create new consolidated summaries. Each consolidated summary should follow the original format but will contain multiple IDs, multiple reaction data structures, and a merged summary that accounts for all the conversations in the consolidated group. Ensure all parts of the summary are updated accordingly, especially the authors and topic section.\n\nThe aim is to create a more streamlined and concise set of summaries by reducing redundancy and grouping similar topics together.' 


    # THIS PROMPT IS THE ONE I USED TO RUN THE 3rd summary I RAN, it does not have sub-bullets
    prompt = "Given a series of bullet summaries of conversation threads, each summary is structured as follows:\n\n1. An identification number (ID)\n2. Reactions (Data of reactions include the type of reaction, count, and image URL)\n3. Conversation participants\n4. Topic of the conversation\n5. A brief summary of the discussion\n\nFormat: \"ID: [ID number]\n[Reactions data]\n\"[Conversation participants] talk about [Topic]: [Summary].\"\n\nFor instance,\n\n\"ID: 0\nReactions: {\\n\"fire\": {\\n\"count\": 9,\\n\"image_url\": \"https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f525.svg\"\\n},\\n\"thumbsup_tone4\": {\\n\"count\": 1,\\n\"image_url\": \"https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f44d-1f3fe.svg\"\\n}\\n}\\n\"John and Jane talk about AI: John shares an article about the advancement of AI, and Jane provides her insights on the potential of AI in the future.\"\"\n\nHere are the summaries:\n\n<Insert bullet summaries here>\n\nYour task is:\n\nTake the bullet summaries and create new consolidated summaries. For each consolidated summary, DO NOT include the ID or reactions sections from the original format. Instead, your output should ONLY follow the format of \"[Conversation participants] talk about [Topic]: [Summary].\", containing multiple conversation participants, a merged topic, and a merged summary that accounts for all the conversations in the consolidated group. Ensure all parts of the summary are updated accordingly.\n\nThe aim is to create a more streamlined and concise set of summaries by reducing redundancy and grouping similar topics together."

    # this one did not yield a single topic everytime, sometimes there were multiple topics in there 
#     prompt = ("Given a series of bullet summaries of conversation threads, each summary is structured as follows:\n\n"
# "1. An identification number (ID)\n"
# "2. Reactions (Data of reactions include the type of reaction, count, and image URL)\n"
# "3. Conversation participants\n"
# "4. Topic of the conversation\n"
# "5. A brief summary of the discussion\n\n"
# "Format: \"ID: [ID number]\n[Reactions data]\n"
# "\"[Conversation participants] talk about [Topic]: [Summary].\"\n\n"
# "For instance,\n\n"
# "\"ID: 0\nReactions: {\\n\"fire\": {\\n\"count\": 9,\\n\"image_url\": \"https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f525.svg\"\\n},\\n"
# "\"thumbsup_tone4\": {\\n\"count\": 1,\\n\"image_url\": \"https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f44d-1f3fe.svg\"\\n}\\n}\\n"
# "\"John and Jane talk about AI: John shares an article about the advancement of AI, and Jane provides her insights on the potential of AI in the future.\"\"\n\n"
# "Here are the summaries:\n\n"
# "<Insert bullet summaries here>\n\n"
# "Your task is:\n\n"
# "Take the bullet summaries and create new consolidated summaries. For each consolidated summary, DO NOT include the ID or reactions sections from the original format. "
# "Instead, your output should follow this format:\n\n"
# "- [Topic]\n"
# "    - [Conversation participants]: [Concise point made in the conversation]\n"
# "    - [Conversation participants]: [Concise point made in the conversation]\n"
# "    - ...\n\n"
# "There should be one or more sub-bullets for each topic, and each sub-bullet should represent a different significant point made in the conversation. "
# "Ensure all parts of the summary are updated accordingly.\n\n"
# "The aim is to create a more streamlined, organized, and concise set of summaries by reducing redundancy and grouping similar topics together.")

#     prompt = prompt = ("Given a series of bullet summaries of conversation threads, each summary is structured as follows:\n\n"
# "1. An identification number (ID)\n"
# "2. Reactions (Data of reactions include the type of reaction, count, and image URL)\n"
# "3. Conversation participants\n"
# "4. Topic of the conversation\n"
# "5. A brief summary of the discussion\n\n"
# "Format: \"ID: [ID number]\n[Reactions data]\n"
# "\"[Conversation participants] talk about [Topic]: [Summary].\"\n\n"
# "For instance,\n\n"
# "\"ID: 0\nReactions: {\\n\"fire\": {\\n\"count\": 9,\\n\"image_url\": \"https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f525.svg\"\\n},\\n"
# "\"thumbsup_tone4\": {\\n\"count\": 1,\\n\"image_url\": \"https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f44d-1f3fe.svg\"\\n}\\n}\\n"
# "\"John and Jane talk about AI: John shares an article about the advancement of AI, and Jane provides her insights on the potential of AI in the future.\"\"\n\n"
# "Here are the summaries:\n\n"
# "<Insert bullet summaries here>\n\n"
# "Your task is:\n\n"
# "Take the bullet summaries and create a new consolidated summary for a single topic. DO NOT include the ID or reactions sections from the original format. "
# "Instead, your output should follow this format:\n\n"
# "- [Topic]\n"
# "    - [Conversation participants]: [Concise point made in the conversation]\n"
# "    - [Conversation participants]: [Concise point made in the conversation]\n"
# "    - ...\n\n"
# "There should be one or more sub-bullets under the single topic, and each sub-bullet should represent a different significant point made in the conversation. "
# "Ensure all parts of the summary are updated accordingly.\n\n"
# "The aim is to create a more streamlined, organized, and concise set of summaries by reducing redundancy and grouping similar topics together.")




    prompt = prompt.replace("<Insert bullet summaries here>", bullet_summaries_str)
    return prompt

def prompt_reformat_summary(summary):
#     prompt = ("Given a summary of a conversation thread in the following format:\n\n"
# "\"[Conversation participants] talk about [Topic]: [Summary]\"\n\n"
# "For instance,\n\n"
# "\"John and Jane talk about AI: John shares an article about the advancement of AI, and Jane provides her insights on the potential of AI in the future.\"\n\n"
# "Here is the summary:\n\n"
# "<Insert summary here>\n\n"
# "Your task is:\n\n"
# "1. Identify the topic of the summary.\n"
# "2. Identify any significant points that were made by the participants.\n"
# "3. Output a new version of the summary that first states the topic and then details the significant points made by each participant. Your output should follow this format:\n\n"
# "[Topic]\n"
# "    [Conversation participants]: [Concise point made in the conversation]\n"
# "    [Conversation participants]: [Concise point made in the conversation]\n"
# "    ...\n\n"
# "Ensure all parts of the summary are updated accordingly, and the output is concise and specific. The sub-bullets should reference the participants who made the significant points."
# "The aim is to create a more organized and concise summary by focusing on the topic and the key details.")

    prompt = ("Given a summary of a conversation thread in the following format:\n\n"
    "\"[Conversation participants] talk about [Topic]: [Summary]\"\n\n"
    "For instance,\n\n"
    "\"John and Jane talk about AI: John shares an article about the advancement of AI, and Jane provides her insights on the potential of AI in the future.\"\n\n"
    "Here is the summary:\n\n"
    "<Insert summary here>\n\n"
    "Your task is:\n\n"
    "1. Identify the topic of the summary.\n"
    "2. Identify any significant points that were made by the participants.\n"
    "3. Output a new version of the summary that first states the topic by creating a topic title and then details the significant points made by each participant. Your output should follow this format:\n\n"
    "[Topic Title]\n"
    "    [Concise summary of a significant part of the conversation, mentioning the participants]\n"
    "    [Concise summary of a significant part of the conversation, mentioning the participants]\n"
    "    ...\n\n"
    "Ensure all parts of the summary are updated accordingly, and the output is concise and specific. The sub-bullets should reference the participants who made the significant points."
    "Please make sure that the Topic Title is just the topic title itself. There is no need to do something like: \"Topic Title: [Topic Title]\". Just output the topic title itself."
    "Please make sure there is only one topic per output. Please do not output more than one topic. There should be a single Topic Title along with the sub-bullets for the entire summary."
    "The aim is to create a more organized and concise summary by focusing on the topic and the key details." 
    "Please make sure there is only one topic for the entire summary. We do not want multiple topics or nested topics. We want a single topic and the sub-bullets for the entire summary.") # i added this last line

    prompt = prompt.replace("<Insert summary here>", summary)

    return prompt


def prompt_summarize_conversation_thread(discord_msgs_str):
    prompt = 'I have a series of messages formatted in JSON as follows:\n\n{\n "id": "message ID",\n "type": "message type",\n "author_name": "username",\n "timestamp": "timestamp",\n "content": "Message content with line breaks represented by <br>.",\n "reactions": [{"emoji_name": "emoji name", "count": "number of reactions"}],\n "mentions": ["mentioned user names"],\n "reference_messageId": "referenced message ID",\n "embeds": [\n {\n "url": "URL of the embedded content",\n "description": "Description of the embedded content"\n }\n ]\n}\n\nHere are the messages:\n\n<Insert Discord messages here>\n\nAll these Discord messages belong to a single conversation thread. I need you to generate a summary of this entire thread. Ensure to cite the authors in the summary using the author_name field in the provided discord messages. Please consider the "url" and "description" keys in the "embeds" list for context about any URLs posted within the content of the messages. There is no need to add any other metadata like message ID as part of the summary.\n\nThe format of the summary should be as follows: "[Author1, Author2 and others] talk about [INSERT TOPIC HERE]: [INSERT SUMMARY HERE]."\n'

    # replace <Insert Discord messages here> with actual messages
    prompt = prompt.replace("<Insert Discord messages here>", discord_msgs_str)
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

# Function to group messages into threads; will return a list of lists where each list is a "thread" which is a top level message and all of its replies contained as values to a "replies" key in that top level message
def group_messages(messages):
    # this will be a dictionary of message id to message
    message_dict = {}

    # populate the dictionary
    for message in messages:
        message_dict[message['id']] = message

    # To keep track of reply messages; this is how we will know if a message is a reply or a top level message (i.e. the start of a thread)
    reply_ids = set()  

    for message in messages:

        # if there is a reference key and it is not None, then this message is a reply
        if 'reference' in message and message['reference'] is not None:
            parent_message_id = message['reference']['messageId']

            if parent_message_id in message_dict:
                parent_message = message_dict[parent_message_id]

                if 'replies' not in parent_message:
                    parent_message['replies'] = []

                # this will modify the original message_dict as well and will allow us to keep track of the replies to a message
                parent_message['replies'].append(message)

                # Add reply message ID to the set
                reply_ids.add(message['id'])  

    # Create a new list of threads excluding the reply messages; this means that the threads list will only contain top level messages (i.e. the start of a thread); each thread which will be a list containing the top level message, will also contain a list of replies to that message (if any) as a value of the 'replies' key; this nested structure can continue for as many levels as there are replies to a message
    threads = [[message] for message in messages if message['id'] not in reply_ids]

    return threads

# Function to flatten a nested messages list into a single list of messages; it starts with the top level message and then recurses through the replies to that message so that we end up with a single list of messages that were part of that thread
def flatten_thread(thread):
    flattened = []
    for message in thread:
        flattened.append(message)
        if 'replies' in message:
            flattened.extend(flatten_thread(message['replies']))
    return flattened

def merge_consecutive_threads_by_same_author(flattened_threads):
    """
    This function takes a list of flattened threads and merges consecutive threads 
    that start with a message by the same author.
    I believe that the flattened_threads list is already sorted by timestamp, so
    this function should work as expected. 
    """
    merged_threads = []
    current_thread = flattened_threads[0]

    for next_thread in flattened_threads[1:]:
        # Also check if the timestamp differential is less than 5 minutes
        is_diff_less_than_5_minutes = False
        current_thread_timestamp = parser.parse(current_thread[0]['timestamp'])
        next_thread_timestamp = parser.parse(next_thread[0]['timestamp'])

        diff = abs(next_thread_timestamp - current_thread_timestamp)
        if (diff > timedelta(minutes=5)):
            is_diff_less_than_5_minutes = True


        # Check if the first messages in current and next threads are by the same author
        if (current_thread[0]['author']['id'] == next_thread[0]['author']['id']) and is_diff_less_than_5_minutes:
            # If they are, merge the threads
            current_thread += next_thread

        else:
            # If they are not, add the current thread to the list of merged threads
            # and start a new current thread
            merged_threads.append(current_thread)
            current_thread = next_thread

    # Don't forget to add the last thread to the list
    merged_threads.append(current_thread)

    return merged_threads

def sort_messages_by_timestamp(flattened_threads):
    for thread in flattened_threads:
        thread.sort(key=lambda msg: msg['timestamp'])

    return flattened_threads

def extract_emoji_info(thread):
    emoji_info = defaultdict(lambda: {'count': 0, 'image_url': ''})

    for message in thread:
        if 'reactions' in message:
            for reaction in message['reactions']:
                emoji_name = reaction['emoji_name']  # The name of the emoji
                emoji_info[emoji_name]['count'] += reaction['count']  # Increment the count
                emoji_info[emoji_name]['image_url'] = reaction['image_url']  # Get the image link

    return emoji_info

def aggregate_reactions(data):
    reaction_counts = {}

    for key in data:
        obj = data[key]
        reactions = obj.get('reactions', {})

        for emoji_name in reactions:
            reaction = reactions[emoji_name]
            count = reaction['count']
            image_url = reaction['image_url']

            if emoji_name in reaction_counts:
                reaction_counts[emoji_name]['count'] += count
            else:
                reaction_counts[emoji_name] = {'count': count, 'image_url': image_url}

    return reaction_counts

def extract_objects_by_ids(json_object, ids):
    result = {}

    for key, value in json_object.items():
        if key in ids:
            result[key] = value

    return result

def convert_messages_to_threads(discord_message_data):
    # group messages into threads (a thread will be a list of a top level message and its replies, and its replies' replies, etc.)
    threads = group_messages(discord_message_data['messages'])

    # flatten the threads to return a list of lists of messages (each list of messages is a thread)
    flattened_threads = [flatten_thread(thread) for thread in threads]

    merged_flattened_threads = merge_consecutive_threads_by_same_author(flattened_threads)
    # NOTE: i used the below for the 6/9 run which just removes the merging function, but then i switched back to the above 6/16 because I seemed to get too many threads when I didn't merge consecutive threads by same author.
    # merged_flattened_threads = flattened_threads

    sorted_merged_flattened_threads = sort_messages_by_timestamp(merged_flattened_threads)

    formatted_final = []
    for thread in sorted_merged_flattened_threads:
        formatted_thread = []
        for message in thread:
            formatted_thread.append(format_single_message(message))
        formatted_final.append(formatted_thread)

    return formatted_final 