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

# get date a week ago from today
def get_export_after_str():
    today = date.today()
    last_week = today - timedelta(days=7)
    last_week_str = last_week.strftime('%Y-%m-%d')
    return last_week_str

def gen_and_get_discord_export(export_path, discord_token, channel_key, output_type, after):
    # get channel id
    channel_id = CHANNEL_AND_THREAD_IDS[channel_key]['id']

    # get output_ext 
    output_ext = 'html' if output_type == 'htmldark' else 'json'

    # build output file
    output_file = f"export_{channel_key}_after_{after}.{output_ext}"

    # generate discord export
    docker_command = f"docker run --rm -v {export_path}:/out tyrrrz/discordchatexporter:stable export -t {discord_token} -c {channel_id} -f {output_type} -o {output_file} --after {after}"
    print(f"\nDOCKER COMMAND: {docker_command}\n")
    subprocess.run(docker_command, shell=True)

    return output_file, output_type

# create discord export
file_name, file_type = gen_and_get_discord_export(DISCORD_EXPORT_DIR_PATH, DISCORD_TOKEN_ID, 'proof_of_building', 'htmldark', get_export_after_str())

# get file path
file_path = file_path = DISCORD_EXPORT_DIR_PATH_RAW + '/' + file_name
print(f"\nDISCORD EXPORT FILE PATH: {file_path}\n")

# read file as json if json
if file_type == 'json':
    with open(file_path)  as f:
        data = json.load(f)
    print(data)



